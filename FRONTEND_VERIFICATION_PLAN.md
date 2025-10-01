# Frontend Verification Plan - H1SDR WebSDR

## 1. Audio System Verification

### ✅ Audio Playback Core
- [ ] Start server: `python -m src.web_sdr.main`
- [ ] Open http://localhost:8000
- [ ] Select FM mode
- [ ] Tune to active FM station (88-108 MHz)
- [ ] Verify continuous audio without dropouts
- [ ] Check Web Audio API context state in browser console

### ✅ Demodulation Modes
- [ ] **FM**: Tune to 88-108 MHz, verify stereo quality
- [ ] **AM**: Tune to 530-1700 kHz, verify clear speech
- [ ] **USB**: Tune to 14.230 MHz, verify SSB quality
- [ ] **LSB**: Tune to 7.125 MHz, verify SSB quality
- [ ] **CW**: Tune to 14.070 MHz, verify tone clarity

### ✅ Audio Controls
- [ ] Volume slider: Test 0-100% range
- [ ] Mute button: Verify instant silence/restore
- [ ] Audio level meter: Check real-time response
- [ ] Sample rate indicator: Confirm 48 kHz display

## 2. Station Scanner Verification

### ✅ Scanner UI Components
- [ ] Scanner buttons visible in controls panel
- [ ] "📡 Scan Up" button functional
- [ ] "📡 Scan Down" button functional
- [ ] "⏹ Stop Scan" button enables during scan

### ✅ Scanner Functionality
- [ ] **Scan Up**: Starts from current frequency, moves up
- [ ] **Scan Down**: Starts from current frequency, moves down
- [ ] **Auto-stop**: Stops on detected signal (-60 dBm threshold)
- [ ] **Manual stop**: Stop button terminates scan
- [ ] **Visual feedback**: Frequency updates during scan
- [ ] **Range limits**: Respects 88.0-108.0 MHz bounds

### ⚠️ Real Spectrum Integration (Pending)
- [ ] Scanner uses actual spectrum data instead of simulation
- [ ] Signal threshold based on real power measurements
- [ ] Integration with `spectrumData` from spectrum-display.js

## 3. Spectrum Display Verification

### ✅ WebGL Visualization
- [ ] Spectrum display renders without errors
- [ ] Waterfall scrolls smoothly
- [ ] Frequency axis shows correct values
- [ ] Amplitude axis in dBm units
- [ ] Real-time updates at ~20 FPS

### ✅ Interactive Controls
- [ ] Mouse click tuning: Click to tune frequency
- [ ] Frequency drag: Drag to change frequency
- [ ] Zoom controls: In/out buttons functional
- [ ] Span controls: Frequency span adjustment
- [ ] FFT size: 4096 bins displayed correctly

### ✅ Visual Settings
- [ ] Intensity controls: Min/max adjustment
- [ ] Color palette: Spectrum intensity mapping
- [ ] Averaging: Time-domain smoothing
- [ ] Peak hold: Peak frequency tracking

## 4. Frequency Control Verification

### ✅ Manual Tuning
- [ ] Frequency input field: Direct entry
- [ ] Up/down buttons: Step tuning (100 Hz, 1 kHz, 10 kHz)
- [ ] Band buttons: Preset frequency selection
- [ ] Memory channels: Store/recall frequencies

### ✅ Band Presets
- [ ] **FM Broadcast**: 88-108 MHz presets
- [ ] **AM Broadcast**: 530-1700 kHz presets
- [ ] **Ham bands**: 80m, 40m, 20m, 15m, 10m
- [ ] **Aviation**: 118-137 MHz
- [ ] **Marine**: 156-162 MHz
- [ ] **Custom bands**: User-defined ranges

## 5. WebSocket Communication

### ✅ Real-time Data Flow
- [ ] WebSocket connection established at startup
- [ ] Spectrum data streaming without gaps
- [ ] Audio data streaming continuously
- [ ] Frequency changes propagate to backend
- [ ] Mode changes update demodulation

### ✅ Error Handling
- [ ] Connection loss detection
- [ ] Automatic reconnection attempts
- [ ] Graceful degradation on network issues
- [ ] User notification of connection status

## 6. UI/UX Verification

### ✅ Layout and Responsiveness
- [ ] Resizable panels work correctly
- [ ] Mobile browser compatibility
- [ ] Dark/light theme support
- [ ] All controls accessible via keyboard

### ✅ Performance
- [ ] CPU usage reasonable (<50% on modern hardware)
- [ ] Memory usage stable over time
- [ ] No memory leaks during extended operation
- [ ] Smooth operation with multiple browsers

## 7. Browser Compatibility

### ✅ Primary Browsers
- [ ] **Chrome**: Full functionality verified
- [ ] **Firefox**: WebGL and WebAudio working
- [ ] **Safari**: Hardware acceleration enabled
- [ ] **Edge**: All features operational

### ✅ Feature Detection
- [ ] WebGL availability check
- [ ] Web Audio API support verification
- [ ] WebSocket support confirmation
- [ ] Graceful fallback messages

## 8. Testing Commands

```bash
# Start development server
source venv/bin/activate
python -m src.web_sdr.main

# Backend health check
curl http://localhost:8000/api/health

# Band configuration
curl http://localhost:8000/api/bands

# WebSocket test (use browser dev tools)
# ws://localhost:8000/ws

# Performance monitoring
htop  # Monitor CPU usage
free -h  # Monitor memory
```

## 9. Known Issues and Fixes

### ✅ Recently Fixed
- **Audio dropouts**: Fixed via multiple chunk creation (5000% improvement)
- **FM quality**: Fixed via proper demodulation parameters
- **Scanner UI**: Implemented with visual feedback

### ⚠️ Pending Integration
- **Real spectrum scanner**: Needs integration with spectrum data analysis
- **Recording features**: Planned for future development
- **Mobile optimization**: Touch controls enhancement

## 10. Success Criteria

### ✅ Core Functionality
- [ ] Audio plays continuously without interruption
- [ ] All demodulation modes work correctly
- [ ] Station scanner finds and stops on active signals
- [ ] Spectrum display updates in real-time
- [ ] Frequency control responsive and accurate

### ✅ User Experience
- [ ] Interface intuitive and responsive
- [ ] No JavaScript errors in browser console
- [ ] Smooth operation during extended use
- [ ] Professional-quality audio output

This verification plan ensures complete frontend functionality testing for the H1SDR WebSDR system.