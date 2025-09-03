/**
 * WebSocket client for real-time SDR data streaming
 * Handles spectrum, waterfall, and audio data connections
 */

class WebSocketClient {
    constructor(baseUrl = null) {
        this.baseUrl = baseUrl || `ws://${window.location.host}`;
        
        // WebSocket connections
        this.spectrumSocket = null;
        this.waterfallSocket = null;
        this.audioSocket = null;
        this.controlSocket = null;
        
        // Connection states
        this.connections = {
            spectrum: { connected: false, reconnectAttempts: 0 },
            waterfall: { connected: false, reconnectAttempts: 0 },
            audio: { connected: false, reconnectAttempts: 0 },
            control: { connected: false, reconnectAttempts: 0 }
        };
        
        // Reconnection settings
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // Start with 1 second
        this.maxReconnectDelay = 30000; // Max 30 seconds
        
        // Data handlers
        this.dataHandlers = {
            spectrum: [],
            waterfall: [],
            audio: [],
            control: []
        };
        
        // Statistics
        this.stats = {
            bytesReceived: 0,
            messagesReceived: 0,
            reconnections: 0,
            lastActivity: Date.now()
        };
        
        // Health monitoring
        this.healthCheckInterval = null;
        this.pingInterval = null;
        
        console.log('WebSocket client initialized');
    }
    
    // Connection management
    
    async connectSpectrum() {
        return this.connect('spectrum', '/ws/spectrum');
    }
    
    async connectWaterfall() {
        return this.connect('waterfall', '/ws/waterfall');
    }
    
    async connectAudio() {
        return this.connect('audio', '/ws/audio');
    }
    
    async connectControl() {
        return this.connect('control', '/ws/control');
    }
    
    async connect(type, endpoint) {
        if (this.connections[type].connected) {
            console.log(`${type} already connected`);
            return true;
        }
        
        try {
            const url = `${this.baseUrl}${endpoint}`;
            const socket = new WebSocket(url);
            
            socket.binaryType = 'arraybuffer'; // For binary data
            
            socket.onopen = () => this.handleOpen(type, socket);
            socket.onmessage = (event) => this.handleMessage(type, event);
            socket.onclose = (event) => this.handleClose(type, event);
            socket.onerror = (error) => this.handleError(type, error);
            
            // Store socket reference
            this[`${type}Socket`] = socket;
            
            return new Promise((resolve, reject) => {
                socket.addEventListener('open', () => resolve(true));
                socket.addEventListener('error', () => reject(false));
            });
            
        } catch (error) {
            console.error(`Failed to connect ${type}:`, error);
            return false;
        }
    }
    
    handleOpen(type, socket) {
        console.log(`${type} WebSocket connected`);
        this.connections[type].connected = true;
        this.connections[type].reconnectAttempts = 0;
        
        // Update UI status
        this.updateConnectionStatus(type, 'connected');
        
        // Start health monitoring for this connection
        if (type === 'control') {
            this.startHealthMonitoring();
        }
    }
    
    handleMessage(type, event) {
        this.stats.messagesReceived++;
        this.stats.lastActivity = Date.now();
        
        try {
            let data;
            
            if (event.data instanceof ArrayBuffer) {
                // Binary data (spectrum/waterfall/audio)
                this.stats.bytesReceived += event.data.byteLength;
                data = this.parseBinaryMessage(type, event.data);
            } else {
                // Text data (control messages)
                data = JSON.parse(event.data);
            }
            
            // Dispatch to registered handlers
            this.notifyHandlers(type, data);
            
        } catch (error) {
            console.error(`Error processing ${type} message:`, error);
        }
    }
    
    parseBinaryMessage(type, arrayBuffer) {
        const view = new DataView(arrayBuffer);
        
        switch (type) {
            case 'spectrum':
                return this.parseSpectrumData(view);
                
            case 'waterfall':
                return this.parseWaterfallData(view);
                
            case 'audio':
                return this.parseAudioData(view);
                
            default:
                return { raw: arrayBuffer };
        }
    }
    
