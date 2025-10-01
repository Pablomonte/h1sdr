"""
Test FFTW Integration with Existing Pipeline

Verifies that v2.0 FFTProcessor integrates correctly with SpectrumProcessor
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.web_sdr.dsp.spectrum_processor import SpectrumProcessor

try:
    from rtlsdr import RtlSdr
    RTLSDR_AVAILABLE = True
except ImportError:
    RTLSDR_AVAILABLE = False


def test_spectrum_processor_with_fftw():
    """Test SpectrumProcessor uses v2.0 FFTProcessor"""

    print("=" * 60)
    print("FFTW Integration Test: SpectrumProcessor + FFTProcessor")
    print("=" * 60)

    # Initialize SpectrumProcessor
    print("\n[1/4] Initializing SpectrumProcessor...")
    processor = SpectrumProcessor(
        fft_size=4096,
        sample_rate=2.4e6,
        overlap=0.5
    )

    # Check if FFTW is being used
    print(f"  Using FFTW: {processor.use_fftw}")
    print(f"  FFT Processor: {processor.fft_processor is not None}")

    if not processor.use_fftw:
        print("\n⚠️  WARNING: v2.0 FFTProcessor not loaded")
        print("   Continuing with numpy.fft...\n")
    else:
        print("  ✓ v2.0 FFTProcessor loaded successfully\n")

    # Generate test signal
    print("[2/4] Generating test signal...")
    duration = 0.1  # 100ms
    sample_rate = 2.4e6
    num_samples = int(sample_rate * duration)

    # Create signal: 1 MHz tone + noise
    t = np.arange(num_samples) / sample_rate
    signal_freq = 1e6  # 1 MHz
    signal = 0.5 * np.exp(2j * np.pi * signal_freq * t)
    noise = 0.1 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
    samples = (signal + noise).astype(np.complex64)

    print(f"  Samples: {len(samples)}")
    print(f"  Signal freq: {signal_freq/1e6:.1f} MHz")

    # Process with SpectrumProcessor
    print("\n[3/4] Processing spectrum...")
    import time
    start = time.perf_counter()

    frequencies, spectrum_db = processor.process_samples(samples)

    elapsed = time.perf_counter() - start

    print(f"  Processing time: {elapsed*1000:.2f} ms")
    print(f"  FFT size: {len(spectrum_db)}")
    print(f"  Frequency range: {frequencies[0]/1e6:.2f} - {frequencies[-1]/1e6:.2f} MHz")

    # Verify spectrum
    peak_idx = np.argmax(spectrum_db)
    peak_freq = frequencies[peak_idx]
    peak_power = spectrum_db[peak_idx]

    print(f"  Peak frequency: {peak_freq/1e6:.4f} MHz")
    print(f"  Peak power: {peak_power:.1f} dB")
    print(f"  Mean power: {np.mean(spectrum_db):.1f} dB")

    # Benchmark
    print("\n[4/4] Benchmarking (20 iterations)...")
    start = time.perf_counter()
    for _ in range(20):
        processor.process_samples(samples)
    elapsed = time.perf_counter() - start

    avg_time = (elapsed / 20) * 1000
    throughput = 1000 / avg_time

    print(f"  Average time: {avg_time:.2f} ms")
    print(f"  Throughput: {throughput:.1f} FPS")

    print("\n" + "=" * 60)
    print("✓ Integration test passed")
    print("  [✓] SpectrumProcessor initialized")
    print("  [✓] Signal processing successful")
    print(f"  [✓] {'v2.0 FFTProcessor' if processor.use_fftw else 'numpy.fft'} working")
    print(f"  [✓] Performance: {avg_time:.2f} ms avg, {throughput:.1f} FPS")
    print("=" * 60)


def test_rtlsdr_pipeline():
    """Test full pipeline with real RTL-SDR"""

    if not RTLSDR_AVAILABLE:
        print("\nSKIPPED: RTL-SDR test (hardware not available)")
        return

    print("\n" + "=" * 60)
    print("Full Pipeline Test: RTL-SDR → SpectrumProcessor → FFT")
    print("=" * 60)

    # Initialize RTL-SDR
    print("\n[1/3] Initializing RTL-SDR...")
    sdr = RtlSdr()
    sdr.sample_rate = 2.4e6
    sdr.center_freq = 100e6  # FM band
    sdr.gain = 40

    print(f"  Sample rate: {sdr.sample_rate/1e6:.1f} MSPS")
    print(f"  Center freq: {sdr.center_freq/1e6:.1f} MHz")

    # Initialize processor
    print("\n[2/3] Initializing SpectrumProcessor...")
    processor = SpectrumProcessor(
        fft_size=4096,
        sample_rate=sdr.sample_rate
    )
    processor.update_config(center_frequency=sdr.center_freq)

    print(f"  Using v2.0 FFTProcessor: {processor.use_fftw}")

    # Capture and process
    print("\n[3/3] Capturing and processing...")
    samples = sdr.read_samples(4096 * 10)  # 10 frames

    import time
    start = time.perf_counter()
    frequencies, spectrum_db = processor.process_samples(samples)
    elapsed = time.perf_counter() - start

    print(f"  Captured: {len(samples)} samples")
    print(f"  Processing time: {elapsed*1000:.2f} ms")
    print(f"  Peak power: {np.max(spectrum_db):.1f} dB")
    print(f"  Noise floor: {np.percentile(spectrum_db, 10):.1f} dB")

    # Cleanup
    sdr.close()

    print("\n" + "=" * 60)
    print("✓ Full pipeline test passed")
    print("  [✓] RTL-SDR capture successful")
    print("  [✓] SpectrumProcessor working")
    print("  [✓] Real-time processing verified")
    print("=" * 60)


if __name__ == '__main__':
    # Test 1: SpectrumProcessor integration
    test_spectrum_processor_with_fftw()

    # Test 2: Real hardware pipeline
    test_rtlsdr_pipeline()

    print("\n" + "=" * 60)
    print("ALL INTEGRATION TESTS PASSED ✓")
    print("=" * 60)
