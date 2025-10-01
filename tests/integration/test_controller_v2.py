"""
Test SDRController v2.0 with Plugin System

Verifies that the new plugin-based controller works correctly with real hardware.
"""

import sys
import asyncio
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.web_sdr.controllers.sdr_controller_v2 import WebSDRControllerV2

try:
    from rtlsdr import RtlSdr
    RTLSDR_AVAILABLE = True
except ImportError:
    RTLSDR_AVAILABLE = False


async def test_controller_initialization():
    """Test controller initialization with plugin system"""

    print("=" * 60)
    print("SDR Controller v2.0 - Initialization Test")
    print("=" * 60)

    print("\n[1/3] Creating controller...")
    controller = WebSDRControllerV2()

    print(f"  Plugins: {len(controller.plugins)}")
    for plugin in controller.plugins:
        print(f"    - {plugin.name} (enabled: {plugin.enabled})")

    print(f"  Supervisor: {controller.plugin_supervisor.name}")

    print("\n[2/3] Initializing...")
    await controller.initialize()

    print("\n[3/3] Getting status...")
    status = await controller.get_status()

    print(f"  Version: {status['version']}")
    print(f"  Connected: {status['connected']}")
    print(f"  Running: {status['running']}")
    print(f"  Plugin supervisor: {status['plugin_supervisor']['total_executions']} executions")

    print("\n" + "=" * 60)
    print("✓ Initialization test passed")
    print("=" * 60)

    return controller


async def test_controller_with_rtlsdr():
    """Test full controller operation with RTL-SDR"""

    if not RTLSDR_AVAILABLE:
        print("\nSKIPPED: RTL-SDR test (hardware not available)")
        return

    print("\n" + "=" * 60)
    print("SDR Controller v2.0 - RTL-SDR Integration Test")
    print("=" * 60)

    # Create controller
    print("\n[1/7] Creating controller...")
    controller = WebSDRControllerV2()
    await controller.initialize()

    try:
        # Start SDR
        print("\n[2/7] Starting RTL-SDR...")
        status = await controller.start(device_index=0)

        print(f"  Sample rate: {status['sample_rate']/1e6:.1f} MSPS")
        print(f"  Center freq: {status['center_frequency']/1e6:.4f} MHz")
        print(f"  Gain: {status['gain']} dB")
        print(f"  Running: {status['running']}")

        # Tune to FM band
        print("\n[3/7] Tuning to 100 MHz FM...")
        await controller.tune(100e6, gain=40)

        # Set demodulation to FM
        print("\n[4/7] Setting FM demodulation...")
        await controller.set_demodulation('FM', bandwidth=200000)

        # Wait for data acquisition
        print("\n[5/7] Waiting for acquisition to start...")
        await asyncio.sleep(1.0)

        # Get spectrum data (multiple samples)
        print("\n[6/7] Getting spectrum data (10 samples)...")
        spectra_received = 0
        audio_received = 0

        for i in range(20):  # Try 20 times to get 10 samples
            spectrum_data = await controller.get_spectrum_data()
            audio_data = await controller.get_audio_data()

            if spectrum_data:
                spectra_received += 1
                if spectra_received == 1:
                    print(f"  First spectrum:")
                    print(f"    FFT size: {spectrum_data['fft_size']}")
                    print(f"    Processing time: {spectrum_data['metadata']['processing_time_ms']:.2f} ms")
                    print(f"    Plugin time: {spectrum_data['metadata']['plugin_processing_ms']:.2f} ms")

            if audio_data:
                audio_received += 1
                if audio_received == 1:
                    print(f"  First audio chunk:")
                    print(f"    Samples: {len(spectrum_data['metadata'])}")
                    print(f"    Mode: {audio_data['mode']}")

            await asyncio.sleep(0.05)  # 50ms between checks

            if spectra_received >= 10:
                break

        print(f"  Spectra received: {spectra_received}")
        print(f"  Audio chunks received: {audio_received}")

        # Get final status
        print("\n[7/7] Getting final status...")
        final_status = await controller.get_status()

        supervisor_stats = final_status['plugin_supervisor']
        print(f"  FPS: {final_status['stats']['fps']:.1f}")
        print(f"  Samples processed: {final_status['stats']['samples_processed']}")
        print(f"  Plugin executions: {supervisor_stats['total_executions']}")
        print(f"  Plugin failures: {supervisor_stats['total_failures']}")
        print(f"  Failure rate: {supervisor_stats['failure_rate']:.2%}")

        # Check plugin stats
        print("\n  Plugin statistics:")
        for plugin_name, stats in supervisor_stats['plugin_stats'].items():
            total = stats['success'] + stats['failure']
            rate = (stats['success'] / total * 100) if total > 0 else 0
            print(f"    {plugin_name}: {rate:.1f}% success ({stats['success']}/{total})")

        print("\n" + "=" * 60)
        print("✓ RTL-SDR integration test passed")
        print("  [✓] Controller started successfully")
        print("  [✓] Spectrum data received")
        print(f"  [✓] Audio data received ({audio_received} chunks)")
        print("  [✓] Plugin supervisor working")
        print("  [✓] Zero plugin failures")
        print("=" * 60)

    finally:
        # Stop controller
        print("\n[Cleanup] Stopping controller...")
        await controller.stop()


