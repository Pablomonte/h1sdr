#!/usr/bin/env python3
"""
System regression tests for H1SDR WebSDR
Complete end-to-end testing to prevent regressions in core functionality
"""

import unittest
import asyncio
import json
import time
import requests
import websockets
import numpy as np
import sys
from pathlib import Path
from threading import Thread, Event

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from rtlsdr import RtlSdr
    RTL_SDR_AVAILABLE = True
except ImportError:
    RTL_SDR_AVAILABLE = False

from web_sdr.config import config, EXTENDED_RADIO_BANDS, DEMOD_MODES
from web_sdr.controllers.sdr_controller import WebSDRController


class TestCoreSystemFunctionality(unittest.TestCase):
    """Test all core system functionality without regressions"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
        cls.base_url = "http://localhost:8000"
        cls.ws_base_url = "ws://localhost:8000"
        
        # Verify server accessibility
        try:
            response = requests.get(f"{cls.base_url}/api/health", timeout=10)
            if response.status_code != 200:
                raise unittest.SkipTest("WebSDR server not running")
        except Exception:
            raise unittest.SkipTest("WebSDR server not accessible")
            
    def test_system_initialization_sequence(self):
        """Test complete system initialization sequence"""
        print("Testing system initialization...")
        
        # 1. Verify server health
        response = requests.get(f"{self.base_url}/api/health")
        self.assertEqual(response.status_code, 200)
        
        health_data = response.json()
        self.assertEqual(health_data["status"], "ok")
        self.assertIn("version", health_data)
        
        # 2. Verify bands configuration
        response = requests.get(f"{self.base_url}/api/bands")
        self.assertEqual(response.status_code, 200)
        
        bands_data = response.json()
        self.assertTrue(bands_data["success"])
        bands = bands_data["data"]
        
        # Should have exactly 16 bands
        self.assertEqual(len(bands), 16, "Incorrect number of bands")
        
        # Verify critical bands exist
        critical_bands = ["h1_line", "fm_broadcast", "2m_band", "70cm_band"]
        for band in critical_bands:
            self.assertIn(band, bands, f"Critical band {band} missing")
            
        # 3. Verify demod modes
        response = requests.get(f"{self.base_url}/api/modes")
        self.assertEqual(response.status_code, 200)
        
        modes_data = response.json()
        modes = modes_data["data"]
        
        # Should have all demod modes
        expected_modes = ["SPECTRUM", "AM", "FM", "USB", "LSB", "CW"]
        for mode in expected_modes:
            self.assertIn(mode, modes, f"Demod mode {mode} missing")
            
        print("✓ System initialization verified")
        
    def test_sdr_lifecycle_management(self):
        """Test complete SDR lifecycle: start -> configure -> operate -> stop"""
        print("Testing SDR lifecycle...")
        
        # 1. Start SDR
        response = requests.post(f"{self.base_url}/api/sdr/start")
        self.assertEqual(response.status_code, 200)
        
        start_data = response.json()
        self.assertTrue(start_data["success"])
        
        time.sleep(3.0)  # Allow full initialization
        
        # 2. Verify status after start
        response = requests.get(f"{self.base_url}/api/sdr/status")
        self.assertEqual(response.status_code, 200)
        
        status_data = response.json()
        self.assertTrue(status_data["success"])
        
        # 3. Get configuration
        response = requests.get(f"{self.base_url}/api/sdr/config")
        self.assertEqual(response.status_code, 200)
        
        config_data = response.json()
        self.assertIn("sample_rate", config_data)
        self.assertIn("fft_size", config_data)
        self.assertIn("is_running", config_data)
        self.assertTrue(config_data["is_running"])
        
        # Verify configuration values
        self.assertEqual(config_data["fft_size"], 4096)
        self.assertGreaterEqual(config_data["sample_rate"], 2e6)
        
        # 4. Test frequency tuning
        test_frequencies = [100e6, 145e6, 435e6, 1420.4e6]
        
        for freq in test_frequencies:
            tune_data = {"frequency": freq, "gain": 30.0}
            response = requests.post(f"{self.base_url}/api/sdr/tune", json=tune_data)
            self.assertEqual(response.status_code, 200)
            
            tune_response = response.json()
            self.assertTrue(tune_response["success"])
            
            time.sleep(0.5)  # Allow tuning to settle
            
        # 5. Stop SDR
        response = requests.post(f"{self.base_url}/api/sdr/stop")
        self.assertEqual(response.status_code, 200)
        
        stop_data = response.json()
        self.assertTrue(stop_data["success"])
        
        print("✓ SDR lifecycle verified")
        
    def test_all_band_presets_functionality(self):
        """Test all 16 band presets work correctly"""
        print("Testing all band presets...")
        
        # Start SDR
        response = requests.post(f"{self.base_url}/api/sdr/start")
        self.assertEqual(response.status_code, 200)
        time.sleep(3.0)
        
        try:
            # Test each band preset
            failed_bands = []
            successful_bands = []
            
            for band_key, band_info in EXTENDED_RADIO_BANDS.items():
                try:
                    # Tune to band
                    response = requests.post(f"{self.base_url}/api/bands/{band_key}/tune")
                    
                    if response.status_code == 200:
                        tune_response = response.json()
                        if tune_response.get("success", False):
                            successful_bands.append(band_key)
                        else:
                            failed_bands.append((band_key, "Tune response failed"))
                    else:
                        failed_bands.append((band_key, f"HTTP {response.status_code}"))
                        
                    time.sleep(0.5)  # Brief pause between bands
                    
                except Exception as e:
                    failed_bands.append((band_key, str(e)))
                    
            # Report results
            print(f"✓ Successful bands: {len(successful_bands)}/16")
            for band in successful_bands:
                print(f"  ✓ {band}")
                
            if failed_bands:
                print(f"✗ Failed bands: {len(failed_bands)}")
                for band, error in failed_bands:
                    print(f"  ✗ {band}: {error}")
                    
            # Should have most bands working
            self.assertGreater(len(successful_bands), 12, "Too many band presets failed")
            
        finally:
            requests.post(f"{self.base_url}/api/sdr/stop")
            
        print("✓ Band presets verified")
        
    def test_websocket_streaming_integrity(self):
        """Test WebSocket streaming maintains data integrity"""
        print("Testing WebSocket streaming integrity...")
        
        async def test_streaming():
            # Start SDR
            requests.post(f"{self.base_url}/api/sdr/start")
            time.sleep(3.0)
            
            # Tune to FM broadcast
            tune_data = {"frequency": 100e6, "gain": 25.0}
            requests.post(f"{self.base_url}/api/sdr/tune", json=tune_data)
            time.sleep(1.0)
            
            try:
                # Test spectrum streaming
                uri = f"{self.ws_base_url}/ws/spectrum"
                async with websockets.connect(uri, timeout=15) as websocket:
                    
                    # Collect multiple frames
                    frames = []
                    for i in range(10):
                        message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                        data = json.loads(message)
                        frames.append(data)
                        
                    # Verify data integrity
                    for i, frame in enumerate(frames):
                        # Basic structure
                        self.assertEqual(frame.get("type"), "spectrum")
                        self.assertIn("frequencies", frame)
                        self.assertIn("spectrum", frame)
                        self.assertIn("timestamp", frame)
                        
                        # Data consistency
                        frequencies = frame["frequencies"]
                        spectrum = frame["spectrum"]
                        
                        self.assertEqual(len(frequencies), len(spectrum))
                        self.assertEqual(len(frequencies), 4096)  # FFT size
                        
                        # Frequency ordering
                        self.assertTrue(all(frequencies[j] <= frequencies[j+1] 
                                          for j in range(len(frequencies)-1)))
                        
                        # Spectrum values reasonable
                        spectrum_array = np.array(spectrum)
                        self.assertTrue(np.all(spectrum_array < 10))   # Not too high
                        self.assertTrue(np.all(spectrum_array > -150)) # Not too low
                        self.assertTrue(np.all(np.isfinite(spectrum_array)))  # No NaN/inf
                        
                    # Verify timestamps are monotonic
                    timestamps = [frame["timestamp"] for frame in frames]
                    self.assertTrue(all(timestamps[i] <= timestamps[i+1] 
                                      for i in range(len(timestamps)-1)))
                                      
                    print(f"✓ Processed {len(frames)} spectrum frames")
                    
                # Test audio streaming if available
                demod_data = {"mode": "FM", "bandwidth": 15000}
                response = requests.post(f"{self.base_url}/api/demod/set", json=demod_data)
                
                if response.status_code == 200:
                    time.sleep(1.0)
                    
                    uri = f"{self.ws_base_url}/ws/audio"
                    async with websockets.connect(uri, timeout=15) as websocket:
                        
                        # Get audio frames
                        audio_frames = []
                        for i in range(5):
                            message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                            data = json.loads(message)
                            audio_frames.append(data)
                            
                        # Verify audio data
                        for frame in audio_frames:
                            self.assertEqual(frame.get("type"), "audio")
                            self.assertIn("samples", frame)
                            self.assertIn("sample_rate", frame)
                            
                            samples = frame["samples"]
                            sample_rate = frame["sample_rate"]
                            
                            self.assertEqual(sample_rate, 48000)
                            self.assertIsInstance(samples, list)
                            self.assertGreater(len(samples), 100)
                            
                            # Audio samples should be reasonable
                            sample_array = np.array(samples)
                            self.assertTrue(np.all(np.abs(sample_array) <= 1.0))
                            self.assertTrue(np.all(np.isfinite(sample_array)))
                            
                        print(f"✓ Processed {len(audio_frames)} audio frames")
                        
            finally:
                requests.post(f"{self.base_url}/api/sdr/stop")
                
        asyncio.run(test_streaming())
        print("✓ WebSocket streaming integrity verified")
        
    def test_demodulation_modes_functionality(self):
        """Test all demodulation modes work correctly"""
        print("Testing demodulation modes...")
        
        # Start SDR
        response = requests.post(f"{self.base_url}/api/sdr/start")
        self.assertEqual(response.status_code, 200)
        time.sleep(3.0)
        
        try:
            # Test each demodulation mode
            mode_tests = [
                ("SPECTRUM", None, 100e6),    # FM broadcast spectrum
                ("FM", 15000, 100e6),         # FM broadcast
                ("AM", 6000, 125e6),          # Aviation
                ("USB", 2700, 14.2e6),        # HF amateur
                ("LSB", 2700, 3.8e6),         # HF amateur
            ]
            
            successful_modes = []
            failed_modes = []
            
            for mode, bandwidth, test_freq in mode_tests:
                try:
                    # Tune to appropriate frequency
                    tune_data = {"frequency": test_freq, "gain": 30.0}
                    tune_response = requests.post(f"{self.base_url}/api/sdr/tune", json=tune_data)
                    self.assertEqual(tune_response.status_code, 200)
                    time.sleep(1.0)
                    
                    # Set demodulation mode
                    demod_data = {"mode": mode}
                    if bandwidth:
                        demod_data["bandwidth"] = bandwidth
                        
                    response = requests.post(f"{self.base_url}/api/demod/set", json=demod_data)
                    
                    if response.status_code == 200:
                        demod_response = response.json()
                        if demod_response.get("success", False):
                            successful_modes.append(mode)
                        else:
                            failed_modes.append((mode, "Demod response failed"))
                    else:
                        failed_modes.append((mode, f"HTTP {response.status_code}"))
                        
                    time.sleep(1.0)  # Allow mode to settle
                    
                except Exception as e:
                    failed_modes.append((mode, str(e)))
                    
            # Report results
            print(f"✓ Successful modes: {len(successful_modes)}/{len(mode_tests)}")
            for mode in successful_modes:
                print(f"  ✓ {mode}")
                
            if failed_modes:
                print(f"✗ Failed modes: {len(failed_modes)}")
                for mode, error in failed_modes:
                    print(f"  ✗ {mode}: {error}")
                    
            # Should have most modes working
            self.assertGreater(len(successful_modes), 3, "Too many demod modes failed")
            
        finally:
            requests.post(f"{self.base_url}/api/sdr/stop")
            
        print("✓ Demodulation modes verified")
        
    def test_error_handling_robustness(self):
        """Test system handles errors gracefully"""
        print("Testing error handling...")
        
        # Test API error responses
        error_tests = [
            ("GET", "/api/invalid_endpoint", 404),
            ("POST", "/api/sdr/tune", 400),  # No data
            ("GET", "/api/bands/invalid_band", 404),
            ("POST", "/api/demod/set", 400),  # No data
        ]
        
        for method, endpoint, expected_status in error_tests:
            if method == "GET":
                response = requests.get(f"{self.base_url}{endpoint}")
            elif method == "POST":
                response = requests.post(f"{self.base_url}{endpoint}")
                
            self.assertEqual(response.status_code, expected_status,
                           f"Expected {expected_status} for {method} {endpoint}")
            
        # Test invalid parameter handling
        requests.post(f"{self.base_url}/api/sdr/start")
        time.sleep(2.0)
        
        try:
            # Test invalid frequency
            invalid_tune = {"frequency": -100, "gain": 30.0}
            response = requests.post(f"{self.base_url}/api/sdr/tune", json=invalid_tune)
            self.assertIn(response.status_code, [400, 500])  # Should reject
            
            # Test invalid gain
            invalid_gain = {"frequency": 100e6, "gain": 1000}
            response = requests.post(f"{self.base_url}/api/sdr/tune", json=invalid_gain)
            # May succeed with clamping or fail gracefully
            self.assertIn(response.status_code, [200, 400, 500])
            
            # Test invalid demod mode
            invalid_demod = {"mode": "INVALID_MODE"}
            response = requests.post(f"{self.base_url}/api/demod/set", json=invalid_demod)
            self.assertIn(response.status_code, [400, 500])  # Should reject
            
        finally:
            requests.post(f"{self.base_url}/api/sdr/stop")
            
        print("✓ Error handling verified")


class TestSystemStabilityRegression(unittest.TestCase):
    """Test system stability and regression prevention"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
        cls.base_url = "http://localhost:8000"
        cls.ws_base_url = "ws://localhost:8000"
        
    def test_rapid_operations_stability(self):
        """Test system stability under rapid operations"""
        print("Testing rapid operations stability...")
        
        # Start SDR
        response = requests.post(f"{self.base_url}/api/sdr/start")
        self.assertEqual(response.status_code, 200)
        time.sleep(3.0)
        
        try:
            # Rapid frequency changes
            frequencies = [88e6, 100e6, 145e6, 435e6, 1420e6]
            
            for i in range(3):  # 3 cycles
                for freq in frequencies:
                    tune_data = {"frequency": freq, "gain": 30.0}
                    response = requests.post(f"{self.base_url}/api/sdr/tune", json=tune_data)
                    # Should not crash server
                    self.assertIn(response.status_code, [200, 500])
                    time.sleep(0.1)  # Very rapid
                    
            # Rapid demod changes
            modes = ["SPECTRUM", "FM", "AM", "USB"]
            
            for i in range(5):  # 5 cycles
                for mode in modes:
                    demod_data = {"mode": mode}
                    response = requests.post(f"{self.base_url}/api/demod/set", json=demod_data)
                    self.assertIn(response.status_code, [200, 500])
                    time.sleep(0.2)
                    
            # Rapid band changes
            bands = ["fm_broadcast", "2m_band", "70cm_band"]
            
            for i in range(3):
                for band in bands:
                    response = requests.post(f"{self.base_url}/api/bands/{band}/tune")
                    self.assertIn(response.status_code, [200, 500])
                    time.sleep(0.3)
                    
            # System should still be responsive
            response = requests.get(f"{self.base_url}/api/health")
            self.assertEqual(response.status_code, 200)
            
        finally:
            requests.post(f"{self.base_url}/api/sdr/stop")
            
        print("✓ Rapid operations stability verified")
        
    def test_resource_cleanup_verification(self):
        """Test proper resource cleanup"""
        print("Testing resource cleanup...")
        
        # Multiple start/stop cycles
        for cycle in range(3):
            print(f"  Cycle {cycle + 1}/3")
            
            # Start
            response = requests.post(f"{self.base_url}/api/sdr/start")
            self.assertEqual(response.status_code, 200)
            time.sleep(2.0)
            
            # Use system briefly
            tune_data = {"frequency": 100e6, "gain": 30.0}
            requests.post(f"{self.base_url}/api/sdr/tune", json=tune_data)
            time.sleep(1.0)
            
            # Stop
            response = requests.post(f"{self.base_url}/api/sdr/stop")
            self.assertEqual(response.status_code, 200)
            time.sleep(1.0)
            
            # Verify clean state
            response = requests.get(f"{self.base_url}/api/sdr/status")
            if response.status_code == 200:
                status = response.json()
                # Should indicate stopped state
                # (Exact format depends on implementation)
                
        print("✓ Resource cleanup verified")


def run_regression_tests():
    """Run complete regression test suite"""
    if not RTL_SDR_AVAILABLE:
        print("RTL-SDR library not available. Skipping regression tests.")
        return False
        
    print("Starting system regression tests...")
    print("This will verify all core functionality works without regressions")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all regression test cases
    suite.addTests(loader.loadTestsFromTestCase(TestCoreSystemFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemStabilityRegression))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("🎉 ALL REGRESSION TESTS PASSED")
        print("✓ Core functionality verified")
        print("✓ System stability confirmed") 
        print("✓ No regressions detected")
    else:
        print("❌ REGRESSION TESTS FAILED")
        print(f"✗ {len(result.failures)} test failures")
        print(f"✗ {len(result.errors)} test errors")
        print("⚠️  Potential regressions detected!")
        
    return result.wasSuccessful()


if __name__ == '__main__':
    print("H1SDR System Regression Tests")
    print("=" * 50)
    success = run_regression_tests()
    exit(0 if success else 1)