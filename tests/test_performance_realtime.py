#!/usr/bin/env python3
"""
Performance tests for H1SDR WebSDR with real hardware
Tests real-time performance metrics: 20 FPS, <100ms latency, memory usage, etc.
"""

import unittest
import time
import psutil
import numpy as np
import asyncio
import json
import sys
import requests
import websockets
from pathlib import Path
from threading import Thread, Event
from concurrent.futures import ThreadPoolExecutor
import gc

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from rtlsdr import RtlSdr
    RTL_SDR_AVAILABLE = True
except ImportError:
    RTL_SDR_AVAILABLE = False

from web_sdr.controllers.sdr_controller import WebSDRController
from web_sdr.config import config


class TestRealtimePerformance(unittest.TestCase):
    """Test real-time performance metrics"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
        cls.base_url = "http://localhost:8000"
        cls.ws_base_url = "ws://localhost:8000"
        
        # Verify server is accessible
        try:
            response = requests.get(f"{cls.base_url}/api/health", timeout=5)
            if response.status_code != 200:
                raise unittest.SkipTest("WebSDR server not running")
        except Exception:
            raise unittest.SkipTest("WebSDR server not accessible")
            
    def setUp(self):
        """Setup for performance tests"""
        # Start SDR with optimal settings
        response = requests.post(f"{self.base_url}/api/sdr/start")
        if response.status_code == 200:
            time.sleep(2.0)
            
            # Tune to FM broadcast for reliable signals
            tune_data = {"frequency": 100e6, "gain": 30.0}
            requests.post(f"{self.base_url}/api/sdr/tune", json=tune_data)
            time.sleep(1.0)
            
        # Get initial process info
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
    def tearDown(self):
        """Cleanup after tests"""
        requests.post(f"{self.base_url}/api/sdr/stop")
        
    def test_spectrum_frame_rate_stability(self):
        """Test spectrum streaming achieves stable 20 FPS"""
        async def measure_frame_rate():
            uri = f"{self.ws_base_url}/ws/spectrum"
            frame_timestamps = []
            
            try:
                async with websockets.connect(uri, timeout=15) as websocket:
                    # Collect frames for 10 seconds
                    start_time = time.time()
                    
                    while time.time() - start_time < 10.0:
                        message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        frame_timestamps.append(time.time())
                        
                    # Analyze frame rate
                    if len(frame_timestamps) >= 2:
                        intervals = [frame_timestamps[i+1] - frame_timestamps[i] 
                                   for i in range(len(frame_timestamps)-1)]
                        
                        avg_interval = np.mean(intervals)
                        std_interval = np.std(intervals)
                        avg_fps = 1.0 / avg_interval
                        
                        # Target: 20 FPS ± 2 FPS
                        self.assertGreater(avg_fps, 18, f"FPS too low: {avg_fps:.1f}")
                        self.assertLess(avg_fps, 22, f"FPS too high: {avg_fps:.1f}")
                        
                        # Frame timing should be stable (coefficient of variation < 20%)
                        cv = std_interval / avg_interval
                        self.assertLess(cv, 0.2, f"Frame timing unstable: CV={cv:.3f}")
                        
                        print(f"Frame rate: {avg_fps:.1f} FPS ± {std_interval*1000:.1f}ms")
                        
            except Exception as e:
                self.fail(f"Frame rate test failed: {e}")
                
        asyncio.run(measure_frame_rate())
        
    def test_end_to_end_latency(self):
        """Test end-to-end latency < 100ms"""
        async def measure_latency():
            uri = f"{self.ws_base_url}/ws/spectrum"
            latencies = []
            
            try:
                async with websockets.connect(uri, timeout=10) as websocket:
                    # Measure latency for multiple frames
                    for i in range(20):
                        request_time = time.time()
                        
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        response_time = time.time()
                        
                        data = json.loads(message)
                        data_timestamp = data.get("timestamp", response_time)
                        
                        # Calculate different latency metrics
                        network_latency = (response_time - request_time) * 1000  # ms
                        data_age = (response_time - data_timestamp) * 1000  # ms
                        
                        latencies.append({
                            'network': network_latency,
                            'data_age': data_age,
                            'total': network_latency + data_age
                        })
                        
                        time.sleep(0.1)  # Don't overwhelm
                        
                    # Analyze latencies
                    network_latencies = [l['network'] for l in latencies]
                    total_latencies = [l['total'] for l in latencies]
                    
                    avg_network = np.mean(network_latencies)
                    avg_total = np.mean(total_latencies)
                    p95_total = np.percentile(total_latencies, 95)
                    
                    print(f"Network latency: {avg_network:.1f}ms avg")
                    print(f"Total latency: {avg_total:.1f}ms avg, {p95_total:.1f}ms p95")
                    
                    # Requirements: <100ms total latency for 95th percentile
                    self.assertLess(p95_total, 100, f"Latency too high: {p95_total:.1f}ms")
                    self.assertLess(avg_total, 80, f"Average latency too high: {avg_total:.1f}ms")
                    
            except Exception as e:
                self.fail(f"Latency test failed: {e}")
                
        asyncio.run(measure_latency())
        
    def test_memory_usage_stability(self):
        """Test memory usage remains stable (~50MB typical)"""
        initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        memory_samples = [initial_memory]
        
        async def stream_and_monitor():
            uri = f"{self.ws_base_url}/ws/spectrum"
            
            try:
                async with websockets.connect(uri, timeout=15) as websocket:
                    # Stream for 30 seconds while monitoring memory
                    start_time = time.time()
                    
                    while time.time() - start_time < 30.0:
                        # Receive data
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        
                        # Sample memory every 2 seconds
                        if len(memory_samples) < 15:  # 30s / 2s = 15 samples
                            current_memory = self.process.memory_info().rss / 1024 / 1024
                            memory_samples.append(current_memory)
                            
                        await asyncio.sleep(0.05)  # Don't overwhelm
                        
            except Exception as e:
                self.fail(f"Memory monitoring failed: {e}")
                
        # Run streaming with memory monitoring
        asyncio.run(stream_and_monitor())
        
        # Analyze memory usage
        avg_memory = np.mean(memory_samples)
        max_memory = np.max(memory_samples)
        memory_growth = max_memory - initial_memory
        
        print(f"Memory usage: {avg_memory:.1f}MB avg, {max_memory:.1f}MB peak")
        print(f"Memory growth: {memory_growth:.1f}MB over 30s")
        
        # Requirements
        self.assertLess(avg_memory, 100, f"Average memory too high: {avg_memory:.1f}MB")
        self.assertLess(max_memory, 150, f"Peak memory too high: {max_memory:.1f}MB")
        self.assertLess(memory_growth, 20, f"Memory growth too high: {memory_growth:.1f}MB")
        
    def test_concurrent_client_performance(self):
        """Test performance with multiple concurrent clients"""
        async def concurrent_client(client_id, results):
            uri = f"{self.ws_base_url}/ws/spectrum"
            frame_count = 0
            start_time = time.time()
            
            try:
                async with websockets.connect(uri, timeout=15) as websocket:
                    # Stream for 15 seconds
                    while time.time() - start_time < 15.0:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        frame_count += 1
                        
                    # Calculate performance metrics
                    duration = time.time() - start_time
                    fps = frame_count / duration
                    results[client_id] = {'fps': fps, 'frames': frame_count}
                    
            except Exception as e:
                results[client_id] = {'error': str(e)}
                
        async def test_concurrent():
            n_clients = 5  # Test with 5 concurrent clients
            results = {}
            
            # Create concurrent client tasks
            tasks = []
            for i in range(n_clients):
                task = concurrent_client(i, results)
                tasks.append(task)
                
            # Run all clients concurrently
            await asyncio.gather(*tasks)
            
            # Analyze results
            successful_clients = 0
            fps_values = []
            
            for client_id, result in results.items():
                if 'error' in result:
                    print(f"Client {client_id} failed: {result['error']}")
                else:
                    successful_clients += 1
                    fps = result['fps']
                    fps_values.append(fps)
                    print(f"Client {client_id}: {fps:.1f} FPS ({result['frames']} frames)")
                    
            # Requirements
            self.assertGreater(successful_clients, 3, "Too many clients failed")
            
            if fps_values:
                avg_fps = np.mean(fps_values)
                min_fps = np.min(fps_values)
                
                # Each client should maintain reasonable frame rate
                self.assertGreater(min_fps, 15, f"Minimum FPS too low: {min_fps:.1f}")
                self.assertGreater(avg_fps, 18, f"Average FPS too low: {avg_fps:.1f}")
                
        asyncio.run(test_concurrent())
        
    def test_cpu_usage_under_load(self):
        """Test CPU usage remains reasonable under full load"""
        cpu_samples = []
        
        async def load_test():
            # Start multiple streams
            uris = [f"{self.ws_base_url}/ws/spectrum" for _ in range(3)]
            
            async def stream_client(uri):
                try:
                    async with websockets.connect(uri, timeout=15) as websocket:
                        start_time = time.time()
                        while time.time() - start_time < 20.0:
                            await asyncio.wait_for(websocket.recv(), timeout=5.0)
                            await asyncio.sleep(0.01)
                except Exception:
                    pass  # Ignore individual client errors
                    
            # Sample CPU usage during load test
            async def cpu_monitor():
                start_time = time.time()
                while time.time() - start_time < 20.0:
                    cpu_percent = self.process.cpu_percent()
                    cpu_samples.append(cpu_percent)
                    await asyncio.sleep(1.0)
                    
            # Run load test with monitoring
            tasks = [stream_client(uri) for uri in uris]
            tasks.append(cpu_monitor())
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        # Run load test
        asyncio.run(load_test())
        
        if cpu_samples:
            avg_cpu = np.mean(cpu_samples)
            max_cpu = np.max(cpu_samples)
            
            print(f"CPU usage: {avg_cpu:.1f}% avg, {max_cpu:.1f}% peak")
            
            # Should not use excessive CPU
            self.assertLess(avg_cpu, 50, f"Average CPU too high: {avg_cpu:.1f}%")
            self.assertLess(max_cpu, 80, f"Peak CPU too high: {max_cpu:.1f}%")


class TestStreamingStability(unittest.TestCase):
    """Test long-term streaming stability"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
        cls.base_url = "http://localhost:8000"
        cls.ws_base_url = "ws://localhost:8000"
        
    def test_long_duration_stability(self):
        """Test streaming stability over extended period"""
        async def stability_test():
            # Start SDR
            requests.post(f"{self.base_url}/api/sdr/start")
            time.sleep(2.0)
            
            tune_data = {"frequency": 145e6, "gain": 35.0}
            requests.post(f"{self.base_url}/api/sdr/tune", json=tune_data)
            time.sleep(1.0)
            
            uri = f"{self.ws_base_url}/ws/spectrum"
            frame_intervals = []
            error_count = 0
            
            try:
                async with websockets.connect(uri, timeout=20) as websocket:
                    # Stream for 60 seconds (shorter for testing)
                    start_time = time.time()
                    last_frame_time = start_time
                    
                    while time.time() - start_time < 60.0:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                            current_time = time.time()
                            
                            # Record frame interval
                            interval = current_time - last_frame_time
                            frame_intervals.append(interval)
                            last_frame_time = current_time
                            
                        except asyncio.TimeoutError:
                            error_count += 1
                            if error_count > 5:
                                break
                                
                    # Analyze stability
                    if len(frame_intervals) > 10:
                        avg_interval = np.mean(frame_intervals)
                        std_interval = np.std(frame_intervals)
                        cv = std_interval / avg_interval
                        
                        avg_fps = 1.0 / avg_interval
                        
                        print(f"Long-term stability: {avg_fps:.1f} FPS, CV={cv:.3f}")
                        print(f"Errors: {error_count}")
                        
                        # Stability requirements
                        self.assertGreater(avg_fps, 15, "Long-term FPS too low")
                        self.assertLess(cv, 0.3, "Long-term timing too unstable")
                        self.assertLess(error_count, 3, "Too many streaming errors")
                        
            except Exception as e:
                self.fail(f"Stability test failed: {e}")
            finally:
                requests.post(f"{self.base_url}/api/sdr/stop")
                
        asyncio.run(stability_test())
        
    def test_band_switching_performance(self):
        """Test performance during rapid band switching"""
        bands_to_test = ["fm_broadcast", "2m_band", "70cm_band", "h1_line"]
        
        async def switching_test():
            # Start SDR
            requests.post(f"{self.base_url}/api/sdr/start")
            time.sleep(2.0)
            
            uri = f"{self.ws_base_url}/ws/spectrum"
            switching_times = []
            
            try:
                async with websockets.connect(uri, timeout=20) as websocket:
                    for band in bands_to_test:
                        # Measure switching time
                        switch_start = time.time()
                        
                        # Switch band
                        response = requests.post(f"{self.base_url}/api/bands/{band}/tune")
                        self.assertEqual(response.status_code, 200)
                        
                        # Wait for first frame on new frequency
                        message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                        switch_end = time.time()
                        
                        switching_time = (switch_end - switch_start) * 1000  # ms
                        switching_times.append(switching_time)
                        
                        print(f"Band {band}: {switching_time:.0f}ms switching time")
                        
                        # Brief pause between switches
                        await asyncio.sleep(0.5)
                        
                    # Analyze switching performance
                    avg_switch_time = np.mean(switching_times)
                    max_switch_time = np.max(switching_times)
                    
                    print(f"Switching: {avg_switch_time:.0f}ms avg, {max_switch_time:.0f}ms max")
                    
                    # Requirements: band switching should be fast
                    self.assertLess(avg_switch_time, 2000, "Average switching too slow")
                    self.assertLess(max_switch_time, 5000, "Max switching too slow")
                    
            except Exception as e:
                self.fail(f"Band switching test failed: {e}")
            finally:
                requests.post(f"{self.base_url}/api/sdr/stop")
                
        asyncio.run(switching_test())


