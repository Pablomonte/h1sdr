"""
Audio Demodulators - High-performance demodulation algorithms
Implements AM, FM, SSB, and CW demodulation for WebSDR
"""

import numpy as np
import logging
from typing import Optional, Tuple
from scipy import signal as scipy_signal

logger = logging.getLogger(__name__)

class AudioDemodulators:
    """Collection of audio demodulation algorithms optimized for real-time processing"""
    
    def __init__(self, audio_sample_rate: int = 48000):
        """
        Initialize demodulators
        
        Args:
            audio_sample_rate: Output audio sample rate
        """
        self.audio_sample_rate = audio_sample_rate
        
        # State variables for stateful demodulators
        self._fm_previous_phase = 0.0
        self._cw_oscillator_phase = 0.0
        
        # Filter design parameters
        self._audio_filter_cache = {}
        
        logger.debug(f"Audio demodulators initialized for {audio_sample_rate} Hz output")
    
    def am_demodulate(self, iq_samples: np.ndarray, sample_rate: float,
                     bandwidth: Optional[float] = None) -> np.ndarray:
        """
        AM (Amplitude Modulation) demodulation using envelope detection
        
        Args:
            iq_samples: Complex IQ samples
            sample_rate: Sample rate of input samples
            bandwidth: Audio bandwidth in Hz (optional filtering)
            
        Returns:
            Demodulated audio samples
        """
        try:
            # Envelope detection - compute magnitude
            amplitude = np.abs(iq_samples)
            
            # Remove DC component
            audio = amplitude - np.mean(amplitude)
            
            # Apply audio filtering if bandwidth specified
            if bandwidth is not None and bandwidth < sample_rate / 2:
                audio = self._apply_audio_filter(audio, sample_rate, bandwidth)
            
            # Resample to audio sample rate if needed
            if sample_rate != self.audio_sample_rate:
                audio = self._resample_audio(audio, sample_rate, self.audio_sample_rate)
            
            # Normalize and apply AGC
            audio = self._apply_agc(audio, target_level=0.3)
            
            return audio.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Error in AM demodulation: {e}")
            return np.zeros(len(iq_samples), dtype=np.float32)
    
    def fm_demodulate(self, iq_samples: np.ndarray, sample_rate: float,
                     bandwidth: Optional[float] = None, 
                     deviation: float = 75000) -> np.ndarray:
        """
        FM (Frequency Modulation) demodulation using quadrature detector
        
        This implements a high-quality quadrature FM demodulator similar to
        the fmdemod_quadri_cf function from csdr, which is much more robust
        against noise than simple phase differentiation.
        
        Args:
            iq_samples: Complex IQ samples
            sample_rate: Sample rate of input samples
            bandwidth: Audio bandwidth in Hz
            deviation: FM deviation in Hz (75kHz for broadcast FM)
            
        Returns:
            Demodulated audio samples
        """
        try:
            # Remove DC offset
            iq_samples = iq_samples - np.mean(iq_samples)
            
            # Apply limiting to remove amplitude variations (hard limiting)
            # This is crucial for FM - we only care about frequency, not amplitude
            magnitude = np.abs(iq_samples)
            # Avoid division by zero
            magnitude = np.where(magnitude < 1e-10, 1e-10, magnitude)
            limited_samples = iq_samples / magnitude
            
            # Quadrature FM demodulation
            # This is based on the formula: d/dt[atan2(Q,I)] = (I*dQ/dt - Q*dI/dt)/(I²+Q²)
            # Since we have limited samples, I²+Q² = 1, so we just need I*dQ/dt - Q*dI/dt
            
            I = np.real(limited_samples)
            Q = np.imag(limited_samples)
            
            # Calculate derivatives using forward difference
            dI = np.diff(I, prepend=I[0])
            dQ = np.diff(Q, prepend=Q[0])
            
            # Quadrature detector output
            discriminator_out = I * dQ - Q * dI
            
            # Convert to frequency deviation in Hz
            # Scale by sample rate and normalize by 2π
            audio = discriminator_out * sample_rate / (2 * np.pi)
            
            # Normalize by deviation for proper audio level
            audio = audio / deviation
            
            # Pre-filter before de-emphasis to remove high-frequency noise
            if bandwidth is not None:
                # Use a wider pre-filter before de-emphasis
                pre_filter_bw = min(bandwidth * 2, sample_rate * 0.4)
                audio = self._apply_audio_filter(audio, sample_rate, pre_filter_bw)
            
            # Apply de-emphasis filter for broadcast FM (75μs time constant)
            if deviation >= 50000:  # Broadcast FM
                audio = self._apply_deemphasis(audio, sample_rate, time_constant=75e-6)
            
            # Apply final audio filtering
            if bandwidth is not None:
                audio = self._apply_audio_filter(audio, sample_rate, bandwidth)
            
            # Resample to audio sample rate if needed
            if sample_rate != self.audio_sample_rate:
                audio = self._resample_audio(audio, sample_rate, self.audio_sample_rate)
            
            # Apply AGC with appropriate settings for FM
            audio = self._apply_agc(audio, target_level=0.4, attack_time=0.001, release_time=0.1)
            
            return audio.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Error in FM demodulation: {e}")
            return np.zeros(len(iq_samples), dtype=np.float32)
    
    def ssb_demodulate(self, iq_samples: np.ndarray, mode: str, sample_rate: float,
                      bandwidth: Optional[float] = None) -> np.ndarray:
        """
        SSB (Single Sideband) demodulation
        
        Args:
            iq_samples: Complex IQ samples
            mode: 'usb' or 'lsb'
            sample_rate: Sample rate of input samples
            bandwidth: Audio bandwidth in Hz
            
        Returns:
            Demodulated audio samples
        """
        try:
            mode = mode.lower()
            if mode not in ['usb', 'lsb']:
                raise ValueError("SSB mode must be 'usb' or 'lsb'")
            
            # For SSB, we need to shift the spectrum and take real part
            # This is a simplified approach - more sophisticated methods exist
            
            if mode == 'usb':
                # Upper sideband - take real part directly
                audio = np.real(iq_samples)
            else:  # lsb
                # Lower sideband - conjugate and take real part
                audio = np.real(np.conj(iq_samples))
            
            # Apply audio filtering
            if bandwidth is None:
                bandwidth = 2700  # Typical SSB bandwidth
            
            audio = self._apply_audio_filter(audio, sample_rate, bandwidth, 
                                           filter_type='bandpass', 
                                           low_cutoff=300, high_cutoff=bandwidth)
            
            # Resample to audio sample rate
            if sample_rate != self.audio_sample_rate:
                audio = self._resample_audio(audio, sample_rate, self.audio_sample_rate)
            
            # Apply AGC with faster attack for SSB
            audio = self._apply_agc(audio, target_level=0.4, attack_time=0.001)
            
            return audio.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Error in SSB demodulation: {e}")
            return np.zeros(len(iq_samples), dtype=np.float32)
    
    def cw_demodulate(self, iq_samples: np.ndarray, sample_rate: float,
                     tone_frequency: float = 600, bandwidth: float = 500) -> np.ndarray:
        """
        CW (Continuous Wave) demodulation using BFO (Beat Frequency Oscillator)
        
        Args:
            iq_samples: Complex IQ samples
            sample_rate: Sample rate of input samples
            tone_frequency: BFO tone frequency in Hz
            bandwidth: CW filter bandwidth in Hz
            
        Returns:
            Demodulated audio samples
        """
        try:
            # Generate BFO (Beat Frequency Oscillator)
            t = np.arange(len(iq_samples)) / sample_rate
            bfo_i = np.cos(2 * np.pi * tone_frequency * t)
            bfo_q = np.sin(2 * np.pi * tone_frequency * t)
            bfo = bfo_i + 1j * bfo_q
            
            # Mix with BFO
            mixed = iq_samples * np.conj(bfo)
            
            # Take real part for audio
            audio = np.real(mixed)
            
            # Apply narrow CW filter
            audio = self._apply_audio_filter(audio, sample_rate, bandwidth,
                                           filter_type='bandpass',
                                           low_cutoff=tone_frequency - bandwidth/2,
                                           high_cutoff=tone_frequency + bandwidth/2)
            
            # Resample to audio sample rate
            if sample_rate != self.audio_sample_rate:
                audio = self._resample_audio(audio, sample_rate, self.audio_sample_rate)
            
            # Apply AGC with very fast attack for CW
            audio = self._apply_agc(audio, target_level=0.5, attack_time=0.0001)
            
            return audio.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Error in CW demodulation: {e}")
            return np.zeros(len(iq_samples), dtype=np.float32)
    
    # Helper methods
    
    def _apply_audio_filter(self, audio: np.ndarray, sample_rate: float, 
                           bandwidth: float, filter_type: str = 'lowpass',
                           low_cutoff: Optional[float] = None,
                           high_cutoff: Optional[float] = None) -> np.ndarray:
        """Apply audio filtering"""
        try:
            # Create filter key for caching
            filter_key = f"{filter_type}_{sample_rate}_{bandwidth}_{low_cutoff}_{high_cutoff}"
            
            if filter_key not in self._audio_filter_cache:
                nyquist = sample_rate / 2
                
                if filter_type == 'lowpass':
                    cutoff = min(bandwidth, nyquist * 0.95)
                    sos = scipy_signal.butter(6, cutoff / nyquist, 
                                            btype='lowpass', output='sos')
                elif filter_type == 'bandpass':
                    low = max(low_cutoff or 300, 1) / nyquist
                    high = min(high_cutoff or bandwidth, nyquist * 0.95) / nyquist
                    if high > low:
                        sos = scipy_signal.butter(4, [low, high], 
                                                btype='bandpass', output='sos')
                    else:
                        # Fallback to lowpass if bandpass range is invalid
                        sos = scipy_signal.butter(6, high, btype='lowpass', output='sos')
                else:
                    return audio  # Unknown filter type
                
                self._audio_filter_cache[filter_key] = sos
            
            sos = self._audio_filter_cache[filter_key]
            filtered = scipy_signal.sosfilt(sos, audio)
            
            return filtered
            
        except Exception as e:
            logger.warning(f"Audio filtering failed: {e}")
            return audio  # Return unfiltered on error
    
    def _apply_deemphasis(self, audio: np.ndarray, sample_rate: float, 
                         time_constant: float = 75e-6) -> np.ndarray:
        """Apply de-emphasis filter for FM"""
        try:
            # De-emphasis filter: H(s) = 1 / (1 + s*τ)
            # where τ is the time constant
            
            # Convert to digital filter
            # Cutoff frequency: fc = 1 / (2π * τ)
            cutoff_freq = 1 / (2 * np.pi * time_constant)
            
            # Design digital filter
            nyquist = sample_rate / 2
            cutoff_norm = cutoff_freq / nyquist
            
            if cutoff_norm >= 1.0:
                return audio  # No filtering needed
            
            # First-order lowpass filter for de-emphasis
            b, a = scipy_signal.butter(1, cutoff_norm, btype='lowpass')
            deemphasized = scipy_signal.filtfilt(b, a, audio)
            
            return deemphasized
            
        except Exception as e:
            logger.warning(f"De-emphasis filter failed: {e}")
            return audio
    
    def _resample_audio(self, audio: np.ndarray, input_rate: float, 
                       output_rate: float) -> np.ndarray:
        """Resample audio to different sample rate"""
        try:
            if input_rate == output_rate:
                return audio
            
            # Calculate resampling ratio
            resample_ratio = output_rate / input_rate
            output_length = int(len(audio) * resample_ratio)
            
            # Use scipy resampling
            resampled = scipy_signal.resample(audio, output_length)
            
            return resampled
            
        except Exception as e:
            logger.warning(f"Audio resampling failed: {e}")
            return audio
    
    def _apply_agc(self, audio: np.ndarray, target_level: float = 0.3,
                  attack_time: float = 0.01, release_time: float = 0.1) -> np.ndarray:
        """Apply Automatic Gain Control (AGC)"""
        try:
            if len(audio) == 0:
                return audio
            
            # Simple AGC implementation
            # Calculate RMS level in overlapping windows
            window_size = max(1, int(len(audio) * 0.01))  # 1% of signal length
            
            # Compute envelope
            abs_audio = np.abs(audio)
            
            # Smooth the envelope
            if len(abs_audio) > window_size:
                envelope = scipy_signal.filtfilt(
                    np.ones(window_size) / window_size, [1], abs_audio
                )
            else:
                envelope = np.mean(abs_audio) * np.ones_like(abs_audio)
            
            # Calculate gain
            gain = np.ones_like(audio)
            nonzero_mask = envelope > 1e-10
            
            if np.any(nonzero_mask):
                gain[nonzero_mask] = target_level / envelope[nonzero_mask]
                
                # Limit gain range
                gain = np.clip(gain, 0.1, 10.0)
                
                # Apply gain
                audio = audio * gain
            
            # Final limiting
            audio = np.clip(audio, -1.0, 1.0)
            
            return audio
            
        except Exception as e:
            logger.warning(f"AGC failed: {e}")
            # Fallback: simple normalization
            max_val = np.max(np.abs(audio))
            if max_val > 0:
                return audio / max_val * target_level
            return audio
    
    def get_demodulator_info(self) -> dict:
        """Get information about available demodulators"""
        return {
            'available_modes': ['AM', 'FM', 'USB', 'LSB', 'CW'],
            'audio_sample_rate': self.audio_sample_rate,
            'filter_cache_size': len(self._audio_filter_cache),
            'am': {
                'description': 'Amplitude Modulation (envelope detection)',
                'typical_bandwidth': '6000 Hz',
                'use_cases': ['Aircraft', 'AM broadcast', 'Utility stations']
            },
            'fm': {
                'description': 'Frequency Modulation (phase differentiation)', 
                'typical_bandwidth': '15000 Hz',
                'deviation': '75000 Hz (broadcast FM)',
                'use_cases': ['FM broadcast', 'VHF/UHF communications', 'Two-way radio']
            },
            'usb': {
                'description': 'Upper Sideband (single sideband)',
                'typical_bandwidth': '2700 Hz',
                'use_cases': ['HF amateur radio', 'HF voice communications']
            },
            'lsb': {
                'description': 'Lower Sideband (single sideband)',
                'typical_bandwidth': '2700 Hz', 
                'use_cases': ['HF amateur radio', 'HF voice communications']
            },
            'cw': {
                'description': 'Continuous Wave (Morse code)',
                'typical_bandwidth': '500 Hz',
                'tone_frequency': '600 Hz',
                'use_cases': ['Amateur radio CW', 'Weak signal communications']
            }
        }