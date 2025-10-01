"""
Demodulator Plugin - Audio demodulation processing

Demodulates IQ samples for audio output (AM/FM/SSB/CW).
"""

import asyncio
import numpy as np
from typing import Dict, Any, Optional
from .base_plugin import BasePlugin

import logging
logger = logging.getLogger(__name__)


class DemodulatorPlugin(BasePlugin):
    """
    Plugin for audio demodulation

    Supports multiple demodulation modes: AM, FM, USB, LSB, CW
    """

    def __init__(self, audio_demodulator, sample_rate: float = 2.4e6,
                 audio_sample_rate: int = 48000, name: str = "DemodulatorPlugin"):
        """
        Initialize demodulator plugin

        Args:
            audio_demodulator: AudioDemodulators instance
            sample_rate: IQ sample rate in Hz
            audio_sample_rate: Output audio sample rate in Hz
            name: Plugin name
        """
        super().__init__(name)
        self.audio_demodulator = audio_demodulator
        self.sample_rate = sample_rate
        self.audio_sample_rate = audio_sample_rate

        # Current demodulation settings
        self.mode = 'FM'
        self.bandwidth = 15000  # Hz
        self.enabled = False  # Disabled by default (only active when not in SPECTRUM mode)

        # Audio buffer for accumulation
        self.audio_buffer = []
        self.target_chunk_size = audio_sample_rate // 10  # 100ms chunks

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Demodulate IQ samples to audio

        Args:
            data: Dictionary containing 'iq_samples' and 'demod_config'

        Returns:
            Dictionary with audio samples
        """
        if not self.enabled:
            return {'type': 'audio', 'status': 'disabled'}

        self.call_count += 1
        start_time = asyncio.get_event_loop().time()

        try:
            # Extract data
            iq_samples = data.get('iq_samples')
            if iq_samples is None:
                raise ValueError("No IQ samples in data")

            # Get demod config
            demod_config = data.get('demod_config', {})
            self.mode = demod_config.get('mode', self.mode)
            self.bandwidth = demod_config.get('bandwidth', self.bandwidth)

            # Demodulate in executor (blocking I/O)
            loop = asyncio.get_event_loop()
            audio_samples = await loop.run_in_executor(
                None,
                self._demodulate,
                iq_samples
            )

            if audio_samples is None or len(audio_samples) == 0:
                return {
                    'type': 'audio',
                    'status': 'no_output',
                    'mode': self.mode
                }

            # Add to buffer
            self.audio_buffer.extend(audio_samples)

            # Send chunk if ready
            audio_chunk = None
            if len(self.audio_buffer) >= self.target_chunk_size:
                audio_chunk = np.array(self.audio_buffer[:self.target_chunk_size])
                self.audio_buffer = self.audio_buffer[self.target_chunk_size:]

            # Update stats
            processing_time = asyncio.get_event_loop().time() - start_time
            self.total_processing_time += processing_time
            self.success_count += 1

            result = {
                'type': 'audio',
                'status': 'success',
                'mode': self.mode,
                'metadata': {
                    'sample_rate': self.audio_sample_rate,
                    'bandwidth': self.bandwidth,
                    'buffer_size': len(self.audio_buffer),
                    'processing_time_ms': processing_time * 1000
                }
            }

            if audio_chunk is not None:
                result['audio_samples'] = audio_chunk
                result['chunk_size'] = len(audio_chunk)

            return result

        except Exception as e:
            self.failure_count += 1
            self.logger.error(f"Demodulation failed: {e}")
            raise

    def _demodulate(self, iq_samples: np.ndarray) -> Optional[np.ndarray]:
        """
        Synchronous demodulation (called in executor)

        Args:
            iq_samples: Complex IQ samples

        Returns:
            Audio samples or None
        """
        try:
            # Demodulate based on mode
            if self.mode == 'AM':
                audio = self.audio_demodulator.am_demodulate(iq_samples, self.sample_rate)
            elif self.mode == 'FM':
                audio = self.audio_demodulator.fm_demodulate(
                    iq_samples,
                    self.sample_rate,
                    deviation=75000 if self.bandwidth > 100000 else 3000
                )
            elif self.mode == 'USB':
                audio = self.audio_demodulator.ssb_demodulate(iq_samples, 'usb', self.sample_rate)
            elif self.mode == 'LSB':
                audio = self.audio_demodulator.ssb_demodulate(iq_samples, 'lsb', self.sample_rate)
            elif self.mode == 'CW':
                audio = self.audio_demodulator.cw_demodulate(iq_samples, 600, self.sample_rate)
            else:
                self.logger.warning(f"Unknown demod mode: {self.mode}")
                return None

            # Resample if needed
            if self.sample_rate != self.audio_sample_rate:
                from scipy import signal as scipy_signal
                audio = scipy_signal.resample(
                    audio,
                    int(len(audio) * self.audio_sample_rate / self.sample_rate)
                )

            # Apply bandwidth filter
            if self.bandwidth < self.audio_sample_rate / 2:
                from scipy import signal as scipy_signal
                nyquist = self.audio_sample_rate / 2
                normalized_cutoff = self.bandwidth / nyquist
                b, a = scipy_signal.butter(4, normalized_cutoff, btype='low')
                audio = scipy_signal.filtfilt(b, a, audio)

            # Normalize
            if len(audio) > 0:
                max_val = np.max(np.abs(audio))
                if max_val > 0:
                    audio = audio / max_val * 0.5  # Prevent clipping

            return audio

        except Exception as e:
            self.logger.error(f"Demodulation error: {e}")
            return None

    def set_mode(self, mode: str, bandwidth: int = None):
        """
        Set demodulation mode

        Args:
            mode: Demodulation mode (AM/FM/USB/LSB/CW)
            bandwidth: Optional bandwidth in Hz
        """
        self.mode = mode
        if bandwidth is not None:
            self.bandwidth = bandwidth

        self.logger.info(f"Demod mode: {mode}, bandwidth: {self.bandwidth} Hz")

    def clear_buffer(self):
        """Clear audio buffer"""
        self.audio_buffer.clear()
        self.logger.info("Audio buffer cleared")
