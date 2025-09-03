/**
 * Frequency Controller Component
 * Handles frequency input, validation, and tuning controls
 */

import { formatFrequency, parseFrequency, isValidFrequency, clampFrequency } from '../utils/frequency-utils.js';
import { HARDWARE, CONFIG, log } from '../config.js';
import { apiClient } from '../services/api-client.js';

/**
 * Frequency Controller class
 */
export class FrequencyController {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentFrequency = HARDWARE.RTL_SDR.min_frequency;
        this.callbacks = new Map();
        
        this.init();
    }

    /**
     * Initialize frequency controller
     */
    init() {
        if (!this.container) {
            log('error', 'Frequency controller container not found');
            return;
        }

        this.createUI();
        this.attachEventListeners();
    }

    /**
     * Create frequency controller UI
     */
    createUI() {
        this.container.innerHTML = `
            <div class="control-section">
                <div class="control-section-title">Frequency Control</div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label for="freq-input">Frequency</label>
                        <input type="text" 
                               id="freq-input" 
                               class="control-input" 
                               placeholder="146.5 MHz"
                               title="Enter frequency (e.g., 146.5 MHz, 1420.4 MHz)">
                    </div>
                    
                    <div class="control-group">
                        <label for="freq-slider">Fine Tune</label>
                        <input type="range" 
                               id="freq-slider" 
                               class="control-input" 
                               min="-1000000" 
                               max="1000000" 
                               value="0" 
                               step="1000"
                               title="Fine frequency adjustment (±1 MHz)">
                    </div>
                    
                    <div class="control-group">
                        <label>&nbsp;</label>
                        <button id="tune-btn" class="control-button">Tune</button>
                    </div>
                </div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label>Current</label>
                        <div id="current-freq" class="value-display">---</div>
                    </div>
                    
                    <div class="control-group">
                        <label>Range</label>
                        <div class="value-display">
                            ${formatFrequency(HARDWARE.RTL_SDR.min_frequency)} - 
                            ${formatFrequency(HARDWARE.RTL_SDR.max_frequency)}
                        </div>
                    </div>
                </div>
                
                <div class="control-row">
                    <div class="freq-presets">
                        <button class="control-button secondary" data-freq="88000000">88 MHz</button>
                        <button class="control-button secondary" data-freq="146520000">146.52 MHz</button>
                        <button class="control-button secondary" data-freq="433920000">433.92 MHz</button>
                        <button class="control-button secondary" data-freq="1420405751">H1 Line</button>
                    </div>
                </div>
            </div>
        `;

        // Get UI elements
        this.freqInput = this.container.querySelector('#freq-input');
        this.freqSlider = this.container.querySelector('#freq-slider');
        this.tuneBtn = this.container.querySelector('#tune-btn');
        this.currentFreqDisplay = this.container.querySelector('#current-freq');
        this.presetButtons = this.container.querySelectorAll('[data-freq]');
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Frequency input
        this.freqInput.addEventListener('input', (e) => {
            this.validateFrequencyInput(e.target.value);
        });

        this.freqInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.handleTune();
            }
        });

        // Fine tune slider
        this.freqSlider.addEventListener('input', (e) => {
            this.handleFineTune(parseInt(e.target.value));
        });

        // Tune button
        this.tuneBtn.addEventListener('click', () => {
            this.handleTune();
        });

        // Preset buttons
        this.presetButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const frequency = parseInt(e.target.dataset.freq);
                this.setFrequency(frequency);
            });
        });
    }

    /**
     * Validate frequency input
     * @param {string} input - Frequency input string
     */
    validateFrequencyInput(input) {
        const frequency = parseFrequency(input);
        const isValid = isValidFrequency(frequency, 
            HARDWARE.RTL_SDR.min_frequency, 
            HARDWARE.RTL_SDR.max_frequency
        );

        // Update input styling
        this.freqInput.classList.toggle('error', !isValid && input.length > 0);
        
        // Enable/disable tune button
        this.tuneBtn.disabled = !isValid || input.length === 0;

        if (isValid) {
            // Update preview in tune button
            this.tuneBtn.textContent = `Tune to ${formatFrequency(frequency)}`;
        } else {
            this.tuneBtn.textContent = 'Tune';
        }
    }

    /**
     * Handle fine tune adjustment
     * @param {number} offset - Frequency offset in Hz
     */
    handleFineTune(offset) {
        if (this.currentFrequency) {
            const newFreq = this.currentFrequency + offset;
            const clampedFreq = clampFrequency(newFreq, 
                HARDWARE.RTL_SDR.min_frequency, 
                HARDWARE.RTL_SDR.max_frequency
            );
            
            this.freqInput.value = formatFrequency(clampedFreq);
            this.validateFrequencyInput(this.freqInput.value);
        }
    }

    /**
     * Handle tune button click
     */
    async handleTune() {
        const frequency = parseFrequency(this.freqInput.value);
        
        if (!isValidFrequency(frequency, 
            HARDWARE.RTL_SDR.min_frequency, 
            HARDWARE.RTL_SDR.max_frequency
        )) {
            log('warn', 'Invalid frequency for tuning:', frequency);
            return;
        }

        try {
            this.tuneBtn.disabled = true;
            this.tuneBtn.textContent = 'Tuning...';

            const response = await apiClient.tuneFrequency(frequency);
            
            if (response.isSuccess()) {
                this.setFrequency(frequency);
                log('info', `Tuned to ${formatFrequency(frequency)}`);
                
                // Trigger callback
                this.trigger('frequency-changed', { frequency });
            } else {
                log('error', 'Failed to tune:', response.getError());
                this.showError(response.getError());
            }
        } catch (error) {
            log('error', 'Tuning error:', error);
            this.showError(error.message);
        } finally {
            this.tuneBtn.disabled = false;
            this.tuneBtn.textContent = 'Tune';
        }
    }

    /**
     * Set current frequency
     * @param {number} frequency - Frequency in Hz
     */
    setFrequency(frequency) {
        this.currentFrequency = frequency;
        this.freqInput.value = formatFrequency(frequency);
        this.currentFreqDisplay.textContent = formatFrequency(frequency);
        
        // Reset fine tune slider
        this.freqSlider.value = 0;
        
        // Validate input
        this.validateFrequencyInput(this.freqInput.value);
    }

    /**
     * Get current frequency
     * @returns {number} Current frequency in Hz
     */
    getFrequency() {
        return this.currentFrequency;
    }

    /**
     * Show error message
     * @param {string} message - Error message
     */
    showError(message) {
        // Create temporary error display
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

        // Remove after 3 seconds
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

    /**
     * Update from external source (e.g., spectrum click)
     * @param {number} frequency - New frequency in Hz
     */
    updateFromExternal(frequency) {
        const clampedFreq = clampFrequency(frequency,
            HARDWARE.RTL_SDR.min_frequency,
            HARDWARE.RTL_SDR.max_frequency
        );
        
        this.setFrequency(clampedFreq);
    }

    /**
     * Enable or disable the controller
     * @param {boolean} enabled - Enable state
     */
    setEnabled(enabled) {
        this.freqInput.disabled = !enabled;
        this.freqSlider.disabled = !enabled;
        this.tuneBtn.disabled = !enabled;
        this.presetButtons.forEach(btn => btn.disabled = !enabled);
    }
}

export default FrequencyController;