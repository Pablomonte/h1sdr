"""
WebSDR Controller - RTL-SDR interface for web application
Handles RTL-SDR device management, data acquisition and processing
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, Union
import threading
from queue import Queue, Empty

import numpy as np
from rtlsdr import RtlSdr

from ..config import config, DEMOD_MODES
from ..models.sdr_models import SDRStatus, SpectrumData, AudioData
from ..dsp.spectrum_processor import SpectrumProcessor
from ..dsp.demodulators import AudioDemodulators

logger = logging.getLogger(__name__)

class WebSDRController:
    """Main controller for RTL-SDR operations in web environment"""
    
    def __init__(self):
        self.sdr: Optional[RtlSdr] = None
        self.is_running = False
        self.is_connected = False
        
        # Current configuration
        self.current_config = {
            'device_index': config.rtlsdr_device_index,
            'sample_rate': config.rtlsdr_sample_rate,
            'center_frequency': config.rtlsdr_default_freq,
            'gain': config.rtlsdr_default_gain,
            'ppm_correction': config.rtlsdr_ppm_correction
        }
        
        # Current demodulation settings
        self.demod_config = {
            'mode': 'SPECTRUM',
            'bandwidth': DEMOD_MODES['SPECTRUM']['bandwidth_default']
        }
        
        # DSP components
        self.spectrum_processor = SpectrumProcessor(
            fft_size=config.fft_size,
            sample_rate=config.rtlsdr_sample_rate
        )
        self.audio_demodulator = AudioDemodulators()
        
        # Data streaming
        self.data_queue = Queue(maxsize=10)
        self.spectrum_data = None
        self.audio_data = None
        self.acquisition_thread = None
        
        # Audio buffering for smooth streaming
        self.audio_buffer = []
        # Optimal chunk size for smooth audio (100ms for better continuity)
        self.target_audio_chunk_size = config.audio_sample_rate // 10  # 100ms chunks = 4800 samples
        
        # Performance tracking
        self.stats = {
            'samples_processed': 0,
            'fps': 0.0,
            'last_fps_time': time.time(),
            'processing_times': []
        }
        
    async def initialize(self):
        """Initialize the SDR controller"""
        logger.info("Initializing WebSDR Controller")
        # Controller is ready, actual SDR connection happens on start()
        
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current SDR status"""
        return {
            'connected': self.is_connected,
            'running': self.is_running,
            'device_index': self.current_config['device_index'] if self.is_connected else None,
            'sample_rate': self.current_config['sample_rate'] if self.is_connected else None,
            'center_frequency': self.current_config['center_frequency'] if self.is_connected else None,
            'gain': self.current_config['gain'] if self.is_connected else None,
            'ppm_correction': self.current_config['ppm_correction'] if self.is_connected else None,
            'demod_mode': self.demod_config['mode'],
            'demod_bandwidth': self.demod_config['bandwidth'],
            'stats': self.stats.copy()
        }
        
    async def start(self, device_index: int = 0) -> Dict[str, Any]:
        """Start SDR with specified device"""
        if self.is_running:
            raise RuntimeError("SDR is already running")
            
        try:
            # Initialize RTL-SDR
            self.sdr = RtlSdr(device_index=device_index)
            
            # Configure SDR
            self.sdr.sample_rate = self.current_config['sample_rate']
            self.sdr.center_freq = self.current_config['center_frequency']
            self.sdr.gain = self.current_config['gain']
            
            if self.current_config['ppm_correction'] != 0:
                self.sdr.freq_correction = self.current_config['ppm_correction']
            
            # Try to optimize settings
            try:
                self.sdr.set_direct_sampling(0)
                self.sdr.set_bias_tee(False)
            except AttributeError:
                logger.warning("Some SDR optimization methods not available")
            
            self.current_config['device_index'] = device_index
            self.is_connected = True
            
            # Update spectrum processor
            self.spectrum_processor.update_config(
                sample_rate=self.current_config['sample_rate'],
                center_frequency=self.current_config['center_frequency']
            )
            
            # Start data acquisition thread
            self.is_running = True
            self.acquisition_thread = threading.Thread(
                target=self._acquisition_worker,
                daemon=True
            )
            self.acquisition_thread.start()
            
            logger.info(f"SDR started successfully on device {device_index}")
            logger.info(f"Sample rate: {self.current_config['sample_rate']/1e6:.2f} MHz")
            logger.info(f"Center frequency: {self.current_config['center_frequency']/1e6:.4f} MHz")
            logger.info(f"Gain: {self.current_config['gain']} dB")
            
            return await self.get_status()
            
        except Exception as e:
            self.is_connected = False
            self.is_running = False
            if self.sdr:
                try:
                    self.sdr.close()
                except:
                    pass
                self.sdr = None
            logger.error(f"Failed to start SDR: {e}")
            raise
    
    async def stop(self):
        """Stop SDR operations"""
        self.is_running = False
        
        # Wait for acquisition thread to finish
        if self.acquisition_thread and self.acquisition_thread.is_alive():
            self.acquisition_thread.join(timeout=2.0)
        
        # Close SDR
        if self.sdr:
            try:
                self.sdr.close()
                logger.info("SDR device closed")
            except Exception as e:
                logger.error(f"Error closing SDR: {e}")
            finally:
                self.sdr = None
        
        self.is_connected = False
        
        # Clear audio buffer
        self.audio_buffer.clear()
        
        logger.info("SDR stopped")
    
    async def tune(self, frequency: float, gain: Optional[float] = None) -> Dict[str, Any]:
        """Tune to specified frequency"""
        if not self.is_connected:
            raise RuntimeError("SDR is not connected")
            
        try:
            # Validate frequency range
            if not (24e6 <= frequency <= 1766e6):  # RTL-SDR range
                raise ValueError(f"Frequency {frequency/1e6:.3f} MHz is outside RTL-SDR range (24-1766 MHz)")
            
            # Set frequency
            self.sdr.center_freq = frequency
            self.current_config['center_frequency'] = frequency
            
            # Set gain if provided
            if gain is not None:
                self.sdr.gain = gain
                self.current_config['gain'] = gain
            
            # Update spectrum processor
            self.spectrum_processor.update_config(
                center_frequency=frequency
            )
            
            logger.info(f"Tuned to {frequency/1e6:.4f} MHz")
            if gain is not None:
                logger.info(f"Gain set to {gain} dB")
            
            return {
                'frequency': frequency,
                'gain': gain if gain is not None else self.current_config['gain']
            }
            
        except Exception as e:
            logger.error(f"Error tuning to {frequency/1e6:.4f} MHz: {e}")
            raise
    
    async def set_demodulation(self, mode: str, bandwidth: Optional[int] = None) -> Dict[str, Any]:
        """Set demodulation mode and bandwidth"""
        if mode not in DEMOD_MODES:
            raise ValueError(f"Invalid demodulation mode: {mode}")
        
        mode_config = DEMOD_MODES[mode]
        
        # Set bandwidth
        if bandwidth is None:
            bandwidth = mode_config['bandwidth_default']
        else:
            # Validate bandwidth range
            if not (mode_config['bandwidth_min'] <= bandwidth <= mode_config['bandwidth_max']):
                raise ValueError(
                    f"Bandwidth {bandwidth} Hz is outside range for {mode} "
                    f"({mode_config['bandwidth_min']}-{mode_config['bandwidth_max']} Hz)"
                )
        
        self.demod_config['mode'] = mode
        self.demod_config['bandwidth'] = bandwidth
        
        logger.info(f"Demodulation set to {mode}, bandwidth {bandwidth} Hz")
        
        return {
            'mode': mode,
            'bandwidth': bandwidth,
            'audio_enabled': mode != 'SPECTRUM'
        }
    
    async def get_spectrum_data(self) -> Optional[Dict[str, Any]]:
        """Get latest spectrum data for WebSocket streaming"""
        try:
            # Get data from queue (non-blocking)
            try:
                samples = self.data_queue.get_nowait()
            except Empty:
                return None
            
            # Process spectrum
            start_time = time.time()
            frequencies, spectrum_db = self.spectrum_processor.process_samples(samples)
            processing_time = time.time() - start_time
            
            # Update performance stats
            self._update_performance_stats(processing_time)
            
            # Create spectrum data
            spectrum_data = {
                'type': 'spectrum',
                'frequencies': frequencies.tolist(),
                'spectrum': spectrum_db.tolist(),
                'timestamp': datetime.now().isoformat(),
                'sample_rate': self.current_config['sample_rate'],
                'center_frequency': self.current_config['center_frequency'],
                'fft_size': config.fft_size,
                'metadata': {
                    'gain': self.current_config['gain'],
                    'demod_mode': self.demod_config['mode'],
                    'processing_time_ms': processing_time * 1000,
                    'fps': self.stats['fps']
                }
            }
            
            # Store for reuse
            self.spectrum_data = spectrum_data
            
            # Generate audio data if needed
            if self.demod_config['mode'] != 'SPECTRUM':
                audio_samples = await self._process_audio(samples)
                if audio_samples is not None and len(audio_samples) > 0:
                    # Log audio generation rate periodically
                    logger.debug(f"Audio samples generated: {len(audio_samples)}, mode: {self.demod_config['mode']}")

                    # Add to audio buffer for accumulation
                    # Convert numpy array to Python list to avoid JSON serialization issues
                    if hasattr(audio_samples, 'tolist'):
                        self.audio_buffer.extend(audio_samples.tolist())
                    else:
                        self.audio_buffer.extend(list(audio_samples))

                    logger.debug(f"Audio buffer size: {len(self.audio_buffer)}/{self.target_audio_chunk_size}")

                    # Send when we have enough samples for a smooth chunk
                    if len(self.audio_buffer) >= self.target_audio_chunk_size:
                        chunk_samples = self.audio_buffer[:self.target_audio_chunk_size]
                        self.audio_buffer = self.audio_buffer[self.target_audio_chunk_size:]
                        
                        self.audio_data = {
                            'type': 'audio',
                            'samples': chunk_samples,  # Already a Python list
                            'sample_rate': config.audio_sample_rate,
                            'timestamp': datetime.now().isoformat(),
                            'mode': self.demod_config['mode'],
                            'metadata': {
                                'bandwidth': self.demod_config['bandwidth'],
                                'chunk_size': len(chunk_samples)
                            },
                            '_sent': False  # Mark as not sent yet
                        }
            
            return spectrum_data
            
        except Exception as e:
            logger.error(f"Error processing spectrum data: {e}")
            return None
    
    async def get_audio_data(self) -> Optional[Dict[str, Any]]:
        """Get latest audio data for WebSocket streaming"""
        if self.audio_data and not self.audio_data.get('_sent', False):
            # Mark as sent to prevent duplicate streaming
            self.audio_data['_sent'] = True
            # Return a clean copy without the _sent flag
            audio_copy = {k: v for k, v in self.audio_data.items() if k != '_sent'}
            return audio_copy
        return None
    
    def _acquisition_worker(self):
        """Background thread for continuous data acquisition"""
        logger.info("Starting SDR acquisition worker")
        
        # Calculate read size for ~100ms chunks
        read_size = int(self.current_config['sample_rate'] * 0.1)
        read_size = (read_size // 1024) * 1024  # Align to 1024 samples
        
        while self.is_running:
            try:
                # Read samples from SDR
                samples = self.sdr.read_samples(read_size)
                
                # Add to processing queue (non-blocking)
                try:
                    self.data_queue.put_nowait(samples)
                except:
                    # Queue full, drop oldest sample
                    try:
                        self.data_queue.get_nowait()
                        self.data_queue.put_nowait(samples)
                    except Empty:
                        pass
                
                self.stats['samples_processed'] += len(samples)
                
            except Exception as e:
                if self.is_running:  # Only log if we're still supposed to be running
                    logger.error(f"Error in acquisition worker: {e}")
                break
        
        logger.info("SDR acquisition worker stopped")
    
    async def _process_audio(self, samples: np.ndarray) -> Optional[np.ndarray]:
        """Process samples for audio output"""
        try:
            mode = self.demod_config['mode']
            sample_rate = self.current_config['sample_rate']

            # Demodulate based on mode
            if mode == 'AM':
                audio = self.audio_demodulator.am_demodulate(samples, sample_rate)
            elif mode == 'FM':
                audio = self.audio_demodulator.fm_demodulate(samples, sample_rate)
            elif mode == 'USB':
                audio = self.audio_demodulator.ssb_demodulate(samples, 'usb', sample_rate)
            elif mode == 'LSB':
                audio = self.audio_demodulator.ssb_demodulate(samples, 'lsb', sample_rate)
            elif mode == 'CW':
                tone_freq = DEMOD_MODES['CW'].get('tone_frequency', 600)
                audio = self.audio_demodulator.cw_demodulate(samples, tone_freq, sample_rate)
            else:
                return None

            # Resample to audio sample rate if needed
            # Use a more efficient resampling for the large downsampling ratio
            if sample_rate != config.audio_sample_rate:
                from scipy import signal as scipy_signal
                # Calculate the exact resampling ratio
                resample_ratio = config.audio_sample_rate / sample_rate
                # For large downsampling ratios, use decimate for better quality
                if resample_ratio < 0.1:  # If downsampling by more than 10x
                    # First apply anti-aliasing filter and decimate
                    decimation_factor = int(sample_rate / config.audio_sample_rate)
                    if decimation_factor > 1:
                        audio = scipy_signal.decimate(audio, decimation_factor, zero_phase=True)
                else:
                    # Use regular resampling for smaller ratios
                    audio = scipy_signal.resample(
                        audio,
                        int(len(audio) * config.audio_sample_rate / sample_rate)
                    )
            
            # Apply bandwidth limiting
            bandwidth = self.demod_config.get('bandwidth', 3000)  # Default 3kHz
            audio_rate = config.audio_sample_rate
            
            if bandwidth < audio_rate / 2:  # Avoid aliasing
                from scipy import signal as scipy_signal
                # Design low-pass filter for bandwidth limiting
                nyquist = audio_rate / 2
                normalized_cutoff = bandwidth / nyquist
                b, a = scipy_signal.butter(4, normalized_cutoff, btype='low')
                audio = scipy_signal.filtfilt(b, a, audio)
            
            # Normalize audio
            if len(audio) > 0:
                max_val = np.max(np.abs(audio))
                if max_val > 0:
                    audio = audio / max_val * 0.5  # Prevent clipping
            
            return audio
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return None
    
    def _update_performance_stats(self, processing_time: float):
        """Update performance statistics"""
        current_time = time.time()
        
        # Track processing times
        self.stats['processing_times'].append(processing_time)
        if len(self.stats['processing_times']) > 100:
            self.stats['processing_times'].pop(0)
        
        # Update FPS calculation
        if current_time - self.stats['last_fps_time'] >= 1.0:
            # Calculate FPS based on spectrum updates
            time_diff = current_time - self.stats['last_fps_time']
            frame_count = len(self.stats['processing_times'])
            self.stats['fps'] = frame_count / time_diff if time_diff > 0 else 0
            self.stats['last_fps_time'] = current_time
            self.stats['processing_times'].clear()
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.stop()
        logger.info("WebSDR Controller cleaned up")