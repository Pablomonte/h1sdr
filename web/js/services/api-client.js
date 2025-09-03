/**
 * API Client Service
 * Handles communication with the H1SDR backend API
 */

import { CONFIG, log } from '../config.js';

/**
 * API Client class for H1SDR backend communication
 */
export class APIClient {
    constructor(baseUrl = CONFIG.API_BASE_URL) {
        this.baseUrl = baseUrl;
        this.defaultHeaders = {
            'Content-Type': 'application/json',
        };
    }

    /**
     * Make HTTP request to API
     * @param {string} endpoint - API endpoint
     * @param {object} options - Request options
     * @returns {Promise} Response promise
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: { ...this.defaultHeaders, ...options.headers },
            ...options
        };

        try {
            log('debug', `API Request: ${config.method || 'GET'} ${url}`);
            const response = await fetch(url, config);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            log('debug', `API Response: ${url}`, data);
            return data;
        } catch (error) {
            log('error', `API Error: ${url}`, error);
            throw error;
        }
    }

    /**
     * GET request
     * @param {string} endpoint - API endpoint
     * @param {object} headers - Additional headers
     * @returns {Promise} Response promise
     */
    async get(endpoint, headers = {}) {
        return this.request(endpoint, { method: 'GET', headers });
    }

    /**
     * POST request
     * @param {string} endpoint - API endpoint
     * @param {object} data - Request body data
     * @param {object} headers - Additional headers
     * @returns {Promise} Response promise
     */
    async post(endpoint, data = {}, headers = {}) {
        return this.request(endpoint, {
            method: 'POST',
            headers,
            body: JSON.stringify(data)
        });
    }

    /**
     * PUT request
     * @param {string} endpoint - API endpoint
     * @param {object} data - Request body data
     * @param {object} headers - Additional headers
     * @returns {Promise} Response promise
     */
    async put(endpoint, data = {}, headers = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            headers,
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE request
     * @param {string} endpoint - API endpoint
     * @param {object} headers - Additional headers
     * @returns {Promise} Response promise
     */
    async delete(endpoint, headers = {}) {
        return this.request(endpoint, { method: 'DELETE', headers });
    }

    // Health and Status APIs
    /**
     * Get system health status
     * @returns {Promise} Health status
     */
    async getHealth() {
        return this.get('/api/health');
    }

    /**
     * Get SDR status
     * @returns {Promise} SDR status
     */
    async getSdrStatus() {
        return this.get('/api/sdr/status');
    }

    // SDR Control APIs
    /**
     * Start SDR with specified device
     * @param {number} deviceIndex - RTL-SDR device index
     * @returns {Promise} Start result
     */
    async startSdr(deviceIndex = 0) {
        return this.post('/api/sdr/start', { device_index: deviceIndex });
    }

    /**
     * Stop SDR
     * @returns {Promise} Stop result
     */
    async stopSdr() {
        return this.post('/api/sdr/stop');
    }

    /**
     * Tune to frequency
     * @param {number} frequency - Frequency in Hz
     * @param {number} gain - Gain in dB (optional)
     * @returns {Promise} Tune result
     */
    async tuneFrequency(frequency, gain = null) {
        const data = { frequency };
        if (gain !== null) {
            data.gain = gain;
        }
        return this.post('/api/sdr/tune', data);
    }

    // Band Management APIs
    /**
     * Get all available bands
     * @returns {Promise} Bands data
     */
    async getBands() {
        return this.get('/api/bands');
    }

    /**
     * Get specific band information
     * @param {string} bandKey - Band key
     * @returns {Promise} Band data
     */
    async getBand(bandKey) {
        return this.get(`/api/bands/${bandKey}`);
    }

    /**
     * Tune to preset band
     * @param {string} bandKey - Band key
     * @returns {Promise} Tune result
     */
    async tuneToBand(bandKey) {
        return this.post(`/api/bands/${bandKey}/tune`);
    }

    // Demodulation APIs
    /**
     * Get available demodulation modes
     * @returns {Promise} Demodulation modes
     */
    async getDemodModes() {
        return this.get('/api/modes');
    }

    /**
     * Set demodulation mode
     * @param {string} mode - Demodulation mode
     * @param {number} bandwidth - Bandwidth in Hz (optional)
     * @returns {Promise} Set result
     */
    async setDemodulation(mode, bandwidth = null) {
        const data = { mode };
        if (bandwidth !== null) {
            data.bandwidth = bandwidth;
        }
        return this.post('/api/demod/set', data);
    }
}

/**
 * API Response wrapper class
 */
export class APIResponse {
    constructor(data) {
        this.success = data.success || false;
        this.data = data.data || null;
        this.message = data.message || '';
        this.error = data.error || null;
    }

    /**
     * Check if response is successful
     * @returns {boolean} Success status
     */
    isSuccess() {
        return this.success === true;
    }

    /**
     * Get response data or throw error
     * @returns {*} Response data
     * @throws {Error} If response failed
     */
    getData() {
        if (!this.isSuccess()) {
            throw new Error(this.error || this.message || 'API request failed');
        }
        return this.data;
    }

    /**
     * Get error message
     * @returns {string} Error message
     */
    getError() {
        return this.error || this.message || 'Unknown error';
    }
}

/**
 * Create API client instance with error handling wrapper
 * @param {string} baseUrl - Base URL for API
 * @returns {APIClient} API client instance
 */
export function createAPIClient(baseUrl = CONFIG.API_BASE_URL) {
    return new Proxy(new APIClient(baseUrl), {
        get(target, prop) {
            const method = target[prop];
            
            if (typeof method === 'function') {
                return async function(...args) {
                    try {
                        const result = await method.apply(target, args);
                        return new APIResponse(result);
                    } catch (error) {
                        log('error', `API method ${prop} failed:`, error);
                        return new APIResponse({
                            success: false,
                            error: error.message,
                            data: null
                        });
                    }
                };
            }
            
            return method;
        }
    });
}

// Default API client instance
export const apiClient = createAPIClient();

export default apiClient;