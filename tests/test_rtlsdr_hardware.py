#!/usr/bin/env python3
"""
Hardware-dependent tests for RTL-SDR device detection and configuration
Tests real RTL-SDR Blog V4 hardware functionality
"""

import unittest
import numpy as np
import time
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from rtlsdr import RtlSdr
    RTL_SDR_AVAILABLE = True
except ImportError:
    RTL_SDR_AVAILABLE = False

from web_sdr.controllers.sdr_controller import WebSDRController
from web_sdr.config import config, EXTENDED_RADIO_BANDS

class TestRTLSDRHardware(unittest.TestCase):
    """Test RTL-SDR hardware detection and basic operations"""
    
    @classmethod
    def setUpClass(cls):
        """Check if RTL-SDR hardware is available"""
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR library not available")
            
        # Try to detect RTL-SDR device
        try:
            sdr = RtlSdr()
            sdr.close()
            cls.hardware_available = True
        except Exception as e:
            raise unittest.SkipTest(f"No RTL-SDR hardware detected: {e}")
    
    def setUp(self):
        """Set up test fixtures"""
        self.controller = WebSDRController()
        self.test_frequencies = [
            100e6,     # FM broadcast
            145e6,     # 2m amateur
            435e6,     # 70cm amateur
            1420.4e6,  # H1 line
        ]
        
    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'controller') and self.controller.is_running:
            self.controller.cleanup()
            
    def test_rtlsdr_device_detection(self):
        """Test RTL-SDR device detection and enumeration"""
        # Try to open RTL-SDR
        sdr = RtlSdr()
        
        # Verify device can be opened
        self.assertIsNotNone(sdr)
        
        # Check device info - verify it's an RTL-SDR object
        device_info = str(sdr)
        # The object should be a valid RtlSdr instance
        self.assertIn("RtlSdr", device_info)
        
        # Check tuner info - tuner_type returns integer constant
        tuner_type = sdr.get_tuner_type()
        # Valid tuner types (numeric constants): 1=E4000, 2=FC0012, 3=FC0013, 4=FC2580, 5=R820T, 6=R828D
        self.assertIn(tuner_type, [1, 2, 3, 4, 5, 6])
        # Verify we can get actual tuner string for R828D (expected on RTL-SDR Blog V4)
        tuner_gains = sdr.get_gains()
        self.assertIsInstance(tuner_gains, list)
        self.assertGreater(len(tuner_gains), 0)
        
        sdr.close()
        
    def test_rtlsdr_basic_configuration(self):
        """Test basic RTL-SDR configuration parameters"""
        sdr = RtlSdr()
        
        # Test sample rate configuration
        test_rates = [1e6, 2e6, 2.4e6, 2.8e6]
        for rate in test_rates:
            try:
                sdr.sample_rate = rate
                actual_rate = sdr.sample_rate
                # Allow 1% tolerance
                self.assertAlmostEqual(actual_rate, rate, delta=rate*0.01)
            except Exception as e:
                self.fail(f"Failed to set sample rate {rate}: {e}")
                
        # Test center frequency configuration
        for freq in self.test_frequencies:
            try:
                sdr.center_freq = freq
                actual_freq = sdr.center_freq
                # Allow 1kHz tolerance
                self.assertAlmostEqual(actual_freq, freq, delta=1000)
            except Exception as e:
                self.fail(f"Failed to set frequency {freq}: {e}")
                
        # Test gain settings
        valid_gains = sdr.get_gains()
        self.assertIsInstance(valid_gains, list)
        self.assertGreater(len(valid_gains), 0)
        
        for gain in valid_gains[:3]:  # Test first 3 gain values
            try:
                sdr.gain = gain
                actual_gain = sdr.gain
                # RTL-SDR has discrete gain values, allow reasonable tolerance
                self.assertAlmostEqual(actual_gain, gain, delta=1.0)
            except Exception as e:
                self.fail(f"Failed to set gain {gain}: {e}")
                
        sdr.close()
        
    def test_rtlsdr_frequency_range(self):
        """Test RTL-SDR frequency range and tuning accuracy"""
        sdr = RtlSdr()
        sdr.sample_rate = 2.4e6
        
        # Test frequency range limits
        test_ranges = [
            (24e6, 30e6),      # HF upper
            (88e6, 108e6),     # FM broadcast
            (144e6, 148e6),    # 2m amateur
            (430e6, 450e6),    # 70cm amateur
            (1420e6, 1430e6),  # H1 line region
        ]
        
        for freq_min, freq_max in test_ranges:
            # Test minimum frequency
            sdr.center_freq = freq_min
            self.assertAlmostEqual(sdr.center_freq, freq_min, delta=1000)
            
            # Test maximum frequency
            sdr.center_freq = freq_max
            self.assertAlmostEqual(sdr.center_freq, freq_max, delta=1000)
            
            # Test mid-point
            freq_mid = (freq_min + freq_max) / 2
            sdr.center_freq = freq_mid
            self.assertAlmostEqual(sdr.center_freq, freq_mid, delta=1000)
            
        sdr.close()
        
    def test_rtlsdr_sample_acquisition(self):
        """Test RTL-SDR sample acquisition and data format"""
        sdr = RtlSdr()
        sdr.sample_rate = 2.4e6
        sdr.center_freq = 100e6  # FM broadcast
        sdr.gain = 'auto'
        
        # Test different sample counts
        sample_counts = [1024, 8192, 256*1024]
        
        for n_samples in sample_counts:
            samples = sdr.read_samples(n_samples)
            
            # Verify sample count
            self.assertEqual(len(samples), n_samples)
            
            # Verify complex samples
            self.assertTrue(np.iscomplexobj(samples))
            
            # Verify data type
            self.assertEqual(samples.dtype, np.complex128)
            
            # Verify reasonable signal levels
            power = np.mean(np.abs(samples)**2)
            self.assertGreater(power, 1e-6)  # Should have some signal
            self.assertLess(power, 1.0)      # Should not be saturated
            
        sdr.close()
        
    def test_rtlsdr_streaming_stability(self):
        """Test RTL-SDR continuous streaming stability"""
        sdr = RtlSdr()
        sdr.sample_rate = 2.4e6
        sdr.center_freq = 100e6
        sdr.gain = 40.0
        
        # Test continuous acquisition
        n_iterations = 10
        sample_size = 8192
        powers = []
        
        for i in range(n_iterations):
            samples = sdr.read_samples(sample_size)
            power = np.mean(np.abs(samples)**2)
            powers.append(power)
            time.sleep(0.1)  # 100ms between reads
            
        # Check stability (coefficient of variation < 50%)
        power_mean = np.mean(powers)
        power_std = np.std(powers)
        cv = power_std / power_mean
        
        self.assertLess(cv, 0.5, f"Power variation too high: CV={cv:.3f}")
        
        sdr.close()


