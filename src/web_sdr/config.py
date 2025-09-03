"""
Configuration module for WebSDR
Centralized configuration management
"""

import os
from typing import Dict, Any, List
from pydantic_settings import BaseSettings

class WebSDRConfig(BaseSettings):
    """Configuration settings for WebSDR application"""
    
    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True
    reload: bool = True
    
    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]
    cors_credentials: bool = True
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]
    
    # RTL-SDR settings
    rtlsdr_device_index: int = 0
    rtlsdr_sample_rate: float = 2.4e6
    rtlsdr_default_freq: float = 100e6
    rtlsdr_default_gain: float = 40.0
    rtlsdr_ppm_correction: int = 0
    
    # DSP settings
    fft_size: int = 4096  # Increased for better resolution
    spectrum_fps: float = 20.0
    waterfall_height: int = 1000
    audio_sample_rate: int = 48000
    
    # WebSocket settings
    websocket_ping_interval: int = 30
    websocket_ping_timeout: int = 10
    max_spectrum_clients: int = 10
    max_audio_clients: int = 5
    
    # Performance settings
    buffer_size: int = 8192
    worker_threads: int = 2
    
    class Config:
        env_file = ".env"
        env_prefix = "WEBSDR_"

# Global configuration instance
config = WebSDRConfig()

# Extended radio bands configuration with detailed specifications
EXTENDED_RADIO_BANDS: Dict[str, Dict[str, Any]] = {
    # Radioastronomía
    'h1_line': {
        'name': 'H1 Line (21cm)',
        'center_freq': 1420.405751e6,
        'bandwidth': 2.4e6,
        'description': 'Neutral hydrogen line at 21cm',
        'typical_gain': 40,
        'integration_time': 10,
        'modes': ['SPECTRUM'],
        'category': 'radioastronomy'
    },
    'oh_1665': {
        'name': 'OH Line 1665 MHz',
        'center_freq': 1665.4018e6,
        'bandwidth': 2.4e6,
        'description': 'Hydroxyl radical line',
        'typical_gain': 40,
        'integration_time': 5,
        'modes': ['SPECTRUM'],
        'category': 'radioastronomy'
    },
    'oh_1667': {
        'name': 'OH Line 1667 MHz', 
        'center_freq': 1667.3590e6,
        'bandwidth': 2.4e6,
        'description': 'Hydroxyl radical line',
        'typical_gain': 40,
        'integration_time': 5,
        'modes': ['SPECTRUM'],
        'category': 'radioastronomy'
    },
    
    # Broadcast
    'fm_broadcast': {
        'name': 'FM Broadcast',
        'center_freq': 100e6,
        'bandwidth': 20e6,
        'description': 'FM broadcast band (88-108 MHz)',
        'typical_gain': 20,
        'integration_time': 1,
        'modes': ['FM', 'SPECTRUM'],
        'category': 'broadcast'
    },
    # Note: AM Broadcast (0.5-1.7 MHz) removed - below RTL-SDR range (24-1766 MHz)
    
    # Radioaficionados HF - Only bands >= 24 MHz (RTL-SDR compatible)
    # Note: 160m, 80m, 40m, 30m, 20m, 17m, 15m bands removed - below RTL-SDR range
    '12m_band': {
        'name': '12m Band',
        'center_freq': 24.94e6,
        'bandwidth': 100e3,
        'description': '12 meter amateur band (24.89-24.99 MHz)',
        'typical_gain': 35,
        'integration_time': 2,
        'modes': ['USB', 'CW', 'SPECTRUM'],
        'category': 'amateur_hf'
    },
    '10m_band': {
        'name': '10m Band',
        'center_freq': 28.5e6,
        'bandwidth': 1.7e6,
        'description': '10 meter amateur band (28.0-29.7 MHz)',
        'typical_gain': 35,
        'integration_time': 2,
        'modes': ['USB', 'CW', 'FM', 'SPECTRUM'],
        'category': 'amateur_hf'
    },
    
    # Radioaficionados VHF/UHF
    '6m_band': {
        'name': '6m Band',
        'center_freq': 51e6,
        'bandwidth': 4e6,
        'description': '6 meter amateur band (50-54 MHz)',
        'typical_gain': 30,
        'integration_time': 1,
        'modes': ['USB', 'CW', 'FM', 'SPECTRUM'],
        'category': 'amateur_vhf'
    },
    '2m_band': {
        'name': '2m Band',
        'center_freq': 145e6,
        'bandwidth': 4e6,
        'description': '2 meter amateur band (144-148 MHz)',
        'typical_gain': 30,
        'integration_time': 1,
        'modes': ['FM', 'USB', 'CW', 'SPECTRUM'],
        'category': 'amateur_vhf'
    },
    '70cm_band': {
        'name': '70cm Band',
        'center_freq': 435e6,
        'bandwidth': 30e6,
        'description': '70cm amateur band (420-450 MHz)',
        'typical_gain': 30,
        'integration_time': 1,
        'modes': ['FM', 'USB', 'CW', 'SPECTRUM'],
        'category': 'amateur_uhf'
    },
    
    # Digital modes - Note: HF digital modes removed (below 24 MHz RTL-SDR range)
    # FT8 and WSPR on 20m/40m bands are below RTL-SDR frequency range
    
    # Utilities
    'aviation': {
        'name': 'Aviation',
        'center_freq': 125e6,
        'bandwidth': 25e6,
        'description': 'Aviation communications (118-137 MHz)',
        'typical_gain': 30,
        'integration_time': 1,
        'modes': ['AM', 'SPECTRUM'],
        'category': 'utility'
    },
    'marine': {
        'name': 'Marine VHF',
        'center_freq': 160e6,
        'bandwidth': 5e6,
        'description': 'Marine VHF communications',
        'typical_gain': 30,
        'integration_time': 1,
        'modes': ['FM', 'SPECTRUM'],
        'category': 'utility'
    },
    'weather_satellite': {
        'name': 'Weather Satellite',
        'center_freq': 137.5e6,
        'bandwidth': 1e6,
        'description': 'NOAA weather satellites (137-138 MHz)',
        'typical_gain': 30,
        'integration_time': 1,
        'modes': ['FM', 'SPECTRUM'],
        'category': 'satellite'
    },
    'ism_433': {
        'name': 'ISM 433 MHz',
        'center_freq': 433.92e6,
        'bandwidth': 2e6,
        'description': 'ISM band at 433 MHz',
        'typical_gain': 30,
        'integration_time': 1,
        'modes': ['FM', 'SPECTRUM'],
        'category': 'ism'
    },
    'ism_868': {
        'name': 'ISM 868 MHz',
        'center_freq': 868e6,
        'bandwidth': 10e6,
        'description': 'European ISM band at 868 MHz',
        'typical_gain': 30,
        'integration_time': 1,
        'modes': ['FM', 'SPECTRUM'],
        'category': 'ism'
    },
    'ism_915': {
        'name': 'ISM 915 MHz',
        'center_freq': 915e6,
        'bandwidth': 26e6,
        'description': 'US ISM band at 915 MHz',
        'typical_gain': 30,
        'integration_time': 1,
        'modes': ['FM', 'SPECTRUM'],
        'category': 'ism'
    },
    
    # Test signals
    'aircraft_test': {
        'name': 'Aircraft (Test)',
        'center_freq': 118e6,
        'bandwidth': 2.4e6,
        'description': 'Aircraft communications (strong test signals)',
        'typical_gain': 25,
        'integration_time': 1,
        'modes': ['AM', 'SPECTRUM'],
        'category': 'test'
    }
}

