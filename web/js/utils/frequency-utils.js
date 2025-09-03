/**
 * Frequency Utilities
 * Helper functions for frequency formatting and conversions
 */

import { FREQUENCY_FORMAT } from '../config.js';

/**
 * Format frequency for display
 * @param {number} frequency - Frequency in Hz
 * @param {Object} options - Formatting options
 * @returns {string} Formatted frequency string
 */
export function formatFrequency(frequency, options = {}) {
    const opts = { ...FREQUENCY_FORMAT, ...options };
    
    if (!frequency || isNaN(frequency)) {
        return 'N/A';
    }
    
    if (!opts.USE_SI_PREFIXES) {
        return `${frequency.toFixed(0)} Hz`;
    }
    
    const units = [
        { threshold: 1e9, suffix: 'GHz', divisor: 1e9 },
        { threshold: 1e6, suffix: 'MHz', divisor: 1e6 },
        { threshold: 1e3, suffix: 'kHz', divisor: 1e3 },
        { threshold: 1, suffix: 'Hz', divisor: 1 }
    ];
    
    const unit = units.find(u => Math.abs(frequency) >= u.threshold);
    const value = frequency / unit.divisor;
    const precision = unit.suffix === 'Hz' ? 0 : opts.DISPLAY_PRECISION;
    
    const formattedValue = value.toFixed(precision);
    return opts.SHOW_UNITS ? `${formattedValue} ${unit.suffix}` : formattedValue;
}

/**
 * Parse frequency string to Hz
 * @param {string} freqStr - Frequency string (e.g., "146.5 MHz")
 * @returns {number} Frequency in Hz
 */
export function parseFrequency(freqStr) {
    if (typeof freqStr === 'number') {
        return freqStr;
    }
    
    if (!freqStr || typeof freqStr !== 'string') {
        return NaN;
    }
    
    // Remove whitespace and convert to lowercase
    const clean = freqStr.trim().toLowerCase();
    
    // Extract number and unit
    const match = clean.match(/^([0-9.]+)\s*([a-z]*)$/);
    if (!match) {
        return NaN;
    }
    
    const value = parseFloat(match[1]);
    const unit = match[2];
    
    if (isNaN(value)) {
        return NaN;
    }
    
    // Convert to Hz based on unit
    const multipliers = {
        '': 1,
        'hz': 1,
        'khz': 1e3,
        'mhz': 1e6,
        'ghz': 1e9
    };
    
    const multiplier = multipliers[unit] || 1;
    return value * multiplier;
}

/**
 * Format bandwidth for display
 * @param {number} bandwidth - Bandwidth in Hz
 * @returns {string} Formatted bandwidth string
 */
export function formatBandwidth(bandwidth) {
    if (!bandwidth || isNaN(bandwidth)) {
        return 'N/A';
    }
    
    if (bandwidth >= 1e6) {
        return `${(bandwidth / 1e6).toFixed(1)} MHz`;
    } else if (bandwidth >= 1e3) {
        return `${(bandwidth / 1e3).toFixed(1)} kHz`;
    } else {
        return `${bandwidth.toFixed(0)} Hz`;
    }
}

/**
 * Calculate center frequency from start and end frequencies
 * @param {number} startFreq - Start frequency in Hz
 * @param {number} endFreq - End frequency in Hz
 * @returns {number} Center frequency in Hz
 */
export function calculateCenterFrequency(startFreq, endFreq) {
    return (startFreq + endFreq) / 2;
}

/**
 * Calculate frequency from bin index
 * @param {number} binIndex - FFT bin index
 * @param {number} fftSize - FFT size
 * @param {number} sampleRate - Sample rate in Hz
 * @param {number} centerFreq - Center frequency in Hz
 * @returns {number} Frequency in Hz
 */
export function binToFrequency(binIndex, fftSize, sampleRate, centerFreq) {
    const freqPerBin = sampleRate / fftSize;
    const offsetFreq = (binIndex - fftSize / 2) * freqPerBin;
    return centerFreq + offsetFreq;
}

/**
 * Calculate bin index from frequency
 * @param {number} frequency - Frequency in Hz
 * @param {number} fftSize - FFT size
 * @param {number} sampleRate - Sample rate in Hz
 * @param {number} centerFreq - Center frequency in Hz
 * @returns {number} FFT bin index
 */
export function frequencyToBin(frequency, fftSize, sampleRate, centerFreq) {
    const freqPerBin = sampleRate / fftSize;
    const offsetFreq = frequency - centerFreq;
    return Math.round(offsetFreq / freqPerBin + fftSize / 2);
}

/**
 * Generate frequency scale labels
 * @param {number} startFreq - Start frequency in Hz
 * @param {number} endFreq - End frequency in Hz
 * @param {number} numLabels - Number of labels to generate
 * @returns {Array} Array of {frequency, label} objects
 */
export function generateFrequencyScale(startFreq, endFreq, numLabels = 10) {
    const labels = [];
    const span = endFreq - startFreq;
    
    for (let i = 0; i < numLabels; i++) {
        const frequency = startFreq + (span * i) / (numLabels - 1);
        const label = formatFrequency(frequency, { DISPLAY_PRECISION: 1 });
        labels.push({ frequency, label });
    }
    
    return labels;
}

/**
 * Validate frequency range
 * @param {number} frequency - Frequency to validate
 * @param {number} minFreq - Minimum allowed frequency
 * @param {number} maxFreq - Maximum allowed frequency
 * @returns {boolean} True if frequency is valid
 */
export function isValidFrequency(frequency, minFreq = 0, maxFreq = Infinity) {
    return !isNaN(frequency) && frequency >= minFreq && frequency <= maxFreq;
}

/**
 * Clamp frequency to valid range
 * @param {number} frequency - Frequency to clamp
 * @param {number} minFreq - Minimum allowed frequency
 * @param {number} maxFreq - Maximum allowed frequency
 * @returns {number} Clamped frequency
 */
export function clampFrequency(frequency, minFreq, maxFreq) {
    return Math.max(minFreq, Math.min(maxFreq, frequency));
}

/**
 * Calculate Doppler shift for radio astronomy
 * @param {number} observedFreq - Observed frequency in Hz
 * @param {number} restFreq - Rest frequency in Hz (default: H1 line)
 * @returns {number} Velocity in m/s (positive = receding)
 */
export function calculateDopplerVelocity(observedFreq, restFreq = 1420405751) {
    const c = 299792458; // Speed of light in m/s
    return c * (observedFreq - restFreq) / restFreq;
}

/**
 * Format velocity for display
 * @param {number} velocity - Velocity in m/s
 * @returns {string} Formatted velocity string
 */
export function formatVelocity(velocity) {
    if (!velocity || isNaN(velocity)) {
        return 'N/A';
    }
    
    const absVel = Math.abs(velocity);
    const sign = velocity >= 0 ? '+' : '-';
    
    if (absVel >= 1000) {
        return `${sign}${(absVel / 1000).toFixed(1)} km/s`;
    } else {
        return `${sign}${absVel.toFixed(0)} m/s`;
    }
}

export default {
    formatFrequency,
    parseFrequency,
    formatBandwidth,
    calculateCenterFrequency,
    binToFrequency,
    frequencyToBin,
    generateFrequencyScale,
    isValidFrequency,
    clampFrequency,
    calculateDopplerVelocity,
    formatVelocity
};