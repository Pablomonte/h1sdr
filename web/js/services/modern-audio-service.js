/**
 * Modern AudioService using AudioWorklet for H1SDR
 * Production-grade real-time audio processing for SDR applications
 */

class ModernAudioService {
    constructor() {
        this.audioContext = null;
        this.audioWorkletNode = null;
        this.gainNode = null;
        this.analyserNode = null;

        // Configuration
        this.sampleRate = 48000;
        this.workletPath = '/static/js/audio-worklet.js';

        // Audio state
        this.isInitialized = false;
        this.isPlaying = false;
        this.volume = 0.5;
        this.squelchLevel = 0.0;

        // Performance monitoring
        this.stats = {
            samplesProcessed: 0,
            bufferUnderruns: 0,
            signalLevel: 0,
            bufferPercent: 0
        };

        // Event callbacks
        this.onStatusChange = null;
        this.onStatsUpdate = null;
        this.onError = null;

        console.log('ModernAudioService initialized');
    }

    /**
     * Initialize the audio system with AudioWorklet
     */
    async initialize() {
        try {
            console.log('🎵 Initializing modern audio system...');

            // Check AudioWorklet support
            if (!window.AudioWorklet) {
                throw new Error('AudioWorklet not supported in this browser');
            }

            // Create audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.sampleRate,
                latencyHint: 'interactive'
            });

            console.log(`🎵 Audio context created: ${this.audioContext.sampleRate}Hz, state: ${this.audioContext.state}`);

