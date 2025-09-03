# H1SDR Installation

## Requirements

### Hardware
- RTL-SDR Blog V3/V4 or compatible
- USB 3.0 port recommended
- 4GB RAM minimum

### Software
- Python 3.12+
- Linux/Windows/macOS
- Modern browser with WebGL

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

### 5. Run
```bash
source venv/bin/activate
python -m src.web_sdr.main
# Open browser: http://localhost:8000
```

## Troubleshooting

### RTL-SDR Not Found
```bash
lsusb | grep RTL
sudo rmmod dvb_usb_rtl28xxu rtl2832
sudo usermod -a -G dialout $USER
```

### No Audio
- Check demod mode (not SPECTRUM)
- Verify browser audio permissions
- Test with FM broadcast band first

### Performance Issues
```bash
# Reduce in .env:
WEBSDR_FFT_SIZE=2048
WEBSDR_SPECTRUM_FPS=10.0
```

## Production Setup

### Systemd Service
```bash
sudo tee /etc/systemd/system/h1sdr.service <<EOF
[Unit]
Description=H1SDR WebSDR
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/h1sdr
ExecStart=/opt/h1sdr/venv/bin/python -m src.web_sdr.main
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now h1sdr
```