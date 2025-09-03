# H1SDR User Guide

## Quick Start

1. **Start Server**: `python -m src.web_sdr.main`
2. **Open Browser**: http://localhost:8000
3. **Click "Start SDR"** to initialize hardware
4. **Select Band** from dropdown or enter frequency
5. **Choose Demod Mode** (FM for broadcast, SPECTRUM for analysis)

## Interface Controls

### Hardware
- **Gain**: 0-50 dB RF gain
- **Device**: RTL-SDR selection

### Tuning
- **Band Dropdown**: 16 presets
- **Manual Frequency**: Direct entry in MHz
- **Click Spectrum**: Instant tune

### Demodulation
- **SPECTRUM**: Visual only, no audio
- **FM**: Broadcast/narrowband FM
- **AM**: Aviation, shortwave
- **USB/LSB**: Amateur SSB
- **CW**: Morse code

### Display
- **Intensity**: Min/Max dB sliders
- **Zoom**: Spectrum magnification
- **Waterfall**: Time-frequency display

## Radio Astronomy Mode

### Hydrogen Line (1420.405751 MHz)
1. Select "H1 Line (21cm)" band
2. Set gain to 40 dB
3. Use SPECTRUM mode
4. Adjust intensity: Min -80, Max -10
5. Look for peaks indicating H1 emission

### Doppler Analysis
```
Velocity = c × (f_observed - 1420.405751) / 1420.405751
```
- Redshift: Receding sources
- Blueshift: Approaching sources

## Amateur Radio

### FM Repeaters (2m Band)
1. Select "2m Band (144-148 MHz)"
2. Mode: FM
3. Click on repeater signals in spectrum

### SSB Operation
1. Select amateur band (10m, 6m, etc.)
2. Mode: USB (>10 MHz) or LSB (<10 MHz)
3. Fine-tune for natural voice

## Tips & Tricks

### Best Reception
- Use outdoor antenna
- Add LNA for weak signals
- Allow 10min warmup for stability
- Minimize cable length

### Performance
- Lower FFT size if laggy
- Reduce FPS for slow connections
- Use USB 3.0 ports only
- Close unused browser tabs

### Recording (CLI)
```bash
# Record raw IQ
rtl_sdr -f 100e6 -s 2.4e6 recording.iq

# Play back
cat recording.iq | python analyze.py
```

## Keyboard Shortcuts

- **Space**: Start/Stop SDR
- **↑/↓**: Adjust frequency
- **←/→**: Adjust gain
- **M**: Mute audio
- **F**: Fullscreen spectrum

## Common Frequencies

### Broadcast
- **FM Radio**: 88-108 MHz
- **Aviation**: 118-137 MHz
- **Marine**: 156-162 MHz

### Satellites
- **NOAA 15**: 137.620 MHz
- **NOAA 18**: 137.9125 MHz
- **NOAA 19**: 137.100 MHz
- **ISS**: 145.800 MHz

### Amateur Calling
- **2m FM**: 146.520 MHz
- **70cm FM**: 446.000 MHz
- **10m SSB**: 28.400 MHz

## Troubleshooting

### No Signals
- Check antenna connection
- Increase gain
- Try FM broadcast first
- Verify RTL-SDR detected

### Overload/Distortion
- Reduce gain
- Add bandpass filter
- Move away from transmitters

### Audio Issues
- Not in SPECTRUM mode
- Check browser volume
- Allow audio permissions

## Advanced Usage

### Custom Bands
Edit `src/web_sdr/config.py`:
```python
'custom_band': {
    'name': 'My Band',
    'center_freq': 150e6,
    'bandwidth': 2.4e6,
    'typical_gain': 30
}
```

### API Control
```python
import requests

# Tune programmatically
requests.post('http://localhost:8000/api/sdr/tune', 
              json={'frequency': 145e6, 'gain': 30})
```