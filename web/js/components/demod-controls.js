/**
 * Demodulation Controls Component
 * Manages demodulation mode selection and parameters
 */

import { DEMOD_DEFAULTS, CONFIG, log } from '../config.js';
import { apiClient } from '../services/api-client.js';
import { formatBandwidth } from '../utils/frequency-utils.js';

/**
 * Demodulation Controls class
 */
export class DemodControls {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.modes = new Map();
        this.currentMode = 'SPECTRUM';
        this.currentBandwidth = 2400000;
        this.callbacks = new Map();
        
        this.init();
    }

    /**
     * Initialize demodulation controls
     */
    async init() {
        if (!this.container) {
            log('error', 'Demod controls container not found');
            return;
        }

        await this.loadDemodModes();
        this.createUI();
        this.attachEventListeners();
        this.updateUI();
    }

    /**
     * Load demodulation modes from API
     */
    async loadDemodModes() {
        try {
            const response = await apiClient.getDemodModes();
            
            if (response.isSuccess()) {
                const modesData = response.getData();
                
                // Clear existing modes
                this.modes.clear();
                
                // Process modes data
                for (const [key, mode] of Object.entries(modesData)) {
                    this.modes.set(key, {
                        key,
                        name: mode.name || key,
                        description: mode.description || '',
                        bandwidthDefault: mode.bandwidth_default || DEMOD_DEFAULTS[key]?.bandwidth || 2400,
                        bandwidthMin: mode.bandwidth_min || 100,
                        bandwidthMax: mode.bandwidth_max || 3000000,
                        hasAudio: mode.has_audio !== false,
                        parameters: mode.parameters || {}
                    });
                }
                
                log('info', `Loaded ${this.modes.size} demodulation modes`);
                
            } else {
                log('warn', 'Failed to load demod modes, using defaults');
                this.loadDefaultModes();
            }
        } catch (error) {
            log('error', 'Error loading demod modes:', error);
            this.loadDefaultModes();
        }
    }

    /**
     * Load default demodulation modes
     */
    loadDefaultModes() {
        const defaultModes = {
            SPECTRUM: {
                name: 'Spectrum',
                description: 'Raw spectrum analysis for radio astronomy',
                bandwidthDefault: 2400000,
                bandwidthMin: 100000,
                bandwidthMax: 3200000,
                hasAudio: false
            },
            AM: {
                name: 'AM',
                description: 'Amplitude Modulation',
                bandwidthDefault: 6000,
                bandwidthMin: 1000,
                bandwidthMax: 20000,
                hasAudio: true
            },
            FM: {
                name: 'FM',
                description: 'Frequency Modulation',
                bandwidthDefault: 15000,
                bandwidthMin: 5000,
                bandwidthMax: 200000,
                hasAudio: true
            },
            SSB: {
                name: 'SSB',
                description: 'Single Sideband',
                bandwidthDefault: 2400,
                bandwidthMin: 500,
                bandwidthMax: 5000,
                hasAudio: true
            },
            CW: {
                name: 'CW',
                description: 'Morse Code',
                bandwidthDefault: 500,
                bandwidthMin: 100,
                bandwidthMax: 2000,
                hasAudio: true
            }
        };

        this.modes.clear();
        for (const [key, mode] of Object.entries(defaultModes)) {
            this.modes.set(key, { key, ...mode, parameters: {} });
        }
    }

    /**
     * Create demodulation controls UI
     */
    createUI() {
        this.container.innerHTML = `
            <div class="control-section">
                <div class="control-section-title">Demodulation</div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label for="demod-mode">Mode</label>
                        <select id="demod-mode" class="control-select">
                            ${Array.from(this.modes.values()).map(mode => 
                                `<option value="${mode.key}">${mode.name}</option>`
                            ).join('')}
                        </select>
                    </div>
                    
                    <div class="control-group">
                        <label for="demod-bandwidth">Bandwidth</label>
                        <input type="number" 
                               id="demod-bandwidth" 
                               class="control-input" 
                               min="100" 
                               max="3200000" 
                               step="100"
                               title="Demodulation bandwidth in Hz">
                    </div>
                    
                    <button id="apply-demod-btn" class="control-button">Apply</button>
                </div>
                
                <div id="demod-parameters" class="control-row">
                    <!-- Mode-specific parameters will be inserted here -->
                </div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label>Current Mode</label>
                        <div id="current-mode-display" class="value-display">SPECTRUM</div>
                    </div>
                    
                    <div class="control-group">
                        <label>Audio Output</label>
                        <div class="status-indicator">
                            <div id="audio-status-dot" class="status-dot"></div>
                            <span id="audio-status-text">Disabled</span>
                        </div>
                    </div>
                </div>
                
                <div class="control-row">
                    <div class="control-group full-width">
                        <label>Description</label>
                        <div id="mode-description" class="mode-description">
                            Select a demodulation mode to view details
                        </div>
                    </div>
                </div>
            </div>
            
            <style>
            .mode-description {
                background: var(--bg-dark);
                border: 1px solid var(--border-color);
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                color: var(--text-muted);
                min-height: 40px;
            }
            
            .control-group.full-width {
                flex: 1;
            }
            
            .demod-parameter {
                display: flex;
                flex-direction: column;
                gap: 5px;
                margin-right: 15px;
            }
            
            .demod-parameter label {
                font-size: 11px;
                color: var(--text-muted);
            }
            </style>
        `;

        // Get UI elements
        this.modeSelect = this.container.querySelector('#demod-mode');
        this.bandwidthInput = this.container.querySelector('#demod-bandwidth');
        this.applyBtn = this.container.querySelector('#apply-demod-btn');
        this.parametersContainer = this.container.querySelector('#demod-parameters');
        this.currentModeDisplay = this.container.querySelector('#current-mode-display');
        this.audioStatusDot = this.container.querySelector('#audio-status-dot');
        this.audioStatusText = this.container.querySelector('#audio-status-text');
        this.modeDescription = this.container.querySelector('#mode-description');
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Mode selection
        this.modeSelect.addEventListener('change', (e) => {
            this.updateModeUI(e.target.value);
        });

        // Bandwidth input
        this.bandwidthInput.addEventListener('input', (e) => {
            this.validateBandwidth(e.target.value);
        });

        // Apply button
        this.applyBtn.addEventListener('click', () => {
            this.applyDemodulation();
        });

        // Enter key on bandwidth input
        this.bandwidthInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.applyDemodulation();
            }
        });
    }

    /**
     * Update UI based on selected mode
     * @param {string} modeKey - Selected mode key
     */
    updateModeUI(modeKey) {
        const mode = this.modes.get(modeKey);
        if (!mode) return;

        // Update bandwidth
        this.bandwidthInput.value = mode.bandwidthDefault;
        this.bandwidthInput.min = mode.bandwidthMin;
        this.bandwidthInput.max = mode.bandwidthMax;
        this.currentBandwidth = mode.bandwidthDefault;

        // Update description
        this.modeDescription.textContent = mode.description;

        // Update audio status
        this.updateAudioStatus(mode.hasAudio);

        // Create mode-specific parameters
        this.createModeParameters(mode);

        // Validate bandwidth
        this.validateBandwidth(this.bandwidthInput.value);
    }

    /**
     * Create mode-specific parameter controls
     * @param {object} mode - Mode configuration
     */
    createModeParameters(mode) {
        this.parametersContainer.innerHTML = '';

        const defaults = DEMOD_DEFAULTS[mode.key] || {};
        const parameters = { ...defaults, ...mode.parameters };

        // Create parameter controls based on mode
        switch (mode.key) {
            case 'AM':
                this.createAMParameters(parameters);
                break;
            case 'FM':
                this.createFMParameters(parameters);
                break;
            case 'SSB':
                this.createSSBParameters(parameters);
                break;
            case 'CW':
                this.createCWParameters(parameters);
                break;
            case 'SPECTRUM':
                this.createSpectrumParameters(parameters);
                break;
        }
    }

    /**
     * Create AM-specific parameters
     */
    createAMParameters(params) {
        const agcGroup = this.createParameterGroup('AGC Attack', 'range', {
            min: 0.01,
            max: 1.0,
            step: 0.01,
            value: params.agc_attack || 0.1,
            id: 'am-agc-attack'
        });

        this.parametersContainer.appendChild(agcGroup);
    }

    /**
     * Create FM-specific parameters
     */
    createFMParameters(params) {
        const deviationGroup = this.createParameterGroup('Deviation (Hz)', 'number', {
            min: 1000,
            max: 75000,
            step: 1000,
            value: params.deviation || 5000,
            id: 'fm-deviation'
        });

        this.parametersContainer.appendChild(deviationGroup);
    }

    /**
     * Create SSB-specific parameters
     */
    createSSBParameters(params) {
        const filterGroup = this.createParameterGroup('Filter Shape', 'range', {
            min: 0.01,
            max: 0.5,
            step: 0.01,
            value: params.filter_shape || 0.1,
            id: 'ssb-filter-shape'
        });

        this.parametersContainer.appendChild(filterGroup);
    }

    /**
     * Create CW-specific parameters
     */
    createCWParameters(params) {
        const toneGroup = this.createParameterGroup('Tone (Hz)', 'number', {
            min: 300,
            max: 1200,
            step: 50,
            value: params.tone_frequency || 600,
            id: 'cw-tone'
        });

        this.parametersContainer.appendChild(toneGroup);
    }

    /**
     * Create Spectrum-specific parameters
     */
    createSpectrumParameters(params) {
        const integrationGroup = this.createParameterGroup('Integration (s)', 'number', {
            min: 1,
            max: 3600,
            step: 1,
            value: params.integration_time || 1,
            id: 'spectrum-integration'
        });

        this.parametersContainer.appendChild(integrationGroup);
    }

    /**
     * Create parameter control group
     * @param {string} label - Parameter label
     * @param {string} type - Input type
     * @param {object} attrs - Input attributes
     * @returns {HTMLElement} Parameter group element
     */
    createParameterGroup(label, type, attrs) {
        const group = document.createElement('div');
        group.className = 'demod-parameter';

        const labelEl = document.createElement('label');
        labelEl.textContent = label;
        labelEl.setAttribute('for', attrs.id);

        const input = document.createElement('input');
        input.type = type;
        input.className = 'control-input';
        Object.assign(input, attrs);

        group.appendChild(labelEl);
        group.appendChild(input);

        return group;
    }

    /**
     * Validate bandwidth input
     * @param {string} value - Bandwidth value
     */
    validateBandwidth(value) {
        const bandwidth = parseInt(value);
        const mode = this.modes.get(this.modeSelect.value);
        
        if (!mode) return;

        const isValid = !isNaN(bandwidth) && 
                       bandwidth >= mode.bandwidthMin && 
                       bandwidth <= mode.bandwidthMax;

        this.bandwidthInput.classList.toggle('error', !isValid);
        this.applyBtn.disabled = !isValid;

        if (isValid) {
            this.currentBandwidth = bandwidth;
            this.applyBtn.textContent = `Apply ${formatBandwidth(bandwidth)}`;
        } else {
            this.applyBtn.textContent = 'Apply';
        }
    }

    /**
     * Apply demodulation settings
     */
    async applyDemodulation() {
        const mode = this.modeSelect.value;
        const bandwidth = parseInt(this.bandwidthInput.value);

        if (!this.modes.has(mode)) {
            log('error', 'Invalid demodulation mode:', mode);
            return;
        }

        try {
            this.applyBtn.disabled = true;
            this.applyBtn.textContent = 'Applying...';

            const response = await apiClient.setDemodulation(mode, bandwidth);
            
            if (response.isSuccess()) {
                this.currentMode = mode;
                this.currentBandwidth = bandwidth;
                this.updateUI();
                
                log('info', `Demodulation set to ${mode} with ${formatBandwidth(bandwidth)} bandwidth`);
                
                // Trigger callback
                this.trigger('demod-changed', { 
                    mode, 
                    bandwidth,
                    hasAudio: this.modes.get(mode).hasAudio 
                });
                
            } else {
                log('error', 'Failed to set demodulation:', response.getError());
                this.showError(response.getError());
            }
        } catch (error) {
            log('error', 'Error setting demodulation:', error);
            this.showError(error.message);
        } finally {
            this.applyBtn.disabled = false;
            this.validateBandwidth(this.bandwidthInput.value);
        }
    }

    /**
     * Update UI state
     */
    updateUI() {
        const mode = this.modes.get(this.currentMode);
        if (!mode) return;

        // Update current mode display
        this.currentModeDisplay.textContent = `${mode.name} (${formatBandwidth(this.currentBandwidth)})`;

        // Update audio status
        this.updateAudioStatus(mode.hasAudio);

        // Update mode selection
        this.modeSelect.value = this.currentMode;
        
        // Update mode description
        this.updateModeUI(this.currentMode);
    }

    /**
     * Update audio status indicator
     * @param {boolean} hasAudio - Whether mode has audio output
     */
    updateAudioStatus(hasAudio) {
        if (hasAudio) {
            this.audioStatusDot.classList.add('connected');
            this.audioStatusText.textContent = 'Enabled';
        } else {
            this.audioStatusDot.classList.remove('connected');
            this.audioStatusText.textContent = 'Disabled';
        }
    }

    /**
     * Get current demodulation mode
     * @returns {string} Current mode key
     */
    getCurrentMode() {
        return this.currentMode;
    }

    /**
     * Get current bandwidth
     * @returns {number} Current bandwidth in Hz
     */
    getCurrentBandwidth() {
        return this.currentBandwidth;
    }

    /**
     * Set demodulation mode
     * @param {string} mode - Mode key
     * @param {number} bandwidth - Bandwidth in Hz (optional)
     */
    setMode(mode, bandwidth = null) {
        if (!this.modes.has(mode)) {
            log('warn', 'Unknown demodulation mode:', mode);
            return;
        }

        this.modeSelect.value = mode;
        
        if (bandwidth !== null) {
            this.bandwidthInput.value = bandwidth;
        }
        
        this.updateModeUI(mode);
    }

    /**
     * Show error message
     * @param {string} message - Error message
     */
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        errorDiv.style.cssText = `
            background: var(--error-color);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 13px;
        `;

        this.container.appendChild(errorDiv);

        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 3000);
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
}

export default DemodControls;