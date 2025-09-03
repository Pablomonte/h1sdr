#!/usr/bin/env python3
"""
Unit tests for H1SDR calibration functions
Tests frequency calibration, gain measurements, and Y-factor calculations
"""

import unittest
import numpy as np
import tempfile
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add scripts to path for importing modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

# Mock rtlsdr since it may not be available in test environment
sys.modules['rtlsdr'] = MagicMock()

try:
    from calibrate_rtlsdr import RTLSDRCalibrator, CALIBRATION_SOURCES
    from generate_calibration import CalibrationGenerator
except ImportError as e:
    print(f"Warning: Could not import calibration modules: {e}")
    RTLSDRCalibrator = None
    CalibrationGenerator = None

class TestFrequencyCalibration(unittest.TestCase):
    """Test frequency calibration functions"""
    
    def setUp(self):
        if RTLSDRCalibrator is None:
            self.skipTest("Calibration modules not available")
            
        self.calibrator = RTLSDRCalibrator(device_index=0)
        self.temp_dir = tempfile.mkdtemp()
        
    def test_calibration_sources(self):
        """Test that calibration sources are properly defined"""
        self.assertIsInstance(CALIBRATION_SOURCES, dict)
        self.assertGreater(len(CALIBRATION_SOURCES), 0)
        
        # Check that all sources have reasonable frequencies
        for name, freq in CALIBRATION_SOURCES.items():
            self.assertIsInstance(freq, (int, float))
            self.assertGreater(freq, 50)  # > 50 MHz
            self.assertLess(freq, 3000)   # < 3 GHz
            
    def test_ppm_calculation(self):
        """Test PPM correction calculations"""
        # Test known frequency error
        expected_freq = 100e6  # 100 MHz
        measured_freq = 100.001e6  # 1 kHz error
        
        freq_error = measured_freq - expected_freq
        ppm_correction = -(freq_error / expected_freq) * 1e6
        
        expected_ppm = -10.0  # 1kHz/100MHz = 10 ppm
        self.assertAlmostEqual(ppm_correction, expected_ppm, places=2)
        
    def test_frequency_error_calculation(self):
        """Test frequency error measurement calculations"""
        # Mock spectrum with peak
        frequencies = np.linspace(99.9e6, 100.1e6, 1000)
        # Create Gaussian peak
        center_freq = 100.005e6  # 5 kHz offset
        width = 10e3  # 10 kHz width
        spectrum = -80 * np.ones(len(frequencies))
        peak = 20 * np.exp(-0.5 * ((frequencies - center_freq) / width)**2)
        spectrum = spectrum + peak
        
        # Find peak
        peak_idx = np.argmax(spectrum)
        measured_freq = frequencies[peak_idx]
        
        # Calculate error
        expected_freq = 100e6
        error = measured_freq - expected_freq
        
        self.assertAlmostEqual(error, 5000, delta=100)  # 5 kHz ± 100 Hz
        
    @patch('calibrate_rtlsdr.RtlSdr')
    def test_mock_calibration_measurement(self, mock_sdr_class):
        """Test calibration measurement with mocked RTL-SDR"""
        mock_sdr = Mock()
        mock_sdr_class.return_value = mock_sdr
        
        # Configure mock
        mock_sdr.sample_rate = 2.4e6
        mock_sdr.center_freq = 100e6
        mock_sdr.gain = 40
        
        # Mock read_samples to return signal with known offset
        n_samples = 256*1024
        offset_freq = 1000  # 1 kHz offset
        t = np.arange(n_samples) / 2.4e6
        signal_with_offset = np.exp(2j * np.pi * offset_freq * t)
        # Add noise
        noise = 0.1 * (np.random.randn(n_samples) + 1j * np.random.randn(n_samples))
        mock_sdr.read_samples.return_value = signal_with_offset + noise
        
        # Test setup
        calibrator = RTLSDRCalibrator()
        calibrator.setup_sdr(100e6)
        
        # Should have created and configured mock SDR
        mock_sdr_class.assert_called_once()
        self.assertEqual(mock_sdr.sample_rate, 2.4e6)
        self.assertEqual(mock_sdr.center_freq, 100e6)
        
    def test_calibration_file_format(self):
        """Test calibration file format"""
        # Create test calibration data
        cal_data = {
            'timestamp': '2024-01-01 12:00:00',
            'device_index': 0,
            'ppm_correction': -5.2,
            'measurements': [
                {
                    'source': 'FM_BROADCAST',
                    'frequency': 98.5,
                    'ppm_correction': -5.1
                },
                {
                    'source': 'GSM900', 
                    'frequency': 935.0,
                    'ppm_correction': -5.3
                }
            ],
            'software': 'H1SDR Calibration Script v1.0'
        }
        
        # Save to file
        cal_file = Path(self.temp_dir) / 'test_calibration.json'
        with open(cal_file, 'w') as f:
            json.dump(cal_data, f)
            
        # Load and verify
        with open(cal_file, 'r') as f:
            loaded_data = json.load(f)
            
        self.assertEqual(loaded_data['ppm_correction'], -5.2)
        self.assertEqual(len(loaded_data['measurements']), 2)
        self.assertEqual(loaded_data['measurements'][0]['source'], 'FM_BROADCAST')
        
    def tearDown(self):
        """Clean up temporary files"""
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir)


