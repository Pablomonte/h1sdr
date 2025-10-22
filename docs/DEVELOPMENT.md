# H1SDR Development Guide (v2.0)

**Architecture:** Plugin-Supervisor Pattern
**Version:** 2.0.0
**Python:** 3.8+

---

## Setup

```bash
git clone https://github.com/usuario/h1sdr.git
cd h1sdr
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest black flake8 pytest-asyncio
```

## Project Structure (v2.0)

```
src/web_sdr/
├── main_v2.py                    # FastAPI app (v2.0 entry point)
├── config.py                     # Settings & bands
├── controllers/
│   └── sdr_controller_v2.py      # Hardware control with error recovery
├── pipeline/
│   ├── plugin_supervisor.py      # Plugin orchestration (fan-out)
│   └── base_plugin.py           # Plugin base class
├── plugins/
│   ├── spectrum_plugin.py       # Spectrum generation
│   ├── waterfall_plugin.py      # Waterfall generation
│   └── demodulator_plugin.py    # Audio demodulation
├── dsp/
│   ├── fft_processor.py         # Multi-threaded FFTW
│   ├── spectrum_processor.py    # Spectrum analysis
│   └── demodulators.py          # AM/FM/SSB/CW
├── services/
│   └── websocket_service.py     # Client management
└── utils/
    ├── error_handler.py         # Centralized error handling
    ├── logging_config.py        # Structured logging
    └── config_manager.py        # Runtime configuration

web/
├── index.html                   # UI interface
├── js/
│   ├── robust-websocket.js     # Auto-reconnect WebSocket
│   ├── components/             # UI components
│   └── services/               # WebSocket/audio services
└── css/                        # Styling

tests/
├── unit/                       # Unit tests
├── integration/                # Integration tests
│   ├── test_websocket_reconnect.py
│   └── test_stability_short.py
└── manual/                     # Manual test scripts

tools/
├── profile_dsp.py              # Performance profiler
└── analyze_logs.py             # Log analysis
```

## Key Files (v2.0)

### Core System
- **[main_v2.py](../src/web_sdr/main_v2.py)**: FastAPI app, API endpoints, WebSocket handlers
- **[sdr_controller_v2.py](../src/web_sdr/controllers/sdr_controller_v2.py)**: RTL-SDR interface with error recovery
- **[plugin_supervisor.py](../src/web_sdr/pipeline/plugin_supervisor.py)**: Plugin orchestration (fan-out parallel execution)

### DSP Pipeline
- **[fft_processor.py](../src/web_sdr/dsp/fft_processor.py)**: Multi-threaded FFTW (4 threads)
- **[spectrum_processor.py](../src/web_sdr/dsp/spectrum_processor.py)**: FFT analysis and scaling
- **[demodulators.py](../src/web_sdr/dsp/demodulators.py)**: AM/FM/SSB/CW demodulation

### Plugins
- **[spectrum_plugin.py](../src/web_sdr/plugins/spectrum_plugin.py)**: Spectrum data generation
- **[waterfall_plugin.py](../src/web_sdr/plugins/waterfall_plugin.py)**: Waterfall data (optional)
- **[demodulator_plugin.py](../src/web_sdr/plugins/demodulator_plugin.py)**: Audio demodulation (optional)

### Infrastructure
- **[error_handler.py](../src/web_sdr/utils/error_handler.py)**: Centralized error handling with retry
- **[logging_config.py](../src/web_sdr/utils/logging_config.py)**: Structured logging system
- **[config_manager.py](../src/web_sdr/utils/config_manager.py)**: Runtime configuration updates

### Frontend
- **[robust-websocket.js](../web/js/robust-websocket.js)**: Auto-reconnecting WebSocket client
- **[websocket_service.py](../src/web_sdr/services/websocket_service.py)**: Server-side client management

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

### Creating a Plugin (v2.0)

Plugins run in parallel with 100% error isolation. Create a new plugin by inheriting from `BasePlugin`:

