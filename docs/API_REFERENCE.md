# H1SDR API Reference (v2.0)

**Architecture:** Plugin-Supervisor Pattern
**Version:** 2.0.0
**Base URL:** `http://localhost:8000`

---

## REST Endpoints

### System

#### `GET /api/health`
System health check with plugin supervisor stats

**Response:**
```json
{
  "status": "ok",
  "version": "2.0.0",
  "architecture": "plugin-supervisor",
  "sdr_connected": false,
  "active_connections": 0,
  "plugins": 3,
  "plugin_supervisor": {
    "total_executions": 1234,
    "total_failures": 0,
    "failure_rate": 0.0
  }
}
```

#### `GET /api/sdr/status`
SDR device status

**Response:**
```json
{
  "success": true,
  "data": {
    "is_running": true,
    "frequency": 145000000,
    "sample_rate": 2400000,
    "gain": 40.0,
    "center_freq": 145000000
  }
}
```

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

### Plugin Management (v2.0)

#### `GET /api/plugins`
List all plugins with stats

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "name": "SpectrumPlugin",
      "enabled": true,
      "stats": {
        "name": "SpectrumPlugin",
        "enabled": true,
        "call_count": 1234,
        "success_count": 1234,
        "failure_count": 0,
        "success_rate": 100.0,
        "avg_processing_time_ms": 42.3,
        "total_processing_time_s": 52.1
      }
    },
    {
      "name": "WaterfallPlugin",
      "enabled": true,
      "stats": { /* ... */ }
    },
    {
      "name": "DemodulatorPlugin",
      "enabled": false,
      "stats": { /* ... */ }
    }
  ]
}
```

#### `POST /api/plugins/{name}/enable`
Enable a plugin

**Request:** `POST /api/plugins/WaterfallPlugin/enable`

**Response:**
```json
{
  "success": true,
  "message": "Plugin WaterfallPlugin enabled"
}
```

#### `POST /api/plugins/{name}/disable`
Disable a plugin

**Request:** `POST /api/plugins/DemodulatorPlugin/disable`

**Response:**
```json
{
  "success": true,
  "message": "Plugin DemodulatorPlugin disabled"
}
```

## WebSocket Endpoints

### `/ws/spectrum`
Real-time FFT data (19.9 FPS sustained)

**Features:**
- Auto-reconnect with exponential backoff (1s → 30s)
- Connection status messages on connect
- Performance metadata included

**Connection Status (sent on connect):**
```json
{
  "type": "connection_status",
  "connected": true,
  "message": "Connected to spectrum stream",
  "timestamp": 1693785632.123
}
```

**Spectrum Data:**
```json
{
  "type": "spectrum",
  "frequencies": [...],           // Array of frequency bins (Hz)
  "spectrum": [...],               // Power levels (dB)
  "timestamp": 1693785632.123,
  "metadata": {
    "processing_time_ms": 50.2,   // Total pipeline time
    "fps": 19.9,                   // Current throughput
    "plugin_processing_ms": 47.5  // Plugin supervisor time
  }
}
```

**Client Implementation:**
```javascript
// Use RobustWebSocket for auto-reconnect
const ws = new RobustWebSocket('ws://localhost:8000/ws/spectrum', null, {
  timeout: 2000,
  shouldReconnect: (event, ws) => true,
  automaticOpen: true,
  ignoreConnectivityEvents: false
});
```

### `/ws/audio`
Demodulated audio (48 kHz)

**Audio Data:**
```json
{
  "type": "audio",
  "samples": [...],         // Float32 audio samples
  "sample_rate": 48000,     // Always 48 kHz
  "timestamp": 1693785632.123
}
```

### `/ws/waterfall`
Waterfall data

**Status:** Plugin available but may be disabled for performance

**Waterfall Data:**
```json
{
  "type": "waterfall",
  "data": [...],            // 2D array of intensity values
  "width": 4096,            // FFT size
  "timestamp": 1693785632.123
}
```

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

### Basic Usage

```javascript
// Check system health
const health = await fetch('/api/health').then(r => r.json());
console.log(`System: ${health.status}, Plugins: ${health.plugins}`);

// Start SDR
await fetch('/api/sdr/start', {method: 'POST'});

// Tune to 2m band
await fetch('/api/bands/2m_band/tune', {method: 'POST'});

// Connect spectrum with auto-reconnect
const ws = new RobustWebSocket('ws://localhost:8000/ws/spectrum');
ws.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'spectrum') {
    console.log(`FPS: ${data.metadata.fps}, Processing: ${data.metadata.processing_time_ms}ms`);
    // Update visualization...
  }
});
```

### Plugin Management

```javascript
// List all plugins
const plugins = await fetch('/api/plugins').then(r => r.json());
plugins.data.forEach(p => {
  console.log(`${p.name}: ${p.enabled ? 'enabled' : 'disabled'}, Success rate: ${p.stats.success_rate}%`);
});

// Enable waterfall plugin
await fetch('/api/plugins/WaterfallPlugin/enable', {method: 'POST'});

// Disable demodulator to improve performance
await fetch('/api/plugins/DemodulatorPlugin/disable', {method: 'POST'});
```

### Monitoring Performance

```javascript
// Monitor plugin stats in real-time
setInterval(async () => {
  const health = await fetch('/api/health').then(r => r.json());
  const supervisor = health.plugin_supervisor;
  console.log(`Executions: ${supervisor.total_executions}, Failures: ${supervisor.total_failures}, Rate: ${supervisor.failure_rate}%`);
}, 5000);
```

### Complete WebSocket Example

```javascript
// Include robust-websocket.js in your HTML
const ws = new RobustWebSocket('ws://localhost:8000/ws/spectrum', null, {
  timeout: 2000,
  shouldReconnect: (event, ws) => true,
  automaticOpen: true
});

ws.addEventListener('open', () => {
  console.log('Connected to spectrum stream');
});

ws.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);

  switch(data.type) {
    case 'connection_status':
      console.log(data.message);
      break;

    case 'spectrum':
      // Update spectrum display
      updateSpectrum(data.frequencies, data.spectrum);

      // Monitor performance
      if (data.metadata.fps < 15) {
        console.warn('Low FPS detected:', data.metadata.fps);
      }
      break;
  }
});

ws.addEventListener('close', () => {
  console.log('Disconnected (will auto-reconnect)');
});
```

---

## Error Handling (v2.0)

All API endpoints return standardized error responses:

```json
{
  "success": false,
  "error": "Description of what went wrong",
  "details": {
    "category": "hardware|network|processing|configuration",
    "severity": "warning|error|critical",
    "recoverable": true
  }
}
```

## Performance Notes

- **Target FPS:** 20 FPS
- **Sustained Performance:** 19.9 FPS (99.5% of target)
- **Plugin Isolation:** 100% error isolation between plugins
- **FFT Processing:** 0.03 ms (multi-threaded FFTW)
- **Spectrum Processing:** 42.3 ms average
- **Plugin Processing:** 47.5 ms average (includes all enabled plugins)
- **WebSocket Packaging:** 4.2 ms