# H1SDR Test Suite

Comprehensive hardware-dependent TDD test suite for H1SDR WebSDR system.

## Overview

This test suite validates the complete H1SDR system using **real RTL-SDR hardware** to ensure authentic testing without mocks. All tests are designed to work with actual radio signals and hardware interfaces.

## Test Modules

### 🔧 `test_rtlsdr_hardware.py`
**RTL-SDR Hardware Detection & Configuration**
- RTL-SDR device detection and enumeration
- Basic configuration (sample rate, frequency, gain)
- Frequency range and tuning accuracy
- Sample acquisition and data format validation
- Streaming stability tests
- WebSDR controller integration

### 📊 `test_dsp_realtime.py` 
**DSP Processing with Real Signals**
- FFT processing with FM broadcast signals
- Spectrum analysis and peak detection
- Demodulation testing (AM/FM/SSB/CW)
- Signal analysis with real data
- Windowing effects and resolution testing
- SNR estimation and dynamic range

### 🌐 `test_websocket_streaming.py`
**WebSocket Streaming & Integration**
- FastAPI endpoint validation
- WebSocket connection and data streaming
- Real-time spectrum data integrity
- Audio streaming with demodulation
- Multiple concurrent client handling
- Complete WebSDR workflow testing

### ⚡ `test_performance_realtime.py`
**Real-time Performance Metrics**
- 20 FPS spectrum streaming verification
- End-to-end latency testing (<100ms target)
- Memory usage stability (~50MB typical)
- Concurrent client performance
- CPU usage under load
- Long-term streaming stability

### 🔒 `test_system_regression.py`
**System Regression & Stability**
- Complete system functionality verification
- All 16 band presets testing
- Demodulation modes validation
- Error handling robustness
- Resource cleanup verification
- Rapid operations stability

## Prerequisites

### Hardware Requirements
- **RTL-SDR Device**: RTL-SDR Blog V3/V4 or compatible
- **USB Connection**: USB 3.0 recommended for stability
- **Antenna**: Connected for signal reception
- **Computer**: 4GB+ RAM, modern CPU

### Software Requirements
- **Python 3.12+** with pip
- **RTL-SDR Library**: `pip install pyrtlsdr`
- **WebSDR Server**: Running at `http://localhost:8000`
- **Dependencies**: All packages from `requirements.txt`

### Signal Environment  
- **FM Broadcast**: 88-108 MHz signals available
- **Amateur Radio**: Local 2m/70cm activity (optional)
- **Aviation**: ATC signals at 118-137 MHz (optional)

## Running Tests

### Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Verify RTL-SDR hardware
rtl_test -t

# Start WebSDR server (in separate terminal)
python -m src.web_sdr.main

# Run complete test suite
python tests/run_all_tests.py
```

### Individual Test Modules
```bash
# Hardware tests only
python -m tests.test_rtlsdr_hardware

# DSP tests only  
python -m tests.test_dsp_realtime

# WebSocket tests only
python -m tests.test_websocket_streaming

# Performance tests only
python -m tests.test_performance_realtime

# Regression tests only
python -m tests.test_system_regression
```

### Using pytest
```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_rtlsdr_hardware.py -v

# With coverage (if pytest-cov installed)
pytest tests/ --cov=src

# Quick tests only (skip long performance tests)
pytest tests/ -m "not slow"
```

### Test Runner Options
```bash
# Complete test suite
python tests/run_all_tests.py

# Specific test group
python tests/run_all_tests.py --test-group hardware
python tests/run_all_tests.py --test-group performance

# Quick mode (skip long tests)
python tests/run_all_tests.py --quick

# Skip dependency checks (if hardware verified)
python tests/run_all_tests.py --skip-hardware --skip-server
```

## Test Results Interpretation

### Success Criteria
- ✅ **Hardware Tests**: RTL-SDR detection, configuration, streaming
- ✅ **DSP Tests**: Spectrum processing, demodulation accuracy
- ✅ **WebSocket Tests**: Real-time streaming, data integrity
- ✅ **Performance Tests**: 20 FPS, <100ms latency, stable memory
- ✅ **Regression Tests**: All core functionality working

### Common Failure Modes

**Hardware Not Detected**
```
❌ RTL-SDR hardware not available: No devices found
```
- Check USB connection
- Verify driver installation: `rtl_test -t`
- Try different USB port (USB 3.0 preferred)

**WebSDR Server Not Running**
```
❌ WebSDR server not accessible: Connection refused
```
- Start server: `python -m src.web_sdr.main`
- Check port availability: `lsof -i :8000`
- Verify no firewall blocking

**Performance Issues**
```
❌ FPS too low: 12.3 FPS (expected >18)
```
- Check CPU load during tests
- Verify USB 3.0 connection
- Close other applications
- Check for dropped samples

**Signal Quality Issues**
```
❌ No signals detected in FM broadcast
```
- Connect antenna properly
- Try different location (away from interference)
- Adjust gain settings
- Check antenna connection

## Development

### Adding New Tests
1. Create test class inheriting from `unittest.TestCase`
2. Add `@classmethod setUpClass(cls)` with RTL-SDR check
3. Use real hardware in `setUp()` method
4. Include teardown for resource cleanup
5. Add to appropriate test runner group

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing  
- **System Tests**: End-to-end functionality
- **Performance Tests**: Real-time metrics validation
- **Regression Tests**: Prevent functionality degradation

### Best Practices
- Always test with real RTL-SDR hardware
- Use actual radio signals (FM, amateur, etc.)
- Verify data integrity and format
- Check performance metrics
- Include proper cleanup
- Handle hardware failures gracefully

## Troubleshooting

### RTL-SDR Issues
```bash
# Reset USB drivers
sudo rmmod dvb_usb_rtl28xxu rtl2832
sudo modprobe rtl2832

# Check permissions
sudo usermod -a -G dialout $USER

# Test basic functionality
rtl_test -s 2.4e6 -d 0 -t
```

### WebSDR Issues
```bash
# Check server status
curl http://localhost:8000/api/health

# View server logs
python -m src.web_sdr.main

# Check port usage
lsof -i :8000
```

### Performance Issues
```bash
# Monitor system resources
htop
free -h

# Check USB throughput
lsusb -t

# Verify sample rate stability
rtl_test -s 2.4e6 -d 0 -t
```

## Expected Test Duration

- **Hardware Tests**: ~30 seconds
- **DSP Tests**: ~60 seconds
- **WebSocket Tests**: ~45 seconds  
- **Performance Tests**: ~3-5 minutes
- **Regression Tests**: ~2 minutes

**Total Suite**: ~6-8 minutes

## CI/CD Integration

For automated testing with hardware:

```yaml
# Example GitHub Actions (if hardware available)
- name: Setup RTL-SDR
  run: |
    sudo apt install rtl-sdr librtlsdr-dev
    rtl_test -t

- name: Run Hardware Tests
  run: |
    python tests/run_all_tests.py --test-group hardware
```

---

*Tests designed to prevent regressions and ensure H1SDR reliability with real hardware*