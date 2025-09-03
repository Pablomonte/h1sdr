/**
 * DSP Utilities
 * Digital Signal Processing helper functions
 */

/**
 * Apply window function to data
 * @param {Float32Array} data - Input data
 * @param {string} windowType - Window type ('hann', 'blackman', 'hamming', 'rectangular')
 * @returns {Float32Array} Windowed data
 */
export function applyWindow(data, windowType = 'hann') {
    const length = data.length;
    const windowed = new Float32Array(length);
    
    for (let i = 0; i < length; i++) {
        let window = 1.0;
        
        switch (windowType.toLowerCase()) {
            case 'hann':
            case 'hanning':
                window = 0.5 * (1 - Math.cos(2 * Math.PI * i / (length - 1)));
                break;
                
            case 'hamming':
                window = 0.54 - 0.46 * Math.cos(2 * Math.PI * i / (length - 1));
                break;
                
            case 'blackman':
                window = 0.42 - 0.5 * Math.cos(2 * Math.PI * i / (length - 1)) + 
                         0.08 * Math.cos(4 * Math.PI * i / (length - 1));
                break;
                
            case 'rectangular':
            case 'none':
            default:
                window = 1.0;
                break;
        }
        
        windowed[i] = data[i] * window;
    }
    
    return windowed;
}

/**
 * Convert linear amplitude to dB
 * @param {number} amplitude - Linear amplitude
 * @param {number} reference - Reference level (default: 1.0)
 * @returns {number} Level in dB
 */
export function linearToDb(amplitude, reference = 1.0) {
    if (amplitude <= 0 || reference <= 0) {
        return -Infinity;
    }
    return 20 * Math.log10(amplitude / reference);
}

/**
 * Convert dB to linear amplitude
 * @param {number} db - Level in dB
 * @param {number} reference - Reference level (default: 1.0)
 * @returns {number} Linear amplitude
 */
export function dbToLinear(db, reference = 1.0) {
    return reference * Math.pow(10, db / 20);
}

/**
 * Calculate power spectral density from complex FFT
 * @param {Float32Array} fftReal - Real part of FFT
 * @param {Float32Array} fftImag - Imaginary part of FFT
 * @returns {Float32Array} Power spectral density
 */
export function calculatePSD(fftReal, fftImag) {
    const length = fftReal.length;
    const psd = new Float32Array(length);
    
    for (let i = 0; i < length; i++) {
        psd[i] = fftReal[i] * fftReal[i] + fftImag[i] * fftImag[i];
    }
    
    return psd;
}

/**
 * Apply exponential moving average
 * @param {Float32Array} newData - New data
 * @param {Float32Array} avgData - Current average (modified in-place)
 * @param {number} alpha - Smoothing factor (0-1)
 */
export function exponentialMovingAverage(newData, avgData, alpha = 0.1) {
    const length = Math.min(newData.length, avgData.length);
    
    for (let i = 0; i < length; i++) {
        avgData[i] = alpha * newData[i] + (1 - alpha) * avgData[i];
    }
}

/**
 * Find peaks in spectrum data
 * @param {Float32Array} spectrum - Spectrum data
 * @param {number} threshold - Minimum peak height (dB above noise floor)
 * @param {number} minDistance - Minimum distance between peaks (bins)
 * @returns {Array} Array of {index, value} peak objects
 */
export function findPeaks(spectrum, threshold = 10, minDistance = 10) {
    const peaks = [];
    const length = spectrum.length;
    
    // Calculate noise floor (median of spectrum)
    const sorted = spectrum.slice().sort((a, b) => a - b);
    const noiseFloor = sorted[Math.floor(sorted.length * 0.5)];
    const thresholdValue = noiseFloor + threshold;
    
    for (let i = minDistance; i < length - minDistance; i++) {
        if (spectrum[i] > thresholdValue) {
            // Check if it's a local maximum
            let isPeak = true;
            for (let j = i - minDistance; j <= i + minDistance; j++) {
                if (j !== i && spectrum[j] >= spectrum[i]) {
                    isPeak = false;
                    break;
                }
            }
            
            if (isPeak) {
                peaks.push({
                    index: i,
                    value: spectrum[i],
                    snr: spectrum[i] - noiseFloor
                });
                
                // Skip ahead to avoid duplicate detection
                i += minDistance;
            }
        }
    }
    
    // Sort by SNR (highest first)
    peaks.sort((a, b) => b.snr - a.snr);
    
    return peaks;
}

/**
 * Calculate signal-to-noise ratio
 * @param {Float32Array} spectrum - Spectrum data
 * @param {number} signalBin - Bin index of signal
 * @param {number} noiseStart - Start of noise region
 * @param {number} noiseEnd - End of noise region
 * @returns {number} SNR in dB
 */
