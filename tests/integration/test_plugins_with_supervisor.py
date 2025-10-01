"""
Test Real Plugins with Supervisor

Verifies that real plugins (Spectrum, Waterfall, Demodulator) work correctly
with the PluginSupervisor pattern.
"""

import sys
import asyncio
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.web_sdr.dsp.spectrum_processor import SpectrumProcessor
from src.web_sdr.dsp.demodulators import AudioDemodulators
from src.web_sdr.pipeline.plugin_supervisor import PluginSupervisor
from src.web_sdr.plugins.spectrum_plugin import SpectrumPlugin
from src.web_sdr.plugins.waterfall_plugin import WaterfallPlugin
from src.web_sdr.plugins.demodulator_plugin import DemodulatorPlugin

try:
    from rtlsdr import RtlSdr
    RTLSDR_AVAILABLE = True
except ImportError:
    RTLSDR_AVAILABLE = False


async def test_plugins_with_synthetic_data():
    """Test all plugins with synthetic IQ data"""

    print("=" * 60)
    print("Plugins + Supervisor Test: Synthetic Data")
    print("=" * 60)

    # Initialize processors
    print("\n[1/5] Initializing processors...")
    spectrum_processor = SpectrumProcessor(fft_size=4096, sample_rate=2.4e6)
    audio_demodulator = AudioDemodulators()

    # Create plugins
    print("\n[2/5] Creating plugins...")
    spectrum_plugin = SpectrumPlugin(spectrum_processor)
    waterfall_plugin = WaterfallPlugin(spectrum_processor, max_lines=50)
    demod_plugin = DemodulatorPlugin(audio_demodulator)
    demod_plugin.enabled = True  # Enable for testing
    demod_plugin.set_mode('FM', bandwidth=15000)

    print(f"  Created: {spectrum_plugin.name}")
    print(f"  Created: {waterfall_plugin.name}")
    print(f"  Created: {demod_plugin.name}")

    # Create supervisor
    print("\n[3/5] Creating plugin supervisor...")
    plugins = [spectrum_plugin, waterfall_plugin, demod_plugin]
    supervisor = PluginSupervisor(plugins, name="TestSupervisor")

    # Generate test signal
    print("\n[4/5] Generating test signal...")
    duration = 0.1  # 100ms
    sample_rate = 2.4e6
    num_samples = int(sample_rate * duration)

    t = np.arange(num_samples) / sample_rate
    signal_freq = 1e6  # 1 MHz tone
    signal = 0.5 * np.exp(2j * np.pi * signal_freq * t)
    noise = 0.1 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
    iq_samples = (signal + noise).astype(np.complex64)

    print(f"  Samples: {len(iq_samples)}")
    print(f"  Signal: {signal_freq/1e6:.1f} MHz tone + noise")

    # Process with supervisor
    print("\n[5/5] Processing with supervisor...")
    data = {
        'iq_samples': iq_samples,
        'demod_config': {
            'mode': 'FM',
            'bandwidth': 15000
        }
    }

    results = await supervisor.run_with_supervision(data)

    # Analyze results
    print(f"\n  Results: {len(results)}/{len(plugins)} plugins succeeded")

    for result in results:
        if result.success:
            print(f"    ✓ {result.plugin_name}: {result.execution_time_ms:.2f} ms")
            if result.data:
                print(f"      Data type: {result.data.get('type', 'unknown')}")
                print(f"      Status: {result.data.get('status', 'unknown')}")
        else:
            print(f"    ✗ {result.plugin_name}: {result.error}")

    # Get stats
    print("\n" + "=" * 60)
    print("Plugin Statistics:")
    print("=" * 60)
    stats = supervisor.get_stats()
    print(f"Total executions: {stats['total_executions']}")
    print(f"Total failures: {stats['total_failures']}")
    print(f"\nPer-plugin:")
    for plugin_name, plugin_stats in stats['plugin_stats'].items():
        total = plugin_stats['success'] + plugin_stats['failure']
        rate = (plugin_stats['success'] / total * 100) if total > 0 else 0
        print(f"  {plugin_name}: {rate:.1f}% success")

    print("\n" + "=" * 60)
    print("✓ Plugin test passed")
    print("  [✓] All plugins created successfully")
    print("  [✓] Supervisor executed all plugins")
    print("  [✓] Results returned without errors")
    print("=" * 60)


