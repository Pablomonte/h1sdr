/**
 * Audio Player Component
 * Handles Web Audio API integration for SDR audio playback
 */

import { CONFIG, log } from '../config.js';
import { perfmon } from '../utils/performance-utils.js';

/**
 * Audio Player class using Web Audio API
 */
export class AudioPlayer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.audioContext = null;
        this.sourceNode = null;
        this.gainNode = null;
        this.analyserNode = null;
        this.isPlaying = false;
        this.volume = 0.5;
        this.muted = false;
        this.agcEnabled = true;
        this.squelchLevel = -60; // dB
        this.audioData = new Float32Array(1024);
        
        this.callbacks = new Map();
        
        this.init();
    }

    /**
     * Initialize audio player
     */
    async init() {
        if (!this.container) {
            log('error', 'Audio player container not found');
            return;
        }

        this.createUI();
        this.attachEventListeners();
        
        try {
            await this.initAudioContext();
        } catch (error) {
            log('error', 'Failed to initialize audio context:', error);
            this.showError('Audio not supported by browser');
        }
    }

    /**
     * Initialize Web Audio Context
     */
    async initAudioContext() {
        if (!window.AudioContext && !window.webkitAudioContext) {
            throw new Error('Web Audio API not supported');
        }

        this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: CONFIG.AUDIO_SAMPLE_RATE,
            latencyHint: 'interactive'
        });

        // Create audio nodes
        this.gainNode = this.audioContext.createGain();
        this.analyserNode = this.audioContext.createAnalyser();
        
        // Configure analyser
        this.analyserNode.fftSize = 256;
        this.analyserNode.smoothingTimeConstant = 0.8;
        
        // Connect nodes
        this.gainNode.connect(this.analyserNode);
        this.analyserNode.connect(this.audioContext.destination);
        
        // Set initial volume
        this.gainNode.gain.value = this.volume;
        
        log('info', 'Audio context initialized');
    }

    /**
     * Create audio player UI
     */
    createUI() {
        this.container.innerHTML = `
            <div class="control-section">
                <div class="control-section-title">Audio Controls</div>
                
                <div class="control-row">
                    <button id="play-pause-btn" class="control-button" disabled>
                        <span class="icon">▶</span> Play
                    </button>
                    
                    <button id="mute-btn" class="control-button secondary">
                        <span class="icon">🔊</span>
                    </button>
                    
                    <div class="control-group">
                        <label for="volume-slider">Volume</label>
                        <input type="range" 
                               id="volume-slider" 
                               class="control-input" 
                               min="0" 
                               max="100" 
                               value="50"
                               title="Audio volume">
                    </div>
                </div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label for="squelch-slider">Squelch</label>
                        <input type="range" 
                               id="squelch-slider" 
                               class="control-input" 
                               min="-80" 
                               max="-20" 
                               value="-60"
                               title="Squelch level in dB">
                    </div>
                    
                    <div class="control-group">
                        <div class="toggle-switch">
                            <input type="checkbox" id="agc-toggle" checked>
                            <span class="toggle-slider"></span>
                        </div>
                        <label for="agc-toggle">AGC</label>
                    </div>
                    
                    <div class="control-group">
                        <label>Level</label>
                        <div id="audio-level" class="audio-level-meter">
                            <div class="audio-level-bar"></div>
                        </div>
                    </div>
                </div>
                
                <div class="control-row">
                    <div class="status-indicator">
                        <div id="audio-status-dot" class="status-dot"></div>
                        <span id="audio-status-text">Stopped</span>
                    </div>
                    
                    <div class="control-group">
                        <label>Rate</label>
                        <div class="value-display">${CONFIG.AUDIO_SAMPLE_RATE / 1000} kHz</div>
                    </div>
                </div>
            </div>
            
            <style>
            .audio-level-meter {
                width: 80px;
                height: 16px;
                background: var(--audio-level-bg);
                border-radius: 8px;
                overflow: hidden;
                position: relative;
            }
            
            .audio-level-bar {
                height: 100%;
                background: linear-gradient(to right, 
                    var(--success-color) 0%, 
                    var(--warning-color) 70%, 
                    var(--error-color) 90%);
                width: 0%;
                transition: width 0.1s ease-out;
            }
            </style>
        `;

        // Get UI elements
        this.playPauseBtn = this.container.querySelector('#play-pause-btn');
        this.muteBtn = this.container.querySelector('#mute-btn');
        this.volumeSlider = this.container.querySelector('#volume-slider');
        this.squelchSlider = this.container.querySelector('#squelch-slider');
        this.agcToggle = this.container.querySelector('#agc-toggle');
        this.audioLevelBar = this.container.querySelector('.audio-level-bar');
        this.statusDot = this.container.querySelector('#audio-status-dot');
        this.statusText = this.container.querySelector('#audio-status-text');
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Play/Pause button
        this.playPauseBtn.addEventListener('click', () => {
            if (this.isPlaying) {
                this.stop();
            } else {
                this.play();
            }
        });

        // Mute button
        this.muteBtn.addEventListener('click', () => {
            this.toggleMute();
        });

        // Volume slider
        this.volumeSlider.addEventListener('input', (e) => {
            this.setVolume(parseInt(e.target.value) / 100);
        });

        // Squelch slider
        this.squelchSlider.addEventListener('input', (e) => {
            this.setSquelchLevel(parseInt(e.target.value));
        });

        // AGC toggle
        this.agcToggle.addEventListener('change', (e) => {
            this.setAGCEnabled(e.target.checked);
        });
    }

    /**
     * Start audio playback
     */
    async play() {
        if (!this.audioContext) {
            await this.initAudioContext();
        }

        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }

        this.isPlaying = true;
        this.updateUI();
        this.startLevelMonitoring();
        
        this.trigger('play');
        log('info', 'Audio playback started');
    }

    /**
     * Stop audio playback
     */
    stop() {
        if (this.sourceNode) {
            this.sourceNode.disconnect();
            this.sourceNode = null;
        }

        this.isPlaying = false;
        this.updateUI();
        this.stopLevelMonitoring();
        
        this.trigger('stop');
        log('info', 'Audio playback stopped');
    }

    /**
     * Process incoming audio data
     * @param {Float32Array} audioData - Audio samples
     */
    processAudioData(audioData) {
        if (!this.isPlaying || !this.audioContext) {
            return;
        }

        perfmon.start('audio-processing');

        try {
            // Apply AGC if enabled
            if (this.agcEnabled) {
                this.applyAGC(audioData);
            }

            // Apply squelch
            if (this.isSquelched(audioData)) {
                // Mute audio by filling with zeros
                audioData.fill(0);
            }

            // Create audio buffer and play
            this.playAudioBuffer(audioData);
            
        } finally {
            perfmon.end('audio-processing');
        }
    }

    /**
     * Create and play audio buffer
     * @param {Float32Array} audioData - Audio samples
     */
    playAudioBuffer(audioData) {
        if (!this.audioContext || audioData.length === 0) {
            return;
        }

        const buffer = this.audioContext.createBuffer(
            1, // mono
            audioData.length,
            CONFIG.AUDIO_SAMPLE_RATE
        );

        buffer.copyToChannel(audioData, 0);

        // Disconnect previous source
        if (this.sourceNode) {
            this.sourceNode.disconnect();
        }

        // Create new source
        this.sourceNode = this.audioContext.createBufferSource();
        this.sourceNode.buffer = buffer;
        this.sourceNode.connect(this.gainNode);
        
        // Start playback
        this.sourceNode.start();
    }

    /**
     * Apply simple AGC
     * @param {Float32Array} audioData - Audio samples to process
     */
    applyAGC(audioData) {
        // Calculate RMS level
        let rms = 0;
        for (let i = 0; i < audioData.length; i++) {
            rms += audioData[i] * audioData[i];
        }
        rms = Math.sqrt(rms / audioData.length);

        // Target RMS level
        const targetRMS = 0.2;
        
        if (rms > 0.001) { // Avoid division by zero
            const gain = Math.min(10, targetRMS / rms);
            
            // Apply gain
            for (let i = 0; i < audioData.length; i++) {
                audioData[i] *= gain;
                
                // Soft clipping
                if (audioData[i] > 0.95) {
                    audioData[i] = 0.95;
                } else if (audioData[i] < -0.95) {
                    audioData[i] = -0.95;
                }
            }
        }
    }

    /**
     * Check if audio should be squelched
     * @param {Float32Array} audioData - Audio samples
     * @returns {boolean} True if squelched
     */
    isSquelched(audioData) {
        // Calculate signal level in dB
        let rms = 0;
        for (let i = 0; i < audioData.length; i++) {
            rms += audioData[i] * audioData[i];
        }
        rms = Math.sqrt(rms / audioData.length);
        
        const levelDb = rms > 0 ? 20 * Math.log10(rms) : -100;
        
        return levelDb < this.squelchLevel;
    }

    /**
     * Set audio volume
     * @param {number} volume - Volume (0-1)
     */
    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));
        
        if (this.gainNode) {
            this.gainNode.gain.value = this.muted ? 0 : this.volume;
        }
        
        this.volumeSlider.value = this.volume * 100;
        this.trigger('volume-changed', { volume: this.volume });
    }

    /**
     * Toggle mute
     */
    toggleMute() {
        this.muted = !this.muted;
        
        if (this.gainNode) {
            this.gainNode.gain.value = this.muted ? 0 : this.volume;
        }
        
        this.updateUI();
        this.trigger('mute-changed', { muted: this.muted });
    }

    /**
     * Set squelch level
     * @param {number} level - Squelch level in dB
     */
    setSquelchLevel(level) {
        this.squelchLevel = level;
        this.trigger('squelch-changed', { level });
    }

    /**
     * Enable/disable AGC
     * @param {boolean} enabled - AGC enabled state
     */
    setAGCEnabled(enabled) {
        this.agcEnabled = enabled;
        this.trigger('agc-changed', { enabled });
    }

    /**
     * Start audio level monitoring
     */
    startLevelMonitoring() {
        if (!this.analyserNode) return;

        const monitor = () => {
            if (!this.isPlaying) return;

            const dataArray = new Uint8Array(this.analyserNode.frequencyBinCount);
            this.analyserNode.getByteFrequencyData(dataArray);

            // Calculate average level
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i];
            }
            const avgLevel = sum / dataArray.length / 255;

            // Update UI
            this.audioLevelBar.style.width = `${avgLevel * 100}%`;

            // Continue monitoring
            requestAnimationFrame(monitor);
        };

        monitor();
    }

    /**
     * Stop audio level monitoring
     */
    stopLevelMonitoring() {
        if (this.audioLevelBar) {
            this.audioLevelBar.style.width = '0%';
        }
    }

    /**
     * Update UI state
     */
    updateUI() {
        // Play/Pause button
        const icon = this.playPauseBtn.querySelector('.icon');
        if (this.isPlaying) {
            icon.textContent = '⏸';
            this.playPauseBtn.innerHTML = '<span class="icon">⏸</span> Stop';
            this.playPauseBtn.classList.remove('secondary');
            this.playPauseBtn.classList.add('danger');
        } else {
            icon.textContent = '▶';
            this.playPauseBtn.innerHTML = '<span class="icon">▶</span> Play';
            this.playPauseBtn.classList.remove('danger');
            this.playPauseBtn.classList.add('secondary');
        }

        // Mute button
        const muteIcon = this.muteBtn.querySelector('.icon');
        muteIcon.textContent = this.muted ? '🔇' : '🔊';
        this.muteBtn.classList.toggle('active', this.muted);

        // Status indicator
        if (this.isPlaying) {
            this.statusDot.classList.add('connected');
            this.statusText.textContent = 'Playing';
        } else {
            this.statusDot.classList.remove('connected');
            this.statusText.textContent = 'Stopped';
        }
    }

    /**
     * Show error message
     * @param {string} message - Error message
     */
    showError(message) {
        this.statusText.textContent = `Error: ${message}`;
        this.statusDot.classList.remove('connected');
        this.statusDot.classList.add('error');
    }

    /**
     * Enable audio playback
     * @param {boolean} enabled - Enable state
     */
    setEnabled(enabled) {
        this.playPauseBtn.disabled = !enabled;
        if (!enabled && this.isPlaying) {
            this.stop();
        }
    }

    /**
     * Add event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    on(event, callback) {
        if (!this.callbacks.has(event)) {
            this.callbacks.set(event, []);
        }
        this.callbacks.get(event).push(callback);
    }

    /**
     * Remove event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    off(event, callback) {
        if (this.callbacks.has(event)) {
            const callbacks = this.callbacks.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    /**
     * Trigger event
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    trigger(event, data) {
        if (this.callbacks.has(event)) {
            this.callbacks.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    log('error', `Error in ${event} callback:`, error);
                }
            });
        }
    }

    /**
     * Cleanup resources
     */
    destroy() {
        this.stop();
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        this.callbacks.clear();
    }
}

export default AudioPlayer;