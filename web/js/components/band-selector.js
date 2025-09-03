/**
 * Band Selector Component
 * Manages radio band presets and selection
 */

import { formatFrequency } from '../utils/frequency-utils.js';
import { apiClient } from '../services/api-client.js';
import { CONFIG, log } from '../config.js';

/**
 * Band Selector class
 */
export class BandSelector {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.bands = new Map();
        this.selectedBand = null;
        this.callbacks = new Map();
        
        this.init();
    }

    /**
     * Initialize band selector
     */
    async init() {
        if (!this.container) {
            log('error', 'Band selector container not found');
            return;
        }

        this.createUI();
        await this.loadBands();
        this.attachEventListeners();
    }

    /**
     * Create band selector UI
     */
    createUI() {
        this.container.innerHTML = `
            <div class="control-section">
                <div class="control-section-title">Band Selection</div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label for="band-category">Category</label>
                        <select id="band-category" class="control-select">
                            <option value="all">All Bands</option>
                            <option value="radioastronomy">Radio Astronomy</option>
                            <option value="amateur">Amateur Radio</option>
                            <option value="broadcast">Broadcast</option>
                            <option value="aviation">Aviation</option>
                            <option value="satellite">Satellite</option>
                            <option value="marine">Marine</option>
                            <option value="utility">Utility</option>
                        </select>
                    </div>
                    
                    <div class="control-group">
                        <label for="band-search">Search</label>
                        <input type="text" 
                               id="band-search" 
                               class="control-input" 
                               placeholder="Search bands..."
                               title="Search by name or frequency">
                    </div>
                </div>
                
                <div id="band-grid" class="band-grid">
                    <!-- Bands will be populated here -->
                </div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label>Selected Band</label>
                        <div id="selected-band-info" class="value-display">None</div>
                    </div>
                    
                    <button id="tune-band-btn" class="control-button" disabled>
                        Tune to Band
                    </button>
                </div>
            </div>
        `;

        // Get UI elements
        this.categorySelect = this.container.querySelector('#band-category');
        this.searchInput = this.container.querySelector('#band-search');
        this.bandGrid = this.container.querySelector('#band-grid');
        this.selectedBandInfo = this.container.querySelector('#selected-band-info');
        this.tuneBandBtn = this.container.querySelector('#tune-band-btn');
    }

    /**
     * Load bands from API
     */
    async loadBands() {
        try {
            const response = await apiClient.getBands();
            
            if (response.isSuccess()) {
                const bandsData = response.getData();
                
                // Clear existing bands
                this.bands.clear();
                
                // Process bands data
                for (const [key, band] of Object.entries(bandsData)) {
                    this.bands.set(key, {
                        key,
                        name: band.name,
                        centerFreq: band.center_freq,
                        bandwidth: band.bandwidth,
                        description: band.description,
                        category: band.category || 'utility',
                        modes: band.modes || ['SPECTRUM'],
                        typicalGain: band.typical_gain || 40,
                        integrationTime: band.integration_time || 1
                    });
                }
                
                log('info', `Loaded ${this.bands.size} radio bands`);
                this.renderBands();
                
            } else {
                log('error', 'Failed to load bands:', response.getError());
                this.showError('Failed to load radio bands');
            }
        } catch (error) {
            log('error', 'Error loading bands:', error);
            this.showError('Network error loading bands');
        }
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Category filter
        this.categorySelect.addEventListener('change', () => {
            this.renderBands();
        });

        // Search input
        this.searchInput.addEventListener('input', (e) => {
            this.filterBands(e.target.value);
        });

        // Tune to band button
        this.tuneBandBtn.addEventListener('click', () => {
            this.tuneToSelectedBand();
        });
    }

    /**
     * Render bands grid
     */
    renderBands() {
        const category = this.categorySelect.value;
        const searchTerm = this.searchInput.value.toLowerCase();
        
        // Filter bands
        let filteredBands = Array.from(this.bands.values());
        
        if (category !== 'all') {
            filteredBands = filteredBands.filter(band => band.category === category);
        }
        
        if (searchTerm) {
            filteredBands = filteredBands.filter(band => 
                band.name.toLowerCase().includes(searchTerm) ||
                band.description.toLowerCase().includes(searchTerm) ||
                formatFrequency(band.centerFreq).toLowerCase().includes(searchTerm)
            );
        }

        // Sort bands by frequency
        filteredBands.sort((a, b) => a.centerFreq - b.centerFreq);

        // Clear grid
        this.bandGrid.innerHTML = '';

        if (filteredBands.length === 0) {
            this.bandGrid.innerHTML = '<div class="no-bands">No bands found</div>';
            return;
        }

        // Create band buttons
        filteredBands.forEach(band => {
            const bandButton = this.createBandButton(band);
            this.bandGrid.appendChild(bandButton);
        });
    }

    /**
     * Create band button element
     * @param {object} band - Band data
     * @returns {HTMLElement} Band button element
     */
    createBandButton(band) {
        const button = document.createElement('button');
        button.className = 'band-button';
        button.dataset.bandKey = band.key;
        
        // Create band info
        const nameSpan = document.createElement('span');
        nameSpan.className = 'band-name';
        nameSpan.textContent = band.name;
        
        const freqSpan = document.createElement('span');
        freqSpan.className = 'band-frequency';
        freqSpan.textContent = formatFrequency(band.centerFreq);
        
        const descSpan = document.createElement('div');
        descSpan.className = 'band-description';
        descSpan.textContent = band.description;
        descSpan.style.fontSize = '11px';
        descSpan.style.color = 'var(--text-muted)';
        descSpan.style.marginTop = '2px';
        
        button.appendChild(nameSpan);
        button.appendChild(freqSpan);
        button.appendChild(descSpan);
        
        // Add click handler
        button.addEventListener('click', () => {
            this.selectBand(band.key);
        });
        
        // Add double-click to tune
        button.addEventListener('dblclick', () => {
            this.selectBand(band.key);
            this.tuneToSelectedBand();
        });
        
        return button;
    }

    /**
     * Filter bands by search term
     * @param {string} searchTerm - Search term
     */
    filterBands(searchTerm) {
        this.renderBands();
    }

    /**
     * Select a band
     * @param {string} bandKey - Band key
     */
    selectBand(bandKey) {
        const band = this.bands.get(bandKey);
        if (!band) {
            log('warn', 'Band not found:', bandKey);
            return;
        }

        // Update selection
        this.selectedBand = band;

        // Update UI
        this.updateSelection();
        this.updateSelectedBandInfo();

        // Trigger callback
        this.trigger('band-selected', { band });
    }

    /**
     * Update visual selection
     */
    updateSelection() {
        // Remove previous selection
        const previousSelected = this.bandGrid.querySelector('.band-button.active');
        if (previousSelected) {
            previousSelected.classList.remove('active');
        }

        // Add new selection
        if (this.selectedBand) {
            const selectedButton = this.bandGrid.querySelector(
                `[data-band-key="${this.selectedBand.key}"]`
            );
            if (selectedButton) {
                selectedButton.classList.add('active');
            }
        }

        // Enable/disable tune button
        this.tuneBandBtn.disabled = !this.selectedBand;
    }

    /**
     * Update selected band info display
     */
    updateSelectedBandInfo() {
        if (!this.selectedBand) {
            this.selectedBandInfo.textContent = 'None';
            return;
        }

        const band = this.selectedBand;
        const info = `${band.name} - ${formatFrequency(band.centerFreq)}`;
        this.selectedBandInfo.textContent = info;
        this.selectedBandInfo.title = `${band.description}\nBandwidth: ${formatFrequency(band.bandwidth)}\nModes: ${band.modes.join(', ')}`;
    }

    /**
     * Tune to selected band
     */
    async tuneToSelectedBand() {
        if (!this.selectedBand) {
            log('warn', 'No band selected for tuning');
            return;
        }

        try {
            this.tuneBandBtn.disabled = true;
            this.tuneBandBtn.textContent = 'Tuning...';

            const response = await apiClient.tuneToBand(this.selectedBand.key);
            
            if (response.isSuccess()) {
                log('info', `Tuned to ${this.selectedBand.name}`);
                this.trigger('band-tuned', { band: this.selectedBand });
            } else {
                log('error', 'Failed to tune to band:', response.getError());
                this.showError(response.getError());
            }
        } catch (error) {
            log('error', 'Error tuning to band:', error);
            this.showError(error.message);
        } finally {
            this.tuneBandBtn.disabled = false;
            this.tuneBandBtn.textContent = 'Tune to Band';
        }
    }

    /**
     * Get selected band
     * @returns {object|null} Selected band data
     */
    getSelectedBand() {
        return this.selectedBand;
    }

    /**
     * Get band by key
     * @param {string} bandKey - Band key
     * @returns {object|null} Band data
     */
    getBand(bandKey) {
        return this.bands.get(bandKey);
    }

    /**
     * Get all bands
     * @returns {Map} All bands
     */
    getAllBands() {
        return new Map(this.bands);
    }

    /**
     * Set selected band by frequency (find closest)
     * @param {number} frequency - Target frequency in Hz
     */
    selectByFrequency(frequency) {
        let closestBand = null;
        let minDistance = Infinity;

        for (const band of this.bands.values()) {
            const distance = Math.abs(band.centerFreq - frequency);
            if (distance < minDistance) {
                minDistance = distance;
                closestBand = band;
            }
        }

        if (closestBand) {
            this.selectBand(closestBand.key);
        }
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

    /**
     * Refresh bands from server
     */
    async refresh() {
        await this.loadBands();
    }
}

export default BandSelector;