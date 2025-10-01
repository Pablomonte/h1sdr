/**
 * Robust WebSocket Manager with Auto-Reconnect
 *
 * Features:
 * - Exponential backoff (1s → 30s max)
 * - Message queuing while disconnected
 * - Auto-flush on reconnect
 * - No user intervention required
 *
 * Part of: H1SDR v2.0 Phase 1 - Core Performance
 */

class RobustWebSocket {
    constructor(url, options = {}) {
        this.url = url;
        this.ws = null;

        // Reconnection parameters
        this.reconnectDelay = options.reconnectDelay || 1000;  // Start at 1s
        this.maxDelay = options.maxDelay || 30000;             // Cap at 30s
        this.reconnectAttempt = 0;

        // Message queue for offline operation
        this.messageQueue = [];
        this.maxQueueSize = options.maxQueueSize || 100;

        // Callbacks
        this.onMessage = options.onMessage || (() => {});
        this.onOpen = options.onOpen || (() => {});
        this.onClose = options.onClose || (() => {});
        this.onError = options.onError || (() => {});

        // State
        this.isIntentionallyClosed = false;

        // Auto-connect
        this.connect();
    }

    connect() {
        if (this.isIntentionallyClosed) {
            console.log('[WebSocket] Skip reconnect (intentionally closed)');
            return;
        }

        console.log(`[WebSocket] Connecting to ${this.url} (attempt ${this.reconnectAttempt + 1})...`);

        try {
            this.ws = new WebSocket(this.url);
            this._attachEventHandlers();
        } catch (error) {
            console.error('[WebSocket] Connection failed:', error);
            this.scheduleReconnect();
        }
    }

    _attachEventHandlers() {
        this.ws.onopen = (event) => {
            console.log('[WebSocket] Connected');
            this.reconnectDelay = 1000;
            this.reconnectAttempt = 0;

            // Flush queued messages
            const queuedCount = this.messageQueue.length;
            if (queuedCount > 0) {
                console.log(`[WebSocket] Flushing ${queuedCount} queued messages...`);
                while (this.messageQueue.length > 0) {
                    this.send(this.messageQueue.shift());
                }
            }

            this.onOpen(event);
        };

        this.ws.onclose = (event) => {
            console.warn(`[WebSocket] Disconnected (code: ${event.code}, reason: ${event.reason || 'none'})`);
            this.onClose(event);

            if (!this.isIntentionallyClosed) {
                this.scheduleReconnect();
            }
        };

        this.ws.onerror = (error) => {
            console.error('[WebSocket] Error:', error);
            this.onError(error);
        };

        this.ws.onmessage = (event) => {
            try {
                // Handle both binary and JSON messages
                let data;
                if (event.data instanceof Blob) {
                    // Binary data (spectrum/waterfall)
                    data = event.data;
                } else {
                    // JSON data (control messages)
                    data = JSON.parse(event.data);
                }
                this.onMessage(data);
            } catch (error) {
                console.error('[WebSocket] Message parsing error:', error);
            }
        };
    }

    scheduleReconnect() {
        // Exponential backoff with max cap
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempt),
            this.maxDelay
        );

        console.log(`[WebSocket] Reconnecting in ${(delay / 1000).toFixed(1)}s...`);

        setTimeout(() => {
            this.reconnectAttempt++;
            this.connect();
        }, delay);
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            // Send immediately
            const message = typeof data === 'string' ? data : JSON.stringify(data);
            this.ws.send(message);
        } else {
            // Queue for later
            console.warn('[WebSocket] Queuing message (not connected)');

            if (this.messageQueue.length >= this.maxQueueSize) {
                console.warn('[WebSocket] Queue full, dropping oldest message');
                this.messageQueue.shift();
            }

            this.messageQueue.push(data);
        }
    }

    close() {
        console.log('[WebSocket] Closing connection (intentional)');
        this.isIntentionallyClosed = true;

        if (this.ws) {
            this.ws.close();
        }
    }

    getState() {
        if (!this.ws) return 'DISCONNECTED';

        const states = {
            [WebSocket.CONNECTING]: 'CONNECTING',
            [WebSocket.OPEN]: 'OPEN',
            [WebSocket.CLOSING]: 'CLOSING',
            [WebSocket.CLOSED]: 'CLOSED'
        };

        return states[this.ws.readyState] || 'UNKNOWN';
    }

    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}


/**
 * Example usage for H1SDR WebSocket streaming
 */
function createH1SDRWebSocket() {
    const ws = new RobustWebSocket('ws://localhost:8000/ws', {
        reconnectDelay: 1000,
        maxDelay: 30000,
        maxQueueSize: 100,

        onOpen: (event) => {
            console.log('[H1SDR] WebSocket connected');
            updateConnectionStatus('connected');

            // Request spectrum streaming
            ws.send({
                type: 'subscribe',
                channel: 'spectrum',
                fps: 20
            });
        },

        onClose: (event) => {
            console.log('[H1SDR] WebSocket disconnected');
            updateConnectionStatus('disconnected');
        },

        onError: (error) => {
            console.error('[H1SDR] WebSocket error:', error);
            updateConnectionStatus('error');
        },

        onMessage: (data) => {
            if (data instanceof Blob) {
                // Binary spectrum/waterfall data
                handleBinaryData(data);
            } else if (data.type === 'status') {
                // Control messages
                updateStatus(data);
            }
        }
    });

    return ws;
}

function updateConnectionStatus(status) {
    const indicator = document.getElementById('connection-status');
    if (indicator) {
        indicator.className = `status-${status}`;
        indicator.textContent = status.toUpperCase();
    }
}

function handleBinaryData(blob) {
    // Decode binary spectrum data
    blob.arrayBuffer().then(buffer => {
        const data = new Float32Array(buffer);
        // Update spectrum display
        if (window.spectrumDisplay) {
            window.spectrumDisplay.update(data);
        }
    });
}

function updateStatus(data) {
    console.log('[H1SDR] Status update:', data);
}


// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RobustWebSocket, createH1SDRWebSocket };
}
