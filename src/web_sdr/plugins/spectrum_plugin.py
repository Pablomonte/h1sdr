"""
Spectrum Plugin - Real-time FFT spectrum processing

Processes IQ samples and generates spectrum data for visualization.
"""

import asyncio
import numpy as np
import time
from typing import Dict, Any
from .base_plugin import BasePlugin

import logging
logger = logging.getLogger(__name__)


class SpectrumPlugin(BasePlugin):
    """
    Plugin for real-time spectrum processing

    Uses the SpectrumProcessor (with v2.0 FFTProcessor) to generate
    spectrum data for real-time waterfall and spectrum displays.
    """

    def __init__(self, spectrum_processor, name: str = "SpectrumPlugin"):
        """
        Initialize spectrum plugin

        Args:
            spectrum_processor: SpectrumProcessor instance (with FFTW)
            name: Plugin name
        """
        super().__init__(name)
        self.spectrum_processor = spectrum_processor
        self.latest_spectrum = None
        self.latest_frequencies = None
        self.processing_times = []

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process IQ samples to spectrum

        Args:
            data: Dictionary containing 'iq_samples' and metadata

        Returns:
            Dictionary with spectrum data
        """
        if not self.enabled:
            return {'type': 'spectrum', 'status': 'disabled'}

        self.call_count += 1
        start_time = asyncio.get_event_loop().time()

        try:
            # Extract IQ samples
            iq_samples = data.get('iq_samples')
            if iq_samples is None:
                raise ValueError("No IQ samples in data")

            # Process spectrum (runs in executor to avoid blocking)
            loop = asyncio.get_event_loop()
            frequencies, spectrum_db = await loop.run_in_executor(
                None,
                self.spectrum_processor.process_samples,
                iq_samples
            )

            # Store latest
            self.latest_frequencies = frequencies
            self.latest_spectrum = spectrum_db

            # Update stats
            processing_time = asyncio.get_event_loop().time() - start_time
            self.total_processing_time += processing_time
            self.processing_times.append(processing_time)
            if len(self.processing_times) > 100:
                self.processing_times.pop(0)

            self.success_count += 1

            return {
                'type': 'spectrum',
                'status': 'success',
                'frequencies': frequencies,
                'spectrum_db': spectrum_db,
                'metadata': {
                    'fft_size': len(spectrum_db),
                    'processing_time_ms': processing_time * 1000,
                    'peak_power_db': float(np.max(spectrum_db)) if len(spectrum_db) > 0 else 0,
                    'mean_power_db': float(np.mean(spectrum_db)) if len(spectrum_db) > 0 else 0
                }
            }

        except Exception as e:
            self.failure_count += 1
            self.logger.error(f"Spectrum processing failed: {e}")
            raise

    def get_latest_spectrum(self) -> tuple:
        """
        Get most recent spectrum data

        Returns:
            Tuple of (frequencies, spectrum_db) or (None, None)
        """
        return self.latest_frequencies, self.latest_spectrum

    def get_average_processing_time(self) -> float:
        """
        Get average processing time over recent samples

        Returns:
            Average processing time in milliseconds
        """
        if not self.processing_times:
            return 0.0
        return (sum(self.processing_times) / len(self.processing_times)) * 1000
