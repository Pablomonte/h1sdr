"""
Spectrum Processor - High-performance FFT processing for WebSDR
Optimized spectrum analysis with configurable parameters
"""

import numpy as np
import logging
from typing import Tuple, Optional
from scipy import signal as scipy_signal

logger = logging.getLogger(__name__)

class SpectrumProcessor:
    """High-performance spectrum processor for real-time FFT analysis"""
    
    def __init__(self, fft_size: int = 2048, sample_rate: float = 2.4e6,
                 overlap: float = 0.5, window_type: str = 'hann'):
        """
        Initialize spectrum processor
        
        Args:
            fft_size: FFT size in samples
            sample_rate: Sample rate in Hz
            overlap: Overlap factor (0.0 to 0.9)
            window_type: Window function type
        """
        self.fft_size = fft_size
        self.sample_rate = sample_rate
        self.overlap = overlap
        self.window_type = window_type
        self.center_frequency = 100e6  # Default center frequency
        
        # Pre-compute window function
        self.window = self._create_window()
        
        # Frequency array
        self.frequencies = None
        self._update_frequency_array()
        
        # Overlap buffer for streaming processing
        self.overlap_samples = int(fft_size * overlap)
        self.overlap_buffer = np.zeros(self.overlap_samples, dtype=np.complex64)
        
        # Performance optimization
        self.use_fftw = False
        try:
            import pyfftw
            self.fftw_input = pyfftw.empty_aligned(fft_size, dtype='complex64')
            self.fftw_output = pyfftw.empty_aligned(fft_size, dtype='complex64')
            self.fftw_object = pyfftw.FFTW(self.fftw_input, self.fftw_output)
            self.use_fftw = True
            logger.info("Using FFTW for accelerated FFT computation")
        except ImportError:
            logger.info("Using NumPy FFT (install pyfftw for better performance)")
        
        # Smoothing and averaging
        self.enable_smoothing = True
        self.smoothing_factor = 0.3
        self.previous_spectrum = None
        
    def _create_window(self) -> np.ndarray:
        """Create window function"""
        if self.window_type == 'hann':
            return np.hanning(self.fft_size).astype(np.float32)
        elif self.window_type == 'hamming':
            return np.hamming(self.fft_size).astype(np.float32)
        elif self.window_type == 'blackman':
            return np.blackman(self.fft_size).astype(np.float32)
        elif self.window_type == 'kaiser':
            return np.kaiser(self.fft_size, beta=8.6).astype(np.float32)
        else:
            return np.ones(self.fft_size, dtype=np.float32)
    
    def _update_frequency_array(self):
        """Update frequency array based on sample rate and center frequency"""
        freq_bins = np.fft.fftfreq(self.fft_size, 1/self.sample_rate)
        self.frequencies = np.fft.fftshift(freq_bins) + self.center_frequency
    
    def update_config(self, sample_rate: Optional[float] = None,
                     center_frequency: Optional[float] = None,
                     fft_size: Optional[int] = None):
        """Update processor configuration"""
        updated = False
        
        if sample_rate is not None and sample_rate != self.sample_rate:
            self.sample_rate = sample_rate
            updated = True
        
        if center_frequency is not None and center_frequency != self.center_frequency:
            self.center_frequency = center_frequency
            updated = True
        
        if fft_size is not None and fft_size != self.fft_size:
            self.fft_size = fft_size
            self.window = self._create_window()
            self.overlap_samples = int(fft_size * self.overlap)
            self.overlap_buffer = np.zeros(self.overlap_samples, dtype=np.complex64)
            
            # Update FFTW objects if using
            if self.use_fftw:
                try:
                    import pyfftw
                    self.fftw_input = pyfftw.empty_aligned(fft_size, dtype='complex64')
                    self.fftw_output = pyfftw.empty_aligned(fft_size, dtype='complex64')
                    self.fftw_object = pyfftw.FFTW(self.fftw_input, self.fftw_output)
                except ImportError:
                    self.use_fftw = False
            updated = True
        
        if updated:
            self._update_frequency_array()
            logger.debug(f"Spectrum processor updated: SR={self.sample_rate/1e6:.2f}MHz, "
                        f"CF={self.center_frequency/1e6:.4f}MHz, FFT={self.fft_size}")
    
    def process_samples(self, samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Process IQ samples to spectrum
        
        Args:
            samples: Complex IQ samples
            
        Returns:
            Tuple of (frequencies, spectrum_db)
        """
        try:
            # Ensure we have enough samples
            if len(samples) < self.fft_size:
                # Zero-pad if necessary
                padded = np.zeros(self.fft_size, dtype=np.complex64)
                padded[:len(samples)] = samples.astype(np.complex64)
                samples = padded
            elif len(samples) > self.fft_size:
                # Use overlap-add processing for long sequences
                return self._process_long_sequence(samples)
            else:
                samples = samples.astype(np.complex64)
            
            # Apply window function
            windowed = samples * self.window
            
            # Compute FFT
            if self.use_fftw:
                self.fftw_input[:] = windowed
                self.fftw_object()
                fft_result = self.fftw_output.copy()
            else:
                fft_result = np.fft.fft(windowed)
            
            # Shift zero frequency to center
            fft_shifted = np.fft.fftshift(fft_result)
            
            # Compute power spectrum
            power_spectrum = np.abs(fft_shifted) ** 2
            
            # Convert to dB
            spectrum_db = 10 * np.log10(np.maximum(power_spectrum, 1e-10))
            
            # Apply smoothing if enabled
            if self.enable_smoothing and self.previous_spectrum is not None:
                spectrum_db = (self.smoothing_factor * spectrum_db + 
                              (1 - self.smoothing_factor) * self.previous_spectrum)
            
            self.previous_spectrum = spectrum_db.copy()
            
            return self.frequencies.copy(), spectrum_db
            
        except Exception as e:
            logger.error(f"Error processing spectrum: {e}")
            # Return empty arrays on error
            return np.array([]), np.array([])
    
    def _process_long_sequence(self, samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Process long sample sequences using overlap-add"""
        samples = samples.astype(np.complex64)
        
        # Calculate hop size
        hop_size = self.fft_size - self.overlap_samples
        
        # Initialize output accumulator
        total_length = len(samples)
        num_frames = (total_length - self.overlap_samples) // hop_size
        
        if num_frames <= 0:
            # Not enough samples, fall back to zero-padding
            padded = np.zeros(self.fft_size, dtype=np.complex64)
            padded[:len(samples)] = samples
            return self.process_samples(padded)
        
        # Process frames and accumulate power spectra
        power_accumulator = np.zeros(self.fft_size)
        frame_count = 0
        
        for i in range(num_frames):
            start_idx = i * hop_size
            end_idx = start_idx + self.fft_size
            
            if end_idx > total_length:
                break
            
            frame = samples[start_idx:end_idx]
            
            # Apply window
            windowed = frame * self.window
            
            # Compute FFT
            if self.use_fftw:
                self.fftw_input[:] = windowed
                self.fftw_object()
                fft_result = self.fftw_output.copy()
            else:
                fft_result = np.fft.fft(windowed)
            
            # Accumulate power
            power_accumulator += np.abs(fft_result) ** 2
            frame_count += 1
        
        if frame_count > 0:
            # Average the accumulated power
            power_spectrum = power_accumulator / frame_count
            
            # Shift and convert to dB
            power_shifted = np.fft.fftshift(power_spectrum)
            spectrum_db = 10 * np.log10(np.maximum(power_shifted, 1e-10))
            
            # Apply smoothing
            if self.enable_smoothing and self.previous_spectrum is not None:
                spectrum_db = (self.smoothing_factor * spectrum_db + 
                              (1 - self.smoothing_factor) * self.previous_spectrum)
            
            self.previous_spectrum = spectrum_db.copy()
            
            return self.frequencies.copy(), spectrum_db
        else:
            return np.array([]), np.array([])
    
    def process_waterfall_data(self, samples: np.ndarray) -> np.ndarray:
        """
        Process samples specifically for waterfall display
        
        Args:
            samples: Complex IQ samples
            
        Returns:
            Power spectrum suitable for waterfall (linear scale, normalized)
        """
        _, spectrum_db = self.process_samples(samples)
        
        if len(spectrum_db) == 0:
            return np.array([])
        
        # Convert dB back to linear scale for better waterfall visualization
        spectrum_linear = 10 ** (spectrum_db / 10)
        
        # Normalize to 0-255 range for efficient transmission
        if np.max(spectrum_linear) > np.min(spectrum_linear):
            normalized = (spectrum_linear - np.min(spectrum_linear))
            normalized = normalized / np.max(normalized) * 255
        else:
            normalized = np.zeros_like(spectrum_linear)
        
        return normalized.astype(np.uint8)
    
    def get_bin_frequency(self, bin_index: int) -> float:
        """Get frequency for a specific FFT bin"""
        if 0 <= bin_index < len(self.frequencies):
            return self.frequencies[bin_index]
        return 0.0
    
    def get_frequency_bin(self, frequency: float) -> int:
        """Get FFT bin index for a specific frequency"""
        if self.frequencies is None or len(self.frequencies) == 0:
            return 0
        
        # Find closest frequency bin
        freq_diff = np.abs(self.frequencies - frequency)
        return int(np.argmin(freq_diff))
    
    def get_spectrum_info(self) -> dict:
        """Get spectrum processor information"""
        return {
            'fft_size': self.fft_size,
            'sample_rate': self.sample_rate,
            'center_frequency': self.center_frequency,
            'frequency_resolution': self.sample_rate / self.fft_size,
            'frequency_span': self.sample_rate,
            'window_type': self.window_type,
            'overlap': self.overlap,
            'smoothing_enabled': self.enable_smoothing,
            'smoothing_factor': self.smoothing_factor,
            'using_fftw': self.use_fftw,
            'frequency_range': {
                'min': float(np.min(self.frequencies)) if self.frequencies is not None else 0,
                'max': float(np.max(self.frequencies)) if self.frequencies is not None else 0
            }
        }