#!/usr/bin/env python3
"""
DSP Pipeline Performance Profiling Tool

Profiles critical paths in the H1SDR DSP pipeline:
- FFT processing
- Plugin execution
- WebSocket message packaging
- Overall throughput

Usage:
    python tools/profile_dsp.py [--samples N] [--runs N]
"""

import argparse
import sys
import time
import cProfile
import pstats
import io
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.web_sdr.dsp.fft_processor import FFTProcessor
from src.web_sdr.dsp.spectrum_processor import SpectrumProcessor
from src.web_sdr.plugins import SpectrumPlugin, WaterfallPlugin, DemodulatorPlugin
from src.web_sdr.pipeline.plugin_supervisor import PluginSupervisor
from src.web_sdr.dsp.demodulators import AudioDemodulators
import asyncio


class DSPProfiler:
    """Profiles DSP pipeline components"""

    def __init__(self, sample_rate: float = 2.4e6, fft_size: int = 4096):
        self.sample_rate = sample_rate
        self.fft_size = fft_size

        # Initialize components
        self.fft_processor = FFTProcessor(fft_size=fft_size, enable_threading=True)
        self.spectrum_processor = SpectrumProcessor(
            fft_size=fft_size,
            sample_rate=sample_rate
        )
        self.audio_demod = AudioDemodulators()

        # Initialize plugins
        self.spectrum_plugin = SpectrumPlugin(self.spectrum_processor)
        self.waterfall_plugin = WaterfallPlugin(self.spectrum_processor, max_lines=100)
        self.demod_plugin = DemodulatorPlugin(
            self.audio_demod,
            sample_rate=sample_rate,
            audio_sample_rate=48000
        )

        # Plugin supervisor
        self.supervisor = PluginSupervisor(
            [self.spectrum_plugin, self.waterfall_plugin, self.demod_plugin],
            name="ProfilerSupervisor"
        )

    def generate_test_samples(self, num_samples: int) -> np.ndarray:
        """Generate synthetic IQ samples for testing"""
        # Generate complex samples with some signal content
        t = np.arange(num_samples) / self.sample_rate

        # Mix of sine waves at different frequencies
        signal = (
            0.3 * np.exp(2j * np.pi * 100e3 * t) +  # 100 kHz tone
            0.2 * np.exp(2j * np.pi * 250e3 * t) +  # 250 kHz tone
            0.1 * np.exp(2j * np.pi * -150e3 * t)   # -150 kHz tone
        )

        # Add noise
        noise = 0.05 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))

        return (signal + noise).astype(np.complex64)

    def profile_fft(self, samples: np.ndarray, runs: int = 100) -> Dict[str, Any]:
        """Profile FFT processing"""
        print(f"\nProfiling FFT processing ({runs} runs)...")

        # FFT processor needs exactly fft_size samples
        fft_samples = samples[:self.fft_size]

        # Warmup
        for _ in range(10):
            _ = self.fft_processor.process(fft_samples)

        # Benchmark
        times = []
        for _ in range(runs):
            start = time.perf_counter()
            result = self.fft_processor.process(fft_samples)
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)  # Convert to ms

        return {
            'component': 'FFT Processor',
            'runs': runs,
            'min_ms': min(times),
            'max_ms': max(times),
            'avg_ms': np.mean(times),
            'std_ms': np.std(times),
            'median_ms': np.median(times),
            'throughput_fps': 1000 / np.mean(times)
        }

    def profile_spectrum_processor(self, samples: np.ndarray, runs: int = 100) -> Dict[str, Any]:
        """Profile spectrum processing"""
        print(f"Profiling spectrum processor ({runs} runs)...")

        # Warmup
        for _ in range(10):
            _ = self.spectrum_processor.process_samples(samples)

        # Benchmark
        times = []
        for _ in range(runs):
            start = time.perf_counter()
            result = self.spectrum_processor.process_samples(samples)
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        return {
            'component': 'Spectrum Processor',
            'runs': runs,
            'min_ms': min(times),
            'max_ms': max(times),
            'avg_ms': np.mean(times),
            'std_ms': np.std(times),
            'median_ms': np.median(times),
            'throughput_fps': 1000 / np.mean(times)
        }

    async def profile_plugins_async(self, samples: np.ndarray, runs: int = 100) -> Dict[str, Any]:
        """Profile plugin execution"""
        print(f"Profiling plugin execution ({runs} runs)...")

        plugin_data = {
            'iq_samples': samples,
            'demod_config': {'mode': 'SPECTRUM', 'bandwidth': 200000}
        }

        # Warmup
        for _ in range(10):
            _ = await self.supervisor.run_with_supervision(plugin_data)

        # Benchmark
        times = []
        for _ in range(runs):
            start = time.perf_counter()
            results = await self.supervisor.run_with_supervision(plugin_data)
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        return {
            'component': 'Plugin Supervisor',
            'runs': runs,
            'min_ms': min(times),
            'max_ms': max(times),
            'avg_ms': np.mean(times),
            'std_ms': np.std(times),
            'median_ms': np.median(times),
            'throughput_fps': 1000 / np.mean(times)
        }

    def profile_websocket_packaging(self, samples: np.ndarray, runs: int = 100) -> Dict[str, Any]:
        """Profile WebSocket message creation"""
        print(f"Profiling WebSocket message packaging ({runs} runs)...")

        # Process samples to get spectrum data
        frequencies, spectrum_db = self.spectrum_processor.process_samples(samples)

        # Benchmark packaging
        times = []
        for _ in range(runs):
            start = time.perf_counter()

            # Simulate WebSocket message creation
            message = {
                'type': 'spectrum',
                'frequencies': frequencies.tolist(),
                'spectrum': spectrum_db.tolist(),
                'timestamp': time.time(),
                'metadata': {
                    'sample_rate': self.sample_rate,
                    'fft_size': self.fft_size,
                    'gain': 40.0
                }
            }

            # Convert to JSON (simulating what happens in WebSocket)
            import json
            json_str = json.dumps(message)
            json_size = len(json_str)

            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        return {
            'component': 'WebSocket Packaging',
            'runs': runs,
            'min_ms': min(times),
            'max_ms': max(times),
            'avg_ms': np.mean(times),
            'std_ms': np.std(times),
            'median_ms': np.median(times),
            'message_size_kb': json_size / 1024,
            'throughput_fps': 1000 / np.mean(times)
        }

    async def profile_end_to_end_async(self, samples: np.ndarray, runs: int = 50) -> Dict[str, Any]:
        """Profile end-to-end pipeline"""
        print(f"Profiling end-to-end pipeline ({runs} runs)...")

        plugin_data = {
            'iq_samples': samples,
            'demod_config': {'mode': 'SPECTRUM', 'bandwidth': 200000}
        }

        times = []
        for _ in range(runs):
            start = time.perf_counter()

            # Full pipeline
            results = await self.supervisor.run_with_supervision(plugin_data)

            # Extract and package spectrum
            for result in results:
                if result.success and result.data.get('type') == 'spectrum':
                    spectrum_result = result.data
                    message = {
                        'type': 'spectrum',
                        'frequencies': spectrum_result['frequencies'].tolist(),
                        'spectrum': spectrum_result['spectrum_db'].tolist(),
                        'timestamp': time.time()
                    }
                    import json
                    json_str = json.dumps(message)
                    break

            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        return {
            'component': 'End-to-End Pipeline',
            'runs': runs,
            'min_ms': min(times),
            'max_ms': max(times),
            'avg_ms': np.mean(times),
            'std_ms': np.std(times),
            'median_ms': np.median(times),
            'throughput_fps': 1000 / np.mean(times)
        }


