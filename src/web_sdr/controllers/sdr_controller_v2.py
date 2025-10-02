"""
WebSDR Controller v2.0 - Plugin-based architecture

Enhanced controller using PluginSupervisor for modular processing.
Provides error isolation and parallel execution of plugins.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
import threading
from queue import Queue, Empty

import numpy as np
from rtlsdr import RtlSdr

from ..config import config, DEMOD_MODES
from ..models.sdr_models import SDRStatus, SpectrumData, AudioData
from ..dsp.spectrum_processor import SpectrumProcessor
from ..dsp.demodulators import AudioDemodulators
from ..pipeline.plugin_supervisor import PluginSupervisor, PluginResult
from ..plugins import SpectrumPlugin, WaterfallPlugin, DemodulatorPlugin
from ..utils.error_handler import (
    error_handler,
    handle_errors,
    HardwareError,
    ProcessingError,
    ErrorSeverity
)

logger = logging.getLogger(__name__)

class WebSDRControllerV2:
    """
    Main controller for RTL-SDR operations using v2.0 plugin architecture

    Key features:
    - Plugin-based processing with supervisor pattern
    - Error isolation (plugin failures don't stop acquisition)
    - Parallel plugin execution (fan-out)
    - FFTW-accelerated spectrum processing
    """

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

        # DSP components (for plugins)
        self.spectrum_processor = SpectrumProcessor(
            fft_size=config.fft_size,
            sample_rate=config.rtlsdr_sample_rate
        )
        self.audio_demodulator = AudioDemodulators()

        # Plugin system
        self.plugins: List = []
        self.plugin_supervisor: Optional[PluginSupervisor] = None
        self._initialize_plugins()

        # Data streaming
        self.data_queue = Queue(maxsize=10)
        self.latest_results: List[PluginResult] = []
        self.acquisition_thread = None

        # Performance tracking
        self.stats = {
            'samples_processed': 0,
            'fps': 0.0,
            'last_fps_time': time.time(),
            'processing_times': [],
            'plugin_stats': {}
        }

    def _initialize_plugins(self):
        """Initialize plugin system"""
        logger.info("Initializing v2.0 plugin system...")

        # Create plugins
        self.spectrum_plugin = SpectrumPlugin(self.spectrum_processor)
        self.waterfall_plugin = WaterfallPlugin(self.spectrum_processor, max_lines=100)
        self.demod_plugin = DemodulatorPlugin(
            self.audio_demodulator,
            sample_rate=config.rtlsdr_sample_rate,
            audio_sample_rate=config.audio_sample_rate
        )

        # Demod plugin disabled by default (enabled when mode != SPECTRUM)
        self.demod_plugin.enabled = False

        self.plugins = [
            self.spectrum_plugin,
            self.waterfall_plugin,
            self.demod_plugin
        ]

        # Create supervisor
        self.plugin_supervisor = PluginSupervisor(
            self.plugins,
            name="WebSDR-Supervisor"
        )

        logger.info(f"Initialized {len(self.plugins)} plugins with supervisor")

    async def initialize(self):
        """Initialize the SDR controller"""
        logger.info("Initializing WebSDR Controller v2.0")
        logger.info(f"Plugin supervisor: {self.plugin_supervisor.name}")

    async def get_status(self) -> Dict[str, Any]:
        """Get current SDR status including plugin stats"""
        supervisor_stats = self.plugin_supervisor.get_stats() if self.plugin_supervisor else {}

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
            'stats': self.stats.copy(),
            'plugin_supervisor': supervisor_stats,
            'version': '2.0'
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
            logger.info(f"Plugin system: Active with {len(self.plugins)} plugins")

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

        # Clear plugin buffers
        if self.demod_plugin:
            self.demod_plugin.clear_buffer()
        if self.waterfall_plugin:
            self.waterfall_plugin.clear_buffer()

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

        # Enable/disable demodulator plugin
        if mode == 'SPECTRUM':
            self.demod_plugin.enabled = False
        else:
            self.demod_plugin.enabled = True
            self.demod_plugin.set_mode(mode, bandwidth)

        logger.info(f"Demodulation set to {mode}, bandwidth {bandwidth} Hz")
        logger.info(f"Demodulator plugin: {'enabled' if self.demod_plugin.enabled else 'disabled'}")

        return {
            'mode': mode,
            'bandwidth': bandwidth,
            'audio_enabled': mode != 'SPECTRUM'
        }

    async def get_spectrum_data(self) -> Optional[Dict[str, Any]]:
        """
        Get latest spectrum data for WebSocket streaming

        Uses v2.0 plugin supervisor for parallel processing
        """
        try:
            # Get data from queue (non-blocking)
            try:
                samples = self.data_queue.get_nowait()
            except Empty:
                return None

            # Process with plugin supervisor
            start_time = time.time()

            # Prepare data for plugins
            plugin_data = {
                'iq_samples': samples,
                'demod_config': self.demod_config.copy()
            }

            # Run plugins with supervisor (parallel execution)
            results = await self.plugin_supervisor.run_with_supervision(plugin_data)

            processing_time = time.time() - start_time

            # Store results
            self.latest_results = results

            # Update performance stats
            self._update_performance_stats(processing_time)

            # Extract spectrum data from results
            spectrum_data = None
            for result in results:
                if result.success and result.data.get('type') == 'spectrum':
                    spectrum_result = result.data

                    # Build spectrum data response
                    spectrum_data = {
                        'type': 'spectrum',
                        'frequencies': spectrum_result['frequencies'].tolist(),
                        'spectrum': spectrum_result['spectrum_db'].tolist(),
                        'timestamp': datetime.now().isoformat(),
                        'sample_rate': self.current_config['sample_rate'],
                        'center_frequency': self.current_config['center_frequency'],
                        'fft_size': config.fft_size,
                        'metadata': {
                            'gain': self.current_config['gain'],
                            'demod_mode': self.demod_config['mode'],
                            'processing_time_ms': processing_time * 1000,
                            'fps': self.stats['fps'],
                            'plugin_processing_ms': result.execution_time_ms
                        }
                    }
                    break

            return spectrum_data

        except Exception as e:
            logger.error(f"Error processing spectrum data: {e}")
            return None

    async def get_audio_data(self) -> Optional[Dict[str, Any]]:
        """Get latest audio data from demodulator plugin"""
        if not self.demod_plugin.enabled:
            return None

        try:
            # Extract audio data from latest results
            for result in self.latest_results:
                if result.success and result.data.get('type') == 'audio':
                    audio_result = result.data

                    # Check if we have audio samples
                    if 'audio_samples' in audio_result:
                        return {
                            'type': 'audio',
                            'samples': audio_result['audio_samples'].tolist(),
                            'sample_rate': audio_result['metadata']['sample_rate'],
                            'timestamp': datetime.now().isoformat(),
                            'mode': audio_result['mode'],
                            'metadata': {
                                'bandwidth': audio_result['metadata']['bandwidth'],
                                'chunk_size': audio_result.get('chunk_size', 0)
                            }
                        }

            return None

        except Exception as e:
            logger.error(f"Error getting audio data: {e}")
            return None

    def _acquisition_worker(self):
        """Background thread for continuous data acquisition"""
        logger.info("Starting SDR acquisition worker (v2.0 with plugin supervisor)")

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
        logger.info("WebSDR Controller v2.0 cleaned up")