    parseSpectrumData(view) {
        // Spectrum data format:
        // 4 bytes: timestamp (uint32)
        // 4 bytes: sample_rate (float32)
        // 4 bytes: center_frequency (float32)
        // 4 bytes: fft_size (uint32)
        // N * 4 bytes: spectrum values (float32 array)
        
        const timestamp = view.getUint32(0, true);
        const sampleRate = view.getFloat32(4, true);
        const centerFrequency = view.getFloat32(8, true);
        const fftSize = view.getUint32(12, true);
        
        const spectrumData = new Float32Array(view.buffer, 16, fftSize);
        
        // Generate frequency array
        const frequencies = new Float32Array(fftSize);
        const binSize = sampleRate / fftSize;
        const startFreq = centerFrequency - sampleRate / 2;
        
        for (let i = 0; i < fftSize; i++) {
            frequencies[i] = startFreq + i * binSize;
        }
        
        return {
            timestamp,
            sampleRate,
            centerFrequency,
            fftSize,
            spectrum: spectrumData,
            frequencies
        };
    }
    
    parseWaterfallData(view) {
        // Waterfall data format:
        // 4 bytes: timestamp (uint32)
        // 4 bytes: fft_size (uint32)
        // N bytes: waterfall line (uint8 array - normalized 0-255)
        
        const timestamp = view.getUint32(0, true);
        const fftSize = view.getUint32(4, true);
        
        const waterfallData = new Uint8Array(view.buffer, 8, fftSize);
        
        return {
            timestamp,
            fftSize,
            data: waterfallData
        };
    }
    
    parseAudioData(view) {
        // Audio data format:
        // 4 bytes: timestamp (uint32)
        // 4 bytes: sample_rate (float32)
        // 4 bytes: num_samples (uint32)
        // N * 4 bytes: audio samples (float32 array)
        
        const timestamp = view.getUint32(0, true);
        const sampleRate = view.getFloat32(4, true);
        const numSamples = view.getUint32(8, true);
        
        const audioData = new Float32Array(view.buffer, 12, numSamples);
        
        return {
            timestamp,
            sampleRate,
            numSamples,
            audio: audioData
        };
    }
    
    handleClose(type, event) {
        console.log(`${type} WebSocket closed:`, event.code, event.reason);
        this.connections[type].connected = false;
        
        // Update UI status
        this.updateConnectionStatus(type, 'disconnected');
        
        // Attempt reconnection if not a clean close
        if (event.code !== 1000 && this.connections[type].reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect(type);
        }
    }
    
    handleError(type, error) {
        console.error(`${type} WebSocket error:`, error);
        this.updateConnectionStatus(type, 'error');
    }
    
