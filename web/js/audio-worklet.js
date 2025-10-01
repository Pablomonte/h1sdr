/**
 * H1SDR AudioWorklet Processor
 * High-performance real-time audio processing for SDR applications
 */

class SDRAudioProcessor extends AudioWorkletProcessor {
    constructor(options) {
        super();

        // Audio configuration
        this.sampleRate = options?.processorOptions?.sampleRate || sampleRate;
        this.bufferSize = 128; // AudioWorklet quantum size

        // Circular buffer for continuous audio - LARGER BUFFER
        this.circularBufferSize = this.sampleRate * 10; // 10 seconds buffer for maximum stability
        this.circularBuffer = new Float32Array(this.circularBufferSize);
        this.writeIndex = 0;
        this.readIndex = 0;
        this.bufferLength = 0;

        // Audio processing state - ADAPTIVE PRE-BUFFERING
        this.isPlaying = false;
        this.preBuffering = true;
        this.minPreBufferSize = this.sampleRate * 2.0; // 2000ms pre-buffer for smooth playback
        this.optimalBufferSize = this.sampleRate * 4.0; // Target 4s buffer level
        this.maxPreBufferSize = this.sampleRate * 6.0; // Maximum 6s before starting playback

        // Volume and effects
        this.volume = 0.5;
        this.squelchThreshold = 0.0;
        this.agcEnabled = true;
        this.agcTarget = 0.3;
        this.agcGain = 1.0;
        this.agcAttack = 0.01;
        this.agcRelease = 0.003;

        // Performance monitoring
        this.processedSamples = 0;
        this.bufferUnderruns = 0;
        this.lastLogTime = 0;

        // Message handling
        this.port.onmessage = this.handleMessage.bind(this);

        console.log('SDRAudioProcessor initialized:', {
            sampleRate: this.sampleRate,
            bufferSize: this.bufferSize,
            circularBufferSize: this.circularBufferSize
        });
    }

    handleMessage(event) {
        const { type, data } = event.data;

        switch (type) {
            case 'audioData':
                this.writeAudioData(data);
                break;

            case 'setVolume':
                this.volume = Math.max(0, Math.min(1, data));
                break;

            case 'setSquelch':
                this.squelchThreshold = data;
                break;

            case 'setAGC':
                this.agcEnabled = data.enabled;
                this.agcTarget = data.target || this.agcTarget;
                break;

            case 'start':
                this.startPlayback();
                break;

            case 'stop':
                this.stopPlayback();
                break;

            case 'getStats':
                this.sendStats();
                break;
        }
    }

    writeAudioData(audioData) {
        if (!audioData || audioData.length === 0) return;

        const samplestoWrite = audioData.length;

        // Write to circular buffer
        for (let i = 0; i < samplestoWrite; i++) {
            this.circularBuffer[this.writeIndex] = audioData[i];
            this.writeIndex = (this.writeIndex + 1) % this.circularBufferSize;

            // Handle buffer overflow
            if (this.bufferLength < this.circularBufferSize) {
                this.bufferLength++;
            } else {
                // Buffer overflow - advance read pointer
                this.readIndex = (this.readIndex + 1) % this.circularBufferSize;
            }
        }

        // Check if we should start playing after pre-buffering - CONSERVATIVE START LOGIC
        if (this.preBuffering) {
            const shouldStart = this.bufferLength >= this.optimalBufferSize;
            const hasOptimalBuffer = this.bufferLength >= this.optimalBufferSize;

            if (shouldStart) {
                this.preBuffering = false;
                this.isPlaying = true;

                this.port.postMessage({
                    type: 'status',
                    data: {
                        playing: true,
                        preBuffering: false,
                        bufferLength: this.bufferLength,
                        bufferHealthy: hasOptimalBuffer,
                        bufferPercent: (this.bufferLength / this.optimalBufferSize * 100).toFixed(1)
                    }
                });
            }
        }
    }