export function calculateSNR(spectrum, signalBin, noiseStart, noiseEnd) {
    const signalPower = spectrum[signalBin];
    
    // Calculate average noise power
    let noisePower = 0;
    let noiseCount = 0;
    
    for (let i = noiseStart; i < noiseEnd; i++) {
        if (i !== signalBin) {
            noisePower += spectrum[i];
            noiseCount++;
        }
    }
    
    if (noiseCount === 0) {
        return Infinity;
    }
    
    noisePower /= noiseCount;
    
    return linearToDb(signalPower / noisePower);
}

/**
 * Apply simple AGC (Automatic Gain Control)
 * @param {Float32Array} signal - Input signal
 * @param {number} targetLevel - Target RMS level
 * @param {number} attackTime - Attack time constant
 * @param {number} releaseTime - Release time constant
 * @param {object} state - AGC state object (modified in-place)
 * @returns {Float32Array} AGC output
 */
export function applyAGC(signal, targetLevel = 0.5, attackTime = 0.1, releaseTime = 0.01, state = { gain: 1.0 }) {
    const output = new Float32Array(signal.length);
    
    for (let i = 0; i < signal.length; i++) {
        const inputLevel = Math.abs(signal[i]);
        const error = targetLevel - inputLevel * state.gain;
        
        // Update gain
        if (error < 0) {
            // Input too loud, reduce gain quickly (attack)
            state.gain *= (1 - attackTime);
        } else {
            // Input too quiet, increase gain slowly (release)
            state.gain *= (1 + releaseTime * error / targetLevel);
        }
        
        // Clamp gain to reasonable range
        state.gain = Math.max(0.001, Math.min(1000, state.gain));
        
        output[i] = signal[i] * state.gain;
    }
    
    return output;
}

/**
 * Simple FIR low-pass filter
 * @param {Float32Array} signal - Input signal
 * @param {number} cutoff - Cutoff frequency (normalized, 0-0.5)
 * @param {number} taps - Number of filter taps
 * @returns {Float32Array} Filtered signal
 */
export function lowPassFilter(signal, cutoff, taps = 31) {
    // Generate filter coefficients (windowed sinc)
    const coeffs = new Float32Array(taps);
    const center = (taps - 1) / 2;
    
    for (let i = 0; i < taps; i++) {
        let coeff;
        if (i === center) {
            coeff = 2 * cutoff;
        } else {
            const x = i - center;
            coeff = Math.sin(2 * Math.PI * cutoff * x) / (Math.PI * x);
        }
        
        // Apply Hamming window
        const window = 0.54 - 0.46 * Math.cos(2 * Math.PI * i / (taps - 1));
        coeffs[i] = coeff * window;
    }
    
    // Normalize coefficients
    const sum = coeffs.reduce((a, b) => a + b, 0);
    for (let i = 0; i < taps; i++) {
        coeffs[i] /= sum;
    }
    
    // Apply filter
    const output = new Float32Array(signal.length);
    const delay = Math.floor(taps / 2);
    
    for (let i = 0; i < signal.length; i++) {
        let sum = 0;
        for (let j = 0; j < taps; j++) {
            const sampleIndex = i - delay + j;
            if (sampleIndex >= 0 && sampleIndex < signal.length) {
                sum += signal[sampleIndex] * coeffs[j];
            }
        }
        output[i] = sum;
    }
    
    return output;
}

/**
 * Calculate RMS (Root Mean Square) level
 * @param {Float32Array} signal - Input signal
 * @returns {number} RMS level
 */
export function calculateRMS(signal) {
    let sum = 0;
    for (let i = 0; i < signal.length; i++) {
        sum += signal[i] * signal[i];
    }
    return Math.sqrt(sum / signal.length);
}

/**
 * Normalize signal to given peak level
 * @param {Float32Array} signal - Input signal
 * @param {number} targetPeak - Target peak level
 * @returns {Float32Array} Normalized signal
 */
export function normalize(signal, targetPeak = 1.0) {
    let peak = 0;
    for (let i = 0; i < signal.length; i++) {
        peak = Math.max(peak, Math.abs(signal[i]));
    }
    
    if (peak === 0) {
        return signal.slice();
    }
    
    const gain = targetPeak / peak;
    const output = new Float32Array(signal.length);
    
    for (let i = 0; i < signal.length; i++) {
        output[i] = signal[i] * gain;
    }
    
    return output;
}

export default {
    applyWindow,
    linearToDb,
    dbToLinear,
    calculatePSD,
    exponentialMovingAverage,
    findPeaks,
    calculateSNR,
    applyAGC,
    lowPassFilter,
    calculateRMS,
    normalize
};