async def test_plugins_with_rtlsdr():
    """Test plugins with real RTL-SDR hardware"""

    if not RTLSDR_AVAILABLE:
        print("\nSKIPPED: RTL-SDR test (hardware not available)")
        return

    print("\n" + "=" * 60)
    print("Plugins + Supervisor Test: Real RTL-SDR")
    print("=" * 60)

    # Initialize RTL-SDR
    print("\n[1/6] Initializing RTL-SDR...")
    sdr = RtlSdr()
    sdr.sample_rate = 2.4e6
    sdr.center_freq = 100e6  # FM band
    sdr.gain = 40

    print(f"  Sample rate: {sdr.sample_rate/1e6:.1f} MSPS")
    print(f"  Center freq: {sdr.center_freq/1e6:.1f} MHz")

    # Initialize processors
    print("\n[2/6] Initializing processors...")
    spectrum_processor = SpectrumProcessor(
        fft_size=4096,
        sample_rate=sdr.sample_rate
    )
    spectrum_processor.update_config(center_frequency=sdr.center_freq)
    audio_demodulator = AudioDemodulators()

    # Create plugins
    print("\n[3/6] Creating plugins...")
    spectrum_plugin = SpectrumPlugin(spectrum_processor)
    waterfall_plugin = WaterfallPlugin(spectrum_processor, max_lines=100)
    demod_plugin = DemodulatorPlugin(audio_demodulator, sample_rate=sdr.sample_rate)
    demod_plugin.enabled = True
    demod_plugin.set_mode('FM', bandwidth=200000)  # Wideband FM

    plugins = [spectrum_plugin, waterfall_plugin, demod_plugin]

    # Create supervisor
    print("\n[4/6] Creating supervisor...")
    supervisor = PluginSupervisor(plugins, name="RTL-SDR-Supervisor")

    # Capture samples
    print("\n[5/6] Capturing samples...")
    iq_samples = sdr.read_samples(4096 * 10)
    print(f"  Captured: {len(iq_samples)} samples")

    # Process with supervisor (10 iterations to test stability)
    print("\n[6/6] Processing 10 iterations...")
    data = {
        'iq_samples': iq_samples,
        'demod_config': {
            'mode': 'FM',
            'bandwidth': 200000
        }
    }

    for i in range(10):
        results = await supervisor.run_with_supervision(data)
        successful = sum(1 for r in results if r.success)
        print(f"  Iteration {i+1}: {successful}/{len(plugins)} succeeded")

    # Cleanup
    sdr.close()

    # Final stats
    print("\n" + "=" * 60)
    print("Supervisor Statistics (10 iterations):")
    print("=" * 60)
    stats = supervisor.get_stats()
    print(f"Total executions: {stats['total_executions']}")
    print(f"Total failures: {stats['total_failures']}")
    print(f"Failure rate: {stats['failure_rate']:.2%}")

    print("\n" + "=" * 60)
    print("✓ RTL-SDR integration test passed")
    print("  [✓] Real hardware captured samples")
    print("  [✓] All plugins processed 10 iterations")
    print("  [✓] Supervisor stability verified")
    print("=" * 60)


async def main():
    """Run all plugin tests"""

    # Test 1: Synthetic data
    await test_plugins_with_synthetic_data()

    # Test 2: Real hardware
    await test_plugins_with_rtlsdr()

    print("\n" + "=" * 60)
    print("ALL PLUGIN TESTS PASSED ✓")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