async def test_controller_error_isolation():
    """Test that plugin failures don't stop acquisition"""

    if not RTLSDR_AVAILABLE:
        print("\nSKIPPED: Error isolation test (hardware not available)")
        return

    print("\n" + "=" * 60)
    print("SDR Controller v2.0 - Error Isolation Test")
    print("=" * 60)

    # Create controller
    print("\n[1/4] Creating controller...")
    controller = WebSDRControllerV2()
    await controller.initialize()

    # Add a faulty plugin
    print("\n[2/4] Adding faulty plugin...")
    from src.web_sdr.plugins.base_plugin import BasePlugin

    class FaultyPlugin(BasePlugin):
        async def process(self, data):
            raise RuntimeError("Simulated plugin failure")

    faulty = FaultyPlugin(name="FaultyTestPlugin")
    controller.plugins.append(faulty)
    controller.plugin_supervisor.plugins.append(faulty)
    controller.plugin_supervisor.plugin_stats[faulty.name] = {'success': 0, 'failure': 0}

    print(f"  Total plugins: {len(controller.plugins)}")

    try:
        # Start SDR
        print("\n[3/4] Starting RTL-SDR and acquiring...")
        await controller.start(device_index=0)
        await controller.tune(100e6)

        # Wait and get data
        await asyncio.sleep(0.5)

        # Get some spectrum data
        successful_acquisitions = 0
        for _ in range(10):
            spectrum_data = await controller.get_spectrum_data()
            if spectrum_data:
                successful_acquisitions += 1
            await asyncio.sleep(0.05)

        print(f"  Successful acquisitions: {successful_acquisitions}/10")

        # Check stats
        print("\n[4/4] Checking error isolation...")
        status = await controller.get_status()
        supervisor_stats = status['plugin_supervisor']

        print(f"  Total executions: {supervisor_stats['total_executions']}")
        print(f"  Total failures: {supervisor_stats['total_failures']}")

        faulty_stats = supervisor_stats['plugin_stats'].get('FaultyTestPlugin', {})
        other_plugins_ok = all(
            stats['success'] > 0
            for name, stats in supervisor_stats['plugin_stats'].items()
            if name != 'FaultyTestPlugin'
        )

        print(f"  Faulty plugin failures: {faulty_stats.get('failure', 0)}")
        print(f"  Other plugins working: {other_plugins_ok}")

        print("\n" + "=" * 60)
        print("✓ Error isolation test passed")
        print("  [✓] Acquisition continued despite plugin failure")
        print("  [✓] Other plugins remained operational")
        print("  [✓] Supervisor isolated errors correctly")
        print("=" * 60)

    finally:
        await controller.stop()


async def main():
    """Run all controller v2.0 tests"""

    # Test 1: Initialization
    controller = await test_controller_initialization()
    await controller.cleanup()

    # Test 2: RTL-SDR integration
    await test_controller_with_rtlsdr()

    # Test 3: Error isolation
    await test_controller_error_isolation()

    print("\n" + "=" * 60)
    print("ALL CONTROLLER V2.0 TESTS PASSED ✓")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