class TestResourceUtilization(unittest.TestCase):
    """Test resource utilization and limits"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
        cls.base_url = "http://localhost:8000"
        cls.ws_base_url = "ws://localhost:8000"
        
    def test_memory_leak_detection(self):
        """Test for memory leaks during continuous operation"""
        # Force garbage collection
        gc.collect()
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        async def leak_test():
            # Start SDR
            requests.post(f"{self.base_url}/api/sdr/start")
            time.sleep(2.0)
            
            uri = f"{self.ws_base_url}/ws/spectrum"
            memory_samples = []
            
            try:
                # Run multiple connection cycles
                for cycle in range(5):
                    async with websockets.connect(uri, timeout=15) as websocket:
                        # Stream for 10 seconds
                        start_time = time.time()
                        while time.time() - start_time < 10.0:
                            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                            
                            # Sample memory occasionally
                            if len(memory_samples) <= cycle * 2:
                                current_memory = process.memory_info().rss / 1024 / 1024
                                memory_samples.append(current_memory)
                                
                    # Brief pause between cycles
                    await asyncio.sleep(1.0)
                    gc.collect()  # Force GC between cycles
                    
                # Check for memory growth trend
                if len(memory_samples) >= 3:
                    # Linear regression to detect growth trend
                    x = np.arange(len(memory_samples))
                    y = np.array(memory_samples)
                    
                    slope, _ = np.polyfit(x, y, 1)
                    
                    print(f"Memory trend: {slope:.2f} MB/cycle")
                    print(f"Memory samples: {[f'{m:.1f}' for m in memory_samples]} MB")
                    
                    # Should not have significant memory growth
                    self.assertLess(slope, 2.0, f"Potential memory leak: {slope:.2f} MB/cycle")
                    
                    final_memory = memory_samples[-1]
                    memory_growth = final_memory - initial_memory
                    self.assertLess(memory_growth, 30, f"Excessive memory growth: {memory_growth:.1f} MB")
                    
            except Exception as e:
                self.fail(f"Memory leak test failed: {e}")
            finally:
                requests.post(f"{self.base_url}/api/sdr/stop")
                
        asyncio.run(leak_test())
        
    def test_connection_limits(self):
        """Test system handles connection limits gracefully"""
        async def connection_limit_test():
            # Start SDR
            requests.post(f"{self.base_url}/api/sdr/start")
            time.sleep(2.0)
            
            uri = f"{self.ws_base_url}/ws/spectrum"
            connections = []
            successful_connections = 0
            
            try:
                # Try to open many connections (more than limit)
                for i in range(15):  # Try more than max_spectrum_clients (10)
                    try:
                        websocket = await websockets.connect(uri, timeout=5)
                        connections.append(websocket)
                        successful_connections += 1
                        
                        # Verify connection works
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        
                    except Exception as e:
                        print(f"Connection {i} failed: {e}")
                        break
                        
                print(f"Successful connections: {successful_connections}")
                
                # Should allow up to configured limit
                self.assertGreaterEqual(successful_connections, 5, "Too few connections allowed")
                self.assertLessEqual(successful_connections, 12, "No connection limit enforced")
                
                # Test existing connections still work
                working_connections = 0
                for websocket in connections[:5]:  # Test first 5
                    try:
                        await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        working_connections += 1
                    except Exception:
                        pass
                        
                self.assertGreater(working_connections, 3, "Existing connections degraded")
                
            finally:
                # Clean up connections
                for websocket in connections:
                    try:
                        await websocket.close()
                    except Exception:
                        pass
                        
                requests.post(f"{self.base_url}/api/sdr/stop")
                
        asyncio.run(connection_limit_test())


def run_performance_tests():
    """Run all performance tests"""
    if not RTL_SDR_AVAILABLE:
        print("RTL-SDR library not available. Skipping performance tests.")
        return False
        
    print("Starting performance tests...")
    print("Note: These tests require WebSDR server running and may take several minutes")
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add performance test cases
    suite.addTests(loader.loadTestsFromTestCase(TestRealtimePerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestStreamingStability))
    suite.addTests(loader.loadTestsFromTestCase(TestResourceUtilization))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("H1SDR Real-Time Performance Tests")
    print("=" * 50)
    success = run_performance_tests()
    exit(0 if success else 1)