# H1SDR Architecture

## System Overview

```
RTL-SDR → FastAPI Backend → WebSocket → Web Frontend
         (Signal Processing)           (Visualization)
```

## Core Components

### Hardware Layer
- **RTL-SDR Interface**: Device control via pyrtlsdr
- **Supported**: RTL-SDR Blog V3/V4, generic RTL2832U
- **Sample Rate**: 2.4 MSPS (24 MHz - 1766 MHz range)

### Backend (FastAPI)
```
src/web_sdr/
├── main.py              # FastAPI app, WebSocket endpoints
├── config.py            # 16 band presets, configuration
├── controllers/         # SDR hardware control
├── dsp/                 # FFTW processing, demodulation
└── services/            # WebSocket management
```

### Frontend (Web)
```
web/
├── index.html          # Main interface
├── js/                 # WebGL spectrum, audio player
├── css/                # Responsive styling
└── static/             # Assets
```

## Data Flow

1. **IQ Samples**: RTL-SDR → 8192 sample buffer
2. **FFT Processing**: 4096-point FFTW @ 20 FPS
3. **WebSocket Stream**: JSON spectrum/audio data
4. **Visualization**: WebGL canvas rendering

## Key Features

### Signal Processing
- **FFT**: 4096 points, ~586 Hz resolution
- **Demodulation**: AM, FM, USB, LSB, CW
- **Audio**: 48 kHz Web Audio API output

### Performance
- **Latency**: <100ms end-to-end
- **Connections**: 10 spectrum, 5 audio max
- **Memory**: ~50MB typical usage

### Configuration
```python
# Environment variables (.env)
WEBSDR_HOST=127.0.0.1
WEBSDR_PORT=8000
WEBSDR_RTLSDR_DEVICE_INDEX=0
WEBSDR_RTLSDR_SAMPLE_RATE=2400000.0
WEBSDR_FFT_SIZE=4096
WEBSDR_SPECTRUM_FPS=20.0
```

## WebSocket Protocol

**Spectrum Data:**
```json
{
  "type": "spectrum",
  "frequencies": [array],
  "spectrum": [dBFS_array],
  "timestamp": unix_time
}
```

**Audio Data:**
```json
{
  "type": "audio",
  "samples": [float32_array],
  "sample_rate": 48000
}
```

## Deployment

### Development
```bash
source venv/bin/activate
python -m src.web_sdr.main
```

### Production
```bash
uvicorn src.web_sdr.main:app --host 0.0.0.0 --port 8000
```

### Systemd Service
```ini
[Service]
ExecStart=/opt/h1sdr/venv/bin/python -m src.web_sdr.main
WorkingDirectory=/opt/h1sdr
Restart=always
```