# H1SDR Development

## Setup

```bash
git clone https://github.com/usuario/h1sdr.git
cd h1sdr
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest black flake8
```

## Project Structure

```
src/web_sdr/
├── main.py           # FastAPI app
├── config.py         # Settings & bands
├── controllers/      # Hardware control
├── dsp/             # Signal processing
└── services/        # WebSocket mgmt

web/
├── index.html       # UI interface
├── js/              # Frontend logic
└── css/             # Styling
```

## Key Files

- **main.py**: API endpoints, WebSocket handlers
- **sdr_controller.py**: RTL-SDR interface
- **spectrum.py**: FFT processing
- **demodulator.py**: AM/FM/SSB demod
- **websocket_service.py**: Client management

## Adding Features

### New Band
```python
# src/web_sdr/config.py
EXTENDED_RADIO_BANDS['new_band'] = {
    'name': 'New Band',
    'center_freq': 150e6,
    'bandwidth': 2.4e6,
    'typical_gain': 30,
    'modes': ['FM', 'AM']
}
```

### New API Endpoint
```python
# src/web_sdr/main.py
@app.post("/api/custom/action")
async def custom_action(param: str):
    result = await sdr_controller.custom_method(param)
    return {"success": True, "data": result}
```

### New Demod Mode
```python
# src/web_sdr/dsp/demodulator.py
def demod_custom(iq_samples, params):
    # Process IQ samples
    return audio_samples
```

## Testing

```bash
# Run tests
pytest tests/

# Specific module
pytest tests/test_dsp.py -v

# With coverage
pytest --cov=src tests/
```

### Test Hardware
```python
# tests/test_hardware.py
def test_rtlsdr_detection():
    from rtlsdr import RtlSdr
    sdr = RtlSdr()
    assert sdr.valid_gains_db is not None
    sdr.close()
```

## Code Style

```bash
# Format code
black src/ tests/

# Check style
flake8 src/ --max-line-length=100

# Type checking
mypy src/
```

## WebSocket Protocol

### Adding Stream Type
```python
# New data stream
async def broadcast_custom(self, data):
    message = json.dumps({
        "type": "custom",
        "data": data,
        "timestamp": time.time()
    })
    await self._broadcast(self.custom_clients, message)
```

## Frontend Development

### Spectrum Rendering
```javascript
// web/js/spectrum.js
class SpectrumDisplay {
    render(data) {
        const canvas = this.canvas;
        const ctx = canvas.getContext('2d');
        // Draw spectrum using data.frequencies and data.spectrum
    }
}
```

### WebSocket Client
```javascript
// Connect to new stream
const ws = new WebSocket('ws://localhost:8000/ws/custom');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    processCustomData(data);
};
```

## Performance Profiling

```bash
# CPU profiling
python -m cProfile -o profile.stats src/web_sdr/main.py

# Memory profiling
pip install memory_profiler
python -m memory_profiler src/web_sdr/main.py
```

## Debugging

### Enable Debug Mode
```bash
# .env
WEBSDR_DEBUG=true
WEBSDR_RELOAD=true
```

### WebSocket Debug
```javascript
// Browser console
ws = new WebSocket('ws://localhost:8000/ws/spectrum');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

### RTL-SDR Debug
```python
import logging
logging.basicConfig(level=logging.DEBUG)
# Shows all RTL-SDR operations
```

## Contributing

### Branch Strategy
```bash
git checkout -b feature/new-feature
# Make changes
git commit -m "Add new feature"
git push origin feature/new-feature
```

### Commit Style
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `perf:` Performance
- `refactor:` Code restructure

### PR Requirements
1. Tests pass (`pytest`)
2. Code formatted (`black`)
3. No linting errors (`flake8`)
4. Documentation updated
5. Tested with real hardware

## Build & Release

### Version Update
```python
# src/web_sdr/__init__.py
__version__ = "1.1.0"
```

### Create Release
```bash
git tag -a v1.1.0 -m "Release version 1.1.0"
git push origin v1.1.0
```

### Docker Build
```bash
docker build -t h1sdr:latest .
docker run -p 8000:8000 --device /dev/bus/usb h1sdr:latest
```

## Resources

- [RTL-SDR API](https://pyrtlsdr.readthedocs.io/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [WebSocket Guide](https://websockets.readthedocs.io/)
- [DSP Theory](https://dspguide.com/)