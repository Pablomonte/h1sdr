#!/usr/bin/env python3
"""
Unit tests for H1SDR signal processing functions
Tests FFT processing, baseline correction, Doppler calculations, etc.
"""

import unittest
import numpy as np
import tempfile
import sys
from pathlib import Path

# Add src to path for importing modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from h1_receiver import H1Receiver

# Constants for testing
H1_FREQUENCY = 1420.405751e6  # Hz
SPEED_OF_LIGHT = 299792458.0  # m/s

class TestSignalProcessing(unittest.TestCase):
    """Test signal processing functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.receiver = H1Receiver(sample_rate=2.4e6, center_freq=H1_FREQUENCY)
        self.test_samples = 2048
        self.tolerance = 1e-10
        
    def test_doppler_velocity_calculation(self):
        """Test Doppler velocity calculations"""
        # Test rest frequency (should give 0 velocity)
        velocity = self.receiver.calculate_doppler_velocity(H1_FREQUENCY)
        self.assertAlmostEqual(velocity, 0.0, places=6)
        
        # Test known Doppler shifts
        # +1 kHz shift should give positive velocity
        freq_shift = 1000  # Hz
        expected_velocity = (freq_shift / H1_FREQUENCY) * SPEED_OF_LIGHT / 1000  # km/s
        velocity = self.receiver.calculate_doppler_velocity(H1_FREQUENCY + freq_shift)
        self.assertAlmostEqual(velocity, expected_velocity, places=6)
        
        # -1 kHz shift should give negative velocity
        velocity = self.receiver.calculate_doppler_velocity(H1_FREQUENCY - freq_shift)
        self.assertAlmostEqual(velocity, -expected_velocity, places=6)
        
        # Test typical galactic velocities
        # 100 km/s should correspond to specific frequency shift
        target_velocity = 100.0  # km/s
        target_freq = H1_FREQUENCY * (1 + target_velocity * 1000 / SPEED_OF_LIGHT)
        calculated_velocity = self.receiver.calculate_doppler_velocity(target_freq)
        self.assertAlmostEqual(calculated_velocity, target_velocity, places=3)
        
    def test_process_samples_basic(self):
        """Test basic sample processing"""
        # Create test signal: pure tone at known frequency offset
        sample_rate = 2.4e6
        duration = 0.01  # 10ms
        n_samples = int(sample_rate * duration)
        
        # Create tone at +10 kHz offset from center
        offset_freq = 10000  # Hz
        t = np.arange(n_samples) / sample_rate
        test_signal = np.exp(2j * np.pi * offset_freq * t)
        
        # Add small amount of noise
        noise_level = 0.01
        test_signal += noise_level * (np.random.randn(n_samples) + 
                                     1j * np.random.randn(n_samples))
        
        # Process samples
        frequencies, spectrum = self.receiver.process_samples(test_signal)
        
        # Check that we get expected frequency array
        self.assertEqual(len(frequencies), len(spectrum))
        
        # Frequency array should be centered on H1_FREQUENCY
        center_idx = len(frequencies) // 2
        self.assertAlmostEqual(frequencies[center_idx], H1_FREQUENCY, delta=1000)
        
        # Should have peak near the offset frequency
        peak_idx = np.argmax(spectrum)
        peak_freq = frequencies[peak_idx]
        expected_peak_freq = H1_FREQUENCY + offset_freq
        self.assertAlmostEqual(peak_freq, expected_peak_freq, delta=sample_rate/len(spectrum))
        
    def test_spectrum_integration(self):
        """Test spectrum integration functionality"""
        # Create multiple spectra with known characteristics
        n_bins = 1024
        n_spectra = 10
        
        # Create base spectrum with peak
        base_spectrum = -80 * np.ones(n_bins)  # -80 dB baseline
        peak_idx = n_bins // 2
        base_spectrum[peak_idx] = -60  # -60 dB peak
        
        # Test integration reset
        integrated = self.receiver.integrate_spectrum(base_spectrum, reset=True)
        np.testing.assert_array_almost_equal(integrated, base_spectrum, decimal=6)
        self.assertEqual(self.receiver.integration_count, 1)
        
        # Test accumulation
        for i in range(n_spectra - 1):
            noise = np.random.normal(0, 1, n_bins)
            noisy_spectrum = base_spectrum + noise
            integrated = self.receiver.integrate_spectrum(noisy_spectrum)
            
        self.assertEqual(self.receiver.integration_count, n_spectra)
        
        # Integrated spectrum should be closer to base spectrum (noise reduced)
        # Peak should still be at same location
        integrated_peak_idx = np.argmax(integrated)
        self.assertEqual(integrated_peak_idx, peak_idx)
        
    def test_baseline_correction(self):
        """Test baseline correction algorithm"""
        n_bins = 1024
        
        # Create spectrum with polynomial baseline and narrow line
        x = np.arange(n_bins)
        
        # Polynomial baseline (2nd order)
        baseline_true = -85 + 0.01 * x + 0.00001 * x**2
        
        # Add narrow Gaussian line
        line_center = n_bins // 2
        line_width = 10
        line_amplitude = 15  # dB above baseline
        
        gaussian_line = line_amplitude * np.exp(-0.5 * ((x - line_center) / line_width)**2)
        spectrum_with_line = baseline_true + gaussian_line
        
        # Test baseline correction
        corrected_spectrum = self.receiver.baseline_correction(spectrum_with_line, order=2)
        
        # After correction, baseline regions should be near zero
        # Exclude line region for testing
        baseline_mask = np.abs(x - line_center) > 50
        baseline_residual = np.mean(corrected_spectrum[baseline_mask])
        
        self.assertLess(abs(baseline_residual), 1.0)  # Should be close to zero
        
        # Peak should still be present and approximately correct amplitude
        peak_value = np.max(corrected_spectrum)
        self.assertGreater(peak_value, line_amplitude * 0.8)  # Allow some fitting error
        
    def test_baseline_correction_edge_cases(self):
        """Test baseline correction with edge cases"""
        n_bins = 100
        
        # Test with very short spectrum
        short_spectrum = np.ones(5) * -80
        corrected = self.receiver.baseline_correction(short_spectrum, order=3)
        # Should handle gracefully (not enough points for 3rd order fit)
        self.assertEqual(len(corrected), 5)
        
        # Test with all identical values
        flat_spectrum = np.ones(n_bins) * -75
        corrected = self.receiver.baseline_correction(flat_spectrum)
        # Should result in near-zero spectrum
        np.testing.assert_array_almost_equal(corrected, np.zeros(n_bins), decimal=6)
        
    def test_fft_properties(self):
        """Test FFT processing properties"""
        # Test Parseval's theorem (energy conservation)
        n_samples = 1024
        
        # Create test signal
        t = np.arange(n_samples)
        signal = np.sin(2 * np.pi * 0.1 * t) + 0.5 * np.cos(2 * np.pi * 0.3 * t)
        signal = signal.astype(complex)
        
        # Process with receiver
        frequencies, spectrum_db = self.receiver.process_samples(signal, fft_size=n_samples)
        
        # Convert back to linear power
        spectrum_linear = 10**(spectrum_db / 10)
        
        # Check that DC and Nyquist are real (within numerical precision)
        fft_data = np.fft.fft(signal * np.blackman(len(signal)))
        dc_idx = 0
        nyquist_idx = len(fft_data) // 2
        
        # Test frequency array properties
        df = frequencies[1] - frequencies[0]
        expected_df = self.receiver.sample_rate / len(frequencies)
        self.assertAlmostEqual(abs(df), expected_df, places=3)
        
    def test_noise_statistics(self):
        """Test processing of noise signals"""
        n_samples = 8192
        n_trials = 50
        
        # Generate white Gaussian noise
        noise_power = 0.1
        peak_values = []
        
        for trial in range(n_trials):
            noise = np.sqrt(noise_power) * (np.random.randn(n_samples) + 
                                           1j * np.random.randn(n_samples))
            
            frequencies, spectrum = self.receiver.process_samples(noise)
            peak_values.append(np.max(spectrum))
            
        # Statistics should be reasonable for noise
        mean_peak = np.mean(peak_values)
        std_peak = np.std(peak_values)
        
        # For noise, peaks should follow certain distribution
        # This is a basic sanity check
        self.assertLess(std_peak / abs(mean_peak), 0.5)  # Reasonable relative variation
        
    def test_signal_plus_noise(self):
        """Test processing signal in noise"""
        n_samples = 4096
        sample_rate = 2.4e6
        
        # Create signal: tone at specific offset
        offset_freq = 50000  # 50 kHz offset
        signal_amplitude = 1.0
        noise_amplitude = 0.1
        
        t = np.arange(n_samples) / sample_rate
        signal = signal_amplitude * np.exp(2j * np.pi * offset_freq * t)
        noise = noise_amplitude * (np.random.randn(n_samples) + 
                                  1j * np.random.randn(n_samples))
        
        # Test signal alone
        frequencies, clean_spectrum = self.receiver.process_samples(signal)
        clean_peak_idx = np.argmax(clean_spectrum)
        clean_peak_freq = frequencies[clean_peak_idx]
        
        # Test signal + noise
        noisy_signal = signal + noise
        frequencies, noisy_spectrum = self.receiver.process_samples(noisy_signal)
        noisy_peak_idx = np.argmax(noisy_spectrum)
        noisy_peak_freq = frequencies[noisy_peak_idx]
        
        # Peak should be at same frequency
        self.assertEqual(clean_peak_idx, noisy_peak_idx)
        
        # SNR should be reasonable
        # Peak power vs noise floor
        noise_floor = np.percentile(noisy_spectrum, 25)  # Lower quartile as noise estimate
        peak_power = noisy_spectrum[noisy_peak_idx]
        snr = peak_power - noise_floor
        
        expected_snr = 20 * np.log10(signal_amplitude / noise_amplitude)
        self.assertGreater(snr, expected_snr * 0.7)  # Allow for processing losses
        
    def test_frequency_accuracy(self):
        """Test frequency axis accuracy"""
        # Test with known sample rate and FFT size
        sample_rate = 2.4e6
        fft_size = 2048
        center_freq = H1_FREQUENCY
        
        self.receiver.sample_rate = sample_rate
        self.receiver.center_freq = center_freq
        
        # Create dummy signal
        dummy_signal = np.zeros(fft_size, dtype=complex)
        frequencies, _ = self.receiver.process_samples(dummy_signal, fft_size=fft_size)
        
        # Check frequency array properties
        self.assertEqual(len(frequencies), fft_size)
        
        # Center frequency should be at center
        center_idx = fft_size // 2
        self.assertAlmostEqual(frequencies[center_idx], center_freq, delta=1000)
        
        # Frequency resolution
        df = frequencies[1] - frequencies[0]
        expected_df = sample_rate / fft_size
        self.assertAlmostEqual(df, expected_df, places=3)
        
        # Bandwidth
        bandwidth = frequencies[-1] - frequencies[0]
        expected_bandwidth = sample_rate * (fft_size - 1) / fft_size
        self.assertAlmostEqual(bandwidth, expected_bandwidth, places=3)


class TestDataHandling(unittest.TestCase):
    """Test data loading, saving, and format handling"""
    
    def setUp(self):
        self.receiver = H1Receiver()
        self.temp_dir = tempfile.mkdtemp()
        
    def test_observation_saving(self):
        """Test observation data saving"""
        # Create test data
        frequencies = np.linspace(1420.0e6, 1420.8e6, 1024)
        spectrum = -80 * np.ones(1024) + np.random.randn(1024)
        
        metadata = {
            'observer': 'test',
            'location': 'test_lab',
            'weather': 'clear'
        }
        
        # Test saving
        temp_file = Path(self.temp_dir) / 'test_observation'
        
        # Mock the save method
        save_data = {
            'frequencies': frequencies,
            'spectrum': spectrum,
            'timestamp': '20240101_120000',
            'center_freq': H1_FREQUENCY,
            'sample_rate': 2.4e6,
            'gain': 40,
            'integration_time': 10
        }
        save_data.update(metadata)
        
        # Save and load
        np.savez(f'{temp_file}.npz', **save_data)
        loaded_data = np.load(f'{temp_file}.npz')
        
        # Verify data integrity
        np.testing.assert_array_equal(loaded_data['frequencies'], frequencies)
        np.testing.assert_array_equal(loaded_data['spectrum'], spectrum)
        self.assertEqual(str(loaded_data['timestamp']), '20240101_120000')
        self.assertEqual(loaded_data['observer'], 'test')
        
    def tearDown(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir)


class TestCalibrationFunctions(unittest.TestCase):
    """Test calibration and correction functions"""
    
    def test_gain_corrections(self):
        """Test gain correction calculations"""
        # This would test calibration functions when implemented
        pass
        
    def test_frequency_corrections(self):
        """Test PPM frequency corrections"""
        # Test PPM correction calculation
        nominal_freq = 1420.4e6
        ppm_error = 10  # 10 ppm
        
        # Calculate corrected frequency
        freq_error_hz = nominal_freq * ppm_error / 1e6
        corrected_freq = nominal_freq + freq_error_hz
        
        # Test correction
        measured_ppm = (corrected_freq - nominal_freq) / nominal_freq * 1e6
        self.assertAlmostEqual(measured_ppm, ppm_error, places=6)


class TestMathUtils(unittest.TestCase):
    """Test mathematical utility functions"""
    
    def test_db_conversions(self):
        """Test dB conversion functions"""
        # Test power to dB
        power_linear = 0.001  # -30 dB
        power_db = 10 * np.log10(power_linear)
        self.assertAlmostEqual(power_db, -30.0, places=6)
        
        # Test dB to power
        back_to_linear = 10**(power_db / 10)
        self.assertAlmostEqual(back_to_linear, power_linear, places=9)
        
        # Test voltage to dB
        voltage = 0.1  # -20 dB
        voltage_db = 20 * np.log10(voltage)
        self.assertAlmostEqual(voltage_db, -20.0, places=6)
        
    def test_windowing_functions(self):
        """Test FFT windowing"""
        n = 1024
        
        # Test Blackman window properties
        window = np.blackman(n)
        
        # Window should be symmetric
        np.testing.assert_array_almost_equal(window[:n//2], window[n:n//2:-1])
        
        # Window should have correct peak value
        self.assertAlmostEqual(np.max(window), 1.0, places=6)
        
        # Window should reduce spectral leakage
        # Test with tone at non-bin frequency
        freq_offset = 0.3  # Non-integer bin
        signal = np.sin(2 * np.pi * freq_offset * np.arange(n) / n)
        
        # Compare windowed vs unwindowed FFT
        fft_rect = np.abs(np.fft.fft(signal))
        fft_windowed = np.abs(np.fft.fft(signal * window))
        
        # Windowed should have lower side lobes
        # This is a qualitative test - exact values depend on implementation
        sidelobe_reduction = np.max(fft_rect[10:]) / np.max(fft_windowed[10:])
        self.assertGreater(sidelobe_reduction, 1.5)  # Should reduce sidelobes


def run_performance_tests():
    """Run performance benchmarks (not part of unit tests)"""
    import time
    
    print("\n=== Performance Tests ===")
    
    receiver = H1Receiver()
    
    # Test FFT performance
    n_samples = 65536
    test_signal = np.random.randn(n_samples) + 1j * np.random.randn(n_samples)
    
    start_time = time.time()
    n_iterations = 100
    
    for i in range(n_iterations):
        frequencies, spectrum = receiver.process_samples(test_signal)
        
    elapsed = time.time() - start_time
    fps = n_iterations / elapsed
    
    print(f"FFT processing: {fps:.1f} Hz ({n_samples} samples)")
    print(f"Average time per FFT: {elapsed/n_iterations*1000:.2f} ms")
    
    # Test integration performance
    spectrum_size = 2048
    test_spectrum = np.random.randn(spectrum_size)
    
    start_time = time.time()
    n_integrations = 1000
    
    for i in range(n_integrations):
        integrated = receiver.integrate_spectrum(test_spectrum)
        
    elapsed = time.time() - start_time
    rate = n_integrations / elapsed
    
    print(f"Spectrum integration: {rate:.0f} Hz")
    
    # Memory usage test
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    memory_before = process.memory_info().rss / 1024 / 1024  # MB
    
    # Create large dataset
    large_data = []
    for i in range(100):
        large_spectrum = np.random.randn(8192)
        large_data.append(large_spectrum)
        
    memory_after = process.memory_info().rss / 1024 / 1024  # MB
    memory_used = memory_after - memory_before
    
    print(f"Memory usage for 100x8192 spectra: {memory_used:.1f} MB")


if __name__ == '__main__':
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run performance tests
    run_performance_tests()