    scheduleReconnect(type) {
        const connection = this.connections[type];
        connection.reconnectAttempts++;
        this.stats.reconnections++;
        
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, connection.reconnectAttempts - 1),
            this.maxReconnectDelay
        );
        
        console.log(`Reconnecting ${type} in ${delay}ms (attempt ${connection.reconnectAttempts})`);
        
        setTimeout(() => {
            if (!connection.connected) {
                const endpoint = this.getEndpointForType(type);
                this.connect(type, endpoint);
            }
        }, delay);
    }
    
    getEndpointForType(type) {
        const endpoints = {
            spectrum: '/ws/spectrum',
            waterfall: '/ws/waterfall',
            audio: '/ws/audio',
            control: '/ws/control'
        };
        return endpoints[type];
    }
    
    updateConnectionStatus(type, status) {
        const statusElement = document.getElementById('connection-status');
        if (!statusElement) return;
        
        const statusMap = {
            connected: { class: 'online', text: 'Connected' },
            disconnected: { class: 'offline', text: 'Disconnected' },
            error: { class: 'offline', text: 'Error' },
            connecting: { class: 'connecting', text: 'Connecting...' }
        };
        
        const statusInfo = statusMap[status] || statusMap.disconnected;
        statusElement.className = `status-indicator ${statusInfo.class}`;
        statusElement.textContent = statusInfo.text;
    }
    
    // Data handler registration
    
    addHandler(type, handler) {
        if (this.dataHandlers[type]) {
            this.dataHandlers[type].push(handler);
        }
    }
    
    removeHandler(type, handler) {
        if (this.dataHandlers[type]) {
            const index = this.dataHandlers[type].indexOf(handler);
            if (index > -1) {
                this.dataHandlers[type].splice(index, 1);
            }
        }
    }
    
    notifyHandlers(type, data) {
        if (this.dataHandlers[type]) {
            this.dataHandlers[type].forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in ${type} handler:`, error);
                }
            });
        }
    }
    
    // Control message sending
    
    sendControlMessage(message) {
        if (this.controlSocket && this.connections.control.connected) {
            try {
                this.controlSocket.send(JSON.stringify(message));
                return true;
            } catch (error) {
                console.error('Failed to send control message:', error);
                return false;
            }
        }
        return false;
    }
    
    // SDR control methods
    
    startSDR(config = {}) {
        return this.sendControlMessage({
            type: 'sdr_control',
            action: 'start',
            config
        });
    }
    
    stopSDR() {
        return this.sendControlMessage({
            type: 'sdr_control',
            action: 'stop'
        });
    }
    
    setFrequency(frequency) {
        return this.sendControlMessage({
            type: 'sdr_control',
            action: 'set_frequency',
            frequency
        });
    }
    
    setGain(gain) {
        return this.sendControlMessage({
            type: 'sdr_control',
            action: 'set_gain',
            gain
        });
    }
    
    setSampleRate(sampleRate) {
        return this.sendControlMessage({
            type: 'sdr_control',
            action: 'set_sample_rate',
            sample_rate: sampleRate
        });
    }
    
    setBandwidth(bandwidth) {
        return this.sendControlMessage({
            type: 'sdr_control',
            action: 'set_bandwidth',
            bandwidth
        });
    }
    
    setDemodulation(mode, bandwidth) {
        return this.sendControlMessage({
            type: 'demod_control',
            mode,
            bandwidth
        });
    }
    
    // Health monitoring
    
    startHealthMonitoring() {
        // Ping every 30 seconds
        this.pingInterval = setInterval(() => {
            this.sendControlMessage({ type: 'ping', timestamp: Date.now() });
        }, 30000);
        
        // Check for data activity
        this.healthCheckInterval = setInterval(() => {
            const timeSinceActivity = Date.now() - this.stats.lastActivity;
            
            if (timeSinceActivity > 60000) { // No activity for 1 minute
                console.warn('No WebSocket activity for 60 seconds');
                // Could trigger reconnection or alert user
            }
        }, 10000);
    }
    
    stopHealthMonitoring() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
        
        if (this.healthCheckInterval) {
            clearInterval(this.healthCheckInterval);
            this.healthCheckInterval = null;
        }
    }
    
    // Statistics and monitoring
    
    getStats() {
        return {
            ...this.stats,
            connections: { ...this.connections }
        };
    }
    
    resetStats() {
        this.stats.bytesReceived = 0;
        this.stats.messagesReceived = 0;
        this.stats.reconnections = 0;
        this.stats.lastActivity = Date.now();
    }
    
    // Cleanup
    
    disconnect(type = null) {
        if (type) {
            // Disconnect specific socket
            const socket = this[`${type}Socket`];
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.close(1000, 'Client disconnect');
            }
            this.connections[type].connected = false;
        } else {
            // Disconnect all sockets
            ['spectrum', 'waterfall', 'audio', 'control'].forEach(socketType => {
                this.disconnect(socketType);
            });
        }
    }
    
    cleanup() {
        this.disconnect();
        this.stopHealthMonitoring();
        
        // Clear handlers
        Object.keys(this.dataHandlers).forEach(type => {
            this.dataHandlers[type] = [];
        });
        
        console.log('WebSocket client cleaned up');
    }
}

// Export for module use
window.WebSocketClient = WebSocketClient;