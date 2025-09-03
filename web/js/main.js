/**
 * H1SDR WebSDR - Main Application Controller
 * Coordinates all components and manages the SDR interface
 */

class H1SDRWebApp {
    constructor() {
        // Core services
        this.websocketClient = null;
        this.audioService = null;
        
        // Display components
        this.spectrumDisplay = null;
        this.waterfallDisplay = null;
        
        // UI state
        this.sdrRunning = false;
        this.currentFrequency = 100.0; // MHz
        this.currentBand = '';
        this.demodMode = 'SPECTRUM';
        this.bandwidth = 15000; // Hz
        this.gain = 40.0; // dB
        this.volume = 50; // %
        this.squelch = 0; // %
        
        // Band definitions
        this.bands = {
            'h1_line': { freq: 1420.4057, name: 'H1 Line (1420.4 MHz)' },
            'oh_1665': { freq: 1665.4018, name: 'OH Line 1665 MHz' },
            'oh_1667': { freq: 1667.359, name: 'OH Line 1667 MHz' },
            'fm_broadcast': { freq: 98.0, name: 'FM Broadcast (88-108 MHz)' },
            'am_broadcast': { freq: 1.0, name: 'AM Broadcast (0.5-1.7 MHz)' },
            '160m_band': { freq: 1.9, name: '160m Band (1.8-2.0 MHz)' },
            '80m_band': { freq: 3.75, name: '80m Band (3.5-4.0 MHz)' },
            '40m_band': { freq: 7.15, name: '40m Band (7.0-7.3 MHz)' },
            '30m_band': { freq: 10.125, name: '30m Band (10.1-10.15 MHz)' },
            '20m_band': { freq: 14.175, name: '20m Band (14.0-14.35 MHz)' },
            '17m_band': { freq: 18.12, name: '17m Band (18.07-18.17 MHz)' },
            '15m_band': { freq: 21.225, name: '15m Band (21.0-21.45 MHz)' },
            '12m_band': { freq: 24.94, name: '12m Band (24.89-24.99 MHz)' },
            '10m_band': { freq: 28.85, name: '10m Band (28.0-29.7 MHz)' },
            '6m_band': { freq: 52.0, name: '6m Band (50-54 MHz)' },
            '2m_band': { freq: 146.0, name: '2m Band (144-148 MHz)' },
            '70cm_band': { freq: 435.0, name: '70cm Band (420-450 MHz)' },
            'aviation': { freq: 127.5, name: 'Aviation (118-137 MHz)' },
            'marine': { freq: 159.0, name: 'Marine VHF (156-162 MHz)' },
            'weather_satellite': { freq: 137.5, name: 'Weather Satellite (137-138 MHz)' }
        };
        
        console.log('H1SDR WebApp initialized');
    }
    
    async initialize() {
        try {
            // Initialize services
            await this.initializeServices();
            
            // Initialize display components
            this.initializeDisplays();
            
            // Setup UI event handlers
            this.setupEventHandlers();
            
            // Load user preferences
            this.loadSettings();
            
            // Start the application
            this.startApplication();
            
            console.log('H1SDR WebApp ready');
            return true;
            
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.showError('Failed to initialize application: ' + error.message);
            return false;
        }
    }
    
    async initializeServices() {
        // Initialize WebSocket client
        this.websocketClient = new WebSocketClient();
        
        // Initialize audio service
        this.audioService = new AudioService();
        const audioInitialized = await this.audioService.initialize();
        
        if (!audioInitialized) {
            console.warn('Audio service initialization failed - audio features disabled');
        }
        
        // Connect WebSocket handlers
        this.setupWebSocketHandlers();
    }
    
    initializeDisplays() {
        // Initialize spectrum display
        try {
            this.spectrumDisplay = new SpectrumDisplay('spectrum-canvas');
            
            // Connect click-to-tune
            this.spectrumDisplay.addEventListener('frequencyClick', (event) => {
                const frequency = event.detail.frequency / 1e6; // Convert to MHz
                this.setFrequency(frequency);
            });
            
        } catch (error) {
            console.error('Failed to initialize spectrum display:', error);
        }
        
        // Initialize waterfall display
        try {
            this.waterfallDisplay = new WaterfallDisplay('waterfall-canvas');
            
            // Connect click-to-tune
            this.waterfallDisplay.addEventListener('frequencyClick', (event) => {
                const frequency = event.detail.frequency / 1e6; // Convert to MHz
                this.setFrequency(frequency);
            });
            
        } catch (error) {
            console.error('Failed to initialize waterfall display:', error);
        }
    }
    