def print_profile_results(results: List[Dict[str, Any]]):
    """Print profiling results in a formatted table"""
    print("\n" + "=" * 80)
    print("DSP PIPELINE PERFORMANCE PROFILE")
    print("=" * 80)

    for result in results:
        print(f"\n{result['component']}:")
        print(f"  Runs: {result['runs']}")
        print(f"  Min:    {result['min_ms']:8.3f} ms")
        print(f"  Max:    {result['max_ms']:8.3f} ms")
        print(f"  Avg:    {result['avg_ms']:8.3f} ms")
        print(f"  Median: {result['median_ms']:8.3f} ms")
        print(f"  StdDev: {result['std_ms']:8.3f} ms")

        if 'throughput_fps' in result:
            print(f"  Throughput: {result['throughput_fps']:.1f} FPS")

        if 'message_size_kb' in result:
            print(f"  Message size: {result['message_size_kb']:.2f} KB")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    e2e = next((r for r in results if r['component'] == 'End-to-End Pipeline'), None)
    if e2e:
        print(f"Maximum sustainable FPS: {e2e['throughput_fps']:.1f}")
        print(f"Average latency: {e2e['avg_ms']:.2f} ms")
        print(f"Target FPS (20): {'✅ ACHIEVABLE' if e2e['throughput_fps'] >= 20 else '❌ NOT ACHIEVABLE'}")


async def main():
    parser = argparse.ArgumentParser(description='Profile H1SDR DSP pipeline')
    parser.add_argument('--samples', type=int, default=262144,
                      help='Number of IQ samples (default: 262144 = ~100ms @ 2.4 MSPS)')
    parser.add_argument('--runs', type=int, default=100,
                      help='Number of profiling runs (default: 100)')
    parser.add_argument('--detailed', action='store_true',
                      help='Enable detailed cProfile output')

    args = parser.parse_args()

    print("=" * 80)
    print("H1SDR v2.0 - DSP Pipeline Performance Profiler")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Samples: {args.samples:,} ({args.samples / 2.4e6 * 1000:.1f} ms @ 2.4 MSPS)")
    print(f"  Runs: {args.runs}")
    print(f"  FFT size: 4096")
    print(f"  Sample rate: 2.4 MSPS")

    profiler = DSPProfiler()
    samples = profiler.generate_test_samples(args.samples)

    results = []

    # Profile each component
    results.append(profiler.profile_fft(samples, args.runs))
    results.append(profiler.profile_spectrum_processor(samples, args.runs))
    results.append(await profiler.profile_plugins_async(samples, args.runs))
    results.append(profiler.profile_websocket_packaging(samples, args.runs))
    results.append(await profiler.profile_end_to_end_async(samples, args.runs // 2))

    # Print results
    print_profile_results(results)

    # Detailed profiling if requested
    if args.detailed:
        print("\n" + "=" * 80)
        print("DETAILED PROFILING (cProfile)")
        print("=" * 80)

        profiler_obj = cProfile.Profile()
        profiler_obj.enable()

        # Run end-to-end a few times
        for _ in range(10):
            await profiler.profile_end_to_end_async(samples, 1)

        profiler_obj.disable()

        # Print stats
        s = io.StringIO()
        ps = pstats.Stats(profiler_obj, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # Top 20 functions
        print(s.getvalue())


if __name__ == "__main__":
    asyncio.run(main())
