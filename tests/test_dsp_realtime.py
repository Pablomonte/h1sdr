#!/usr/bin/env python3
"""
DSP tests with real RTL-SDR signals
Tests spectrum processing, demodulation, and signal analysis with live signals
"""

import unittest
import numpy as np
import time
import asyncio
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
from web_sdr.dsp.spectrum_processor import SpectrumProcessor
from web_sdr.dsp.demodulators import AudioDemodulators
from web_sdr.config import config, EXTENDED_RADIO_BANDS, DEMOD_MODES

class TestSpectrumProcessing(unittest.TestCase):
    """Test spectrum processing with real RTL-SDR signals"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
        # Check hardware
        try:
            sdr = RtlSdr()
            sdr.close()
        except Exception:
            raise unittest.SkipTest("RTL-SDR hardware not detected")
            
    def setUp(self):
        """Set up spectrum processor and RTL-SDR"""
        self.sample_rate = 2.4e6
        self.fft_size = 4096
        self.processor = SpectrumProcessor(
            fft_size=self.fft_size,
            sample_rate=self.sample_rate
        )
        self.sdr = None
        
    def tearDown(self):
        """Clean up RTL-SDR"""
        if self.sdr:
            self.sdr.close()
            
    def test_fft_with_fm_broadcast(self):
        """Test FFT processing with FM broadcast signals"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = 100e6  # FM broadcast
        self.sdr.gain = 30.0
        
        # Acquire samples
        samples = self.sdr.read_samples(self.fft_size * 4)
        
        # Process spectrum
        frequencies, spectrum = self.processor.process_samples(samples)
        
        # Verify output format
        self.assertEqual(len(frequencies), self.fft_size)
        self.assertEqual(len(spectrum), self.fft_size)
        
        # Verify frequency range
        expected_span = self.sample_rate
        actual_span = frequencies[-1] - frequencies[0]
        self.assertAlmostEqual(actual_span, expected_span, delta=1000)
        
        # Verify center frequency
        center_idx = len(frequencies) // 2
        expected_center = 100e6
        actual_center = frequencies[center_idx]
        self.assertAlmostEqual(actual_center, expected_center, delta=1000)
        
        # Verify spectrum values are reasonable (dB scale)
        self.assertTrue(np.all(np.isfinite(spectrum)))  # Should be finite values
        self.assertTrue(np.all(spectrum > -200))  # Should not be extremely low
        self.assertTrue(np.all(spectrum < 200))   # Should not be extremely high
        
        # Should detect FM broadcast signals (higher power)
        max_power = np.max(spectrum)
        self.assertGreater(max_power, -60)  # Strong FM signals
        
    def test_fft_resolution_and_binning(self):
        """Test FFT frequency resolution and bin accuracy"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = 145e6  # 2m amateur band
        self.sdr.gain = 40.0
        
        samples = self.sdr.read_samples(self.fft_size * 2)
        frequencies, spectrum = self.processor.process_samples(samples)
        
        # Verify frequency resolution
        expected_resolution = self.sample_rate / self.fft_size
        actual_resolution = frequencies[1] - frequencies[0]
        self.assertAlmostEqual(actual_resolution, expected_resolution, delta=1)
        
        # Test bin indexing
        for i in range(0, len(frequencies), 100):
            expected_freq = frequencies[0] + i * expected_resolution
            actual_freq = frequencies[i]
            self.assertAlmostEqual(actual_freq, expected_freq, delta=1)
            
    def test_spectrum_stability_over_time(self):
        """Test spectrum stability with continuous acquisition"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = 435e6  # 70cm amateur
        self.sdr.gain = 35.0
        
        spectra = []
        n_acquisitions = 5
        
        for i in range(n_acquisitions):
            samples = self.sdr.read_samples(self.fft_size * 2)
            frequencies, spectrum = self.processor.process_samples(samples)
            spectra.append(spectrum)
            time.sleep(0.2)
            
        # Calculate stability metrics
        spectra_array = np.array(spectra)
        mean_spectrum = np.mean(spectra_array, axis=0)
        std_spectrum = np.std(spectra_array, axis=0)
        
        # Coefficient of variation should be reasonable
        cv = np.abs(std_spectrum / mean_spectrum)
        median_cv = np.median(cv)
        
        self.assertLess(median_cv, 0.5, "Spectrum too unstable over time")
        
    def test_windowing_effects(self):
        """Test different windowing functions"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = 433.92e6  # ISM band
        self.sdr.gain = 30.0
        
        samples = self.sdr.read_samples(self.fft_size * 4)
        
        # Test different windows
        window_types = ['hann', 'hamming', 'blackman', 'rectangular']
        spectra = {}
        
        for window_type in window_types:
            processor = SpectrumProcessor(
                fft_size=self.fft_size,
                sample_rate=self.sample_rate,
                window_type=window_type
            )
            processor.update_config(center_frequency=433.92e6)
            frequencies, spectrum = processor.process_samples(samples)
            spectra[window_type] = spectrum
            
        # Different windows should give different results
        hann = spectra['hann']
        rectangular = spectra['rectangular']
        
        # Should not be identical - windowing effects may be subtle with real signals
        diff = np.mean(np.abs(hann - rectangular))
        self.assertGreater(diff, 0.001, "Windowing should affect spectrum")
        
        # Also check maximum difference for more sensitivity
        max_diff = np.max(np.abs(hann - rectangular))
        self.assertGreater(max_diff, 0.01, "Windowing should show some spectral differences")
        
    def test_spectrum_peak_detection(self):
        """Test peak detection in spectrum with real signals"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = 108e6  # Upper FM broadcast
        self.sdr.gain = 25.0
        
        samples = self.sdr.read_samples(self.fft_size * 8)
        
        # Update processor center frequency to match SDR
        self.processor.update_config(center_frequency=108e6)
        frequencies, spectrum = self.processor.process_samples(samples)
        
        # Find peaks above noise floor
        noise_floor = np.percentile(spectrum, 10)  # Bottom 10% as noise
        peak_threshold = noise_floor + 10  # 10 dB above noise
        
        peaks = []
        for i in range(1, len(spectrum)-1):
            if (spectrum[i] > peak_threshold and 
                spectrum[i] > spectrum[i-1] and 
                spectrum[i] > spectrum[i+1]):
                peaks.append((frequencies[i], spectrum[i]))
                
        # Should find at least some peaks in FM broadcast band
        self.assertGreater(len(peaks), 0, "Should detect some signal peaks")
        
        # Peaks should be within the spectrum range (center_freq ± sample_rate/2)
        for freq, power in peaks:
            self.assertGreater(freq, 108e6 - self.sample_rate/2)  # Within spectrum range
            self.assertLess(freq, 108e6 + self.sample_rate/2)     # Within spectrum range
            self.assertGreater(power, noise_floor + 5)  # Significantly above noise


