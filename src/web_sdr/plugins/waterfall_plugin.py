"""
Waterfall Plugin - Waterfall display data generation

Maintains waterfall history buffer and generates waterfall display data.
"""

import asyncio
import numpy as np
from collections import deque
from typing import Dict, Any
from .base_plugin import BasePlugin

import logging
logger = logging.getLogger(__name__)


class WaterfallPlugin(BasePlugin):
    """
    Plugin for waterfall display processing

    Maintains a rolling buffer of spectrum lines for waterfall visualization.
    """

    def __init__(self, spectrum_processor, max_lines: int = 100,
                 name: str = "WaterfallPlugin"):
        """
        Initialize waterfall plugin

        Args:
            spectrum_processor: SpectrumProcessor instance
            max_lines: Maximum waterfall history lines
            name: Plugin name
        """
        super().__init__(name)
        self.spectrum_processor = spectrum_processor
        self.max_lines = max_lines

        # Waterfall buffer (FIFO)
        self.waterfall_buffer = deque(maxlen=max_lines)

        # Colormap normalization
        self.min_db = -80
        self.max_db = 0
        self.auto_scale = True

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process spectrum for waterfall display

        Args:
            data: Dictionary containing 'iq_samples' or 'spectrum_db'

        Returns:
            Dictionary with waterfall data
        """
        if not self.enabled:
            return {'type': 'waterfall', 'status': 'disabled'}

        self.call_count += 1
        start_time = asyncio.get_event_loop().time()

        try:
            # Get spectrum data (either from previous spectrum plugin or process directly)
            spectrum_db = data.get('spectrum_db')

            if spectrum_db is None:
                # Process IQ samples directly
                iq_samples = data.get('iq_samples')
                if iq_samples is None:
                    raise ValueError("No spectrum_db or iq_samples in data")

                # Process spectrum
                loop = asyncio.get_event_loop()
                _, spectrum_db = await loop.run_in_executor(
                    None,
                    self.spectrum_processor.process_samples,
                    iq_samples
                )

            # Auto-scale range if enabled
            if self.auto_scale and len(spectrum_db) > 0:
                # Update range based on percentiles (avoid noise peaks)
                self.min_db = float(np.percentile(spectrum_db, 5))
                self.max_db = float(np.percentile(spectrum_db, 95))

            # Normalize to 0-255 range for waterfall
            if len(spectrum_db) > 0:
                normalized = np.clip(spectrum_db, self.min_db, self.max_db)
                normalized = ((normalized - self.min_db) /
                             (self.max_db - self.min_db) * 255)
                waterfall_line = normalized.astype(np.uint8)
            else:
                waterfall_line = np.array([], dtype=np.uint8)

            # Add to buffer
            self.waterfall_buffer.append(waterfall_line)

            # Update stats
            processing_time = asyncio.get_event_loop().time() - start_time
            self.total_processing_time += processing_time
            self.success_count += 1

            return {
                'type': 'waterfall',
                'status': 'success',
                'waterfall_line': waterfall_line,
                'metadata': {
                    'buffer_size': len(self.waterfall_buffer),
                    'max_lines': self.max_lines,
                    'min_db': self.min_db,
                    'max_db': self.max_db,
                    'auto_scale': self.auto_scale,
                    'processing_time_ms': processing_time * 1000
                }
            }

        except Exception as e:
            self.failure_count += 1
            self.logger.error(f"Waterfall processing failed: {e}")
            raise

    def get_waterfall_buffer(self) -> np.ndarray:
        """
        Get complete waterfall buffer as 2D array

        Returns:
            2D array of waterfall data (time x frequency)
        """
        if len(self.waterfall_buffer) == 0:
            return np.array([])

        return np.array(list(self.waterfall_buffer))

    def set_scale_range(self, min_db: float, max_db: float):
        """
        Set manual scale range

        Args:
            min_db: Minimum dB value
            max_db: Maximum dB value
        """
        self.min_db = min_db
        self.max_db = max_db
        self.auto_scale = False
        self.logger.info(f"Manual scale range: {min_db} to {max_db} dB")

    def enable_auto_scale(self):
        """Enable automatic scale range based on signal"""
        self.auto_scale = True
        self.logger.info("Auto-scale enabled")

    def clear_buffer(self):
        """Clear waterfall history buffer"""
        self.waterfall_buffer.clear()
        self.logger.info("Waterfall buffer cleared")
