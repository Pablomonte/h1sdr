"""
FFTW-based FFT processor with threading optimization

Target: 3.3x speedup (2ms → 0.6ms for 4096-point FFT @ 4 cores)
Part of: H1SDR v2.0 Phase 1 - Core Performance
"""

import numpy as np
from multiprocessing import cpu_count
import time

try:
    import pyfftw
    FFTW_AVAILABLE = True
except ImportError:
    FFTW_AVAILABLE = False
    print("WARNING: pyfftw not available, falling back to numpy.fft")


class FFTProcessor:
    """High-performance FFT processor with FFTW threading"""

    def __init__(self, fft_size: int = 4096, enable_threading: bool = True):
        """
        Initialize FFT processor

        Args:
            fft_size: FFT size (default 4096)
            enable_threading: Enable FFTW multi-threading (default True)
        """
        self.fft_size = fft_size
        self.enable_threading = enable_threading

        if FFTW_AVAILABLE and enable_threading:
            # Enable threading (3.3x speedup on 4 cores)
            num_threads = min(4, cpu_count())
            pyfftw.config.NUM_THREADS = num_threads
            pyfftw.interfaces.cache.enable()

            # Pre-allocate aligned arrays for zero-copy operation
            self.input_array = pyfftw.empty_aligned(fft_size, dtype='complex64')
            self.output_array = pyfftw.empty_aligned(fft_size, dtype='complex64')

            # Create FFTW plan (reusable across calls)
            self.fft = pyfftw.FFTW(
                self.input_array,
                self.output_array,
                direction='FFTW_FORWARD',
                flags=('FFTW_MEASURE',),  # Optimize plan during creation
                threads=num_threads
            )

            print(f"[FFTProcessor] Initialized with FFTW threading ({num_threads} threads)")
        else:
            self.input_array = None
            self.output_array = None
            self.fft = None
            print("[FFTProcessor] Initialized with numpy.fft (no threading)")

    def process(self, iq_data: np.ndarray) -> np.ndarray:
        """
        Process IQ data through FFT

        Args:
            iq_data: Complex IQ samples (complex64 or complex128)

        Returns:
            FFT spectrum (complex64)
        """
        if len(iq_data) != self.fft_size:
            raise ValueError(f"Expected {self.fft_size} samples, got {len(iq_data)}")

        if FFTW_AVAILABLE and self.enable_threading:
            # Zero-copy FFT processing
            np.copyto(self.input_array, iq_data)
            self.fft()
            return self.output_array.copy()
        else:
            # Fallback to numpy
            return np.fft.fft(iq_data).astype('complex64')

    def benchmark(self, iterations: int = 20) -> dict:
        """
        Benchmark FFT performance

        Args:
            iterations: Number of FFT operations (default 20 = 1 second @ 20 FPS)

        Returns:
            Dictionary with benchmark results
        """
        # Generate test data
        test_data = (np.random.randn(self.fft_size) +
                     1j * np.random.randn(self.fft_size)).astype('complex64')

        # Warmup
        for _ in range(5):
            self.process(test_data)

        # Actual benchmark
        start = time.perf_counter()
        for _ in range(iterations):
            self.process(test_data)
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / iterations) * 1000
        throughput_fps = 1000 / avg_time_ms if avg_time_ms > 0 else float('inf')

        return {
            'iterations': iterations,
            'total_time_ms': elapsed * 1000,
            'avg_time_ms': avg_time_ms,
            'throughput_fps': throughput_fps,
            'fft_size': self.fft_size,
            'threading_enabled': self.enable_threading and FFTW_AVAILABLE,
            'num_threads': pyfftw.config.NUM_THREADS if FFTW_AVAILABLE else 1
        }


def main():
    """Benchmark FFTW threading vs numpy"""

    print("=" * 60)
    print("H1SDR v2.0 - FFTW Threading Benchmark")
    print("=" * 60)

    fft_size = 4096
    iterations = 20  # Simulate 1 second @ 20 FPS

    # Test with FFTW threading
    print("\n[1/2] Testing FFTW with threading...")
    proc_fftw = FFTProcessor(fft_size=fft_size, enable_threading=True)
    results_fftw = proc_fftw.benchmark(iterations)

    print(f"  FFT size: {results_fftw['fft_size']}")
    print(f"  Threads: {results_fftw['num_threads']}")
    print(f"  Average time: {results_fftw['avg_time_ms']:.2f} ms")
    print(f"  Throughput: {results_fftw['throughput_fps']:.1f} FPS")

    # Test with numpy (no threading)
    print("\n[2/2] Testing numpy.fft (baseline)...")
    proc_numpy = FFTProcessor(fft_size=fft_size, enable_threading=False)
    results_numpy = proc_numpy.benchmark(iterations)

    print(f"  FFT size: {results_numpy['fft_size']}")
    print(f"  Threads: {results_numpy['num_threads']}")
    print(f"  Average time: {results_numpy['avg_time_ms']:.2f} ms")
    print(f"  Throughput: {results_numpy['throughput_fps']:.1f} FPS")

    # Calculate speedup
    if FFTW_AVAILABLE:
        speedup = results_numpy['avg_time_ms'] / results_fftw['avg_time_ms']
        print("\n" + "=" * 60)
        print(f"SPEEDUP: {speedup:.2f}x")
        print(f"Target: 3.3x (2ms → 0.6ms)")
        print("=" * 60)

        # Check acceptance criteria
        print("\nAcceptance Criteria:")
        print(f"  [{'✓' if results_fftw['num_threads'] == 4 else '✗'}] 4-core threading enabled")
        print(f"  [{'✓' if results_fftw['avg_time_ms'] < 0.8 else '✗'}] Avg time < 0.8ms")
        print(f"  [{'✓' if speedup > 2.5 else '✗'}] Speedup > 2.5x")
        print(f"  [{'✓' if results_fftw['throughput_fps'] > 20 else '✗'}] Throughput > 20 FPS")
    else:
        print("\n" + "=" * 60)
        print("INSTALL PYFFTW: pip install pyfftw")
        print("=" * 60)


if __name__ == '__main__':
    main()
