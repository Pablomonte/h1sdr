"""
Pydantic models for SDR-related data structures
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
import numpy as np

class SDRStatus(BaseModel):
    """SDR device status"""
    connected: bool
    device_index: Optional[int] = None
    sample_rate: Optional[float] = None
    center_frequency: Optional[float] = None
    gain: Optional[float] = None
    ppm_correction: Optional[int] = None
    running: bool = False
    
class SDRConfig(BaseModel):
    """SDR configuration parameters"""
    device_index: int = Field(default=0, ge=0, le=10)
    sample_rate: float = Field(default=2.4e6, gt=0, le=3.2e6)
    center_frequency: float = Field(default=100e6, gt=0, le=2000e6)
    gain: Union[float, str] = Field(default=40.0)
    ppm_correction: int = Field(default=0, ge=-1000, le=1000)
    
    @validator('gain')
    def validate_gain(cls, v):
        if isinstance(v, str) and v != 'auto':
            raise ValueError('gain must be a number or "auto"')
        if isinstance(v, (int, float)) and not (0 <= v <= 50):
            raise ValueError('gain must be between 0 and 50 dB')
        return v

class FrequencyTuneRequest(BaseModel):
    """Request model for frequency tuning"""
    frequency: float = Field(gt=0, le=2000e6, description="Frequency in Hz")
    gain: Optional[float] = Field(default=None, ge=0, le=50, description="Gain in dB")
    
class DemodulationRequest(BaseModel):
    """Request model for demodulation settings"""
    mode: str = Field(description="Demodulation mode")
    bandwidth: Optional[int] = Field(default=None, gt=0, le=200000, description="Bandwidth in Hz")
    
    @validator('mode')
    def validate_mode(cls, v):
        valid_modes = ['AM', 'FM', 'USB', 'LSB', 'CW', 'SPECTRUM']
        if v.upper() not in valid_modes:
            raise ValueError(f'mode must be one of {valid_modes}')
        return v.upper()

class SpectrumData(BaseModel):
    """Spectrum data for WebSocket transmission"""
    type: str = "spectrum"
    frequencies: List[float] = Field(description="Frequency array in Hz")
    spectrum: List[float] = Field(description="Power spectrum in dB")
    timestamp: datetime
    sample_rate: float
    center_frequency: float
    fft_size: int
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            np.ndarray: lambda v: v.tolist()
        }

class AudioData(BaseModel):
    """Audio data for WebSocket transmission"""
    type: str = "audio"
    samples: List[float] = Field(description="Audio samples")
    sample_rate: int = Field(default=48000, description="Audio sample rate")
    timestamp: datetime
    mode: str = Field(description="Demodulation mode")
    metadata: Optional[Dict[str, Any]] = None

class WaterfallData(BaseModel):
    """Waterfall line data for WebSocket transmission"""
    type: str = "waterfall_line"
    frequencies: List[float]
    spectrum: List[float]
    timestamp: datetime
    
class BandInfo(BaseModel):
    """Radio band information"""
    key: str
    name: str
    center_freq: float
    bandwidth: float
    description: str
    typical_gain: float
    integration_time: float
    modes: List[str]
    category: str
    
class APIResponse(BaseModel):
    """Generic API response wrapper"""
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class WebSocketMessage(BaseModel):
    """Generic WebSocket message"""
    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    
class PerformanceStats(BaseModel):
    """Performance statistics"""
    fps: float
    cpu_usage: float
    memory_usage: float
    active_connections: int
    spectrum_clients: int
    audio_clients: int
    waterfall_clients: int
    total_samples_processed: int
    average_processing_time: float