```python
# src/web_sdr/plugins/my_plugin.py
from src.web_sdr.pipeline.base_plugin import BasePlugin
from typing import Dict, Any, Optional
import numpy as np

class MyPlugin(BasePlugin):
    """
    Custom plugin for processing spectrum data

    All plugins must implement:
    - __init__(): Initialize plugin
    - process(): Process data (must be thread-safe)
    - get_stats(): Return plugin statistics
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="MyPlugin", enabled=enabled)
        self.custom_state = {}

    def process(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process data from context

        Args:
            context: Dictionary with 'spectrum', 'frequencies', 'timestamp', etc.

        Returns:
            Dictionary with processed data or None if nothing to output
        """
        if not self.enabled:
            return None

        try:
            # Get input data
            spectrum = context.get('spectrum')
            frequencies = context.get('frequencies')

            # Process data
            result = self._custom_processing(spectrum, frequencies)

            # Return output
            return {
                'type': 'my_data',
                'data': result,
                'timestamp': context.get('timestamp')
            }

        except Exception as e:
            # Errors are caught by supervisor
            raise

    def _custom_processing(self, spectrum, frequencies):
        # Your custom logic here
        return processed_data

    def get_stats(self) -> Dict[str, Any]:
        """Return custom statistics"""
        stats = super().get_stats()
        stats['custom_metric'] = len(self.custom_state)
        return stats
```

**Register Plugin:**
```python
# src/web_sdr/main_v2.py
from src.web_sdr.plugins.my_plugin import MyPlugin

# Add to plugin list
supervisor = PluginSupervisor([
    SpectrumPlugin(),
    WaterfallPlugin(),
    MyPlugin(enabled=True)  # Add your plugin
])
```

**Plugin Guidelines:**
- Plugins run in **ThreadPoolExecutor** (use thread-safe operations)
- Process time budget: ~40ms per plugin (20 FPS target)
- Errors in one plugin **DO NOT** affect others (100% isolation)
- Use `self.enabled` to allow runtime enable/disable
- Return `None` if plugin has no output for this cycle

## Testing

### Run Tests
```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Specific test
pytest tests/integration/test_websocket_reconnect.py -v

# With coverage
pytest --cov=src tests/
```

### WebSocket Reconnect Test (v2.0)
```bash
# Automated test (requires server running on :8000)
python -m pytest tests/integration/test_websocket_reconnect.py -v

# Tests:
# - Initial connection
# - Reconnection after disconnect
# - Multiple concurrent connections
# - Rapid reconnections (simulated exponential backoff)
```

### Stability Test (v2.0)
```bash
# 10-minute stability test
python tests/integration/test_stability_short.py

# Collects metrics every 30s:
# - CPU usage
# - Memory usage
# - Server health
# - Plugin stats (executions, failures, failure rate)

# Results saved to: /tmp/h1sdr_stability_short.jsonl
```

### Manual Tests
```bash
# Browser-based tests (with server running)
firefox web/manual_tests/test_continuous.html
firefox web/manual_tests/test_reconnect.html
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

### Test Plugin (v2.0)
```python
# tests/unit/test_plugins.py
import pytest
from src.web_sdr.plugins.spectrum_plugin import SpectrumPlugin

def test_spectrum_plugin():
    plugin = SpectrumPlugin(enabled=True)

    context = {
        'spectrum': np.random.rand(4096),
        'frequencies': np.linspace(144e6, 146e6, 4096),
        'timestamp': time.time()
    }

    result = plugin.process(context)

    assert result is not None
    assert result['type'] == 'spectrum'
    assert 'data' in result

def test_plugin_error_isolation():
    """Verify errors in one plugin don't affect others"""
    from src.web_sdr.pipeline.plugin_supervisor import PluginSupervisor

    class BrokenPlugin(BasePlugin):
        def process(self, context):
            raise ValueError("Intentional error")

    supervisor = PluginSupervisor([
        SpectrumPlugin(),
        BrokenPlugin(enabled=True)
    ])

    # BrokenPlugin fails, but SpectrumPlugin should still work
    results = supervisor.process_all(context)

    assert 'spectrum' in results  # SpectrumPlugin succeeded
    # BrokenPlugin failure is logged but doesn't crash system
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

## Error Handling (v2.0)

The v2.0 error handler provides automatic retry, categorization, and logging:

### Using Error Handler
```python
from src.web_sdr.utils.error_handler import error_handler, handle_errors

# Automatic retry with exponential backoff
result = await error_handler.retry_async(
    risky_async_function,
    arg1, arg2,
    max_retries=3,
    context="Fetching SDR data"
)

# Decorator for automatic error handling
@handle_errors("Processing spectrum data")
async def process_spectrum(data):
    # If this raises, it's automatically logged with context
    return process(data)

# Error statistics
stats = error_handler.get_error_stats()
print(f"Total errors: {stats['total_errors']}")
print(f"By category: {stats['by_category']}")
```

