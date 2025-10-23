# H1SDR - WebSDR for Radio Astronomy & Multi-Band Operations

**Modern WebSDR system with browser interface for hydrogen line astronomy and amateur radio**

<div align="center">

![H1SDR WebSDR](https://img.shields.io/badge/H1SDR-WebSDR-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12%2B-blue?style=flat&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-WebAPI-red?style=flat&logo=fastapi)
![WebGL](https://img.shields.io/badge/WebGL-Visualization-orange?style=flat)
![RTL-SDR](https://img.shields.io/badge/RTL--SDR-Blog%20V4-green?style=flat)

</div>

## Overview

H1SDR combines radio astronomy capabilities with general-purpose WebSDR operation. Built with FastAPI backend and modern web frontend, optimized for real-time spectrum analysis and multi-mode demodulation.
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/d1e3f8ae-b8dc-49c6-8946-8e3d702256f0" />

### Key Features

- **🌐 Web Interface**: Browser-based with WebGL spectrum display
- **📡 Radio Astronomy**: Hydrogen line detection at 1420.405751 MHz  
- **📻 Multi-Band**: 16 preset bands covering amateur, broadcast, ISM
- **⚡ Real-Time**: FFTW-accelerated 4096-point FFT at 20 FPS
- **🎵 Demodulation**: AM/FM/USB/LSB/CW with Web Audio API
- **🔄 Resizable Layout**: Adjustable interface regions

## Architecture

```
RTL-SDR Hardware → FastAPI Backend → WebSocket → Web Frontend
                  (Signal Processing)          (Visualization)
```

**Current Status:**
- ✅ FastAPI backend with WebSocket streaming
- ✅ FFTW-accelerated signal processing  
- ✅ Multi-mode demodulation operational
- ✅ Web interface with resizable layout
- ✅ RTL-SDR Blog V4 support verified

## Requirements

### Hardware
- **RTL-SDR**: Blog V3/V4 recommended (TCXO for stability)
- **Range**: 24 MHz - 1766 MHz
- **Sample Rate**: Up to 2.4 MSPS
- **Computer**: USB 3.0, 4GB+ RAM

### Software  
- **Python 3.12+**
- **Browser**: Chrome/Firefox with WebGL + Web Audio
- **OS**: Linux/Windows/macOS

## Quick Start

### Installation
```bash
git clone https://github.com/Pablomonte/h1sdr.git
cd h1sdr

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Hardware Check
```bash
rtl_test -t
# Expected: RTL-SDR Blog V4 detected
```

### Run WebSDR
```bash
source venv/bin/activate
python -m src.web_sdr.main
# Open browser: http://localhost:8000
```

### Usage
1. Click **"Start SDR"** 
2. Select band from dropdown
3. Choose demod mode (FM for broadcast, SPECTRUM for analysis)
4. Adjust gain and intensity controls

## Band Presets (16 Available)

### Radio Astronomy
- **H1 Line**: 1420.405751 MHz (21cm hydrogen)
- **OH Lines**: 1665.4 MHz, 1667.4 MHz (hydroxyl)

### Amateur Radio
- **HF**: 12m (24.9 MHz), 10m (28.5 MHz) 
- **VHF/UHF**: 6m (51 MHz), 2m (145 MHz), 70cm (435 MHz)

### Broadcast & Utilities
- **FM Broadcast**: 88-108 MHz
- **Aviation**: 118-137 MHz
- **Marine**: 156-162 MHz
- **Weather Satellites**: 137.5 MHz

### ISM Bands
- **433 MHz, 868 MHz, 915 MHz**

## Project Structure

```
h1sdr/
├── src/web_sdr/              # Modern WebSDR
│   ├── main.py              # FastAPI server
│   ├── config.py            # Band presets
│   ├── controllers/         # SDR hardware
│   ├── dsp/                 # Signal processing
│   └── services/            # WebSocket streaming
├── src/h1_receiver.py        # Legacy CLI receiver
├── web/                     # Frontend
│   ├── index.html          # Main interface
│   ├── js/components/      # UI components
│   └── css/                # Styling
├── docs/                    # Documentation
├── tests/                   # Test suite  
└── data/                    # Storage
```

## Radio Astronomy

### Hydrogen Line (21cm)
- **Rest Frequency**: 1420.405751 MHz
- **Doppler Analysis**: `v = c × (f_obs - f_rest) / f_rest`
- **Resolution**: ~586 Hz per FFT bin
- **Applications**: Galactic rotation, ISM mapping

### Observation Setup
1. Select "H1 Line (21cm)" band
2. Set mode to "SPECTRUM"  
3. Gain: 40 dB typical
4. Adjust intensity: Min -80, Max -10 dB
5. Look for emission peaks

## API & Development

### REST Endpoints
```bash
GET  /api/health              # System status
POST /api/sdr/start           # Start acquisition
POST /api/sdr/tune            # Tune frequency
GET  /api/bands               # List presets
POST /api/bands/{key}/tune    # Tune to preset
```

### WebSocket Streams
```javascript
// Spectrum data (20 FPS)
ws://localhost:8000/ws/spectrum

// Audio data (48 kHz)  
ws://localhost:8000/ws/audio

// Data format
{
  "type": "spectrum",
  "frequencies": [...],
  "spectrum": [...],      // dBFS
  "timestamp": 1693785632.123
}
```

## Configuration

### Environment (.env)
```bash
WEBSDR_HOST=127.0.0.1
WEBSDR_PORT=8000
WEBSDR_RTLSDR_DEVICE_INDEX=0
WEBSDR_RTLSDR_SAMPLE_RATE=2400000.0
WEBSDR_FFT_SIZE=4096
WEBSDR_SPECTRUM_FPS=20.0
```

## Troubleshooting

### RTL-SDR Not Found
```bash
lsusb | grep RTL
sudo rmmod dvb_usb_rtl28xxu rtl2832
rtl_test -t
```

### Performance Issues
- Reduce `WEBSDR_FFT_SIZE=2048`
- Lower `WEBSDR_SPECTRUM_FPS=10.0`
- Use USB 3.0 ports
- Check browser console for errors

### No Audio
- Verify mode is not "SPECTRUM"
- Check browser audio permissions
- Try FM broadcast first

## Technical Specs

### Performance
- **Sample Rate**: 2.4 MSPS
- **FFT**: 4096 points, ~586 Hz resolution
- **Update Rate**: 20 FPS
- **Audio**: 48 kHz Web Audio API
- **Latency**: <100ms end-to-end

### Verified Hardware
- ✅ RTL-SDR Blog V4 (Rafael R828D)
- ✅ RTL-SDR Blog V3 (R820T2)

### Browser Support
- ✅ Chrome 90+, Firefox 88+, Edge 90+
- Requires: WebGL 2.0, Web Audio API, WebSocket

## Development

### Setup
```bash
git clone https://github.com/Pablomonte/h1sdr.git
cd h1sdr
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest black flake8
```

### Testing
```bash
pytest tests/ -v
black src/
flake8 src/
```

### Areas for Contribution
- Digital demodulation modes
- Recording/playback features  
- Mobile interface improvements
- Additional SDR hardware support
- Performance optimizations

## License

GNU General Public License v3.0

## Authors

- **Pablo** - System architecture, radio astronomy
- **Claude Code AI** - Web development, documentation

---

<div align="center">

**🌟 Star this repo if H1SDR helps your SDR projects! 🌟**

*Made with ❤️ for the radio astronomy and SDR community*

*Last Updated: September 2025 - Verified against running system*

</div>