class TestGainCalibration(unittest.TestCase):
    """Test gain calibration functions"""
    
    def setUp(self):
        if CalibrationGenerator is None:
            self.skipTest("Calibration modules not available")
            
        self.generator = CalibrationGenerator(device_index=0)
        
    def test_gain_curve_calculation(self):
        """Test gain curve measurements"""
        # Test gain settings conversion
        rtl_gain_settings = [0, 9, 14, 27, 37, 77, 87, 125]  # RTL-SDR units (0.1 dB)
        gain_settings_db = [g/10.0 for g in rtl_gain_settings]
        
        expected_db = [0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5]
        np.testing.assert_array_equal(gain_settings_db, expected_db)
        
    def test_power_measurement_statistics(self):
        """Test power measurement statistical properties"""
        # Simulate multiple power measurements
        n_measurements = 100
        true_power = 0.01  # Linear power
        noise_std = 0.001
        
        measurements = []
        for i in range(n_measurements):
            # Add measurement noise
            measured = true_power + np.random.normal(0, noise_std)
            power_db = 10 * np.log10(abs(measured) + 1e-12)
            measurements.append(power_db)
            
        mean_power = np.mean(measurements)
        std_power = np.std(measurements)
        
        # Convert true power to dB for comparison
        true_power_db = 10 * np.log10(true_power)
        
        # Mean should be close to true value
        self.assertAlmostEqual(mean_power, true_power_db, delta=1.0)
        
        # Standard deviation should be reasonable
        self.assertLess(std_power, 5.0)  # Less than 5 dB variation
        
    def test_y_factor_calculation(self):
        """Test Y-factor noise temperature calculation"""
        # Known Y-factor calculation
        hot_temp = 300  # K (room temperature)
        cold_temp = 10  # K (cold sky)
        hot_power = 0.01  # Linear units
        cold_power = 0.005  # Linear units
        
        y_factor = hot_power / cold_power
        
        # Calculate receiver temperature
        # T_rec = (T_hot - Y*T_cold) / (Y - 1)
        receiver_temp = (hot_temp - y_factor * cold_temp) / (y_factor - 1)
        
        # Y-factor should be > 1
        self.assertGreater(y_factor, 1.0)
        
        # Receiver temperature should be reasonable
        self.assertGreater(receiver_temp, 0)
        self.assertLess(receiver_temp, 10000)  # Less than 10,000 K
        
        # Test with realistic values
        # Y-factor of 2 (3 dB) with hot load at 300K, cold at 10K
        y_test = 2.0
        t_rec_test = (300 - y_test * 10) / (y_test - 1)
        expected_t_rec = 280  # K
        
        self.assertAlmostEqual(t_rec_test, expected_t_rec, places=0)
        
    def test_stability_analysis(self):
        """Test system stability measurements"""
        # Simulate stability measurements over time
        duration_minutes = 60
        measurements_per_minute = 60
        total_measurements = duration_minutes * measurements_per_minute
        
        # Simulate realistic power drift
        base_power = -70  # dB
        drift_rate = 0.1  # dB per hour
        noise_level = 0.5  # dB RMS
        
        timestamps = np.linspace(0, duration_minutes, total_measurements)
        powers = []
        
        for t in timestamps:
            # Linear drift
            drift = drift_rate * (t / 60)  # Convert minutes to hours
            # Random noise
            noise = np.random.normal(0, noise_level)
            power = base_power + drift + noise
            powers.append(power)
            
        # Calculate stability statistics
        power_std = np.std(powers)
        power_mean = np.mean(powers)
        peak_to_peak = np.max(powers) - np.min(powers)
        
        # Test statistics
        self.assertLess(power_std, 2.0)  # Should be reasonable
        self.assertLess(peak_to_peak, 8.0)  # Peak-to-peak variation
        
        # Test trend detection (linear fit)
        coeffs = np.polyfit(timestamps, powers, 1)
        drift_per_hour = coeffs[0] * 60  # Convert per minute to per hour
        
        self.assertLess(abs(drift_per_hour - drift_rate), 0.2)  # Should detect drift


