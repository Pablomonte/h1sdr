/**
 * Recording Service for H1SDR
 * Handles recording of IQ data and demodulated audio
 */

class RecordingService {
    constructor() {
        this.isRecording = false;
        this.recordingType = 'audio'; // 'audio' or 'iq'
        this.recordedChunks = [];
        this.recordingStartTime = null;
        this.recordingDuration = 0;
        this.maxRecordingDuration = 300; // 5 minutes max
        this.sampleRate = 48000;
        this.centerFrequency = 100e6;
        this.metadata = {};
    }
    
    startRecording(type = 'audio', metadata = {}) {
        if (this.isRecording) {
            console.warn('⚠️ Recording already in progress');
            return false;
        }
        
        this.recordingType = type;
        this.recordedChunks = [];
        this.recordingStartTime = Date.now();
        this.isRecording = true;
        this.metadata = {
            ...metadata,
            startTime: new Date().toISOString(),
            type: type,
            sampleRate: this.sampleRate,
            centerFrequency: this.centerFrequency
        };
        
        console.log(`🔴 Started ${type} recording`, this.metadata);
        
        // Start duration timer
        this.recordingTimer = setInterval(() => {
            this.recordingDuration = (Date.now() - this.recordingStartTime) / 1000;
            
            // Auto-stop after max duration
            if (this.recordingDuration >= this.maxRecordingDuration) {
                console.log('⏱️ Max recording duration reached, auto-stopping');
                this.stopRecording();
            }
            
            // Dispatch duration update event
            window.dispatchEvent(new CustomEvent('recordingDurationUpdate', {
                detail: { duration: this.recordingDuration }
            }));
        }, 100);
        
        return true;
    }
    
    addData(data) {
        if (!this.isRecording) {
            return;
        }
        
        // Clone the data to avoid reference issues
        const dataClone = data instanceof Float32Array ? 
            new Float32Array(data) : 
            new Float32Array(data);
        
        this.recordedChunks.push(dataClone);
        
        // Check memory usage (rough estimate)
        const estimatedSize = this.recordedChunks.reduce((acc, chunk) => 
            acc + chunk.byteLength, 0);
        
        if (estimatedSize > 100 * 1024 * 1024) { // 100MB limit
            console.warn('⚠️ Recording size limit reached, auto-stopping');
            this.stopRecording();
        }
    }
    
    stopRecording() {
        if (!this.isRecording) {
            console.warn('⚠️ No recording in progress');
            return null;
        }
        
        this.isRecording = false;
        clearInterval(this.recordingTimer);
        
        this.metadata.endTime = new Date().toISOString();
        this.metadata.duration = this.recordingDuration;
        this.metadata.chunks = this.recordedChunks.length;
        
        console.log(`⏹️ Stopped recording`, this.metadata);
        
        // Generate file based on recording type
        let file;
        if (this.recordingType === 'audio') {
            file = this.generateWAVFile();
        } else {
            file = this.generateIQFile();
        }
        
        // Reset recording state
        this.recordedChunks = [];
        this.recordingDuration = 0;
        
        return file;
    }
    
    generateWAVFile() {
        // Combine all chunks
        const totalLength = this.recordedChunks.reduce((acc, chunk) => 
            acc + chunk.length, 0);
        const combinedData = new Float32Array(totalLength);
        
        let offset = 0;
        for (const chunk of this.recordedChunks) {
            combinedData.set(chunk, offset);
            offset += chunk.length;
        }
        
        // Convert to 16-bit PCM
        const length = combinedData.length;
        const buffer = new ArrayBuffer(44 + length * 2);
        const view = new DataView(buffer);
        
        // WAV header
        const writeString = (offset, string) => {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        };
        
        writeString(0, 'RIFF');
        view.setUint32(4, 36 + length * 2, true);
        writeString(8, 'WAVE');
        writeString(12, 'fmt ');
        view.setUint32(16, 16, true); // fmt chunk size
        view.setUint16(20, 1, true); // PCM format
        view.setUint16(22, 1, true); // 1 channel
        view.setUint32(24, this.sampleRate, true);
        view.setUint32(28, this.sampleRate * 2, true); // byte rate
        view.setUint16(32, 2, true); // block align
        view.setUint16(34, 16, true); // bits per sample
        writeString(36, 'data');
        view.setUint32(40, length * 2, true);
        
        // Convert float samples to 16-bit PCM
        let index = 44;
        for (let i = 0; i < length; i++) {
            const sample = Math.max(-1, Math.min(1, combinedData[i]));
            view.setInt16(index, sample * 0x7FFF, true);
            index += 2;
        }
        
        const blob = new Blob([buffer], { type: 'audio/wav' });
        const filename = `h1sdr_audio_${this.formatTimestamp()}.wav`;
        
        return { blob, filename, metadata: this.metadata };
    }
    
    generateIQFile() {
        // Combine all chunks
        const totalLength = this.recordedChunks.reduce((acc, chunk) => 
            acc + chunk.length, 0);
        const combinedData = new Float32Array(totalLength);
        
        let offset = 0;
        for (const chunk of this.recordedChunks) {
            combinedData.set(chunk, offset);
            offset += chunk.length;
        }
        
        // Create binary file with metadata header
        const metadataJSON = JSON.stringify(this.metadata);
        const metadataBytes = new TextEncoder().encode(metadataJSON);
        const metadataLength = metadataBytes.length;
        
        // File format: [4 bytes: metadata length][metadata JSON][IQ data as float32]
        const totalSize = 4 + metadataLength + combinedData.byteLength;
        const buffer = new ArrayBuffer(totalSize);
        const view = new DataView(buffer);
        
        // Write metadata length
        view.setUint32(0, metadataLength, true);
        
        // Write metadata
        const uint8View = new Uint8Array(buffer);
        uint8View.set(metadataBytes, 4);
        
        // Write IQ data
        const float32View = new Float32Array(buffer, 4 + metadataLength);
        float32View.set(combinedData);
        
        const blob = new Blob([buffer], { type: 'application/octet-stream' });
        const filename = `h1sdr_iq_${this.formatTimestamp()}.iq32`;
        
        return { blob, filename, metadata: this.metadata };
    }
    
    downloadFile(file) {
        if (!file) return;
        
        const url = URL.createObjectURL(file.blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        console.log(`💾 Downloaded: ${file.filename}`);
    }
    
    formatTimestamp() {
        const now = new Date();
        return now.toISOString().replace(/[:.]/g, '-').slice(0, -5);
    }
    
    setParameters(params) {
        if (params.sampleRate) this.sampleRate = params.sampleRate;
        if (params.centerFrequency) this.centerFrequency = params.centerFrequency;
        if (params.maxDuration) this.maxRecordingDuration = params.maxDuration;
    }
    
    getRecordingStatus() {
        return {
            isRecording: this.isRecording,
            type: this.recordingType,
            duration: this.recordingDuration,
            chunks: this.recordedChunks.length,
            estimatedSize: this.recordedChunks.reduce((acc, chunk) => 
                acc + chunk.byteLength, 0)
        };
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RecordingService;
}