    setupWebSocketHandlers() {
        // Spectrum data handler
        this.websocketClient.addHandler('spectrum', (data) => {
            if (this.spectrumDisplay) {
                this.spectrumDisplay.updateSpectrum(data.spectrum, data.frequencies);
                this.spectrumDisplay.setFrequencyRange(data.centerFrequency, data.sampleRate);
            }
        });
        
        // Waterfall data handler
        this.websocketClient.addHandler('waterfall', (data) => {
            if (this.waterfallDisplay) {
                // Convert uint8 back to float for waterfall
                const floatData = new Float32Array(data.data.length);
                for (let i = 0; i < data.data.length; i++) {
                    floatData[i] = (data.data[i] / 255.0) * 100 - 80; // Scale to -80 to +20 dB
                }
                this.waterfallDisplay.addSpectrumLine(floatData);
            }
        });
        
        // Audio data handler
        this.websocketClient.addHandler('audio', (data) => {
            if (this.audioService && this.audioService.isPlaying) {
                this.audioService.addAudioData(data.audio);
            }
        });
        
        // Control message handler
        this.websocketClient.addHandler('control', (data) => {
            this.handleControlMessage(data);
        });
    }
    
    setupEventHandlers() {
        // SDR control buttons
        document.getElementById('sdr-start')?.addEventListener('click', () => {
            this.startSDR();
        });
        
        document.getElementById('sdr-stop')?.addEventListener('click', () => {
            this.stopSDR();
        });
        
        // Theme toggle
        document.getElementById('theme-toggle')?.addEventListener('click', () => {
            this.toggleTheme();
        });
        
        // Fullscreen toggle
        document.getElementById('fullscreen-toggle')?.addEventListener('click', () => {
            this.toggleFullscreen();
        });
        
        // Frequency control
        document.getElementById('frequency-input')?.addEventListener('change', (e) => {
            const frequency = parseFloat(e.target.value);
            if (!isNaN(frequency)) {
                this.setFrequency(frequency);
            }
        });
        
        // Frequency step buttons
        document.querySelectorAll('.freq-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const step = parseInt(e.target.dataset.step);
                if (!isNaN(step)) {
                    this.adjustFrequency(step);
                }
            });
        });
        
        // Band selector
        document.getElementById('band-select')?.addEventListener('change', (e) => {
            this.currentBand = e.target.value;
        });
        
        document.getElementById('tune-to-band')?.addEventListener('click', () => {
            this.tuneToSelectedBand();
        });
        
        // Demodulation controls
        document.getElementById('mode-select')?.addEventListener('change', (e) => {
            this.setDemodMode(e.target.value);
            // Update audio controls when demod mode changes
            if (window.H1SDRInit && typeof window.H1SDRInit.updateAudioControlsState === 'function') {
                window.H1SDRInit.updateAudioControlsState();
            }
        });
        
        document.getElementById('bandwidth-slider')?.addEventListener('input', (e) => {
            this.setBandwidth(parseInt(e.target.value));
        });
        
        // SDR settings
        document.getElementById('gain-slider')?.addEventListener('input', (e) => {
            this.setGain(parseFloat(e.target.value));
        });
        
        // Spectrum controls
        document.getElementById('spectrum-zoom')?.addEventListener('input', (e) => {
            const zoom = parseFloat(e.target.value);
            this.setSpectrumZoom(zoom);
        });
        
        document.getElementById('reset-zoom')?.addEventListener('click', () => {
            this.resetZoom();
        });
        
        // Waterfall controls
        document.getElementById('colormap-select')?.addEventListener('change', (e) => {
            this.setWaterfallColormap(e.target.value);
        });
        
        document.getElementById('intensity-min')?.addEventListener('input', (e) => {
            const minVal = parseInt(e.target.value);
            const maxVal = parseInt(document.getElementById('intensity-max').value);
            this.setWaterfallIntensity(minVal, maxVal);
        });
        
        document.getElementById('intensity-max')?.addEventListener('input', (e) => {
            const maxVal = parseInt(e.target.value);
            const minVal = parseInt(document.getElementById('intensity-min').value);
            this.setWaterfallIntensity(minVal, maxVal);
        });
        
        document.getElementById('auto-scale')?.addEventListener('click', () => {
            this.autoScaleWaterfall();
        });
        
        // Audio controls
        document.getElementById('audio-play')?.addEventListener('click', () => {
            this.startAudio();
        });
        
        document.getElementById('audio-stop')?.addEventListener('click', () => {
            this.stopAudio();
        });
        
        document.getElementById('volume-slider')?.addEventListener('input', (e) => {
            this.setVolume(parseInt(e.target.value));
        });
        
        document.getElementById('squelch-slider')?.addEventListener('input', (e) => {
            this.setSquelch(parseInt(e.target.value));
        });
    }
    
    async startApplication() {
        // Hide loading overlay
        const loadingOverlay = document.getElementById('loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.classList.add('hidden');
        }
        
        // Connect WebSocket
        try {
            await this.websocketClient.connectControl();
            console.log('Control WebSocket connected');
        } catch (error) {
            console.error('Failed to connect control WebSocket:', error);
        }
    }
    
    // SDR Control Methods
    
    async startSDR() {
        const config = {
            frequency: this.currentFrequency * 1e6, // Convert to Hz
            gain: this.gain,
            sample_rate: 2400000, // 2.4 MSPS
            device_index: 0
        };
        
        const success = this.websocketClient.startSDR(config);
        if (success) {
            // Connect data streams
            await this.websocketClient.connectSpectrum();
            await this.websocketClient.connectWaterfall();
            
            if (this.demodMode !== 'SPECTRUM') {
                await this.websocketClient.connectAudio();
            }
            
            this.sdrRunning = true;
            this.updateSDRButtons();
        }
    }
    
    stopSDR() {
        this.websocketClient.stopSDR();
        this.websocketClient.disconnect('spectrum');
        this.websocketClient.disconnect('waterfall');
        this.websocketClient.disconnect('audio');
        
        this.sdrRunning = false;
        this.updateSDRButtons();
        
        // Stop audio
        this.stopAudio();
    }
    
    setFrequency(frequency) {
        this.currentFrequency = frequency;
        
        // Update UI
        const freqInput = document.getElementById('frequency-input');
        if (freqInput) {
            freqInput.value = frequency.toFixed(4);
        }
        
        // Send to SDR
        if (this.sdrRunning) {
            this.websocketClient.setFrequency(frequency * 1e6);
        }
        
        // Update displays
        if (this.spectrumDisplay) {
            this.spectrumDisplay.setFrequencyRange(frequency * 1e6, 2400000);
        }
        if (this.waterfallDisplay) {
            this.waterfallDisplay.setFrequencyRange(frequency * 1e6, 2400000);
        }
    }
    
    adjustFrequency(stepHz) {
        const stepMHz = stepHz / 1e6;
        this.setFrequency(this.currentFrequency + stepMHz);
    }
    
    tuneToSelectedBand() {
        if (this.currentBand && this.bands[this.currentBand]) {
            this.setFrequency(this.bands[this.currentBand].freq);
        }
    }
    
    setGain(gain) {
        this.gain = gain;
        
        // Update display
        const gainDisplay = document.getElementById('gain-display');
        if (gainDisplay) {
            gainDisplay.textContent = gain.toFixed(1);
        }
        
        // Send to SDR
        if (this.sdrRunning) {
            this.websocketClient.setGain(gain);
        }
    }
    
    setDemodMode(mode) {
        this.demodMode = mode;
        
        // Connect/disconnect audio based on mode
        if (mode === 'SPECTRUM') {
            this.websocketClient.disconnect('audio');
            this.stopAudio();
            this.disableAudioControls();
        } else {
            if (this.sdrRunning) {
                this.websocketClient.connectAudio();
            }
            this.enableAudioControls();
            this.websocketClient.setDemodulation(mode, this.bandwidth);
        }
    }
    
    setBandwidth(bandwidth) {
        this.bandwidth = bandwidth;
        
        // Update display
        const bwDisplay = document.getElementById('bandwidth-display');
        if (bwDisplay) {
            if (bandwidth >= 1000) {
                bwDisplay.textContent = `${(bandwidth / 1000).toFixed(1)} kHz`;
            } else {
                bwDisplay.textContent = `${bandwidth} Hz`;
            }
        }
        
        // Send to SDR
        if (this.sdrRunning && this.demodMode !== 'SPECTRUM') {
            this.websocketClient.setDemodulation(this.demodMode, bandwidth);
        }
    }
    
    // Display Control Methods
    
    setSpectrumZoom(zoom) {
        if (this.spectrumDisplay) {
            this.spectrumDisplay.setZoom(zoom);
        }
        
        const zoomDisplay = document.getElementById('zoom-display');
        if (zoomDisplay) {
            zoomDisplay.textContent = `${zoom}x`;
        }
    }
    
    resetZoom() {
        if (this.spectrumDisplay) {
            this.spectrumDisplay.resetZoom();
        }
        if (this.waterfallDisplay) {
            this.waterfallDisplay.resetZoom();
        }
        
        const zoomSlider = document.getElementById('spectrum-zoom');
        if (zoomSlider) {
            zoomSlider.value = 1;
        }
        
        const zoomDisplay = document.getElementById('zoom-display');
        if (zoomDisplay) {
            zoomDisplay.textContent = '1x';
        }
    }
    
    setWaterfallColormap(colormap) {
        if (this.waterfallDisplay) {
            this.waterfallDisplay.setColormap(colormap);
        }
    }
    
    setWaterfallIntensity(min, max) {
        if (this.waterfallDisplay) {
            this.waterfallDisplay.setIntensityRange(min, max);
        }
        
        // Update displays
        const minDisplay = document.getElementById('intensity-min-display');
        const maxDisplay = document.getElementById('intensity-max-display');
        if (minDisplay) minDisplay.textContent = min;
        if (maxDisplay) maxDisplay.textContent = max;
    }
    
    autoScaleWaterfall() {
        if (this.waterfallDisplay) {
            this.waterfallDisplay.autoScale();
            
            // Update UI controls
            const minSlider = document.getElementById('intensity-min');
            const maxSlider = document.getElementById('intensity-max');
            if (minSlider) minSlider.value = this.waterfallDisplay.minIntensity;
            if (maxSlider) maxSlider.value = this.waterfallDisplay.maxIntensity;
        }
    }
    
    // Audio Control Methods
    
    startAudio() {
        if (this.audioService) {
            this.audioService.startPlayback();
            
            const playBtn = document.getElementById('audio-play');
            const stopBtn = document.getElementById('audio-stop');
            if (playBtn) playBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = false;
        }
    }
    
    stopAudio() {
        if (this.audioService) {
            this.audioService.stopPlayback();
            
            const playBtn = document.getElementById('audio-play');
            const stopBtn = document.getElementById('audio-stop');
            if (playBtn) playBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = true;
        }
    }
    
    setVolume(volume) {
        this.volume = volume;
        
        if (this.audioService) {
            this.audioService.setVolume(volume / 100);
        }
    }
    
    setSquelch(squelch) {
        this.squelch = squelch;
        
        if (this.audioService) {
            this.audioService.setSquelch(squelch);
        }
    }
    
    enableAudioControls() {
        const audioControls = document.querySelectorAll('#audio-play, #audio-stop, #volume-slider, #squelch-slider');
        audioControls.forEach(control => {
            if (control.id !== 'audio-stop') {
                control.disabled = false;
            }
        });
    }
    
    disableAudioControls() {
        const audioControls = document.querySelectorAll('#audio-play, #audio-stop, #volume-slider, #squelch-slider');
        audioControls.forEach(control => {
            control.disabled = true;
        });
    }
    
    // UI Helper Methods
    
    updateSDRButtons() {
        const startBtn = document.getElementById('sdr-start');
        const stopBtn = document.getElementById('sdr-stop');
        
        if (startBtn) startBtn.disabled = this.sdrRunning;
        if (stopBtn) stopBtn.disabled = !this.sdrRunning;
        
        // Update status indicator
        const statusElement = document.getElementById('sdr-status');
        if (statusElement) {
            if (this.sdrRunning) {
                statusElement.className = 'status-indicator online';
                statusElement.textContent = 'RTL-SDR: Online';
            } else {
                statusElement.className = 'status-indicator offline';
                statusElement.textContent = 'RTL-SDR: Offline';
            }
        }
    }
    
    toggleTheme() {
        const body = document.body;
        const themeToggle = document.getElementById('theme-toggle');
        
        if (body.classList.contains('theme-dark')) {
            body.classList.remove('theme-dark');
            body.classList.add('theme-light');
            if (themeToggle) themeToggle.textContent = '🌙';
        } else {
            body.classList.remove('theme-light');
            body.classList.add('theme-dark');
            if (themeToggle) themeToggle.textContent = '☀️';
        }
        
        // Save preference
        localStorage.setItem('theme', body.classList.contains('theme-dark') ? 'dark' : 'light');
    }
    
    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }
    
    handleControlMessage(data) {
        switch (data.type) {
            case 'sdr_status':
                this.handleSDRStatus(data);
                break;
            case 'error':
                this.showError(data.message);
                break;
            case 'pong':
                // Health check response
                break;
            default:
                console.log('Unknown control message:', data);
        }
    }
    
    handleSDRStatus(data) {
        // Update performance info
        if (data.cpu_usage !== undefined) {
            const cpuElement = document.getElementById('cpu-usage');
            if (cpuElement) {
                cpuElement.textContent = `CPU: ${data.cpu_usage.toFixed(1)}%`;
            }
        }
        
        if (data.memory_usage !== undefined) {
            const memElement = document.getElementById('memory-usage');
            if (memElement) {
                memElement.textContent = `RAM: ${data.memory_usage.toFixed(1)} MB`;
            }
        }
        
        if (data.data_rate !== undefined) {
            const rateElement = document.getElementById('data-rate');
            if (rateElement) {
                rateElement.textContent = `Rate: ${(data.data_rate / 1024).toFixed(1)} kB/s`;
            }
        }
    }
    
    showError(message) {
        const errorModal = document.getElementById('error-modal');
        const errorMessage = document.getElementById('error-message');
        
        if (errorModal && errorMessage) {
            errorMessage.textContent = message;
            errorModal.classList.remove('hidden');
        }
        
        console.error('Application error:', message);
    }
    
    loadSettings() {
        // Load theme preference
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'light') {
            document.body.classList.remove('theme-dark');
            document.body.classList.add('theme-light');
            const themeToggle = document.getElementById('theme-toggle');
            if (themeToggle) themeToggle.textContent = '🌙';
        }
        
        // Load other preferences
        const savedFrequency = localStorage.getItem('frequency');
        if (savedFrequency) {
            this.setFrequency(parseFloat(savedFrequency));
        }
    }
    
    saveSettings() {
        localStorage.setItem('frequency', this.currentFrequency.toString());
        localStorage.setItem('gain', this.gain.toString());
        localStorage.setItem('demod_mode', this.demodMode);
        localStorage.setItem('bandwidth', this.bandwidth.toString());
    }
    
    cleanup() {
        if (this.websocketClient) {
            this.websocketClient.cleanup();
        }
        
        if (this.audioService) {
            this.audioService.cleanup();
        }
        
        this.saveSettings();
    }
}

// Initialize application when page loads
let app = null;

document.addEventListener('DOMContentLoaded', async () => {
    app = new H1SDRWebApp();
    const success = await app.initialize();
    
    if (!success) {
        console.error('Failed to initialize H1SDR WebApp');
    }
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (app) {
        app.cleanup();
    }
});

// Handle modal close buttons
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-close') || e.target.id === 'error-ok') {
        const modal = e.target.closest('.modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }
});

// Export for debugging
window.H1SDRApp = app;