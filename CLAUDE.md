# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

H1SDR is an advanced WebSDR system combining radio astronomy capabilities with multi-band amateur radio operations. The project features:
- **Modern WebSDR Interface**: Browser-based operation with resizable layout and WebGL visualization
- **Radio Astronomy**: Specialized for hydrogen line detection at 1420.405751 MHz
- **Multi-Band SDR**: 16 preset bands for amateur radio, broadcast, satellites
- **Real-Time Processing**: FastAPI backend with WebSocket streaming
- **Advanced Demodulation**: AM/FM/SSB/CW with Web Audio API integration
- **High-Performance DSP**: FFTW-accelerated spectrum processing

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify RTL-SDR hardware
rtl_test -t
```

### Running the System
```bash
# Start WebSDR server (primary interface)
python -m src.web_sdr.main
# Access at: http://localhost:8000

# Legacy hydrogen line receiver (CLI)
python src/h1_receiver.py --gain 40 --integration 10

# With custom parameters
python src/h1_receiver.py --frequency 1420.4e6 --rate 2.4e6 --duration 600

# GNU Radio flowgraph (offline processing)
gnuradio-companion src/flowgraphs/h1_line_receiver.grc
```

### Testing
```bash
# Run all tests
pytest tests/

# Run specific test module
pytest tests/test_signal_processing.py -v

# Run with coverage
pytest --cov=src tests/
```

### WebSDR Usage
```bash
# Start web server
source venv/bin/activate
python -m src.web_sdr.main

# Test API endpoints
curl http://localhost:8000/api/health
curl http://localhost:8000/api/bands

# Legacy data processing
python scripts/process_observations.py data/raw/*.npz
python scripts/export_fits.py data/processed/observation.npz
```

## Architecture

### Core Components

1. **WebSDR Frontend** (`web/`)
   - Modern HTML5/WebGL interface
   - Real-time spectrum and waterfall displays
   - Web Audio API for demodulation playback
   - Responsive design for desktop and mobile

2. **FastAPI Backend** (`src/web_sdr/`)
   - Async web server with WebSocket streaming
   - RESTful API for SDR control and band management
   - Real-time data processing and distribution
   - 16+ preset bands for various radio services

3. **Signal Processing Pipeline** (`src/web_sdr/dsp/`)
   - FFTW-accelerated spectrum processing
   - Multi-mode demodulation (AM/FM/SSB/CW)
   - Advanced filtering and AGC algorithms
   - Real-time audio synthesis

4. **Legacy Components** (maintained for compatibility)
   - CLI hydrogen receiver (`src/h1_receiver.py`)
   - GNU Radio integration (`src/flowgraphs/`)
   - Custom blocks (`src/blocks/`) for offline processing
   - Historical implementations in `archive/`

### Key Algorithms

- **Doppler Shift**: `v = c * (f_obs - f_rest) / f_rest`
- **Integration**: Vector averaging of FFT bins over time
- **Baseline Correction**: Polynomial fitting excluding line region
- **RFI Mitigation**: Statistical outlier detection and flagging

## Technical Specifications

### Hardware Requirements
- RTL-SDR with TCXO for frequency stability
- Minimum 2.4 MSPS sample rate capability
- LNA with <1dB noise figure recommended
- SAW filter centered at 1420 MHz (optional)

### WebSDR Parameters
- Default FFT size: 4096 bins (configurable)
- Frequency resolution: ~586 Hz @ 2.4 MSPS
- Spectrum update rate: 20 FPS (configurable)
- Integration time: 1-3600 seconds (astronomy mode)
- Audio sample rate: 48 kHz (Web Audio API)
- WebSocket streaming: Real-time binary protocol

### Data Formats
- **WebSocket Protocol**: Binary streaming for spectrum/waterfall/audio
- **API Responses**: JSON with Pydantic validation
- **Raw IQ**: Complex float32 arrays (legacy support)
- **Spectra**: Float64 arrays with frequency axis
- **Export Formats**: CSV, FITS, PNG (planned)
- **Configuration**: Environment variables and .env files

## WebSDR Architecture Details

### Frontend Components (`web/`)
- **index.html**: Main interface with all controls
- **js/components/**: Spectrum display, waterfall, audio controls
- **js/services/**: WebSocket client, audio service
- **css/**: Modern styling with dark/light themes

### Backend Components (`src/web_sdr/`)
- **main.py**: FastAPI application entry point
- **controllers/**: SDR device management
- **dsp/**: Signal processing and demodulation
- **services/**: WebSocket management and streaming
- **models/**: Pydantic data validation models

### Legacy GNU Radio (Maintained)
- **Flowgraphs**: `src/flowgraphs/` for offline processing
- **Custom blocks**: `src/blocks/` for specialized DSP
- **Archive**: Previous iterations in `archive/legacy_*`

## Debugging and Troubleshooting

### Common Issues

1. **RTL-SDR not found**
   ```bash
   # Check device connection
   lsusb | grep RTL
   # Reset USB permissions
   sudo rmmod dvb_usb_rtl28xxu rtl2832
   ```

2. **Frequency drift**
   - Measure and apply PPM correction
   - Allow 10-minute warmup for TCXO stabilization

3. **Low SNR**
   - Increase integration time
   - Check LNA power and connections
   - Verify antenna pointing and polarization

### Performance Monitoring
```bash
# Monitor CPU usage during acquisition
htop

# Check USB throughput
cat /sys/kernel/debug/usb/devices | grep -A 5 "RTL"

# Memory usage
watch -n 1 free -h
```

## Development Priorities

### Completed Features ✅
- Web-based interface with real-time visualization
- Multi-band preset system (16 bands)
- WebSocket streaming architecture
- Multi-mode demodulation (AM/FM/SSB/CW)
- FastAPI backend with comprehensive API
- Resizable layout with intensity controls

### Future Development Areas
- Recording functionality (IQ and audio)
- Advanced RFI rejection algorithms
- FITS export with WCS headers for astronomy
- Mobile app companion
- Multi-receiver correlation
- Machine learning signal classification
- Integration with astronomy software (CASA, etc.)