### Custom Exceptions
```python
from src.web_sdr.utils.error_handler import (
    HardwareError, NetworkError, ProcessingError
)

# Raise categorized errors
if not sdr.is_connected():
    raise HardwareError(
        "RTL-SDR device not found",
        severity=ErrorSeverity.CRITICAL,
        recoverable=False
    )

# Network errors (auto-retry friendly)
if websocket_closed:
    raise NetworkError(
        "WebSocket connection lost",
        recoverable=True  # Will trigger retry
    )
```

## Structured Logging (v2.0)

Per-component log levels with structured output:

### Setup Logging
```python
from src.web_sdr.utils.logging_config import setup_logging, get_logger
from pathlib import Path

# Initialize logging system
log_config = setup_logging(
    log_dir=Path("logs"),           # None for console-only
    console_level="INFO",            # DEBUG, INFO, WARNING, ERROR
    enable_json=True,                # Enable JSON log for analysis
    component_levels={
        'controllers': 'DEBUG',      # Per-component levels
        'plugins': 'INFO',
        'dsp': 'WARNING'
    }
)

# Get logger with context
logger = get_logger(__name__, {'plugin': 'SpectrumPlugin'})
logger.info("Processing data")
# Output: [2025-10-22 10:30:45.123] [INFO    ] [plugins.spectrum       ] Processing data | plugin=SpectrumPlugin
```

### Change Log Levels at Runtime
```python
# Increase verbosity for debugging
log_config.set_component_level('controllers', logging.DEBUG)

# List all components
components = log_config.list_components()
# {'controllers': 'DEBUG', 'plugins': 'INFO', ...}
```

### Log File Rotation
- Main log: `logs/h1sdr.log` (10 MB per file, 5 backups)
- JSON log: `logs/h1sdr.jsonl` (10 MB per file, 3 backups)
- Automatic rotation when size limit reached

## Configuration Management (v2.0)

Runtime configuration updates with validation:

### Using Config Manager
```python
from src.web_sdr.utils.config_manager import ConfigManager
from src.web_sdr.config import WebSDRConfig

config = WebSDRConfig()
manager = ConfigManager(config)

# Add validator
def validate_fft_size(value):
    return value in [1024, 2048, 4096, 8192]

manager.add_validator('fft_size', validate_fft_size)

# Update config at runtime
if manager.set('fft_size', 4096):
    print("FFT size updated to 4096")
else:
    print("Invalid FFT size")

# Register callback for changes
def on_fft_change(old_value, new_value):
    print(f"FFT changed: {old_value} → {new_value}")
    # Reinitialize FFT processor...

manager.register_callback('fft_size', on_fft_change)

# Rollback to previous value
if not working_correctly:
    manager.rollback('fft_size')

# Save configuration
manager.save_config(Path("config.json"))
```

## Performance Profiling

### DSP Profiler (v2.0)
```bash
# Run comprehensive DSP profiler
python tools/profile_dsp.py

# Output:
# FFT Processor:      0.03 ms (33,828 FPS) ✅
# Spectrum Processor: 42.3 ms (23.7 FPS)   🟡
# Plugin Supervisor:  47.5 ms (21.1 FPS)   🟡
# End-to-End:         50.2 ms (19.9 FPS)   🟡 99.5% of target

# Detailed profiling with cProfile
python tools/profile_dsp.py --cprofile

# Custom sample count
python tools/profile_dsp.py --samples 1000
```

### Traditional Profiling
```bash
# CPU profiling
python -m cProfile -o profile.stats src/web_sdr/main_v2.py

# Analyze results
python -m pstats profile.stats
>>> sort cumtime
>>> stats 20

# Memory profiling
pip install memory_profiler
python -m memory_profiler src/web_sdr/main_v2.py
```

### Monitor Performance in Production
```bash
# Check plugin stats
curl http://localhost:8000/api/plugins | jq '.data[] | {name, success_rate, avg_processing_time_ms}'

# Check system health
curl http://localhost:8000/api/health | jq '.plugin_supervisor'
# {
#   "total_executions": 12345,
#   "total_failures": 0,
#   "failure_rate": 0.0
# }
```

## Debugging

### Enable Debug Mode (v2.0)
```bash
# Start with debug logging
python -m src.web_sdr.main_v2 --debug

# Or via environment variable
export WEBSDR_DEBUG=true
export WEBSDR_RELOAD=true  # Auto-reload on code changes
python -m src.web_sdr.main_v2
```

