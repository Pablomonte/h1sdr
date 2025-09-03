# H1SDR API Reference

## Base URL
```
http://localhost:8000
```

## REST Endpoints

### System
- `GET /api/health` - System health check
- `GET /api/sdr/status` - SDR device status

### SDR Control
- `POST /api/sdr/start` - Start SDR (params: device_index)
- `POST /api/sdr/stop` - Stop SDR
- `POST /api/sdr/tune` - Tune frequency/gain (params: frequency, gain)
- `GET /api/sdr/config` - Get configuration
- `POST /api/sdr/config` - Update configuration
- `POST /api/sdr/bandwidth` - Set sample rate

### Bands
- `GET /api/bands` - List all bands
- `GET /api/bands/{band_key}` - Get band info
- `POST /api/bands/{band_key}/tune` - Tune to band

### Demodulation
- `GET /api/modes` - List demod modes
- `POST /api/demod/set` - Set mode (params: mode, bandwidth)

## WebSocket Endpoints

### `/ws/spectrum`
Real-time FFT data (20 FPS)
```json
{
  "type": "spectrum",
  "frequencies": [...],
  "spectrum": [...],
  "timestamp": 1693785632.123
}
```

### `/ws/audio`
Demodulated audio (48 kHz)
```json
{
  "type": "audio",
  "samples": [...],
  "sample_rate": 48000
}
```

### `/ws/waterfall`
Waterfall data (currently disabled)

## Band Keys

### Radio Astronomy
- `h1_line` - 1420.405751 MHz
- `oh_1665` - 1665.4018 MHz
- `oh_1667` - 1667.359 MHz

### Amateur Radio
- `12m_band` - 24.94 MHz
- `10m_band` - 28.5 MHz
- `6m_band` - 51 MHz
- `2m_band` - 145 MHz
- `70cm_band` - 435 MHz

### Others
- `fm_broadcast` - 100 MHz
- `aviation` - 125 MHz
- `marine` - 160 MHz
- `weather_satellite` - 137.5 MHz
- `ism_433/868/915` - ISM bands

## Demod Modes
- `SPECTRUM` - No demod
- `AM` - 6 kHz default
- `FM` - 15 kHz default
- `USB/LSB` - 2.7 kHz
- `CW` - 500 Hz + BFO

## Quick Examples

```javascript
// Start SDR
fetch('/api/sdr/start', {method: 'POST'})

// Tune to 2m band
fetch('/api/bands/2m_band/tune', {method: 'POST'})

// Connect spectrum
const ws = new WebSocket('ws://localhost:8000/ws/spectrum')
ws.onmessage = (e) => console.log(JSON.parse(e.data))
```