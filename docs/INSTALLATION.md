# H1SDR Installation Guide (v2.0)

**Version:** 2.0.0
**Architecture:** Plugin-Supervisor Pattern

---

## Requirements

### Hardware
- **RTL-SDR:** Blog V3/V4 or compatible device
- **USB Port:** USB 3.0 recommended for best performance
- **RAM:** 4GB minimum, 8GB recommended
- **CPU:** Multi-core processor (v2.0 uses 4 threads for FFT)

### Software
- **Python:** 3.8+ (tested with 3.12)
- **OS:** Linux (recommended), Windows, macOS
- **Browser:** Modern browser with WebGL and Web Audio API
  - Chrome 90+
  - Firefox 88+
  - Safari 14+
  - Edge 90+

### System Libraries (v2.0)
- **FFTW3:** For hardware-accelerated FFT processing
  ```bash
  # Linux (Debian/Ubuntu)
  sudo apt install libfftw3-3 libfftw3-dev

  # Fedora/RHEL
  sudo dnf install fftw fftw-devel

  # macOS
  brew install fftw
  ```

## Quick Install

### 1. RTL-SDR Drivers

**Linux:**
```bash
sudo apt install rtl-sdr librtlsdr-dev

# Blacklist DVB drivers
sudo tee /etc/modprobe.d/blacklist-rtl.conf <<EOF
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
EOF

sudo reboot
```

### 2. Verify Hardware
```bash
rtl_test -t
# Should show: RTL-SDR Blog V4 or similar
```

### 3. Install H1SDR
```bash
git clone https://github.com/usuario/h1sdr.git
cd h1sdr

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure (Optional)
```bash
cp .env.example .env
nano .env  # Edit settings if needed
```

### 5. Run (v2.0)
```bash
source venv/bin/activate
python -m src.web_sdr.main_v2

# Or with debug logging
python -m src.web_sdr.main_v2 --debug

# Server will start on http://localhost:8000
```

**Open in browser:** http://localhost:8000

**Check server health:**
```bash
curl http://localhost:8000/api/health
# Should return: {"status": "ok", "version": "2.0.0", ...}
```

**v2.0 Features Enabled:**
- ✅ Plugin-Supervisor architecture (100% error isolation)
- ✅ Multi-threaded FFTW (4-core FFT processing)
- ✅ Auto-reconnecting WebSocket (exponential backoff)
- ✅ Structured logging with rotation
- ✅ Error handling with automatic retry
- ✅ Performance monitoring (19.9 FPS sustained)

## Troubleshooting

### RTL-SDR Not Found
```bash
# Check if device is detected
lsusb | grep RTL

# Remove conflicting DVB drivers
sudo rmmod dvb_usb_rtl28xxu rtl2832

# Add user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in for group changes to take effect
```

### FFTW Not Found (v2.0)
```bash
# Linux: Install FFTW development package
sudo apt install libfftw3-dev

# Verify installation
pkg-config --modversion fftw3

# Reinstall Python package
pip install --force-reinstall pyfftw
```

### No Audio
- Check demod mode is not SPECTRUM (use AM/FM/SSB)
- Verify browser audio permissions (check browser console)
- Test with FM broadcast band (88-108 MHz) first
- Check DemodulatorPlugin is enabled:
  ```bash
  curl http://localhost:8000/api/plugins | jq '.data[] | select(.name=="DemodulatorPlugin")'
  ```

### Low FPS / Performance Issues (v2.0)
```bash
# Check current performance
curl http://localhost:8000/api/health | jq '.plugin_supervisor'

# Reduce FFT size in .env:
WEBSDR_FFT_SIZE=2048          # Default: 4096
WEBSDR_SPECTRUM_FPS=10.0      # Default: 20.0

# Disable unused plugins
curl -X POST http://localhost:8000/api/plugins/WaterfallPlugin/disable

# Check plugin processing times
curl http://localhost:8000/api/plugins | jq '.data[].stats | {name, avg_processing_time_ms}'
```

### WebSocket Connection Issues (v2.0)
```bash
# Test WebSocket endpoint
websocat ws://localhost:8000/ws/spectrum

# Check WebSocket service logs
# If using systemd:
journalctl -u h1sdr -f | grep -i websocket

# Browser console should show auto-reconnect attempts
# Check browser network tab for WebSocket connections
```

### Plugin Failures (v2.0)
```bash
# Check plugin stats
curl http://localhost:8000/api/plugins | jq '.data[] | {name, enabled, failure_count, success_rate}'

