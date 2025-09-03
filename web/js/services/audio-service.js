/**
 * Web Audio API service for real-time audio processing and playback
 * Supports multiple demodulation modes and audio effects
 */

class AudioService {
    constructor() {
        this.audioContext = null;
        this.sampleRate = 48000;
        this.bufferSize = 4096;
        
        // Audio processing nodes
        this.gainNode = null;
        this.filterNode = null;
        this.analyserNode = null;
        this.scriptProcessor = null;
        
        // Continuous audio buffer management
        this.audioBuffer = [];
        this.bufferThreshold = 10; // Number of buffers to maintain
        this.circularBuffer = new Float32Array(48000 * 2); // 2 seconds circular buffer
        this.writeIndex = 0;
        this.readIndex = 0;
        this.bufferLength = 0;
        this.isPlaying = false;
        
        // Volume and effects
        this.volume = 0.5;
        this.squelchLevel = 0;
        this.agcEnabled = true;
        this.noiseReductionEnabled = false;
        
        // Audio analysis
        this.analyserData = null;
        this.signalLevel = 0;
        this.noiseFloor = -80;
        
        // Performance monitoring
        this.audioDropouts = 0;
        this.bufferUnderruns = 0;
        
        console.log('Audio service initialized');
    }
    
    async initialize() {
        try {
            // Create audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.sampleRate,
                latencyHint: 'interactive'
            });
            
            // Resume context if suspended (required by browsers)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }
            
            // Create audio processing chain
            this.setupAudioChain();
            