            // Resume context if suspended (browser policy requirement)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
                console.log('🎵 Audio context resumed');
            }

            // Load and register the AudioWorklet processor
            await this.audioContext.audioWorklet.addModule(this.workletPath);
            console.log('🎵 AudioWorklet processor loaded');

            // Create the AudioWorkletNode
            this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'sdr-audio-processor', {
                numberOfInputs: 0,
                numberOfOutputs: 1,
                outputChannelCount: [1],
                processorOptions: {
                    sampleRate: this.audioContext.sampleRate
                }
            });

            // Create gain node for volume control
            this.gainNode = this.audioContext.createGain();
            this.gainNode.gain.setValueAtTime(this.volume, this.audioContext.currentTime);

            // Create analyser for signal monitoring
            this.analyserNode = this.audioContext.createAnalyser();
            this.analyserNode.fftSize = 256;
            this.analyserNode.smoothingTimeConstant = 0.3;

            // Connect audio chain: AudioWorklet -> Gain -> Analyser -> Output
            this.audioWorkletNode.connect(this.gainNode);
            this.gainNode.connect(this.analyserNode);
            this.analyserNode.connect(this.audioContext.destination);

            // Setup message handling from worklet
            this.setupWorkletMessaging();

            this.isInitialized = true;
            console.log('✅ Modern audio system initialized successfully');

            return true;

        } catch (error) {
            console.error('❌ Failed to initialize audio system:', error);
            if (this.onError) {
                this.onError(error);
            }
            return false;
        }
    }

    /**
     * Setup bidirectional messaging with AudioWorklet
     */
    setupWorkletMessaging() {
        if (!this.audioWorkletNode) return;

        this.audioWorkletNode.port.onmessage = (event) => {
            const { type, data } = event.data;

            switch (type) {
                case 'status':
                    this.handleStatusUpdate(data);
                    break;

                case 'stats':
                    this.handleStatsUpdate(data);
                    break;

                case 'fullStats':
                    this.stats = { ...this.stats, ...data };
                    if (this.onStatsUpdate) {
                        this.onStatsUpdate(this.stats);
                    }
                    break;

                case 'error':
                    console.error('AudioWorklet error:', data);
                    if (this.onError) {
                        this.onError(new Error(data.message));
                    }
                    break;
            }
        };

        this.audioWorkletNode.port.onerror = (error) => {
            console.error('AudioWorklet port error:', error);
            if (this.onError) {
                this.onError(error);
            }
        };
    }

    /**
     * Handle status updates from worklet
     */
    handleStatusUpdate(status) {
        if (status.playing !== undefined) {
            this.isPlaying = status.playing;
        }

        if (this.onStatusChange) {
            this.onStatusChange(status);
        }

        // Log significant status changes with enhanced monitoring
        if (status.started) {
            console.log('🎵 Audio playback started (pre-buffering)');
        } else if (status.playing && !status.preBuffering) {
            const healthMsg = status.bufferHealthy ? '✅ Healthy buffer' : '⚠️ Low buffer';
            console.log(`🎵 Audio playback active - ${healthMsg} (${status.bufferPercent}%)`);
        } else if (status.underrun) {
            console.warn(`⚠️ Audio buffer underrun, restarting pre-buffer (had ${status.bufferLength} samples, need ${status.minRequired})`);
        } else if (status.lowBuffer) {
            console.warn(`⚠️ Audio buffer critically low, restarting pre-buffer (${status.bufferLength} samples)`);
        } else if (status.stopped) {
            console.log('🎵 Audio playback stopped');
        }
    }

    /**
     * Handle stats updates from worklet
     */
    handleStatsUpdate(stats) {
        this.stats = { ...this.stats, ...stats };

        // Log performance issues and health monitoring
        if (stats.bufferUnderruns > this.stats.bufferUnderruns) {
            console.warn(`⚠️ Buffer underruns: ${stats.bufferUnderruns}`);
        }

        // Monitor buffer health
        if (stats.isHealthy === false && this.stats.isHealthy !== false) {
            console.warn(`⚠️ Audio buffer health degraded to ${stats.bufferHealth}%`);
        } else if (stats.isHealthy === true && this.stats.isHealthy === false) {
            console.log(`✅ Audio buffer health recovered to ${stats.bufferHealth}%`);
        }

        if (this.onStatsUpdate) {
            this.onStatsUpdate(this.stats);
        }
    }

    /**
     * Start audio playback
     */
    async startAudio() {
        try {
            if (!this.isInitialized) {
                const success = await this.initialize();
                if (!success) {
                    throw new Error('Failed to initialize audio system');
                }
            }

            // Ensure audio context is running
            if (this.audioContext.state !== 'running') {
                await this.audioContext.resume();
            }

            // Send start command to worklet
            this.audioWorkletNode.port.postMessage({
                type: 'start'
            });

            console.log('🎵 Audio start command sent to worklet');
            return true;

        } catch (error) {
            console.error('❌ Failed to start audio:', error);
            if (this.onError) {
                this.onError(error);
            }
            throw error;
        }
    }

    /**
     * Stop audio playback
     */
    stopAudio() {
        if (!this.audioWorkletNode) return;

        this.audioWorkletNode.port.postMessage({
            type: 'stop'
        });

        this.isPlaying = false;
        console.log('🎵 Audio stop command sent to worklet');
    }

    /**
     * Process incoming audio data from WebSocket
     */
    processAudioData(audioData) {
        if (!this.audioWorkletNode || !audioData || audioData.length === 0) {
            return;
        }

        // Send audio data to worklet for processing
        this.audioWorkletNode.port.postMessage({
            type: 'audioData',
            data: audioData
        });
    }

    /**
     * Set volume level (0.0 to 1.0)
     */
    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));

        // Update gain node
        if (this.gainNode) {
            this.gainNode.gain.setValueAtTime(this.volume, this.audioContext.currentTime);
        }

        // Update worklet
        if (this.audioWorkletNode) {
            this.audioWorkletNode.port.postMessage({
                type: 'setVolume',
                data: this.volume
            });
        }

        console.log(`🎵 Volume set to ${(this.volume * 100).toFixed(0)}%`);
    }

    /**
     * Set squelch level
     */
    setSquelch(level) {
        this.squelchLevel = level;

        if (this.audioWorkletNode) {
            this.audioWorkletNode.port.postMessage({
                type: 'setSquelch',
                data: level
            });
        }

        console.log(`🎵 Squelch set to ${level.toFixed(3)}`);
    }

    /**
     * Configure AGC (Automatic Gain Control)
     */
    setAGC(enabled, target = 0.3) {
        if (this.audioWorkletNode) {
            this.audioWorkletNode.port.postMessage({
                type: 'setAGC',
                data: { enabled, target }
            });
        }

        console.log(`🎵 AGC ${enabled ? 'enabled' : 'disabled'}, target: ${target}`);
    }

    /**
     * Get current audio statistics
     */
    getStats() {
        if (this.audioWorkletNode) {
            this.audioWorkletNode.port.postMessage({
                type: 'getStats'
            });
        }
        return this.stats;
    }

    /**
     * Create audio analyser for visualization
     */
    createAnalyser() {
        if (!this.analyserNode) return null;

        return {
            node: this.analyserNode,
            getByteFrequencyData: () => {
                const dataArray = new Uint8Array(this.analyserNode.frequencyBinCount);
                this.analyserNode.getByteFrequencyData(dataArray);
                return dataArray;
            },
            getByteTimeDomainData: () => {
                const dataArray = new Uint8Array(this.analyserNode.frequencyBinCount);
                this.analyserNode.getByteTimeDomainData(dataArray);
                return dataArray;
            }
        };
    }

    /**
     * Check if AudioWorklet is supported
     */
    static isSupported() {
        return !!(window.AudioContext || window.webkitAudioContext) &&
               !!window.AudioWorklet;
    }

    /**
     * Get audio context info
     */
    getAudioInfo() {
        if (!this.audioContext) return null;

        return {
            sampleRate: this.audioContext.sampleRate,
            state: this.audioContext.state,
            baseLatency: this.audioContext.baseLatency,
            outputLatency: this.audioContext.outputLatency,
            currentTime: this.audioContext.currentTime
        };
    }

    /**
     * Cleanup resources
     */
    cleanup() {
        console.log('🎵 Cleaning up audio resources...');

        if (this.audioWorkletNode) {
            this.audioWorkletNode.disconnect();
            this.audioWorkletNode = null;
        }

        if (this.gainNode) {
            this.gainNode.disconnect();
            this.gainNode = null;
        }

        if (this.analyserNode) {
            this.analyserNode.disconnect();
            this.analyserNode = null;
        }

        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.isInitialized = false;
        this.isPlaying = false;
        console.log('🎵 Audio cleanup completed');
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModernAudioService;
}

// Global assignment for direct script inclusion
if (typeof window !== 'undefined') {
    window.ModernAudioService = ModernAudioService;
}