# Demodulation modes configuration
DEMOD_MODES = {
    'AM': {
        'name': 'Amplitude Modulation',
        'bandwidth_default': 6000,  # Hz
        'bandwidth_min': 2000,
        'bandwidth_max': 15000,
        'audio_filter': True
    },
    'FM': {
        'name': 'Frequency Modulation',
        'bandwidth_default': 15000,
        'bandwidth_min': 8000,
        'bandwidth_max': 200000,
        'audio_filter': True
    },
    'USB': {
        'name': 'Upper Sideband',
        'bandwidth_default': 2700,
        'bandwidth_min': 1500,
        'bandwidth_max': 4000,
        'audio_filter': True
    },
    'LSB': {
        'name': 'Lower Sideband', 
        'bandwidth_default': 2700,
        'bandwidth_min': 1500,
        'bandwidth_max': 4000,
        'audio_filter': True
    },
    'CW': {
        'name': 'Continuous Wave',
        'bandwidth_default': 500,
        'bandwidth_min': 100,
        'bandwidth_max': 1000,
        'audio_filter': True,
        'tone_frequency': 600  # Hz BFO tone
    },
    'SPECTRUM': {
        'name': 'Spectrum Only',
        'bandwidth_default': 2400000,
        'bandwidth_min': 10000,
        'bandwidth_max': 2400000,
        'audio_filter': False
    }
}