class TestWebSDRController(unittest.TestCase):
    """Test WebSDR controller with real hardware"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR library not available")
            
    def setUp(self):
        """Set up controller for testing"""
        self.controller = WebSDRController()
        
    def tearDown(self):
        """Clean up controller"""
        if self.controller.is_running:
            import asyncio
            asyncio.run(self.controller.cleanup())
            
    def test_controller_initialization(self):
        """Test WebSDR controller initialization"""
        # Test initial state
        self.assertFalse(self.controller.is_running)
        self.assertFalse(self.controller.is_connected)
        
        # Test configuration
        config = self.controller.current_config
        self.assertIsInstance(config, dict)
        self.assertIn('device_index', config)
        self.assertIn('sample_rate', config)
        self.assertIn('center_frequency', config)
        self.assertIn('gain', config)
        
    def test_controller_start_stop(self):
        """Test controller start/stop operations"""
        import asyncio
        
        async def run_test():
            # Test start
            result = await self.controller.start()
            self.assertTrue(self.controller.is_running)
            self.assertTrue(self.controller.is_connected)
            
            # Test status
            status = await self.controller.get_status()
            self.assertIsInstance(status, dict)
            self.assertTrue(status.get('connected', False))
            
            # Test stop
            await self.controller.stop()
            self.assertFalse(self.controller.is_running)
            
        asyncio.run(run_test())
        
    def test_controller_frequency_tuning(self):
        """Test controller frequency tuning"""
        import asyncio
        
        async def run_test():
            await self.controller.start()
            
            # Test tuning to different frequencies
            for freq in [100e6, 145e6, 435e6]:
                await self.controller.tune(freq)
                
                # Verify frequency was set
                status = await self.controller.get_status()
                actual_freq = status.get('center_frequency', 0)
                self.assertAlmostEqual(actual_freq, freq, delta=1000)
                
            await self.controller.stop()
            
        asyncio.run(run_test())
        
    def test_controller_gain_control(self):
        """Test controller RF gain control"""
        import asyncio
        
        async def run_test():
            await self.controller.start()
            
            # Test different gain values
            test_gains = [10.0, 20.0, 30.0, 40.0, 50.0]
            
            for gain in test_gains:
                await self.controller.tune(gain=gain)
                
                # Verify gain was set
                status = await self.controller.get_status()
                actual_gain = status.get('gain', 0)
                # Allow some tolerance for discrete gain steps
                self.assertAlmostEqual(actual_gain, gain, delta=5.0)
                
            await self.controller.stop()
            
        asyncio.run(run_test())
        
    def test_controller_spectrum_data(self):
        """Test spectrum data acquisition"""
        import asyncio
        
        async def run_test():
            await self.controller.start()
            await self.controller.tune(frequency=100e6, gain=30.0)
            
            # Allow time for data acquisition
            await asyncio.sleep(1.0)
            
            # Get spectrum data
            spectrum_data = await self.controller.get_spectrum_data()
            
            if spectrum_data:
                self.assertIsInstance(spectrum_data, dict)
                self.assertIn('frequencies', spectrum_data)
                self.assertIn('spectrum', spectrum_data)
                self.assertIn('timestamp', spectrum_data)
                
                # Verify data format
                frequencies = spectrum_data['frequencies']
                spectrum = spectrum_data['spectrum']
                
                self.assertIsInstance(frequencies, list)
                self.assertIsInstance(spectrum, list)
                self.assertEqual(len(frequencies), len(spectrum))
                self.assertGreater(len(frequencies), 100)  # Should have FFT bins
                
            await self.controller.stop()
            
        asyncio.run(run_test())


class TestBandPresets(unittest.TestCase):
    """Test predefined band configurations with real hardware"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR library not available")
            
    def test_band_definitions(self):
        """Test that all 16 bands are properly defined"""
        self.assertIsInstance(EXTENDED_RADIO_BANDS, dict)
        self.assertEqual(len(EXTENDED_RADIO_BANDS), 16)
        
        for band_key, band_info in EXTENDED_RADIO_BANDS.items():
            self.assertIsInstance(band_info, dict)
            self.assertIn('name', band_info)
            self.assertIn('center_freq', band_info)
            self.assertIn('bandwidth', band_info)
            self.assertIn('typical_gain', band_info)
            
            # Verify reasonable values
            freq = band_info['center_freq']
            self.assertGreater(freq, 10e6)    # > 10 MHz
            self.assertLess(freq, 2000e6)     # < 2 GHz
            
            bw = band_info['bandwidth']
            self.assertGreater(bw, 1000)      # > 1 kHz
            self.assertLess(bw, 10e6)         # < 10 MHz
            
    def test_band_tuning_hardware(self):
        """Test tuning to each predefined band"""
        import asyncio
        
        async def run_test():
            controller = WebSDRController()
            await controller.start()
            
            # Test first 5 bands (to keep test time reasonable)
            test_bands = list(EXTENDED_RADIO_BANDS.items())[:5]
            
            for band_key, band_info in test_bands:
                freq = band_info['center_freq']
                gain = band_info['typical_gain']
                
                # Tune to band
                await controller.tune(frequency=freq, gain=gain)
                
                # Verify tuning
                status = await controller.get_status()
                actual_freq = status.get('frequency', 0)
                actual_gain = status.get('gain', 0)
                
                self.assertAlmostEqual(actual_freq, freq, delta=1000)
                self.assertAlmostEqual(actual_gain, gain, delta=5.0)
                
                # Brief acquisition test
                await asyncio.sleep(0.5)
                spectrum_data = await controller.get_spectrum_data()
                if spectrum_data:
                    self.assertIsInstance(spectrum_data['frequencies'], list)
                    self.assertIsInstance(spectrum_data['spectrum'], list)
                    
            await controller.stop()
            
        asyncio.run(run_test())
        

def run_hardware_tests():
    """Run all hardware-dependent tests with proper setup"""
    if not RTL_SDR_AVAILABLE:
        print("RTL-SDR library not available. Skipping hardware tests.")
        return False
        
    # Check hardware availability
    try:
        sdr = RtlSdr()
        device_info = str(sdr)
        sdr.close()
        print(f"RTL-SDR detected: {device_info}")
    except Exception as e:
        print(f"RTL-SDR hardware not available: {e}")
        return False
        
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRTLSDRHardware))
    suite.addTests(loader.loadTestsFromTestCase(TestWebSDRController))
    suite.addTests(loader.loadTestsFromTestCase(TestBandPresets))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("H1SDR RTL-SDR Hardware Tests")
    print("=" * 50)
    success = run_hardware_tests()
    exit(0 if success else 1)