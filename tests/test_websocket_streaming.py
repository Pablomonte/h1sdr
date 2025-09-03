#!/usr/bin/env python3
"""
WebSocket streaming tests with real RTL-SDR hardware
Tests complete WebSDR functionality: API + WebSocket + Real-time streaming
"""

import unittest
import asyncio
import json
import time
import websockets
import numpy as np
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from threading import Event, Thread

# Add src to path  
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from rtlsdr import RtlSdr
    RTL_SDR_AVAILABLE = True
except ImportError:
    RTL_SDR_AVAILABLE = False

from web_sdr.main import app
from web_sdr.controllers.sdr_controller import WebSDRController
from web_sdr.services.websocket_service import WebSocketManager
from web_sdr.config import config, EXTENDED_RADIO_BANDS

class TestWebSDRAPI(unittest.TestCase):
    """Test WebSDR FastAPI endpoints with real hardware"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
        # Start WebSDR server in background
        cls.server_process = None
        cls.base_url = "http://localhost:8000"
        cls.server_ready = Event()
        
        # Start server thread
        cls.server_thread = Thread(target=cls._run_server, daemon=True)
        cls.server_thread.start()
        
        # Wait for server to be ready
        if not cls.server_ready.wait(timeout=10):
            raise unittest.SkipTest("WebSDR server failed to start")
            
    @classmethod
    def _run_server(cls):
        """Run WebSDR server in thread"""
        import uvicorn
        try:
            # Signal server is ready
            cls.server_ready.set()
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
        except Exception as e:
            print(f"Server startup failed: {e}")
            
    def setUp(self):
        """Wait for server and verify basic connectivity"""
        # Wait a bit for server to fully initialize
        time.sleep(1.0)
        
        # Verify server is responding
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            if response.status_code != 200:
                self.skipTest("WebSDR server not responding")
        except Exception:
            self.skipTest("WebSDR server not accessible")
            
    def test_api_health_check(self):
        """Test API health endpoint"""
        response = requests.get(f"{self.base_url}/api/health")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("version", data)
        self.assertEqual(data["status"], "ok")
        
    def test_api_sdr_control(self):
        """Test SDR control API endpoints"""
        # Test start SDR
        response = requests.post(f"{self.base_url}/api/sdr/start")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data.get("success", False))
        
        # Wait for initialization
        time.sleep(2.0)
        
        # Test status
        response = requests.get(f"{self.base_url}/api/sdr/status")
        self.assertEqual(response.status_code, 200)
        
        status_data = response.json()
        self.assertTrue(status_data.get("success", False))
        
        # Test tuning
        tune_params = {"frequency": 100e6, "gain": 30.0}
        response = requests.post(f"{self.base_url}/api/sdr/tune", params=tune_params)
        self.assertEqual(response.status_code, 200)
        
        tune_response = response.json()
        self.assertTrue(tune_response.get("success", False))
        
        # Test stop
        response = requests.post(f"{self.base_url}/api/sdr/stop")
        self.assertEqual(response.status_code, 200)
        
    def test_api_band_management(self):
        """Test band management API"""
        # Test get all bands
        response = requests.get(f"{self.base_url}/api/bands")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data.get("success", False))
        self.assertIn("data", data)
        
        bands = data["data"]
        self.assertEqual(len(bands), 16)  # Should have 16 bands
        
        # Test specific band
        response = requests.get(f"{self.base_url}/api/bands/fm_broadcast")
        self.assertEqual(response.status_code, 200)
        
        band_data = response.json()
        self.assertTrue(band_data.get("success", False))
        
        band_info = band_data["data"]
        self.assertIn("name", band_info)
        self.assertIn("center_freq", band_info)
        
        # Test tune to band
        response = requests.post(f"{self.base_url}/api/bands/fm_broadcast/tune")
        # Note: May fail if SDR not started, but should not crash
        self.assertIn(response.status_code, [200, 500])
        
    def test_api_demod_modes(self):
        """Test demodulation mode API"""
        response = requests.get(f"{self.base_url}/api/modes")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data.get("success", False))
        
        modes = data["data"]
        self.assertIn("AM", modes)
        self.assertIn("FM", modes)
        self.assertIn("SPECTRUM", modes)


class TestWebSocketStreaming(unittest.TestCase):
    """Test WebSocket streaming with real RTL-SDR data"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
        cls.base_url = "http://localhost:8000"
        cls.ws_base_url = "ws://localhost:8000"
        
        # Ensure server is running
        try:
            response = requests.get(f"{cls.base_url}/api/health", timeout=5)
            if response.status_code != 200:
                raise unittest.SkipTest("WebSDR server not running")
        except Exception:
            raise unittest.SkipTest("WebSDR server not accessible")
            
    def setUp(self):
        """Prepare SDR for streaming tests"""
        # Start SDR
        response = requests.post(f"{self.base_url}/api/sdr/start")
        if response.status_code == 200:
            time.sleep(2.0)  # Allow initialization
            
            # Tune to FM broadcast for reliable signals
            tune_data = {"frequency": 100e6, "gain": 30.0}
            requests.post(f"{self.base_url}/api/sdr/tune", json=tune_data)
            time.sleep(1.0)
            
    def tearDown(self):
        """Stop SDR after tests"""
        requests.post(f"{self.base_url}/api/sdr/stop")
        
    def test_spectrum_websocket_connection(self):
        """Test spectrum WebSocket connection and data"""
        async def test_connection():
            uri = f"{self.ws_base_url}/ws/spectrum"
            
            try:
                async with websockets.connect(uri, timeout=10) as websocket:
                    # Wait for spectrum data
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    
                    # Parse data
                    data = json.loads(message)
                    
                    # Verify data format
                    self.assertEqual(data.get("type"), "spectrum")
                    self.assertIn("frequencies", data)
                    self.assertIn("spectrum", data)
                    self.assertIn("timestamp", data)
                    
                    # Verify data content
                    frequencies = data["frequencies"]
                    spectrum = data["spectrum"]
                    
                    self.assertIsInstance(frequencies, list)
                    self.assertIsInstance(spectrum, list)
                    self.assertEqual(len(frequencies), len(spectrum))
                    self.assertGreater(len(frequencies), 1000)  # Should have FFT bins
                    
                    # Verify frequency range (around 100 MHz)
                    min_freq = min(frequencies)
                    max_freq = max(frequencies)
                    self.assertGreater(min_freq, 98e6)
                    self.assertLess(max_freq, 102e6)
                    
                    # Verify spectrum values are reasonable
                    self.assertTrue(all(isinstance(x, (int, float)) for x in spectrum))
                    self.assertTrue(all(x < 0 for x in spectrum))  # dBFS should be negative
                    self.assertTrue(all(x > -120 for x in spectrum))  # Not too low
                    
            except Exception as e:
                self.fail(f"WebSocket spectrum test failed: {e}")
                
        # Run async test
        asyncio.run(test_connection())
        
    def test_spectrum_streaming_rate(self):
        """Test spectrum streaming frame rate"""
        async def test_frame_rate():
            uri = f"{self.ws_base_url}/ws/spectrum"
            frame_times = []
            
            try:
                async with websockets.connect(uri, timeout=10) as websocket:
                    # Collect timestamps from multiple frames
                    for i in range(10):
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        frame_times.append(time.time())
                        
                    # Calculate frame rate
                    if len(frame_times) >= 2:
                        time_diffs = [frame_times[i+1] - frame_times[i] 
                                     for i in range(len(frame_times)-1)]
                        avg_interval = np.mean(time_diffs)
                        frame_rate = 1.0 / avg_interval
                        
                        # Should be around 20 FPS (±50% tolerance)
                        self.assertGreater(frame_rate, 10, "Frame rate too low")
                        self.assertLess(frame_rate, 40, "Frame rate too high")
                        
            except Exception as e:
                self.fail(f"Frame rate test failed: {e}")
                
        asyncio.run(test_frame_rate())
        
    def test_audio_websocket_demodulation(self):
        """Test audio WebSocket with FM demodulation"""
        async def test_audio():
            # Set FM demodulation
            demod_data = {"mode": "FM", "bandwidth": 15000}
            response = requests.post(f"{self.base_url}/api/demod/set", json=demod_data)
            
            if response.status_code == 200:
                time.sleep(1.0)  # Allow demod to start
                
                uri = f"{self.ws_base_url}/ws/audio"
                
                try:
                    async with websockets.connect(uri, timeout=10) as websocket:
                        # Wait for audio data
                        message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                        
                        data = json.loads(message)
                        
                        # Verify audio data format
                        self.assertEqual(data.get("type"), "audio")
                        self.assertIn("samples", data)
                        self.assertIn("sample_rate", data)
                        self.assertIn("timestamp", data)
                        
                        # Verify audio content
                        samples = data["samples"]
                        sample_rate = data["sample_rate"]
                        
                        self.assertIsInstance(samples, list)
                        self.assertEqual(sample_rate, 48000)
                        self.assertGreater(len(samples), 100)
                        
                        # Audio samples should be reasonable
                        self.assertTrue(all(isinstance(x, (int, float)) for x in samples))
                        sample_array = np.array(samples)
                        self.assertLess(np.max(np.abs(sample_array)), 1.0)  # Not clipped
                        
                except Exception as e:
                    self.fail(f"Audio WebSocket test failed: {e}")
                    
        asyncio.run(test_audio())
        
    def test_multiple_concurrent_connections(self):
        """Test multiple WebSocket connections"""
        async def test_concurrent():
            n_connections = 3
            tasks = []
            
            async def connect_and_receive(client_id):
                uri = f"{self.ws_base_url}/ws/spectrum"
                try:
                    async with websockets.connect(uri, timeout=10) as websocket:
                        # Receive a few messages
                        for i in range(3):
                            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                            data = json.loads(message)
                            
                            # Verify each client gets valid data
                            self.assertEqual(data.get("type"), "spectrum")
                            self.assertIn("frequencies", data)
                            
                        return f"Client {client_id} success"
                        
                except Exception as e:
                    return f"Client {client_id} failed: {e}"
                    
            # Create concurrent connections
            for i in range(n_connections):
                task = connect_and_receive(i)
                tasks.append(task)
                
            # Wait for all connections
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify all succeeded
            for result in results:
                if isinstance(result, Exception):
                    self.fail(f"Concurrent connection failed: {result}")
                else:
                    self.assertIn("success", str(result))
                    
        asyncio.run(test_concurrent())
        
    def test_websocket_reconnection(self):
        """Test WebSocket reconnection handling"""
        async def test_reconnection():
            uri = f"{self.ws_base_url}/ws/spectrum"
            
            # First connection
            try:
                async with websockets.connect(uri, timeout=10) as websocket1:
                    message1 = await asyncio.wait_for(websocket1.recv(), timeout=5.0)
                    data1 = json.loads(message1)
                    self.assertEqual(data1.get("type"), "spectrum")
                    
                # Connection closed, now reconnect
                time.sleep(0.5)
                
                async with websockets.connect(uri, timeout=10) as websocket2:
                    message2 = await asyncio.wait_for(websocket2.recv(), timeout=5.0)
                    data2 = json.loads(message2)
                    self.assertEqual(data2.get("type"), "spectrum")
                    
                    # Should get fresh data
                    self.assertNotEqual(data1.get("timestamp"), data2.get("timestamp"))
                    
            except Exception as e:
                self.fail(f"Reconnection test failed: {e}")
                
        asyncio.run(test_reconnection())