    process(inputs, outputs, parameters) {
        const output = outputs[0];
        if (!output || output.length === 0) return true;

        const outputChannel = output[0];
        const framesToProcess = outputChannel.length;

        if (!this.isPlaying || this.preBuffering) {
            // Fill with silence during pre-buffering or when stopped
            outputChannel.fill(0);
            return true;
        }

        // Check if we have enough data - ADAPTIVE BUFFER MANAGEMENT
        if (this.bufferLength < framesToProcess) {
            // Buffer underrun
            this.bufferUnderruns++;
            outputChannel.fill(0);

            // Always restart pre-buffering on any underrun for stability
            this.preBuffering = true;
            this.isPlaying = false;

            this.port.postMessage({
                type: 'status',
                data: {
                    playing: false,
                    preBuffering: true,
                    underrun: true,
                    bufferLength: this.bufferLength,
                    minRequired: this.minPreBufferSize
                }
            });
            return true;
        }

        // Adaptive buffer level monitoring - restart pre-buffering if buffer gets too low
        if (this.isPlaying && this.bufferLength < this.minPreBufferSize * 0.75) {
            this.preBuffering = true;
            this.isPlaying = false;

            this.port.postMessage({
                type: 'status',
                data: {
                    playing: false,
                    preBuffering: true,
                    lowBuffer: true,
                    bufferLength: this.bufferLength
                }
            });
        }

        // Process audio samples
        let signalLevel = 0;

        for (let i = 0; i < framesToProcess; i++) {
            // Read from circular buffer
            let sample = this.circularBuffer[this.readIndex];
            this.readIndex = (this.readIndex + 1) % this.circularBufferSize;
            this.bufferLength--;

            // Apply AGC if enabled
            if (this.agcEnabled) {
                sample = this.applyAGC(sample);
            }

            // Apply squelch
            if (Math.abs(sample) < this.squelchThreshold) {
                sample = 0;
            }

            // Apply volume
            sample *= this.volume;

            // Track signal level
            signalLevel += Math.abs(sample);

            // Output sample
            outputChannel[i] = sample;
        }

        // Update statistics
        this.processedSamples += framesToProcess;
        signalLevel /= framesToProcess;

        // Send periodic stats (every 100ms) with health monitoring
        const currentTime = currentFrame / this.sampleRate;
        if (currentTime - this.lastLogTime > 0.1) {
            const bufferHealth = this.bufferLength / this.optimalBufferSize;
            const isHealthy = bufferHealth >= 0.5; // At least 50% of optimal buffer

            this.port.postMessage({
                type: 'stats',
                data: {
                    bufferLength: this.bufferLength,
                    bufferPercent: (this.bufferLength / this.circularBufferSize * 100).toFixed(1),
                    bufferHealth: (bufferHealth * 100).toFixed(1),
                    isHealthy: isHealthy,
                    signalLevel: signalLevel.toFixed(4),
                    processedSamples: this.processedSamples,
                    bufferUnderruns: this.bufferUnderruns,
                    agcGain: this.agcGain.toFixed(3),
                    optimalBuffer: this.optimalBufferSize,
                    minBuffer: this.minPreBufferSize
                }
            });
            this.lastLogTime = currentTime;
        }

        return true;
    }

    applyAGC(sample) {
        const sampleLevel = Math.abs(sample);

        // Update AGC gain based on signal level
        if (sampleLevel > this.agcTarget) {
            // Attack: reduce gain quickly
            this.agcGain *= (1 - this.agcAttack);
        } else {
            // Release: increase gain slowly
            this.agcGain *= (1 + this.agcRelease);
        }

        // Clamp AGC gain to reasonable limits
        this.agcGain = Math.max(0.1, Math.min(10.0, this.agcGain));

        return sample * this.agcGain;
    }

    startPlayback() {
        // Reset buffer state
        this.writeIndex = 0;
        this.readIndex = 0;
        this.bufferLength = 0;
        this.circularBuffer.fill(0);

        // Start in pre-buffering mode
        this.isPlaying = false;
        this.preBuffering = true;

        this.port.postMessage({
            type: 'status',
            data: {
                playing: false,
                preBuffering: true,
                started: true
            }
        });
    }

    stopPlayback() {
        this.isPlaying = false;
        this.preBuffering = false;

        // Clear buffer
        this.writeIndex = 0;
        this.readIndex = 0;
        this.bufferLength = 0;
        this.circularBuffer.fill(0);

        this.port.postMessage({
            type: 'status',
            data: {
                playing: false,
                preBuffering: false,
                stopped: true
            }
        });
    }

    sendStats() {
        this.port.postMessage({
            type: 'fullStats',
            data: {
                sampleRate: this.sampleRate,
                bufferSize: this.bufferSize,
                circularBufferSize: this.circularBufferSize,
                bufferLength: this.bufferLength,
                bufferPercent: (this.bufferLength / this.circularBufferSize * 100).toFixed(1),
                processedSamples: this.processedSamples,
                bufferUnderruns: this.bufferUnderruns,
                isPlaying: this.isPlaying,
                preBuffering: this.preBuffering,
                volume: this.volume,
                squelchThreshold: this.squelchThreshold,
                agcEnabled: this.agcEnabled,
                agcGain: this.agcGain.toFixed(3)
            }
        });
    }
}

// Register the processor
registerProcessor('sdr-audio-processor', SDRAudioProcessor);