### Component-Level Debugging
```python
# Enable DEBUG for specific components
from src.web_sdr.utils.logging_config import setup_logging

setup_logging(
    console_level="INFO",
    component_levels={
        'controllers.sdr_controller_v2': 'DEBUG',  # Verbose SDR logs
        'pipeline.plugin_supervisor': 'DEBUG',     # Plugin execution
        'plugins': 'DEBUG',                        # All plugins verbose
        'dsp.fft_processor': 'INFO'                # Normal FFT logs
    }
)
```

### WebSocket Debug (v2.0)
```javascript
// Browser console
const ws = new RobustWebSocket('ws://localhost:8000/ws/spectrum');

// Log all messages
ws.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    console.log(`[${data.type}]`, data);

    if (data.metadata) {
        console.log(`Performance: ${data.metadata.processing_time_ms}ms @ ${data.metadata.fps} FPS`);
    }
});

// Monitor connection events
ws.addEventListener('open', () => console.log('✓ Connected'));
ws.addEventListener('close', () => console.log('✗ Disconnected'));
ws.addEventListener('error', (e) => console.error('Error:', e));
```

### Plugin Debugging
```python
# Check plugin stats
import requests
response = requests.get('http://localhost:8000/api/plugins')
plugins = response.json()['data']

for plugin in plugins:
    print(f"{plugin['name']}:")
    print(f"  Enabled: {plugin['enabled']}")
    print(f"  Calls: {plugin['stats']['call_count']}")
    print(f"  Success rate: {plugin['stats']['success_rate']}%")
    print(f"  Avg time: {plugin['stats']['avg_processing_time_ms']:.2f}ms")
```

### Error History
```python
# View error history
from src.web_sdr.utils.error_handler import error_handler

stats = error_handler.get_error_stats()
print(f"Total errors: {stats['total_errors']}")
print(f"By category: {stats['by_category']}")

# View recent errors for a specific category
hardware_errors = error_handler.error_history.get('hardware:HardwareError', [])
for error in hardware_errors[-5:]:  # Last 5 errors
    print(f"[{error['timestamp']}] {error['message']}")
```

### RTL-SDR Debug
```python
# Enable verbose RTL-SDR logging
import logging
logging.getLogger('rtlsdr').setLevel(logging.DEBUG)

# Check device info
from rtlsdr import RtlSdr
sdr = RtlSdr()
print(f"Gains: {sdr.valid_gains_db}")
print(f"Sample rates: {sdr.valid_gains_db}")
print(f"Center freq range: {sdr.get_center_freq()}")
sdr.close()
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
__version__ = "2.0.0"
```

### Create Release
```bash
# Create annotated tag
git tag -a v2.0.0 -m "Release version 2.0.0 - Plugin-Supervisor Architecture"

# Push tag
git push origin v2.0.0

# Create GitHub release
gh release create v2.0.0 \
  --title "H1SDR v2.0.0 - Plugin-Supervisor Architecture" \
  --notes "Major rewrite with plugin system, error handling, and structured logging"
```

### Docker Build
```bash
# Build image
docker build -t h1sdr:2.0.0 -t h1sdr:latest .

# Run with RTL-SDR device
docker run -p 8000:8000 --device /dev/bus/usb h1sdr:2.0.0

# Run with environment variables
docker run -p 8000:8000 \
  -e WEBSDR_DEBUG=false \
  -e WEBSDR_FFT_SIZE=4096 \
  --device /dev/bus/usb \
  h1sdr:2.0.0

# Run with logs volume
docker run -p 8000:8000 \
  -v $(pwd)/logs:/app/logs \
  --device /dev/bus/usb \
  h1sdr:2.0.0
```

### Production Deployment

#### Systemd Service
```ini
# /etc/systemd/system/h1sdr.service
[Unit]
Description=H1SDR v2.0 WebSDR Server
After=network.target

[Service]
Type=simple
User=sdr
WorkingDirectory=/opt/h1sdr
Environment="PATH=/opt/h1sdr/venv/bin"
ExecStart=/opt/h1sdr/venv/bin/python -m src.web_sdr.main_v2
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable h1sdr
sudo systemctl start h1sdr

# Check status
sudo systemctl status h1sdr

# View logs
sudo journalctl -u h1sdr -f
```

#### Nginx Reverse Proxy
```nginx
# /etc/nginx/sites-available/h1sdr
server {
    listen 80;
    server_name sdr.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

## Resources

- [RTL-SDR API](https://pyrtlsdr.readthedocs.io/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [WebSocket Guide](https://websockets.readthedocs.io/)
- [DSP Theory](https://dspguide.com/)