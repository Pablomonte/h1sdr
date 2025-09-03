#!/usr/bin/env python3
"""
H1 Line Receiver - Main receiver script for hydrogen line observations
"""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from rtlsdr import RtlSdr
from scipy import signal as scipy_signal
from scipy.ndimage import uniform_filter1d

# Import new visualization module
try:
    from .visualization import create_visualization_manager
except ImportError:
    from visualization import create_visualization_manager

# Constants
H1_FREQUENCY = 1420.405751e6  # Hz - Hydrogen line rest frequency
SPEED_OF_LIGHT = 299792458.0  # m/s

class H1Receiver:
    def __init__(self, device_index=0, sample_rate=2.4e6, center_freq=H1_FREQUENCY, 
                 gain=40, ppm_correction=0, use_pyqtgraph=True):
        """
        Initialize the H1 line receiver with optimized visualization
        
        Args:
            device_index: RTL-SDR device index
            sample_rate: Sample rate in Hz
            center_freq: Center frequency in Hz
            gain: RF gain in dB (0-50, or 'auto')
            ppm_correction: Frequency correction in ppm
            use_pyqtgraph: Use PyQtGraph for high-performance visualization
        """
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.center_freq = center_freq
        self.gain = gain
        self.ppm_correction = ppm_correction
        self.use_pyqtgraph = use_pyqtgraph
        
        self.sdr = None
        self.running = False
        
        # Data buffers
        self.power_history = []
        self.spectrum_accumulator = None
        self.integration_count = 0
        
        # Visualization manager
        self.vis_manager = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_sdr(self):
        """Configure the RTL-SDR device with optimized settings"""
        try:
            self.sdr = RtlSdr(device_index=self.device_index)
            
            # Configure sampling parameters first
            self.sdr.sample_rate = self.sample_rate
            self.sdr.center_freq = self.center_freq
            
            # Optimize USB buffer settings for better performance
            # Buffer size should be multiple of 512 and adequate for sample rate
            buffer_size = max(65536, int(self.sample_rate * 0.1))  # 100ms of samples minimum
            buffer_size = (buffer_size + 511) // 512 * 512  # Round up to nearest 512
            
            try:
                self.sdr.set_direct_sampling(0)  # Disable direct sampling
                self.sdr.set_offset_tuning(False)  # Standard tuning
                self.sdr.set_bandwidth(int(self.sample_rate * 0.8))  # 80% of sample rate
                self.logger.info(f"Optimized buffer size: {buffer_size} samples ({buffer_size/self.sample_rate*1000:.1f}ms)")
            except AttributeError:
                # Some methods might not be available in all pyrtlsdr versions
                self.logger.warning("Some optimization methods not available in this pyrtlsdr version")
            
            # Set frequency correction if non-zero
            if self.ppm_correction != 0:
                try:
                    self.sdr.freq_correction = self.ppm_correction
                except Exception as e:
                    self.logger.warning(f"Could not set PPM correction to {self.ppm_correction}: {e}")
                    self.logger.info("Continuing without frequency correction")
            
            # Configure gain settings
            if self.gain == 'auto':
                self.sdr.gain = 'auto'
            else:
                self.sdr.gain = self.gain
            
            # Store optimized buffer size for later use
            self._optimal_buffer_size = buffer_size
                
            self.logger.info(f"RTL-SDR configured with optimizations:")
            self.logger.info(f"  Sample rate: {self.sample_rate/1e6:.2f} MHz")
            self.logger.info(f"  Center frequency: {self.center_freq/1e6:.4f} MHz")
            self.logger.info(f"  Gain: {self.gain} dB")
            self.logger.info(f"  Buffer size: {self._optimal_buffer_size} samples")
            
        except Exception as e:
            self.logger.error(f"Failed to setup RTL-SDR: {e}")
            raise
            
    def calculate_doppler_velocity(self, observed_freq):
        """
        Calculate radial velocity from Doppler shift
        
        Args:
            observed_freq: Observed frequency in Hz
            
        Returns:
            Radial velocity in km/s
        """
        delta_f = observed_freq - H1_FREQUENCY
        velocity = (delta_f / H1_FREQUENCY) * SPEED_OF_LIGHT
        return velocity / 1000  # Convert to km/s
        
    def process_samples(self, samples, fft_size=2048):
        """
        Process IQ samples to extract spectrum with optimized performance
        
        Args:
            samples: Complex IQ samples
            fft_size: FFT size for spectrum calculation
            
        Returns:
            frequencies: Frequency array in Hz
            spectrum: Power spectrum in dB
        """
        # Ensure we have enough samples, pad with zeros if needed
        if len(samples) < fft_size:
            padded_samples = np.zeros(fft_size, dtype=np.complex64)
            padded_samples[:len(samples)] = samples
            samples = padded_samples
        elif len(samples) > fft_size:
            # Use only first fft_size samples for consistent processing
            samples = samples[:fft_size]
        
        # Apply window to reduce spectral leakage (pre-compute window for efficiency)
        if not hasattr(self, '_window') or len(self._window) != fft_size:
            self._window = np.blackman(fft_size).astype(np.float32)
        
        windowed_samples = samples * self._window
        
        # Calculate FFT with optimized data types
        fft_result = np.fft.fftshift(np.fft.fft(windowed_samples))
        
        # Calculate power spectrum more efficiently
        power_spectrum = np.abs(fft_result) ** 2
        spectrum = 10 * np.log10(power_spectrum + 1e-10)  # Power spectrum in dB
        
        # Generate frequency array (cache if same fft_size)
        if not hasattr(self, '_frequencies') or len(self._frequencies) != fft_size:
            self._frequencies = np.fft.fftshift(np.fft.fftfreq(fft_size, 1/self.sample_rate))
            self._frequencies += self.center_freq
        
        return self._frequencies.copy(), spectrum

    def process_samples_batch(self, samples_list, fft_size=2048):
        """
        Process multiple sample chunks efficiently in batch mode
        
        Args:
            samples_list: List of complex IQ sample arrays
            fft_size: FFT size for spectrum calculation
            
        Returns:
            frequencies: Frequency array in Hz
            spectra: List of power spectra in dB
        """
        if not samples_list:
            return None, []
        
        # Pre-compute window and frequency array once
        if not hasattr(self, '_window') or len(self._window) != fft_size:
            self._window = np.blackman(fft_size).astype(np.float32)
        
        if not hasattr(self, '_frequencies') or len(self._frequencies) != fft_size:
            self._frequencies = np.fft.fftshift(np.fft.fftfreq(fft_size, 1/self.sample_rate))
            self._frequencies += self.center_freq
        
        spectra = []
        for samples in samples_list:
            # Process each sample chunk
            if len(samples) < fft_size:
                padded_samples = np.zeros(fft_size, dtype=np.complex64)
                padded_samples[:len(samples)] = samples
                samples = padded_samples
            elif len(samples) > fft_size:
                samples = samples[:fft_size]
            
            windowed_samples = samples * self._window
            fft_result = np.fft.fftshift(np.fft.fft(windowed_samples))
            power_spectrum = np.abs(fft_result) ** 2
            spectrum = 10 * np.log10(power_spectrum + 1e-10)
            spectra.append(spectrum)
        
        return self._frequencies.copy(), spectra
        
    def integrate_spectrum(self, spectrum, reset=False):
        """
        Integrate spectrum over time for improved SNR
        
        Args:
            spectrum: Current spectrum
            reset: Reset the accumulator
            
        Returns:
            Integrated spectrum
        """
        if reset or self.spectrum_accumulator is None:
            self.spectrum_accumulator = spectrum.copy()
            self.integration_count = 1
        else:
            self.spectrum_accumulator += spectrum
            self.integration_count += 1
            
        return self.spectrum_accumulator / self.integration_count
        
    def baseline_correction(self, spectrum, order=3):
        """
        Remove baseline from spectrum using polynomial fitting
        
        Args:
            spectrum: Input spectrum
            order: Polynomial order for baseline fit
            
        Returns:
            Baseline-corrected spectrum
        """
        # Identify channels outside the expected H1 line region
        # (typically +/- 200 kHz around line center)
        freq_indices = np.arange(len(spectrum))
        center_idx = len(spectrum) // 2
        line_width_idx = int(200e3 / (self.sample_rate / len(spectrum)))  # 200 kHz in indices
        
        # Mask for baseline regions (excluding line)
        baseline_mask = np.ones(len(spectrum), dtype=bool)
        baseline_mask[center_idx - line_width_idx:center_idx + line_width_idx] = False
        
        # Fit polynomial to baseline regions
        if np.sum(baseline_mask) > order + 1:
            coeffs = np.polyfit(freq_indices[baseline_mask], spectrum[baseline_mask], order)
            baseline = np.polyval(coeffs, freq_indices)
            corrected = spectrum - baseline
        else:
            corrected = spectrum
            
        return corrected
        
    def save_observation(self, frequencies, spectrum, metadata=None):
        """
        Save observation data to file
        
        Args:
            frequencies: Frequency array
            spectrum: Spectrum data
            metadata: Additional metadata dict
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/raw/h1_observation_{timestamp}.npz"
        
        Path("data/raw").mkdir(parents=True, exist_ok=True)
        
        save_data = {
            'frequencies': frequencies,
            'spectrum': spectrum,
            'timestamp': timestamp,
            'center_freq': self.center_freq,
            'sample_rate': self.sample_rate,
            'gain': self.gain,
            'integration_time': self.integration_count * len(spectrum) / self.sample_rate
        }
        
        if metadata:
            save_data.update(metadata)
            
        np.savez(filename, **save_data)
        self.logger.info(f"Observation saved to {filename}")
        
    def run_observation(self, duration=60, integration_time=10, fft_size=2048, 
                       plot_realtime=True):
        """
        Run observation session with threaded visualization and optimized sampling
        
        Args:
            duration: Total observation duration in seconds
            integration_time: Integration time per spectrum in seconds
            fft_size: FFT size for spectrum calculation
            plot_realtime: Show real-time plot using high-performance visualization
        """
        self.running = True
        self.setup_sdr()
        
        # Use optimized buffer size
        samples_per_read = getattr(self, '_optimal_buffer_size', 
                                 max(65536, int(self.sample_rate * 0.05)))  # 50ms minimum
        
        # Ensure buffer size is practical for real-time processing
        max_buffer = int(self.sample_rate * 0.2)  # Max 200ms
        samples_per_read = min(samples_per_read, max_buffer)
        
        chunk_time = samples_per_read / self.sample_rate
        chunks_per_integration = max(1, int(integration_time / chunk_time))
        
        self.logger.info(f"Starting H1SDR observation with optimized parameters:")
        self.logger.info(f"  Samples per read: {samples_per_read} ({chunk_time*1000:.1f}ms)")
        self.logger.info(f"  Chunks per integration: {chunks_per_integration}")
        self.logger.info(f"  Actual integration time: {chunks_per_integration * chunk_time:.2f}s")
        self.logger.info(f"  Duration: {duration}s")
        
        # Initialize visualization if requested
        if plot_realtime:
            try:
                self.vis_manager = create_visualization_manager(
                    use_pyqtgraph=self.use_pyqtgraph,
                    update_rate_ms=50  # 20 FPS max
                )
                self.vis_manager.start("H1SDR - Real-time Spectrum")
                self.logger.info("High-performance visualization started")
            except Exception as e:
                self.logger.warning(f"Could not start visualization: {e}")
                self.vis_manager = None
            
        start_time = time.time()
        integration_counter = 0
        last_save_time = start_time
        
        try:
            while self.running and (time.time() - start_time) < duration:
                # Read samples with error handling
                try:
                    samples = self.sdr.read_samples(samples_per_read)
                except Exception as e:
                    self.logger.error(f"Error reading samples: {e}")
                    time.sleep(0.001)  # Brief pause before retry
                    continue
                
                # Calculate spectrum
                frequencies, spectrum = self.process_samples(samples, fft_size)
                
                # Integrate spectrum
                integrated_spectrum = self.integrate_spectrum(
                    spectrum, 
                    reset=(integration_counter == 0)
                )
                
                integration_counter += 1
                
                # Process integrated spectrum
                if integration_counter >= chunks_per_integration:
                    # Apply baseline correction
                    corrected_spectrum = self.baseline_correction(integrated_spectrum)
                    
                    # Update visualization (non-blocking, thread-safe)
                    if self.vis_manager is not None:
                        metadata = {
                            'center_freq': self.center_freq,
                            'sample_rate': self.sample_rate,
                            'gain': self.gain,
                            'integration_time': chunks_per_integration * chunk_time
                        }
                        self.vis_manager.update_spectrum(frequencies, corrected_spectrum, metadata)
                    
                    # Save periodically (every 60 seconds approximately)
                    current_time = time.time()
                    if current_time - last_save_time >= 60.0:
                        self.save_observation(frequencies, corrected_spectrum)
                        last_save_time = current_time
                    
                    # Reset counter
                    integration_counter = 0
                    
                # Progress reporting (less frequent to avoid spam)
                if integration_counter == 0:  # Report only after each integration
                    elapsed = time.time() - start_time
                    remaining = duration - elapsed
                    progress_pct = (elapsed / duration) * 100
                    self.logger.info(f"Progress: {elapsed:.1f}s / {duration}s "
                                   f"({progress_pct:.1f}%) - remaining: {remaining:.1f}s")
                
        except KeyboardInterrupt:
            self.logger.info("Observation interrupted by user")
        finally:
            # Clean shutdown
            if self.vis_manager is not None:
                self.vis_manager.stop()
                self.vis_manager = None
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.sdr:
            self.sdr.close()
            self.logger.info("RTL-SDR device closed")
        if self.vis_manager is not None:
            self.vis_manager.stop()
            self.vis_manager = None
            
    def signal_handler(self, signum, frame):
        """Handle interrupt signals"""
        self.logger.info("Received interrupt signal, stopping...")
        self.running = False


def main():
    parser = argparse.ArgumentParser(description='H1 Line Receiver for RTL-SDR')
    parser.add_argument('--device', type=int, default=0, help='RTL-SDR device index')
    parser.add_argument('--frequency', type=float, default=H1_FREQUENCY,
                       help='Center frequency in Hz (default: 1420.4057 MHz)')
    parser.add_argument('--rate', type=float, default=2.4e6,
                       help='Sample rate in Hz (default: 2.4 MHz)')
    parser.add_argument('--gain', type=float, default=40,
                       help='RF gain in dB (0-50, default: 40)')
    parser.add_argument('--ppm', type=float, default=0,
                       help='Frequency correction in ppm')
    parser.add_argument('--duration', type=int, default=300,
                       help='Observation duration in seconds (default: 300)')
    parser.add_argument('--integration', type=float, default=10,
                       help='Integration time in seconds (default: 10)')
    parser.add_argument('--fft-size', type=int, default=2048,
                       help='FFT size (default: 2048)')
    parser.add_argument('--no-plot', action='store_true',
                       help='Disable real-time plotting')
    parser.add_argument('--use-matplotlib', action='store_true',
                       help='Use matplotlib instead of PyQtGraph for visualization')
    
    args = parser.parse_args()
    
    # Create receiver instance
    receiver = H1Receiver(
        device_index=args.device,
        sample_rate=args.rate,
        center_freq=args.frequency,
        gain=args.gain,
        ppm_correction=args.ppm,
        use_pyqtgraph=not args.use_matplotlib
    )
    
    # Setup signal handler
    signal.signal(signal.SIGINT, receiver.signal_handler)
    
    # Run observation
    receiver.run_observation(
        duration=args.duration,
        integration_time=args.integration,
        fft_size=args.fft_size,
        plot_realtime=not args.no_plot
    )


if __name__ == '__main__':
    main()