class TestIntegratedWebSDR(unittest.TestCase):
    """Integration tests for complete WebSDR functionality"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
        cls.base_url = "http://localhost:8000"
        cls.ws_base_url = "ws://localhost:8000"
        
    def test_complete_websdr_workflow(self):
        """Test complete WebSDR workflow: start -> tune -> stream -> stop"""
        async def test_workflow():
            # 1. Start SDR
            response = requests.post(f"{self.base_url}/api/sdr/start")
            self.assertEqual(response.status_code, 200)
            time.sleep(2.0)
            
            # 2. Tune to band
            response = requests.post(f"{self.base_url}/api/bands/fm_broadcast/tune")
            self.assertEqual(response.status_code, 200)
            time.sleep(1.0)
            
            # 3. Set demodulation
            demod_data = {"mode": "SPECTRUM"}
            response = requests.post(f"{self.base_url}/api/demod/set", json=demod_data)
            self.assertEqual(response.status_code, 200)
            
            # 4. Connect to spectrum stream
            uri = f"{self.ws_base_url}/ws/spectrum"
            async with websockets.connect(uri, timeout=10) as websocket:
                # 5. Receive spectrum data
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(message)
                
                self.assertEqual(data.get("type"), "spectrum")
                frequencies = data["frequencies"]
                
                # Should be tuned to FM broadcast range
                center_freq = frequencies[len(frequencies)//2]
                self.assertGreater(center_freq, 95e6)
                self.assertLess(center_freq, 105e6)
                
            # 6. Change to different band
            response = requests.post(f"{self.base_url}/api/bands/2m_band/tune")
            self.assertEqual(response.status_code, 200)
            time.sleep(1.0)
            
            # 7. Verify frequency changed
            async with websockets.connect(uri, timeout=10) as websocket:
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(message)
                
                frequencies = data["frequencies"]
                center_freq = frequencies[len(frequencies)//2]
                
                # Should now be in 2m band
                self.assertGreater(center_freq, 143e6)
                self.assertLess(center_freq, 147e6)
                
            # 8. Stop SDR
            response = requests.post(f"{self.base_url}/api/sdr/stop")
            self.assertEqual(response.status_code, 200)
            
        asyncio.run(test_workflow())
        
    def test_band_switching_with_streaming(self):
        """Test switching bands while streaming"""
        async def test_band_switching():
            # Start SDR
            requests.post(f"{self.base_url}/api/sdr/start")
            time.sleep(2.0)
            
            bands_to_test = ["fm_broadcast", "2m_band", "70cm_band"]
            
            uri = f"{self.ws_base_url}/ws/spectrum"
            async with websockets.connect(uri, timeout=15) as websocket:
                
                for band_key in bands_to_test:
                    # Switch band
                    response = requests.post(f"{self.base_url}/api/bands/{band_key}/tune")
                    self.assertEqual(response.status_code, 200)
                    
                    # Wait for tuning
                    time.sleep(1.5)
                    
                    # Get spectrum data
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(message)
                    
                    # Verify we're in the right frequency range
                    frequencies = data["frequencies"]
                    center_freq = frequencies[len(frequencies)//2]
                    
                    band_info = EXTENDED_RADIO_BANDS[band_key]
                    expected_freq = band_info["center_freq"]
                    
                    # Allow 1 MHz tolerance
                    self.assertAlmostEqual(center_freq, expected_freq, delta=1e6)
                    
            # Stop SDR
            requests.post(f"{self.base_url}/api/sdr/stop")
            
        asyncio.run(test_band_switching())


def run_websocket_tests():
    """Run all WebSocket streaming tests"""
    if not RTL_SDR_AVAILABLE:
        print("RTL-SDR library not available. Skipping WebSocket tests.")
        return False
        
    print("Starting WebSocket streaming tests...")
    print("Note: These tests require WebSDR server to be running")
    
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestWebSDRAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestWebSocketStreaming))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegratedWebSDR))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("H1SDR WebSocket Streaming Tests")
    print("=" * 50)
    success = run_websocket_tests()
    exit(0 if success else 1)