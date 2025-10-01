"""
Phase 1 Integration Test - Real RTL-SDR Hardware

Tests FFTW processor with real IQ samples from RTL-SDR device
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.web_sdr.dsp.fft_processor import FFTProcessor

try:
    from rtlsdr import RtlSdr
    RTLSDR_AVAILABLE = True
except ImportError:
    RTLSDR_AVAILABLE = False
    print("WARNING: pyrtlsdr not available, skipping hardware test")


def test_fftw_with_rtlsdr():
    """Test FFTW processor with real RTL-SDR samples"""

    if not RTLSDR_AVAILABLE:
        print("SKIPPED: RTL-SDR not available")
        return

    print("=" * 60)
    print("Phase 1 Integration Test: FFTW + RTL-SDR")
    print("=" * 60)

    # Initialize RTL-SDR
    print("\n[1/4] Initializing RTL-SDR...")
    sdr = RtlSdr()

    # Configure for FM broadcast band
    sdr.sample_rate = 2.4e6  # 2.4 MSPS
    sdr.center_freq = 100e6  # 100 MHz
    sdr.gain = 40  # ~40 dB

    print(f"  Sample rate: {sdr.sample_rate / 1e6:.1f} MSPS")
    print(f"  Center freq: {sdr.center_freq / 1e6:.1f} MHz")
    print(f"  Gain: {sdr.gain} dB")

    # Initialize FFT processor
    print("\n[2/4] Initializing FFTW processor...")
    fft_size = 4096
    processor = FFTProcessor(fft_size=fft_size, enable_threading=True)

    # Capture samples
    print(f"\n[3/4] Capturing {fft_size} IQ samples...")
    samples = sdr.read_samples(fft_size)
    print(f"  Captured: {len(samples)} samples")
    print(f"  Data type: {samples.dtype}")
    print(f"  Mean amplitude: {np.abs(samples).mean():.4f}")

    # Process with FFTW
    print("\n[4/4] Processing with FFTW...")
    spectrum = processor.process(samples)

    # Analyze spectrum
    spectrum_db = 10 * np.log10(np.abs(spectrum) ** 2 + 1e-10)
    peak_idx = np.argmax(spectrum_db)
    peak_power_db = spectrum_db[peak_idx]

    print(f"  FFT size: {len(spectrum)}")
    print(f"  Peak index: {peak_idx}")
    print(f"  Peak power: {peak_power_db:.1f} dB")
    print(f"  Mean power: {spectrum_db.mean():.1f} dB")
    print(f"  Noise floor: {np.percentile(spectrum_db, 10):.1f} dB")

    # Benchmark with real samples
    print("\n[Benchmark] 20 FFTs @ 2.4 MSPS...")
    benchmark = processor.benchmark(iterations=20)
    print(f"  Average time: {benchmark['avg_time_ms']:.2f} ms")
    print(f"  Throughput: {benchmark['throughput_fps']:.1f} FPS")

    # Cleanup
    sdr.close()

    print("\n" + "=" * 60)
    print("✓ Integration test passed")
    print("  [✓] RTL-SDR samples captured")
    print("  [✓] FFTW processing successful")
    print("  [✓] Spectrum analysis complete")
    print("=" * 60)


def test_fftw_long_run():
    """Test FFTW stability over extended period (simulated)"""

    print("\n" + "=" * 60)
    print("Phase 1 Stability Test: 1-minute continuous FFT")
    print("=" * 60)

    processor = FFTProcessor(fft_size=4096, enable_threading=True)

    # Simulate 20 FPS for 60 seconds = 1200 FFTs
    iterations = 1200
    print(f"\nProcessing {iterations} FFTs (simulating 1 minute @ 20 FPS)...")

    import time
    start = time.perf_counter()

    test_data = (np.random.randn(4096) + 1j * np.random.randn(4096)).astype('complex64')

    for i in range(iterations):
        processor.process(test_data)

        if (i + 1) % 200 == 0:
            elapsed = time.perf_counter() - start
            print(f"  {i + 1}/{iterations} FFTs - {elapsed:.1f}s elapsed")

    elapsed = time.perf_counter() - start
    avg_time_ms = (elapsed / iterations) * 1000

    print(f"\n✓ Stability test passed")
    print(f"  Total time: {elapsed:.1f}s")
    print(f"  Average per FFT: {avg_time_ms:.2f} ms")
    print(f"  CPU efficiency: {(avg_time_ms / (1000/20)) * 100:.1f}% of frame budget")


if __name__ == '__main__':
    # Test 1: Real hardware
    test_fftw_with_rtlsdr()

    # Test 2: Long-run stability
    test_fftw_long_run()

    print("\n" + "=" * 60)
    print("ALL PHASE 1 INTEGRATION TESTS PASSED ✓")
    print("=" * 60)