class TestDemodulation(unittest.TestCase):
    """Test demodulation with real broadcast signals"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
    def setUp(self):
        """Set up demodulator and RTL-SDR"""
        self.sample_rate = 2.4e6
        self.audio_rate = 48000
        self.demodulator = AudioDemodulators(
            audio_sample_rate=self.audio_rate
        )
        self.sdr = None
        
    def tearDown(self):
        """Clean up"""
        if self.sdr:
            self.sdr.close()
            
    def test_fm_demodulation_broadcast(self):
        """Test FM demodulation with real FM broadcast"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = 95e6  # Strong FM station
        self.sdr.gain = 20.0
        
        # Acquire signal
        samples = self.sdr.read_samples(256*1024)
        
        # Demodulate FM
        audio = self.demodulator.fm_demodulate(samples, self.sample_rate, bandwidth=200000)
        
        # Verify audio output
        self.assertIsInstance(audio, np.ndarray)
        self.assertGreater(len(audio), 1000)  # Should have audio samples
        
        # Verify audio is reasonable
        audio_power = np.mean(np.abs(audio)**2)
        self.assertGreater(audio_power, 1e-6)  # Should have signal
        self.assertLess(audio_power, 1.0)      # Should not be saturated
        
        # Test dynamic range
        audio_max = np.max(np.abs(audio))
        self.assertGreater(audio_max, 0.01)    # Should have reasonable level
        self.assertLessEqual(audio_max, 1.0)   # Should be properly limited by AGC
        
    def test_am_demodulation_aviation(self):
        """Test AM demodulation with aviation band"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = 125e6  # Aviation band
        self.sdr.gain = 40.0
        
        samples = self.sdr.read_samples(128*1024)
        
        # Demodulate AM
        audio = self.demodulator.am_demodulate(samples, self.sample_rate, bandwidth=6000)
        
        # Verify output format
        self.assertIsInstance(audio, np.ndarray)
        self.assertGreater(len(audio), 100)
        
        # Audio should be real-valued
        self.assertTrue(np.isrealobj(audio))
        
        # Should have some signal (even if just noise)
        audio_std = np.std(audio)
        self.assertGreater(audio_std, 1e-6)
        
    def test_demodulation_bandwidth_control(self):
        """Test demodulation bandwidth control"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = 100e6
        self.sdr.gain = 30.0
        
        samples = self.sdr.read_samples(128*1024)
        
        # Test different FM bandwidths
        bandwidths = [15000, 50000, 200000]
        audio_outputs = {}
        
        for bw in bandwidths:
            audio = self.demodulator.fm_demodulate(samples, self.sample_rate, bandwidth=bw)
            audio_outputs[bw] = audio
            
            # Verify output length is consistent
            expected_length = len(samples) * self.audio_rate // self.sample_rate
            actual_length = len(audio)
            # Allow 10% tolerance for resampling
            self.assertAlmostEqual(actual_length, expected_length, delta=expected_length*0.1)
            
        # Different bandwidths should give different results
        narrow_audio = audio_outputs[15000]
        wide_audio = audio_outputs[200000]
        
        # Should not be identical (unless no signal)
        correlation = np.corrcoef(narrow_audio[:min(len(narrow_audio), len(wide_audio))],
                                  wide_audio[:min(len(narrow_audio), len(wide_audio))])[0,1]
        if not np.isnan(correlation):
            self.assertLess(correlation, 0.99, "Different bandwidths should give different audio")
            
    def test_demodulation_modes_switching(self):
        """Test switching between different demodulation modes"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = 145.5e6  # 2m amateur
        self.sdr.gain = 35.0
        
        samples = self.sdr.read_samples(128*1024)
        
        # Test all demod modes
        modes_to_test = ['AM', 'FM', 'USB', 'LSB']
        audio_results = {}
        
        for mode in modes_to_test:
            if mode == 'AM':
                audio = self.demodulator.am_demodulate(samples, self.sample_rate, bandwidth=6000)
            elif mode == 'FM':
                audio = self.demodulator.fm_demodulate(samples, self.sample_rate, bandwidth=15000)
            elif mode == 'USB':
                audio = self.demodulator.ssb_demodulate(samples, 'usb', self.sample_rate, bandwidth=2700)
            elif mode == 'LSB':
                audio = self.demodulator.ssb_demodulate(samples, 'lsb', self.sample_rate, bandwidth=2700)
                
            audio_results[mode] = audio
            
            # Verify each mode produces reasonable output
            self.assertIsInstance(audio, np.ndarray)
            self.assertGreater(len(audio), 10)
            self.assertTrue(np.isrealobj(audio))
            
        # Different modes should produce different audio
        am_audio = audio_results['AM']
        fm_audio = audio_results['FM']
        
        min_len = min(len(am_audio), len(fm_audio))
        am_power = np.mean(np.abs(am_audio[:min_len])**2)
        fm_power = np.mean(np.abs(fm_audio[:min_len])**2)
        
        # Powers should be different (unless no signal)
        if am_power > 1e-10 and fm_power > 1e-10:
            power_ratio = max(am_power, fm_power) / min(am_power, fm_power)
            self.assertGreater(power_ratio, 1.01, "Different demod modes should give different results")


class TestSignalAnalysis(unittest.TestCase):
    """Test signal analysis functions with real data"""
    
    @classmethod
    def setUpClass(cls):
        if not RTL_SDR_AVAILABLE:
            raise unittest.SkipTest("RTL-SDR not available")
            
    def setUp(self):
        self.sdr = None
        
    def tearDown(self):
        if self.sdr:
            self.sdr.close()
            
    def test_signal_power_measurement(self):
        """Test accurate signal power measurement"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = 2.4e6
        self.sdr.center_freq = 88e6  # Lower FM broadcast
        self.sdr.gain = 30.0
        
        samples = self.sdr.read_samples(64*1024)
        
        # Calculate power in different ways
        power_linear = np.mean(np.abs(samples)**2)
        power_db = 10 * np.log10(power_linear + 1e-12)
        
        # Peak power
        peak_power = np.max(np.abs(samples)**2)
        peak_db = 10 * np.log10(peak_power + 1e-12)
        
        # RMS power
        rms_power = np.sqrt(power_linear)
        rms_db = 20 * np.log10(rms_power + 1e-12)
        
        # Verify relationships
        self.assertGreater(peak_power, power_linear)  # Peak > average
        self.assertGreater(peak_db, power_db)
        
        # Powers should be reasonable for FM broadcast
        self.assertGreater(power_db, -80)  # Not too weak
        self.assertLess(power_db, 0)       # Should be negative dBFS
        
    def test_frequency_accuracy_with_known_signals(self):
        """Test frequency measurement accuracy with known signals"""
        # Test with FM broadcast stations (known frequencies)
        known_frequencies = [88.1e6, 95.5e6, 101.1e6, 107.9e6]  # Common FM frequencies
        
        for test_freq in known_frequencies[:2]:  # Test first 2 to save time
            self.sdr = RtlSdr()
            self.sdr.sample_rate = 2.4e6
            self.sdr.center_freq = test_freq
            self.sdr.gain = 25.0
            
            samples = self.sdr.read_samples(128*1024)
            
            # Compute spectrum
            processor = SpectrumProcessor(fft_size=4096, sample_rate=2.4e6)
            frequencies, spectrum = processor.process_samples(samples)
            
            # Find peak near center
            center_idx = len(spectrum) // 2
            search_range = 100  # ±100 bins around center
            
            start_idx = max(0, center_idx - search_range)
            end_idx = min(len(spectrum), center_idx + search_range)
            
            local_spectrum = spectrum[start_idx:end_idx]
            local_frequencies = frequencies[start_idx:end_idx]
            
            peak_idx = np.argmax(local_spectrum)
            measured_freq = local_frequencies[peak_idx]
            
            # Should be close to tuned frequency
            freq_error = abs(measured_freq - test_freq)
            self.assertLess(freq_error, 5000, f"Frequency error too large: {freq_error} Hz")
            
            self.sdr.close()
            time.sleep(0.5)  # Brief pause between tests
            
    def test_snr_estimation(self):
        """Test SNR estimation with real signals"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = 2.4e6
        self.sdr.center_freq = 102e6  # Strong FM station
        self.sdr.gain = 30.0
        
        samples = self.sdr.read_samples(256*1024)
        
        # Compute spectrum
        processor = SpectrumProcessor(fft_size=4096, sample_rate=2.4e6)
        frequencies, spectrum = processor.process_samples(samples)
        
        # Estimate noise floor (bottom 20% of spectrum)
        sorted_spectrum = np.sort(spectrum)
        noise_floor = np.mean(sorted_spectrum[:len(sorted_spectrum)//5])
        
        # Find signal peak
        signal_peak = np.max(spectrum)
        
        # Calculate SNR
        snr_db = signal_peak - noise_floor
        
        # Should have reasonable SNR for FM broadcast
        self.assertGreater(snr_db, 10, "SNR should be > 10 dB for FM broadcast")
        self.assertLess(snr_db, 80, "SNR should be < 80 dB (sanity check)")
        
    def test_dynamic_range_measurement(self):
        """Test dynamic range measurement"""
        self.sdr = RtlSdr()
        self.sdr.sample_rate = 2.4e6
        self.sdr.center_freq = 435e6  # Less crowded band
        self.sdr.gain = 40.0
        
        samples = self.sdr.read_samples(512*1024)
        
        # Compute spectrum
        processor = SpectrumProcessor(fft_size=8192, sample_rate=2.4e6)
        frequencies, spectrum = processor.process_samples(samples)
        
        # Measure dynamic range
        max_signal = np.max(spectrum)
        min_signal = np.min(spectrum)
        dynamic_range = max_signal - min_signal
        
        # RTL-SDR typical dynamic range (8-bit ADC, real-world conditions)
        self.assertGreater(dynamic_range, 15, "Dynamic range should be > 15 dB")
        self.assertLess(dynamic_range, 60, "Dynamic range should be realistic for RTL-SDR")
        self.assertLess(dynamic_range, 120, "Dynamic range should be < 120 dB")
        
        # Test quantization noise floor
        # Bottom 5% should be relatively flat (noise floor)
        sorted_spectrum = np.sort(spectrum)
        noise_samples = sorted_spectrum[:len(sorted_spectrum)//20]
        noise_std = np.std(noise_samples)
        
        # Noise floor should be relatively stable
        self.assertLess(noise_std, 5.0, "Noise floor should be stable")


def run_dsp_tests():
    """Run all DSP tests with proper hardware setup"""
    if not RTL_SDR_AVAILABLE:
        print("RTL-SDR library not available. Skipping DSP tests.")
        return False
        
    # Check hardware
    try:
        sdr = RtlSdr()
        device_info = str(sdr)
        sdr.close()
        print(f"RTL-SDR available: {device_info}")
    except Exception as e:
        print(f"RTL-SDR hardware not available: {e}")
        return False
        
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestSpectrumProcessing))
    suite.addTests(loader.loadTestsFromTestCase(TestDemodulation))  
    suite.addTests(loader.loadTestsFromTestCase(TestSignalAnalysis))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("H1SDR DSP Real-Time Tests")
    print("=" * 50)
    success = run_dsp_tests()
    exit(0 if success else 1)