            console.log(`Audio context initialized: ${this.audioContext.sampleRate} Hz`);
            return true;
            
        } catch (error) {
            console.error('Failed to initialize audio context:', error);
            return false;
        }
    }
    
    setupAudioChain() {
        // Create gain node for volume control
        this.gainNode = this.audioContext.createGain();
        this.gainNode.gain.setValueAtTime(this.volume, this.audioContext.currentTime);
        
        // Create filter node for audio processing
        this.filterNode = this.audioContext.createBiquadFilter();
        this.filterNode.type = 'lowpass';
        this.filterNode.frequency.setValueAtTime(15000, this.audioContext.currentTime);
        this.filterNode.Q.setValueAtTime(0.707, this.audioContext.currentTime);
        
        // Create analyser for signal level monitoring
        this.analyserNode = this.audioContext.createAnalyser();
        this.analyserNode.fftSize = 256;
        this.analyserNode.smoothingTimeConstant = 0.3;
        this.analyserData = new Float32Array(this.analyserNode.frequencyBinCount);
        
        // Create script processor for continuous audio processing
        this.scriptProcessor = this.audioContext.createScriptProcessor(this.bufferSize, 0, 1);
        this.scriptProcessor.onaudioprocess = this.processAudioBuffer.bind(this);
        
        // Connect audio chain: ScriptProcessor -> Filter -> Gain -> Analyser -> Output
        this.scriptProcessor.connect(this.filterNode);
        this.filterNode.connect(this.gainNode);
        this.gainNode.connect(this.analyserNode);
        this.analyserNode.connect(this.audioContext.destination);
    }
    
    processAudioBuffer(event) {
        const outputBuffer = event.outputBuffer.getChannelData(0);
        const outputLength = outputBuffer.length;
        
        if (!this.isPlaying || this.bufferLength < outputLength) {
            // Not playing or insufficient data - output silence
            outputBuffer.fill(0);
            if (this.isPlaying) this.bufferUnderruns++;
            return;
        }
        
        // Read from circular buffer
        for (let i = 0; i < outputLength; i++) {
            outputBuffer[i] = this.circularBuffer[this.readIndex] * this.volume;
            this.readIndex = (this.readIndex + 1) % this.circularBuffer.length;
            this.bufferLength--;
        }
        
        // Apply AGC if enabled
        if (this.agcEnabled) {
            this.applyAGC(outputBuffer);
        }
        
        // Apply squelch
        if (this.squelchLevel > 0) {
            this.applySquelch(outputBuffer);
        }
        
        // Update signal level analysis
        this.updateSignalLevel();
    }
    
    applyAGC(buffer) {
        // Simple AGC implementation
        let peak = 0;
        for (let i = 0; i < buffer.length; i++) {
            peak = Math.max(peak, Math.abs(buffer[i]));
        }
        
        if (peak > 0.001) { // Avoid division by zero
            const targetLevel = 0.3;
            const gain = Math.min(10.0, targetLevel / peak);
            
            // Apply gain smoothly
            const currentGain = this.gainNode.gain.value;
            const newGain = currentGain * 0.95 + gain * 0.05;
            
            this.gainNode.gain.setValueAtTime(newGain, this.audioContext.currentTime);
        }
    }
    
    applySquelch(buffer) {
        // Apply squelch based on signal level
        const squelchThreshold = this.noiseFloor + this.squelchLevel;
        
        if (this.signalLevel < squelchThreshold) {
            // Mute audio below squelch threshold
            buffer.fill(0);
        }
    }
    
    updateSignalLevel() {
        // Get frequency domain data for signal level calculation
        this.analyserNode.getFloatFrequencyData(this.analyserData);
        
        // Calculate average signal level
        let sum = 0;
        let count = 0;
        
        for (let i = 0; i < this.analyserData.length; i++) {
            if (this.analyserData[i] > -Infinity) {
                sum += this.analyserData[i];
                count++;
            }
        }
        
        this.signalLevel = count > 0 ? sum / count : -100;
        
        // Update S-meter display
        this.updateSMeter();
    }
    
    updateSMeter() {
        // Convert signal level to S-meter units
        // S9 = -73 dBm, each S-unit = 6 dB
        const s9Level = -73;
        const sUnits = Math.max(0, (this.signalLevel - s9Level + 54) / 6); // S0 to S9
        
        let sMeterText;
        if (sUnits <= 9) {
            sMeterText = `S${Math.floor(sUnits)}`;
        } else {
            const overS9 = (sUnits - 9) * 6;
            sMeterText = `S9+${Math.floor(overS9)}`;
        }
        
        // Update S-meter UI
        const sMeterElement = document.getElementById('s-meter-value');
        const sMeterBar = document.getElementById('s-meter-bar');
        
        if (sMeterElement) {
            sMeterElement.textContent = sMeterText;
        }
        
        if (sMeterBar) {
            const percentage = Math.min(100, Math.max(0, (sUnits / 15) * 100));
            sMeterBar.style.width = `${percentage}%`;
        }
    }
    
    addAudioData(audioData) {
        // Add audio data to buffer for playback
        if (audioData && audioData.length > 0) {
            // Convert to Float32Array if needed
            const floatData = audioData instanceof Float32Array ? 
                             audioData : new Float32Array(audioData);
            
            this.audioBuffer.push(floatData);
            
            // Limit buffer size to prevent excessive latency
            while (this.audioBuffer.length > this.bufferThreshold) {
                this.audioBuffer.shift();
                this.audioDropouts++;
            }
        }
    }
    
    startPlayback() {
        if (!this.audioContext) {
            console.error('Audio context not initialized');
            return false;
        }
        
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }
        
        this.isPlaying = true;
        console.log('Audio playback started');
        return true;
    }
    
    stopPlayback() {
        this.isPlaying = false;
        
        if (this.audioContext && this.audioContext.state === 'running') {
            this.audioContext.suspend();
        }
        
        // Clear audio buffer
        this.audioBuffer = [];
        
        console.log('Audio playback stopped');
    }
    
    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));
        
        if (this.gainNode) {
            this.gainNode.gain.setTargetAtTime(
                this.volume, 
                this.audioContext.currentTime, 
                0.01
            );
        }
        
        // Update volume display
        const volumeDisplay = document.getElementById('volume-display');
        if (volumeDisplay) {
            volumeDisplay.textContent = `${Math.round(this.volume * 100)}%`;
        }
    }
    
    setSquelch(squelchLevel) {
        this.squelchLevel = Math.max(0, Math.min(100, squelchLevel));
        
        // Update squelch display
        const squelchDisplay = document.getElementById('squelch-display');
        if (squelchDisplay) {
            if (this.squelchLevel === 0) {
                squelchDisplay.textContent = 'Off';
            } else {
                squelchDisplay.textContent = `${this.squelchLevel}%`;
            }
        }
    }
    
    setAudioFilter(filterType, frequency, bandwidth) {
        if (!this.filterNode) return;
        
        const currentTime = this.audioContext.currentTime;
        
        switch (filterType) {
            case 'lowpass':
                this.filterNode.type = 'lowpass';
                this.filterNode.frequency.setValueAtTime(frequency, currentTime);
                break;
                
            case 'highpass':
                this.filterNode.type = 'highpass';
                this.filterNode.frequency.setValueAtTime(frequency, currentTime);
                break;
                
            case 'bandpass':
                this.filterNode.type = 'bandpass';
                this.filterNode.frequency.setValueAtTime(frequency, currentTime);
                this.filterNode.Q.setValueAtTime(frequency / bandwidth, currentTime);
                break;
                
            case 'notch':
                this.filterNode.type = 'notch';
                this.filterNode.frequency.setValueAtTime(frequency, currentTime);
                this.filterNode.Q.setValueAtTime(10, currentTime);
                break;
                
            default:
                this.filterNode.type = 'allpass';
        }
    }
    
    enableAGC(enabled) {
        this.agcEnabled = enabled;
    }
    
    enableNoiseReduction(enabled) {
        this.noiseReductionEnabled = enabled;
        
        if (enabled) {
            // Initialize noise reduction parameters
            if (!this.noiseProfile) {
                this.noiseProfile = new Float32Array(512).fill(0);
                this.noiseFloor = 0.01;
                this.noiseReductionStrength = 0.7;
                this.spectralFloorFactor = 0.002;
            }
        }
    }
    
    applyNoiseReduction(audioData) {
        if (!this.noiseReductionEnabled || !this.noiseProfile) {
            return audioData;
        }
        
        const fftSize = 512;
        const overlap = 0.5;
        const hopSize = Math.floor(fftSize * (1 - overlap));
        const numFrames = Math.floor((audioData.length - fftSize) / hopSize) + 1;
        
        const output = new Float32Array(audioData.length);
        const window = this.createHannWindow(fftSize);
        
        // Process each frame
        for (let frame = 0; frame < numFrames; frame++) {
            const start = frame * hopSize;
            const end = Math.min(start + fftSize, audioData.length);
            const frameSize = end - start;
            
            if (frameSize < fftSize) continue;
            
            // Extract and window the frame
            const frameData = new Float32Array(fftSize);
            for (let i = 0; i < fftSize; i++) {
                frameData[i] = audioData[start + i] * window[i];
            }
            
            // Apply spectral subtraction
            const processed = this.spectralSubtraction(frameData);
            
            // Overlap-add the processed frame
            for (let i = 0; i < fftSize; i++) {
                if (start + i < output.length) {
                    output[start + i] += processed[i] * window[i];
                }
            }
        }
        
        // Normalize output
        const maxVal = Math.max(...output.map(Math.abs));
        if (maxVal > 0) {
            for (let i = 0; i < output.length; i++) {
                output[i] /= maxVal;
            }
        }
        
        return output;
    }
    
    spectralSubtraction(frameData) {
        // Simple spectral subtraction noise reduction
        const fftSize = frameData.length;
        const spectrum = this.computeFFT(frameData);
        const magnitude = new Float32Array(fftSize / 2);
        const phase = new Float32Array(fftSize / 2);
        
        // Compute magnitude and phase
        for (let i = 0; i < fftSize / 2; i++) {
            const real = spectrum[i * 2];
            const imag = spectrum[i * 2 + 1];
            magnitude[i] = Math.sqrt(real * real + imag * imag);
            phase[i] = Math.atan2(imag, real);
        }
        
        // Update noise profile (simple exponential average)
        const alpha = 0.98; // Smoothing factor
        for (let i = 0; i < magnitude.length; i++) {
            this.noiseProfile[i] = alpha * this.noiseProfile[i] + (1 - alpha) * magnitude[i];
        }
        
        // Subtract noise spectrum
        for (let i = 0; i < magnitude.length; i++) {
            magnitude[i] = Math.max(
                magnitude[i] - this.noiseReductionStrength * this.noiseProfile[i],
                this.spectralFloorFactor * magnitude[i]
            );
        }
        
        // Reconstruct spectrum
        const cleanSpectrum = new Float32Array(fftSize);
        for (let i = 0; i < fftSize / 2; i++) {
            cleanSpectrum[i * 2] = magnitude[i] * Math.cos(phase[i]);
            cleanSpectrum[i * 2 + 1] = magnitude[i] * Math.sin(phase[i]);
        }
        
        // Inverse FFT
        return this.computeIFFT(cleanSpectrum);
    }
    
    createHannWindow(size) {
        const window = new Float32Array(size);
        for (let i = 0; i < size; i++) {
            window[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (size - 1));
        }
        return window;
    }
    
    computeFFT(data) {
        // Simple DFT implementation (replace with Web Audio API FFT for better performance)
        const N = data.length;
        const output = new Float32Array(N);
        
        for (let k = 0; k < N / 2; k++) {
            let real = 0;
            let imag = 0;
            
            for (let n = 0; n < N; n++) {
                const angle = -2 * Math.PI * k * n / N;
                real += data[n] * Math.cos(angle);
                imag += data[n] * Math.sin(angle);
            }
            
            output[k * 2] = real;
            output[k * 2 + 1] = imag;
        }
        
        return output;
    }
    
    computeIFFT(spectrum) {
        // Simple inverse DFT
        const N = spectrum.length;
        const output = new Float32Array(N / 2);
        
        for (let n = 0; n < N / 2; n++) {
            let real = 0;
            
            for (let k = 0; k < N / 2; k++) {
                const angle = 2 * Math.PI * k * n / (N / 2);
                real += spectrum[k * 2] * Math.cos(angle) - spectrum[k * 2 + 1] * Math.sin(angle);
            }
            
            output[n] = real / (N / 2);
        }
        
        return output;
    }
    
    playAudioBuffer(audioData, sampleRate = 48000) {
        if (!this.audioContext) {
            console.warn('🔊 playAudioBuffer: AudioContext not initialized');
            return;
        }
        
        if (!this.isPlaying) {
            console.warn('🔊 playAudioBuffer: Audio not playing (isPlaying=false)');
            return;
        }
        
        // Write to circular buffer
        this.writeToCircularBuffer(audioData);
    }
    
    writeToCircularBuffer(audioData) {
        // Convert to Float32Array if needed
        const floatData = audioData instanceof Float32Array ? audioData : new Float32Array(audioData);
        
        // Apply noise reduction if enabled
        let processedData = floatData;
        if (this.noiseReductionEnabled) {
            processedData = this.applyNoiseReduction(floatData);
        }
        
        // Write to circular buffer
        for (let i = 0; i < processedData.length; i++) {
            // Check for buffer overflow
            if (this.bufferLength >= this.circularBuffer.length) {
                // Buffer full - drop oldest data
                this.readIndex = (this.readIndex + 1) % this.circularBuffer.length;
                this.bufferLength--;
                this.audioDropouts++;
            }
            
            this.circularBuffer[this.writeIndex] = processedData[i];
            this.writeIndex = (this.writeIndex + 1) % this.circularBuffer.length;
            this.bufferLength++;
        }
        
        // Debug info
        const bufferPercent = (this.bufferLength / this.circularBuffer.length * 100).toFixed(1);
        if (Math.random() < 0.1) { // Log occasionally to avoid spam
            console.log(`🔊 Buffer: ${this.bufferLength} samples (${bufferPercent}%), wrote ${processedData.length}`);
        }
    }
    
    async startAudio() {
        try {
            // Ensure audio context is initialized
            if (!this.audioContext) {
                const success = await this.initialize();
                if (!success) {
                    throw new Error('Failed to initialize audio context');
                }
            }
            
            // Resume audio context if suspended
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
                console.log('🔊 Audio context resumed');
            }
            
            // Reset circular buffer
            this.writeIndex = 0;
            this.readIndex = 0;
            this.bufferLength = 0;
            this.circularBuffer.fill(0);
            
            this.isPlaying = true;
            console.log('🔊 Continuous audio playback started');
            console.log('🔊 Audio context sample rate:', this.audioContext.sampleRate);
            console.log('🔊 Circular buffer size:', this.circularBuffer.length, 'samples');
            console.log('🔊 Volume level:', this.volume);
            
            return true;
        } catch (error) {
            console.error('❌ Failed to start audio:', error);
            this.isPlaying = false;
            throw error;
        }
    }
    
    stopAudio() {
        this.isPlaying = false;
        // Clear circular buffer
        this.writeIndex = 0;
        this.readIndex = 0;
        this.bufferLength = 0;
        this.circularBuffer.fill(0);
        console.log('🔇 Continuous audio playback stopped');
    }
    
    getAudioStats() {
        return {
            sampleRate: this.audioContext ? this.audioContext.sampleRate : 0,
            bufferSize: this.bufferSize,
            circularBufferSize: this.circularBuffer.length,
            circularBufferUsed: this.bufferLength,
            circularBufferPercent: (this.bufferLength / this.circularBuffer.length * 100).toFixed(1),
            signalLevel: this.signalLevel,
            audioDropouts: this.audioDropouts,
            bufferUnderruns: this.bufferUnderruns,
            isPlaying: this.isPlaying,
            volume: this.volume,
            squelchLevel: this.squelchLevel
        };
    }
    
    // WebAudio visualization support
    createAudioAnalyser() {
        if (!this.audioContext) return null;
        
        const analyser = this.audioContext.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.8;
        
        // Connect to the audio chain
        this.gainNode.connect(analyser);
        
        return analyser;
    }
    
    // Audio recording support
    async startRecording() {
        if (!this.audioContext) return null;
        
        try {
            const mediaRecorder = new MediaRecorder(this.audioContext.createMediaStreamDestination().stream);
            const audioChunks = [];
            
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const audioUrl = URL.createObjectURL(audioBlob);
                
                // Create download link
                const downloadLink = document.createElement('a');
                downloadLink.href = audioUrl;
                downloadLink.download = `sdr_recording_${Date.now()}.wav`;
                downloadLink.click();
            };
            
            mediaRecorder.start();
            return mediaRecorder;
            
        } catch (error) {
            console.error('Failed to start recording:', error);
            return null;
        }
    }
    
    cleanup() {
        if (this.scriptProcessor) {
            this.scriptProcessor.disconnect();
            this.scriptProcessor = null;
        }
        
        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close();
        }
        
        this.audioBuffer = [];
        console.log('Audio service cleaned up');
    }
}

// Export for module use
window.AudioService = AudioService;