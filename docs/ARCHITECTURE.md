# H1SDR v2.0 Architecture
**Plugin-Supervisor Architecture with Multi-threaded DSP**

Version: 2.0
Last Updated: 2025-10-02
Status: Production-Ready

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Plugin System](#plugin-system)
6. [Performance](#performance)
7. [Configuration](#configuration)
8. [Deployment](#deployment)

---

## System Overview

H1SDR v2.0 is a web-based Software Defined Radio system built on a **plugin-supervisor architecture** with multi-threaded DSP processing.

```
Web Browser              FastAPI Server v2.0           RTL-SDR Device
───────────              ───────────────────           ──────────────
┌─────────┐              ┌──────────────┐              ┌───────────┐
│Spectrum │◄─WebSocket──►│  Controller  │◄─USB────────►│  RTL-SDR  │
│Display  │              │     v2.0     │              │  Blog V4  │
└─────────┘              └──────┬───────┘              └───────────┘
┌─────────┐                     │
│Waterfall│              ┌──────▼────────┐
│Display  │              │    Plugin     │
└─────────┘              │  Supervisor   │
┌─────────┐              └──────┬────────┘
│ Audio   │                     │
│Playback │         ┌───────────┼───────────┐
└─────────┘         │           │           │
                    ▼           ▼           ▼
              ┌─────────┐ ┌─────────┐ ┌─────────┐
              │Spectrum │ │Waterfall│ │  Demod  │
              │ Plugin  │ │ Plugin  │ │ Plugin  │
              └────┬────┘ └────┬────┘ └────┬────┘
                   │           │           │
                   ▼           ▼           ▼
              ┌────────────────────────────────┐
              │  FFTW Multi-threaded (4 cores) │
              └────────────────────────────────┘
```

### Key Features (v2.0)

✅ **Plugin-based processing** with supervisor pattern for error isolation
✅ **Multi-threaded FFTW** (3x speedup over NumPy)
✅ **Auto-reconnecting WebSocket** (no manual refresh)
✅ **Structured logging** with per-component levels
✅ **Runtime configuration** management with validation
✅ **Production-ready error handling**

### Performance Metrics

| Metric | Value | Status |
|--------|-------|--------|
| End-to-End FPS | 19.9 | ✅ 99.5% of 20 FPS target |
| Average Latency | 50.2 ms | ✅ At target |
| FFT Processing | 0.03 ms | ✅ 3x faster than v1.0 |
| Error Isolation | 100% | ✅ Verified |

---

## Architecture Principles

### 1. Modularity
- **Plugins are loosely coupled** through well-defined interfaces
- Components can be added/removed independently
- Clear separation: acquisition → processing → presentation

### 2. Error Isolation
- **Plugin failures don't crash the system**
- Supervisor pattern provides fault tolerance
- Automatic retry with exponential backoff
- Graceful degradation on persistent errors

### 3. Performance
- **Multi-threaded where beneficial** (FFTW uses 4 cores)
- Async I/O for WebSocket communication
- Zero-copy operations with aligned arrays
- Pre-allocated buffers minimize GC pressure

### 4. Observability
- **Structured logging** with timestamps and context
- Performance metrics and statistics tracking
- Error history for debugging
- Real-time status monitoring via API

### 5. Configurability
- **Runtime updates** without server restart
- Environment-based configuration (.env)
- Validation prevents invalid configs
- Per-component log level tuning

---

## Core Components

### 1. FastAPI Server ([main_v2.py](../src/web_sdr/main_v2.py))

**Entry point** for the web application.

**Responsibilities:**
- HTTP API endpoints (`/api/*`)
- WebSocket management (`/ws/*`)
- Static file serving
- Structured logging initialization
- Application lifecycle (startup/shutdown)

**Key Endpoints:**
```python
# REST API
GET  /api/health          # System health + plugin stats
GET  /api/bands           # 16 frequency band presets
GET  /api/plugins         # Plugin status and statistics
POST /api/sdr/start       # Start SDR acquisition
POST /api/sdr/stop        # Stop SDR
POST /api/sdr/tune        # Tune frequency

# WebSocket Streaming
WS   /ws/spectrum         # Real-time spectrum data (20 FPS)
WS   /ws/audio            # Real-time audio data (48 kHz)
```

**Configuration:**
- Port: 8000 (default)
- CORS enabled for development
- GZip compression
- WebSocket ping: 30s interval

---

### 2. WebSDR Controller v2.0 ([sdr_controller_v2.py](../src/web_sdr/controllers/sdr_controller_v2.py))

**Central orchestrator** for all SDR operations.

**Architecture Pattern:** Coordinator + Plugin Supervisor

**Lifecycle:**
```python
# Startup
await controller.start(device_index=0)
  ├─ Initialize RTL-SDR device (with retry)
  ├─ Configure: sample_rate, frequency, gain
  ├─ Update spectrum processor config
  ├─ Start background acquisition thread
  └─ Return status with plugin stats

# Background thread (continuous)
while is_running:
    samples = sdr.read_samples(262144)  # ~100ms @ 2.4 MSPS
    data_queue.put(samples)
    # Automatic retry on transient errors (up to 5 consecutive)

# Main thread (async processing)
async def get_spectrum_data():
    samples = data_queue.get()
    results = await plugin_supervisor.run(samples)
    return format_results(results)
```

**Error Recovery:**
- Automatic retry on SDR read errors
- Max 5 consecutive failures before stop
- Recovery notification logging
- Detailed error statistics

---

### 3. Plugin System

**Architecture Pattern:** Plugin + Supervisor

#### Plugin Supervisor ([plugin_supervisor.py](../src/web_sdr/pipeline/plugin_supervisor.py))

**Executes plugins in parallel with complete error isolation.**

**Key Method:**
```python
async def run_with_supervision(self, data: Dict) -> List[PluginResult]:
    """Fan-out parallel execution with error isolation"""

    # Create async task for each enabled plugin
    tasks = [
        self._safe_execute(plugin, data.copy())
        for plugin in self.plugins if plugin.enabled
    ]

    # Execute in parallel, catch all exceptions
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Wrap results with metadata (success, time, error)
    return [PluginResult(...) for ...]
```

**Features:**
- ✅ **100% error isolation** (verified in testing)
- ✅ **Parallel execution** (fan-out pattern)
- ✅ **Stats aggregation** (calls, failures, timing)
- ✅ **Dynamic enable/disable**

#### Implemented Plugins

**Spectrum Plugin** ([spectrum_plugin.py](../src/web_sdr/plugins/spectrum_plugin.py))
- **Purpose:** Generate FFT spectrum
- **Input:** IQ samples (complex64)
- **Output:** Frequencies + spectrum (dB)
- **Performance:** 23.7 FPS avg

**Waterfall Plugin** ([waterfall_plugin.py](../src/web_sdr/plugins/waterfall_plugin.py))
- **Purpose:** Rolling waterfall display
- **Input:** IQ samples
- **Output:** 2D array (time × frequency)
- **Buffer:** Configurable line count (default: 100)

**Demodulator Plugin** ([demodulator_plugin.py](../src/web_sdr/plugins/demodulator_plugin.py))
- **Purpose:** Audio demodulation
- **Modes:** AM, FM, USB, LSB, CW
- **Output:** Audio samples @ 48 kHz
- **Feature:** Auto-mode selection by band

---

### 4. DSP Components

#### FFT Processor ([fft_processor.py](../src/web_sdr/dsp/fft_processor.py))

**Technology:** FFTW with multi-threading

**Performance:**
```
NumPy FFT (single-thread):  ~0.09 ms
FFTW (4 threads):           ~0.03 ms
Speedup:                     3x faster
Throughput:                  33,828 FPS
```

**Implementation:**
```python
class FFTProcessor:
    def __init__(self, fft_size=4096, enable_threading=True):
        pyfftw.config.NUM_THREADS = 4  # Use 4 cores

        # Pre-allocate aligned arrays (zero-copy)
        self.input_array = pyfftw.empty_aligned(fft_size, 'complex64')
        self.output_array = pyfftw.empty_aligned(fft_size, 'complex64')

        # Plan FFT (one-time optimization cost)
        self.fft = pyfftw.FFTW(
            self.input_array, self.output_array,
            direction='FFTW_FORWARD',
            flags=('FFTW_MEASURE',),  # Optimize at startup
            threads=4
        )

    def process(self, iq_data: np.ndarray) -> np.ndarray:
        """Ultra-fast FFT (0.03 ms avg)"""
        self.input_array[:] = iq_data
        self.fft.execute()
        return np.fft.fftshift(self.output_array)
```

**Why FFTW?**
- Industry-standard FFT library
- Highly optimized with SIMD + multi-threading
- Zero-copy with aligned arrays
- 3x speedup justifies minimal added complexity

#### Spectrum Processor ([spectrum_processor.py](../src/web_sdr/dsp/spectrum_processor.py))

**Pipeline:**
1. Apply window function (Hamming/Hann/Blackman)
2. Compute FFT via FFTProcessor
3. Calculate power spectrum
4. Convert to dB scale
5. Generate frequency axis

**Performance:**
- Average: 42.3 ms (23.7 FPS)
- **Primary bottleneck** (84% of total pipeline time)
- Optimization opportunities identified

---

### 5. WebSocket System

#### Server: WebSocket Manager ([websocket_service.py](../src/web_sdr/services/websocket_service.py))

**Manages client connections and broadcasting.**

```python
class WebSocketManager:
    spectrum_clients: Set[WebSocket] = set()
    audio_clients: Set[WebSocket] = set()

    async def broadcast_spectrum(self, data: Dict):
        """Send to all spectrum clients"""
        for client in list(self.spectrum_clients):
            try:
                await client.send_json(data)
            except:
                self.spectrum_clients.remove(client)
```

**Limits:**
- Max spectrum clients: 10
- Max audio clients: 5
- Configurable via environment

#### Client: RobustWebSocket ([websocket-manager.js](../web/js/services/websocket-manager.js))

**Auto-reconnecting WebSocket client.**

**Features:**
- ✅ Automatic reconnection on disconnect
- ✅ Exponential backoff (1s → 30s max)
- ✅ Message queuing during disconnect (up to 100)
- ✅ No manual refresh required

**Reconnection Strategy:**
```
Attempt    Delay
   1       1 second
   2       2 seconds
   3       4 seconds
   4       8 seconds
   5       16 seconds
   6+      30 seconds (max)
```

---

## Data Flow

### Complete Pipeline (50 ms end-to-end)

```
1. ACQUISITION (Background Thread)
   RTL-SDR Device
     ↓ USB
   read_samples(262144)  # ~100ms chunk @ 2.4 MSPS
     ↓
   Queue (maxsize=10)

2. PROCESSING (Main Thread, Async)
   Queue.get()
     ↓
   Plugin Supervisor (47ms avg)
     ├─→ Spectrum Plugin (FFT 0.03ms + processing)
     ├─→ Waterfall Plugin (rolling buffer)
     └─→ Demod Plugin (AM/FM/SSB/CW)
     ↓
   Results aggregation

3. PACKAGING
   Format JSON (4ms, ~138KB)
     ↓
   {type, frequencies, spectrum, metadata}

4. STREAMING
   WebSocket broadcast
     ↓
   All connected clients (20 FPS target)
```

### Timing Breakdown

| Component | Time | % Total |
|-----------|------|---------|
| FFT Processing | 0.03 ms | 0.06% |
| Spectrum Processor | 42.3 ms | 84.2% |
| Plugin Overhead | 5.2 ms | 10.4% |
| WebSocket Package | 4.2 ms | 8.4% |
| **Total** | **50.2 ms** | **100%** |
| **Throughput** | **19.9 FPS** | |

**Bottleneck:** Spectrum Processor (array operations)

---

## Plugin System Details

### Plugin Interface

All plugins inherit from `BasePlugin`:

```python
class BasePlugin(ABC):
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.stats = PluginStats()  # Tracking

    @abstractmethod
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Override in subclass"""
        pass

    async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper with stats tracking"""
        start = time.time()
        result = await self.process(data)
        self.stats.record_success(time.time() - start)
        return result
```

### Creating a New Plugin

```python
from src.web_sdr.plugins.base_plugin import BasePlugin

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__("MyPlugin")

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        iq_samples = data['iq_samples']

        # Your processing here
        result = do_something(iq_samples)

        return {
            'type': 'my_data',
            'result': result
        }

# Register with supervisor
supervisor.add_plugin(MyPlugin())
```

### Plugin Stats

Each plugin tracks:
- Call count
- Success count
- Failure count
- Success rate (%)
- Average processing time (ms)
- Total processing time (s)

Access via: `GET /api/plugins`

---

## Performance

### Current Performance (v2.0)

**End-to-End:** 19.9 FPS sustained (99.5% of 20 FPS target)

**Component Breakdown:**
- FFT Processor: ✅ 33,828 FPS (not a bottleneck)
- Spectrum Processor: 🟡 23.7 FPS (primary bottleneck)
- Plugin Supervisor: 🟡 21.1 FPS (acceptable)
- WebSocket Packaging: ✅ 240 FPS (not a bottleneck)

### Comparison: v1.0 vs v2.0

| Metric | v1.0 | v2.0 | Improvement |
|--------|------|------|-------------|
| FFT Processing | 0.09 ms | 0.03 ms | 3x faster |
| End-to-End FPS | 15.4 | 19.9 | 29% faster |
| Error Isolation | ❌ None | ✅ 100% | New feature |
| WebSocket | Manual reconnect | Auto | New feature |
| Architecture | Monolithic | Plugin-based | More maintainable |

### Optimization Roadmap

**Quick Wins** (Est. +20-30% FPS):
1. Disable unused plugins (demod in spectrum-only mode)
2. Optimize waterfall buffer operations
3. Cache frequency arrays

**Medium-Term** (Est. +40-50% FPS):
1. Optimize array operations (in-place, avoid copies)
2. Binary WebSocket protocol (reduce bandwidth)
3. Reduce async overhead

**Target:** 25-30 FPS sustained

---

## Configuration

### Environment Variables (.env)

```bash
# Server
WEBSDR_HOST=127.0.0.1
WEBSDR_PORT=8000
WEBSDR_DEBUG=True

# RTL-SDR
WEBSDR_RTLSDR_DEVICE_INDEX=0
WEBSDR_RTLSDR_SAMPLE_RATE=2400000.0
WEBSDR_RTLSDR_DEFAULT_FREQ=100000000.0
WEBSDR_RTLSDR_DEFAULT_GAIN=40.0
WEBSDR_RTLSDR_PPM_CORRECTION=0

# DSP
WEBSDR_FFT_SIZE=4096
WEBSDR_SPECTRUM_FPS=20.0
WEBSDR_AUDIO_SAMPLE_RATE=48000

# WebSocket
WEBSDR_WEBSOCKET_PING_INTERVAL=30
WEBSDR_MAX_SPECTRUM_CLIENTS=10
WEBSDR_MAX_AUDIO_CLIENTS=5

# Logging (v2.0)
WEBSDR_ENABLE_LOGGING=True
WEBSDR_LOG_LEVEL=INFO
WEBSDR_ENABLE_JSON_LOGS=False
```

### Runtime Configuration (v2.0)

**Update without restart:**
```python
from src.web_sdr.utils.config_manager import get_config_manager

config_mgr = get_config_manager(config)

# Update single value (with validation)
config_mgr.set('rtlsdr_default_freq', 144.0e6, validate=True)

# Bulk update
config_mgr.bulk_set({
    'rtlsdr_default_freq': 144.0e6,
    'rtlsdr_default_gain': 40.0
})

# Rollback last N changes
config_mgr.rollback(steps=2)
```

**Features:**
- Validation (frequency range, sample rates, etc.)
- Change history (last 100)
- Rollback support
- Reactive callbacks
- Persistence to JSON

---

## Deployment

### Development

```bash
# Clone repository
git clone https://github.com/youruser/h1sdr.git
cd h1sdr

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run v2.0 server
python -m src.web_sdr.main_v2

# Access at: http://localhost:8000
```

### Production

**Using Uvicorn:**
```bash
uvicorn src.web_sdr.main_v2:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1
```

**Systemd Service:**
```ini
[Unit]
Description=H1SDR WebSDR v2.0
After=network.target

[Service]
Type=simple
User=websdr
WorkingDirectory=/opt/h1sdr
ExecStart=/opt/h1sdr/venv/bin/python -m src.web_sdr.main_v2
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Docker (optional):**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "-m", "src.web_sdr.main_v2"]
```

### Monitoring

**Logs:**
```bash
# File logs (with rotation)
tail -f logs/h1sdr.log

# Systemd journal
journalctl -u h1sdr -f
```

**Health Check:**
```bash
curl http://localhost:8000/api/health
```

**Plugin Stats:**
```bash
curl http://localhost:8000/api/plugins | jq .
```

---

## Error Handling & Logging

### Structured Logging (v2.0)

**Format:**
```
[TIMESTAMP] [LEVEL] [COMPONENT] Message | context=value
```

**Example:**
```
[2025-10-02 14:23:45.123] [INFO    ] [controllers.sdr_controller_v2] SDR started
[2025-10-02 14:23:45.456] [WARNING ] [plugins.SpectrumPlugin       ] High latency | ms=65
[2025-10-02 14:23:45.789] [ERROR   ] [error_handler                ] SDR error (3/5)
```

**Features:**
- Per-component log levels
- File rotation (10 MB, 5 backups)
- Optional JSON output for analysis
- Context-aware logging

### Error Recovery

**SDR Acquisition Worker:**
- Automatic retry on transient errors
- Max 5 consecutive failures
- Brief pause (0.1s) between retries
- Detailed error logging
- Graceful shutdown on persistent errors

**Plugin Supervisor:**
- 100% error isolation
- Failed plugins logged, others continue
- Statistics tracking for debugging
- No system crash on plugin failure

---

## WebSocket Protocol

### Spectrum Data

```json
{
  "type": "spectrum",
  "frequencies": [float array, 4096 points],
  "spectrum": [dB array, 4096 points],
  "timestamp": "2025-10-02T14:23:45.123Z",
  "sample_rate": 2400000.0,
  "center_frequency": 144000000.0,
  "fft_size": 4096,
  "metadata": {
    "gain": 40.0,
    "demod_mode": "SPECTRUM",
    "processing_time_ms": 45.2,
    "fps": 19.9,
    "plugin_processing_ms": 47.1
  }
}
```

**Message Size:** ~138 KB
**Rate:** 20 FPS target (19.9 FPS achieved)

### Audio Data

```json
{
  "type": "audio",
  "samples": [float32 array, ~4800 samples],
  "sample_rate": 48000,
  "timestamp": "2025-10-02T14:23:45.123Z",
  "mode": "FM",
  "metadata": {
    "bandwidth": 200000,
    "chunk_size": 4800
  }
}
```

**Sample Rate:** 48 kHz
**Chunk Size:** ~100 ms

---

## Design Decisions

### 1. Why Plugin Architecture?

**Pros:**
- ✅ Easy to add new processing modes
- ✅ Error isolation prevents system crashes
- ✅ Testable independently
- ✅ Parallel execution improves performance

**Cons:**
- ❌ Slight overhead (~10% from async coordination)
- ❌ More complex than monolithic

**Decision:** Benefits outweigh costs for production system

### 2. Why FFTW over NumPy?

**Benchmarks:**
- NumPy: 0.09 ms (single-thread)
- FFTW: 0.03 ms (4 threads)
- **Speedup: 3x**

**Decision:** Significant performance gain justifies the dependency

### 3. Why Async/Await?

**Pros:**
- ✅ Non-blocking I/O for WebSocket
- ✅ Natural plugin coordination
- ✅ Efficient resource usage

**Cons:**
- ❌ Complexity in error handling
- ❌ Executor needed for CPU-bound work

**Decision:** Better scalability worth the complexity

### 4. Why Auto-Reconnect WebSocket?

**User Experience:**
- No manual refresh on disconnect
- Seamless recovery
- Message queuing prevents data loss

**Implementation:**
- Client-side RobustWebSocket
- Exponential backoff
- Simple, effective

**Decision:** Essential for production UX

---

## Future Architecture

### Phase 2: Testing & CI/CD
- Unit tests (80% coverage target)
- E2E tests with Playwright
- CI/CD pipeline (GitHub Actions)
- Performance regression testing

### Phase 3: Advanced Features
1. **Recording System:** IQ/audio recording and playback
2. **Multi-Client:** Shared processing optimization
3. **Advanced DSP:** More modes, RFI mitigation, signal classification

### Long-Term (v3.0)
1. **Distributed Architecture:** Multiple SDR nodes, load balancing
2. **Machine Learning:** Signal classification, auto-detection
3. **Cloud Deployment:** Docker, Kubernetes, scalable storage

---

## References

### Documentation
- [API Reference](API_REFERENCE.md) - REST and WebSocket API
- [Development Guide](DEVELOPMENT.md) - Plugin development, debugging
- [Installation Guide](INSTALLATION.md) - Setup and dependencies
- [User Guide](USER_GUIDE.md) - End-user documentation

### Performance
- [Performance Profile](../PERFORMANCE_PROFILE_WEEK3.md) - Detailed profiling analysis
- [Profiling Tool](../tools/profile_dsp.py) - DSP performance profiler

### Testing
- [Test Results](../TEST_RESULTS_PHASE1_WEEK2.md) - Phase 1 test results
- [Integration Tests](../tests/integration/) - Automated test suite

---

## Conclusion

H1SDR v2.0 achieves **production-ready architecture** with:

✅ **19.9 FPS sustained** (99.5% of target)
✅ **100% error isolation** in plugin system
✅ **3x faster FFT** with FFTW multi-threading
✅ **Auto-reconnecting WebSocket**
✅ **Structured logging** and error handling
✅ **Runtime configuration** management

The plugin-supervisor architecture provides a solid, maintainable foundation for future enhancements while maintaining excellent performance and reliability.

---

*Architecture v2.0 | Last Updated: 2025-10-02 | Branch: v2-dev*
