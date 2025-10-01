# Frequency Control Fixes - Session Summary

## Problem
Frequency controls were incoherent - display would show 0.000 MHz, 24.000 MHz, or other incorrect values. Multiple competing state variables caused synchronization issues.

## Root Causes Identified

### 1. Multiple Competing State Variables
- `currentFrequency` (local variable in MHz)
- `window.currentFrequency` (global in Hz)
- `window.H1SDR_spectrum.centerFrequency` (should be single source of truth)

### 2. Missing Initialization
- `window.H1SDR_spectrum.centerFrequency` not initialized at startup
- `getCurrentFrequency()` returning `undefined`, leading to NaN propagation
- `Math.max(24, NaN) = 24` forced frequency to minimum

### 3. Duplicate Polling Loop
- `setInterval` polling every 2 seconds overwriting display
- No validation on polled values
- Competing with event-driven updates

### 4. WebSocket Not Updating Display
- WebSocket updated `centerFrequency` but didn't call `updateFrequencyDisplay()`
- Input field showed stale/incorrect values

## Solutions Implemented

### 1. Single Source of Truth Pattern
**File**: `/home/pablo/repos/h1sdr/web/js/init.js`

Created `getCurrentFrequency()` helper:
```javascript
function getCurrentFrequency() {
    const freq = window.H1SDR_spectrum?.centerFrequency || window.currentFrequency || 100e6;
    return (typeof freq === 'number' && !isNaN(freq) && freq > 0) ? freq : 100e6;
}
```

### 2. Robust Validation
Added validation in `updateFrequencyDisplay()`:
```javascript
function updateFrequencyDisplay(freqHz) {
    if (typeof freqHz !== 'number' || isNaN(freqHz) || freqHz <= 0) {
        console.warn('Invalid frequency provided:', freqHz);
        return;
    }
    // ... update display
}
```

### 3. Event-Driven Updates
Removed duplicate `setInterval` polling (lines 1755-1757). Now purely event-driven:
- User input triggers update
- API responses trigger update
- WebSocket data triggers update
- Band selection triggers update

### 4. WebSocket Display Sync
Added `updateFrequencyDisplay()` call when spectrum data arrives:
```javascript
if (data.center_frequency && window.H1SDR_spectrum) {
    window.H1SDR_spectrum.centerFrequency = data.center_frequency;
    if (window.updateFrequencyDisplay) {
        window.updateFrequencyDisplay(data.center_frequency);
    }
}
```

### 5. Initialization
Added default values to `window.H1SDR_spectrum` object:
```javascript
window.H1SDR_spectrum = {
    // ... other properties
    centerFrequency: 100e6,  // Default 100 MHz
    sampleRate: 2.4e6,       // Default 2.4 MHz
};
```

## Verification

Created Playwright automation tool for testing:
- **Tool**: `/home/pablo/repos/h1sdr/tools/websdr_automator.py`
- **Test**: `/home/pablo/repos/h1sdr/tools/test_frequency_control.py`

### Test Results ✅
```
📻 Setting frequency to 24.0000 MHz
   Input field shows: 24.0000 MHz ✅
   Spectrum display: 24.0000 MHz ✅

📻 Setting frequency to 100.0000 MHz
   Input field shows: 100.0000 MHz ✅
   Spectrum display: 100.0000 MHz ✅

📻 Setting frequency to 1420.4000 MHz
   Input field shows: 1420.4000 MHz ✅
   Spectrum display: 1420.4000 MHz ✅

Final frequency: 1420.4000 MHz
✅ Frequency stayed stable!
```

## Architecture Improvements

### Before
- 3 competing frequency variables
- Polling-based updates every 2 seconds
- No validation pipeline
- WebSocket and UI out of sync

### After
- Single source of truth: `window.H1SDR_spectrum.centerFrequency`
- Event-driven architecture
- Validation at every entry point
- WebSocket, API, and UI synchronized

## Testing Tools

### Playwright Automator
Full-featured automation class for WebSDR testing:
- Browser control (headless/headed)
- Frequency control methods
- Mode selection (SPEC/FM/AM/USB/LSB/CW)
- Band selection
- Frequency scanning
- Screenshot/HTML capture for debugging
- Verification methods

### Usage Example
```python
from websdr_automator import WebSDRAutomator

with WebSDRAutomator(headless=False) as sdr:
    sdr.set_frequency(100.0)  # Tune to 100 MHz
    input_freq = sdr.get_frequency()
    spectrum_freq = sdr.get_spectrum_frequency()
    assert abs(input_freq - 100.0) < 0.001
```

## Lessons Learned

1. **Single Source of Truth is Critical**: Multiple state variables ALWAYS lead to synchronization bugs
2. **Validate Everything**: NaN propagation can cause bizarre behavior
3. **Event-Driven > Polling**: Polling creates race conditions
4. **Test Automation Pays Off**: Playwright caught regressions immediately
5. **WebSocket Bidirectionality**: Both sides must update UI state

## Related Files Modified

- `/home/pablo/repos/h1sdr/web/js/init.js` - Main frequency control logic
- `/home/pablo/repos/h1sdr/tools/websdr_automator.py` - Testing automation
- `/home/pablo/repos/h1sdr/tools/test_frequency_control.py` - Verification test

## Status
✅ **RESOLVED** - All frequency control issues fixed and verified