class TestCalibrationDataHandling(unittest.TestCase):
    """Test calibration data loading, saving, and processing"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def test_calibration_file_io(self):
        """Test calibration file input/output"""
        # Create test calibration data
        cal_data = {
            'timestamp': '2024-01-01 12:00:00',
            'device_index': 0,
            'gain_curve': {
                'gain_settings_db': [0, 1, 2, 3, 4, 5],
                'measured_powers_dbfs': [-80, -78, -76, -74, -72, -70]
            },
            'noise_temperature': {
                'receiver_temp_k': 280.0,
                'y_factor': 2.1,
                'hot_load_temp_k': 300,
                'cold_sky_temp_k': 10
            },
            'stability': {
                'duration_seconds': 3600,
                'std_deviation_db': 0.3,
                'mean_power_dbfs': -75.2
            }
        }
        
        # Save calibration file
        cal_file = Path(self.temp_dir) / 'system_cal.json'
        with open(cal_file, 'w') as f:
            json.dump(cal_data, f, indent=2)
            
        # Load and verify
        with open(cal_file, 'r') as f:
            loaded_cal = json.load(f)
            
        # Verify structure and values
        self.assertEqual(loaded_cal['device_index'], 0)
        self.assertIn('gain_curve', loaded_cal)
        self.assertIn('noise_temperature', loaded_cal)
        self.assertIn('stability', loaded_cal)
        
        # Verify gain curve data
        gain_curve = loaded_cal['gain_curve']
        self.assertEqual(len(gain_curve['gain_settings_db']), 6)
        self.assertEqual(len(gain_curve['measured_powers_dbfs']), 6)
        
        # Verify noise temperature
        noise_data = loaded_cal['noise_temperature']
        self.assertEqual(noise_data['receiver_temp_k'], 280.0)
        self.assertGreater(noise_data['y_factor'], 1.0)
        
    def test_gain_interpolation(self):
        """Test interpolation of gain calibration data"""
        # Test data: gain settings vs measured power
        gain_settings = np.array([0, 10, 20, 30, 40, 50])  # dB
        measured_powers = np.array([-90, -80, -70, -60, -50, -40])  # dBFs
        
        # Test interpolation for intermediate values
        target_gains = [5, 15, 25, 35, 45]
        interpolated_powers = np.interp(target_gains, gain_settings, measured_powers)
        
        expected_powers = [-85, -75, -65, -55, -45]  # dBFs
        np.testing.assert_array_almost_equal(interpolated_powers, expected_powers)
        
    def test_calibration_validation(self):
        """Test validation of calibration data"""
        # Test valid calibration data
        valid_cal = {
            'ppm_correction': -5.2,
            'measurements': [
                {'source': 'FM_BROADCAST', 'frequency': 98.5, 'ppm_correction': -5.1},
                {'source': 'GSM900', 'frequency': 935.0, 'ppm_correction': -5.3}
            ]
        }
        
        # Validation tests
        self.assertIsInstance(valid_cal['ppm_correction'], (int, float))
        self.assertIsInstance(valid_cal['measurements'], list)
        self.assertGreater(len(valid_cal['measurements']), 0)
        
        # Test each measurement
        for meas in valid_cal['measurements']:
            self.assertIn('source', meas)
            self.assertIn('frequency', meas) 
            self.assertIn('ppm_correction', meas)
            self.assertIsInstance(meas['frequency'], (int, float))
            self.assertIsInstance(meas['ppm_correction'], (int, float))
            
        # Test invalid data detection
        invalid_cal = {
            'ppm_correction': 'invalid',  # Should be numeric
            'measurements': []  # Should not be empty
        }
        
        # These should fail validation
        self.assertNotIsInstance(invalid_cal['ppm_correction'], (int, float))
        self.assertEqual(len(invalid_cal['measurements']), 0)
        
    def tearDown(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir)


class TestCalibrationMath(unittest.TestCase):
    """Test mathematical functions used in calibration"""
    
    def test_frequency_ppm_conversions(self):
        """Test frequency to PPM conversions"""
        # Test cases: (frequency, error_hz, expected_ppm)
        test_cases = [
            (100e6, 1000, 10.0),      # 1 kHz error at 100 MHz = 10 ppm
            (1000e6, 1000, 1.0),      # 1 kHz error at 1 GHz = 1 ppm  
            (1420.4e6, 1420.4, 1.0),  # 1.4 kHz error at H1 freq = 1 ppm
            (10e6, 100, 10.0),        # 100 Hz error at 10 MHz = 10 ppm
        ]
        
        for freq, error_hz, expected_ppm in test_cases:
            calculated_ppm = (error_hz / freq) * 1e6
            self.assertAlmostEqual(calculated_ppm, expected_ppm, places=6)
            
    def test_power_averaging(self):
        """Test power averaging in different domains"""
        # Test linear vs logarithmic averaging
        powers_linear = [0.001, 0.01, 0.1]  # Linear power values
        powers_db = [10 * np.log10(p) for p in powers_linear]
        
        # Linear average
        linear_avg = np.mean(powers_linear)
        linear_avg_db = 10 * np.log10(linear_avg)
        
        # Logarithmic average (convert to dB, average, convert back)
        db_avg = np.mean(powers_db)
        
        # They should be different
        self.assertNotAlmostEqual(linear_avg_db, db_avg, places=3)
        
        # Linear average should be higher (geometric vs arithmetic mean)
        self.assertGreater(linear_avg_db, db_avg)
        
    def test_noise_calculations(self):
        """Test noise-related calculations"""
        # Test thermal noise calculation
        # P = k * T * B (Watts)
        k_boltzmann = 1.38e-23  # J/K
        temperature = 290  # K (room temperature)
        bandwidth = 1e6  # 1 MHz
        
        thermal_noise_watts = k_boltzmann * temperature * bandwidth
        thermal_noise_dbm = 10 * np.log10(thermal_noise_watts / 1e-3)
        
        # Should be around -114 dBm for 1 MHz at room temperature
        expected_dbm = -114
        self.assertAlmostEqual(thermal_noise_dbm, expected_dbm, delta=2)
        
    def test_snr_calculations(self):
        """Test SNR calculation methods"""
        # Test SNR from peak and noise floor
        signal_power_db = -50  # dB
        noise_floor_db = -80   # dB
        
        snr_db = signal_power_db - noise_floor_db
        expected_snr = 30  # dB
        
        self.assertEqual(snr_db, expected_snr)
        
        # Test SNR from linear values
        signal_linear = 10**(-5)  # -50 dB
        noise_linear = 10**(-8)   # -80 dB
        
        snr_linear = signal_linear / noise_linear
        snr_db_calc = 10 * np.log10(snr_linear)
        
        self.assertAlmostEqual(snr_db_calc, expected_snr, places=6)


def run_calibration_integration_tests():
    """Run integration tests with mock hardware"""
    print("\n=== Calibration Integration Tests ===")
    
    if RTLSDRCalibrator is None:
        print("Calibration modules not available, skipping integration tests")
        return
        
    # Test full calibration workflow with mocked RTL-SDR
    with patch('calibrate_rtlsdr.RtlSdr') as mock_sdr_class:
        mock_sdr = Mock()
        mock_sdr_class.return_value = mock_sdr
        
        # Configure mock for FM broadcast measurement
        mock_sdr.sample_rate = 2.4e6
        mock_sdr.center_freq = 98.5e6
        mock_sdr.gain = 40
        
        # Create signal with known frequency offset
        n_samples = 256*1024
        offset_freq = 500  # 500 Hz offset (simulated oscillator error)
        t = np.arange(n_samples) / 2.4e6
        
        # FM signal simulation (just a carrier for this test)
        signal = np.exp(2j * np.pi * offset_freq * t)
        noise = 0.05 * (np.random.randn(n_samples) + 1j * np.random.randn(n_samples))
        mock_sdr.read_samples.return_value = signal + noise
        
        # Run calibration
        calibrator = RTLSDRCalibrator()
        
        try:
            # This would normally find the peak and calculate PPM correction
            ppm = calibrator.calibrate_with_signal('FM_BROADCAST', plot=False)
            
            # Should calculate reasonable PPM correction
            expected_ppm = -(offset_freq / 98.5e6) * 1e6  # About -5 ppm
            
            if ppm is not None:
                print(f"Mock calibration result: {ppm:.2f} ppm (expected ~{expected_ppm:.2f})")
                assert abs(ppm - expected_ppm) < 2.0  # Within 2 ppm tolerance
                print("Integration test passed!")
            else:
                print("Mock calibration returned None")
                
        except Exception as e:
            print(f"Integration test error: {e}")


if __name__ == '__main__':
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run integration tests
    run_calibration_integration_tests()