# View error logs
tail -f logs/h1sdr.log | grep ERROR

# Disable problematic plugin
curl -X POST http://localhost:8000/api/plugins/PluginName/disable

# System continues working (100% error isolation)
```

### High Memory Usage
```bash
# Check current memory
free -h

# Reduce buffer sizes in .env:
WEBSDR_BUFFER_SIZE=65536      # Reduce from 131072

# Monitor memory usage
watch -n 1 'ps aux | grep python'
```

## Production Setup (v2.0)

### Systemd Service
```bash
sudo tee /etc/systemd/system/h1sdr.service <<EOF
[Unit]
Description=H1SDR v2.0 WebSDR Server
After=network.target

[Service]
Type=simple
User=sdr
Group=sdr
WorkingDirectory=/opt/h1sdr
Environment="PATH=/opt/h1sdr/venv/bin"
ExecStart=/opt/h1sdr/venv/bin/python -m src.web_sdr.main_v2
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Performance tuning
LimitNOFILE=65536
Nice=-5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable h1sdr
sudo systemctl start h1sdr

# Check status
sudo systemctl status h1sdr

# View logs
sudo journalctl -u h1sdr -f
```

### Environment Variables (Production)
```bash
# Create production config
sudo tee /opt/h1sdr/.env <<EOF
# Server settings
WEBSDR_HOST=0.0.0.0
WEBSDR_PORT=8000
WEBSDR_DEBUG=false

# Performance settings
WEBSDR_FFT_SIZE=4096
WEBSDR_SPECTRUM_FPS=20.0
WEBSDR_BUFFER_SIZE=131072

# Logging (v2.0)
WEBSDR_LOG_DIR=/var/log/h1sdr
WEBSDR_LOG_LEVEL=INFO
WEBSDR_ENABLE_JSON_LOGS=true

# Plugin settings (v2.0)
WEBSDR_ENABLE_WATERFALL=false  # Disable for better performance
EOF

# Create log directory
sudo mkdir -p /var/log/h1sdr
sudo chown sdr:sdr /var/log/h1sdr
```

### Nginx Reverse Proxy (with SSL)
```nginx
# /etc/nginx/sites-available/h1sdr
server {
    listen 80;
    listen [::]:80;
    server_name sdr.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name sdr.example.com;

    # SSL certificates (use certbot)
    ssl_certificate /etc/letsencrypt/live/sdr.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sdr.example.com/privkey.pem;

    # HTTP endpoints
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket endpoints (v2.0)
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;  # 24 hours
        proxy_send_timeout 86400;
    }
}
```

```bash
# Enable site and reload nginx
sudo ln -s /etc/nginx/sites-available/h1sdr /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate (optional)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d sdr.example.com
```

### Docker Deployment (Alternative)
```bash
# Build image
cd h1sdr
docker build -t h1sdr:2.0.0 .

# Run with docker-compose
cat > docker-compose.yml <<EOF
version: '3.8'

services:
  h1sdr:
    image: h1sdr:2.0.0
    container_name: h1sdr
    restart: unless-stopped
    ports:
      - "8000:8000"
    devices:
      - /dev/bus/usb:/dev/bus/usb
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
    environment:
      - WEBSDR_DEBUG=false
      - WEBSDR_FFT_SIZE=4096
      - WEBSDR_LOG_DIR=/app/logs
    privileged: true  # Required for USB access
EOF

# Start container
docker-compose up -d

# View logs
docker-compose logs -f
```

### Monitoring (v2.0)
```bash
# Health check endpoint
curl http://localhost:8000/api/health

# Plugin status monitoring
watch -n 5 'curl -s http://localhost:8000/api/plugins | jq ".data[] | {name, enabled, success_rate}"'

# Performance monitoring
watch -n 5 'curl -s http://localhost:8000/api/health | jq .plugin_supervisor'

# Log monitoring
tail -f /var/log/h1sdr/h1sdr.log

# System resource monitoring
htop -p $(pgrep -f main_v2)
```

---

**For detailed development and API documentation, see:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and design
- [API_REFERENCE.md](API_REFERENCE.md) - API endpoints and WebSocket protocol
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development guide and plugin creation
- [USER_GUIDE.md](USER_GUIDE.md) - User manual for operating the WebSDR