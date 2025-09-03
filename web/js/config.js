/**
 * H1SDR WebSDR Configuration
 * Global configuration settings for the web interface
 */

export const CONFIG = {
    // API Configuration
    API_BASE_URL: '',  // Empty for same-origin requests
    
    // WebSocket Configuration
    WEBSOCKET_BASE_URL: `ws://${window.location.host}`,
    WEBSOCKET_RECONNECT_INTERVAL: 3000, // ms
    WEBSOCKET_MAX_RECONNECT_ATTEMPTS: 10,
    
    // Display Configuration
    SPECTRUM_UPDATE_RATE: 20, // FPS
    WATERFALL_HEIGHT: 400, // pixels
    WATERFALL_HISTORY_SIZE: 1000, // lines
    
    // Audio Configuration
    AUDIO_SAMPLE_RATE: 48000, // Hz
    AUDIO_BUFFER_SIZE: 4096, // samples
    AUDIO_MAX_LATENCY: 100, // ms
    
    // DSP Configuration
    DEFAULT_FFT_SIZE: 2048,
    DEFAULT_WINDOW_FUNCTION: 'hann',
    SPECTRUM_AVERAGING_FACTOR: 0.1,
    
    // Band Presets
    DEFAULT_BAND: 'fm_broadcast',
    CUSTOM_BAND_KEY: 'custom',
    
    // UI Configuration
    THEME: 'dark', // 'dark', 'light', 'high-contrast', 'solarized'
    AUTO_SAVE_SETTINGS: true,
    SETTINGS_STORAGE_KEY: 'h1sdr_settings',
    
    // Performance Configuration
    CANVAS_HIGH_DPI: true,
    USE_WEBGL_ACCELERATION: true,
    BATCH_UI_UPDATES: true,
    
    // Development Configuration
    DEBUG_MODE: false,
    LOG_LEVEL: 'info', // 'debug', 'info', 'warn', 'error'
    MOCK_DATA: false,
};

// Frequency formatting options
export const FREQUENCY_FORMAT = {
    DISPLAY_PRECISION: 3, // decimal places for MHz
    USE_SI_PREFIXES: true,
    SHOW_UNITS: true,
};

// Color schemes for spectrum and waterfall
export const COLOR_SCHEMES = {
    spectrum: {
        default: '#00ff00',
        peak: '#ffff00',
        average: '#ff8800',
        background: '#000000',
    },
    waterfall: {
        jet: ['#000080', '#0000ff', '#00ffff', '#ffff00', '#ff8000', '#ff0000'],
        viridis: ['#440154', '#482777', '#3f4a8a', '#31678e', '#26838f', '#1f9d8a', '#6cce5a', '#b6de2b', '#fee825'],
        plasma: ['#0c0786', '#40039c', '#6a00a7', '#8f0da4', '#b12a90', '#cc4778', '#e16462', '#f2844b', '#fca636', '#fcce25'],
        grayscale: ['#000000', '#404040', '#808080', '#c0c0c0', '#ffffff'],
    }
};

// Default demodulation settings
export const DEMOD_DEFAULTS = {
    AM: {
        bandwidth: 6000,
        agc_attack: 0.1,
        agc_decay: 0.001,
    },
    FM: {
        bandwidth: 15000,
        deviation: 5000,
        de_emphasis: 75e-6,
    },
    SSB: {
        bandwidth: 2400,
        filter_shape: 0.1,
        agc_attack: 0.01,
        agc_decay: 0.0001,
    },
    CW: {
        bandwidth: 500,
        tone_frequency: 600,
        wpm: 20,
    },
    SPECTRUM: {
        bandwidth: 2400000,
        integration_time: 1,
    }
};

// Hardware-specific settings
export const HARDWARE = {
    RTL_SDR: {
        min_frequency: 24e6,
        max_frequency: 1766e6,
        default_sample_rate: 2.4e6,
        supported_sample_rates: [
            250000, 1024000, 1536000, 1792000, 1920000, 2048000, 2160000, 2400000, 2560000, 2880000, 3200000
        ],
        default_gain: 40,
        gain_range: [0, 49.6],
        ppm_range: [-50, 50],
    }
};

// Validation functions
export function validateFrequency(freq) {
    const f = parseFloat(freq);
    return f >= HARDWARE.RTL_SDR.min_frequency && f <= HARDWARE.RTL_SDR.max_frequency;
}

export function validateGain(gain) {
    const g = parseFloat(gain);
    return g >= HARDWARE.RTL_SDR.gain_range[0] && g <= HARDWARE.RTL_SDR.gain_range[1];
}

export function validateSampleRate(rate) {
    const r = parseInt(rate);
    return HARDWARE.RTL_SDR.supported_sample_rates.includes(r);
}

// Local storage helpers
export function saveSettings(settings) {
    if (CONFIG.AUTO_SAVE_SETTINGS) {
        try {
            localStorage.setItem(CONFIG.SETTINGS_STORAGE_KEY, JSON.stringify(settings));
        } catch (e) {
            console.warn('Failed to save settings to localStorage:', e);
        }
    }
}

export function loadSettings() {
    try {
        const saved = localStorage.getItem(CONFIG.SETTINGS_STORAGE_KEY);
        return saved ? JSON.parse(saved) : {};
    } catch (e) {
        console.warn('Failed to load settings from localStorage:', e);
        return {};
    }
}

// Logging utility
export function log(level, message, ...args) {
    if (!CONFIG.DEBUG_MODE && level === 'debug') return;
    
    const levels = ['debug', 'info', 'warn', 'error'];
    const currentLevel = levels.indexOf(CONFIG.LOG_LEVEL);
    const messageLevel = levels.indexOf(level);
    
    if (messageLevel >= currentLevel) {
        console[level](`[H1SDR] ${message}`, ...args);
    }
}

export default CONFIG;