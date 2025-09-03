/**
 * Performance Utilities
 * Tools for monitoring and optimizing performance
 */

import { CONFIG, log } from '../config.js';

/**
 * Performance monitor class
 */
export class PerformanceMonitor {
    constructor() {
        this.metrics = new Map();
        this.enabled = CONFIG.DEBUG_MODE;
    }
    
    /**
     * Start timing a operation
     * @param {string} name - Operation name
     */
    start(name) {
        if (!this.enabled) return;
        
        this.metrics.set(name, {
            startTime: performance.now(),
            count: (this.metrics.get(name)?.count || 0) + 1
        });
    }
    
    /**
     * End timing an operation
     * @param {string} name - Operation name
     * @returns {number} Duration in milliseconds
     */
    end(name) {
        if (!this.enabled) return 0;
        
        const metric = this.metrics.get(name);
        if (!metric) {
            log('warn', `Performance metric '${name}' was not started`);
            return 0;
        }
        
        const duration = performance.now() - metric.startTime;
        metric.totalTime = (metric.totalTime || 0) + duration;
        metric.lastTime = duration;
        metric.avgTime = metric.totalTime / metric.count;
        
        return duration;
    }
    
    /**
     * Get performance statistics
     * @param {string} name - Operation name
     * @returns {object} Performance stats
     */
    getStats(name) {
        const metric = this.metrics.get(name);
        if (!metric) return null;
        
        return {
            count: metric.count,
            lastTime: metric.lastTime,
            avgTime: metric.avgTime,
            totalTime: metric.totalTime
        };
    }
    
    /**
     * Get all performance statistics
     * @returns {object} All performance stats
     */
    getAllStats() {
        const stats = {};
        for (const [name, metric] of this.metrics) {
            stats[name] = {
                count: metric.count,
                lastTime: metric.lastTime,
                avgTime: metric.avgTime,
                totalTime: metric.totalTime
            };
        }
        return stats;
    }
    
    /**
     * Clear all metrics
     */
    clear() {
        this.metrics.clear();
    }
    
    /**
     * Log performance summary
     */
    logSummary() {
        if (!this.enabled) return;
        
        log('info', 'Performance Summary:');
        for (const [name, stats] of Object.entries(this.getAllStats())) {
            log('info', `  ${name}: avg=${stats.avgTime.toFixed(2)}ms, count=${stats.count}, total=${stats.totalTime.toFixed(2)}ms`);
        }
    }
}

// Global performance monitor instance
export const perfmon = new PerformanceMonitor();

/**
 * Throttle function calls
 * @param {Function} func - Function to throttle
 * @param {number} limit - Minimum time between calls (ms)
 * @returns {Function} Throttled function
 */
export function throttle(func, limit) {
    let lastCall = 0;
    return function(...args) {
        const now = Date.now();
        if (now - lastCall >= limit) {
            lastCall = now;
            return func.apply(this, args);
        }
    };
}

/**
 * Debounce function calls
 * @param {Function} func - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

/**
 * Request animation frame with fallback
 * @param {Function} callback - Callback function
 * @returns {number} Request ID
 */
export function requestAnimFrame(callback) {
    return window.requestAnimationFrame || 
           window.webkitRequestAnimationFrame || 
           window.mozRequestAnimationFrame || 
           function(callback) { 
               return setTimeout(callback, 1000 / 60); 
           };
}

/**
 * Cancel animation frame with fallback
 * @param {number} id - Request ID
 */
export function cancelAnimFrame(id) {
    const cancel = window.cancelAnimationFrame || 
                   window.webkitCancelAnimationFrame || 
                   window.mozCancelAnimationFrame || 
                   clearTimeout;
    cancel(id);
}

/**
 * Batch UI updates to avoid layout thrashing
 */
export class UIBatchUpdater {
    constructor() {
        this.updates = [];
        this.scheduled = false;
    }
    
    /**
     * Schedule a UI update
     * @param {Function} updateFunc - Update function
     */
    schedule(updateFunc) {
        this.updates.push(updateFunc);
        
        if (!this.scheduled) {
            this.scheduled = true;
            requestAnimationFrame(() => {
                this.flush();
            });
        }
    }
    
    /**
     * Execute all scheduled updates
     */
    flush() {
        perfmon.start('ui-batch-update');
        
        while (this.updates.length > 0) {
            const update = this.updates.shift();
            try {
                update();
            } catch (error) {
                log('error', 'Error in batched UI update:', error);
            }
        }
        
        this.scheduled = false;
        perfmon.end('ui-batch-update');
    }
}

// Global UI batch updater
export const uiBatcher = new UIBatchUpdater();

/**
 * Memory usage monitor
 */
export class MemoryMonitor {
    constructor() {
        this.samples = [];
        this.maxSamples = 100;
        this.enabled = CONFIG.DEBUG_MODE && 'memory' in performance;
    }
    
    /**
     * Take a memory sample
     */
    sample() {
        if (!this.enabled) return;
        
        const memory = performance.memory;
        const sample = {
            timestamp: Date.now(),
            usedJSHeapSize: memory.usedJSHeapSize,
            totalJSHeapSize: memory.totalJSHeapSize,
            jsHeapSizeLimit: memory.jsHeapSizeLimit
        };
        
        this.samples.push(sample);
        
        // Keep only recent samples
        if (this.samples.length > this.maxSamples) {
            this.samples.shift();
        }
        
        // Log warning if memory usage is high
        const usagePercent = memory.usedJSHeapSize / memory.jsHeapSizeLimit;
        if (usagePercent > 0.8) {
            log('warn', `High memory usage: ${(usagePercent * 100).toFixed(1)}%`);
        }
    }
    
    /**
     * Get current memory usage
     * @returns {object} Memory usage info
     */
    getCurrentUsage() {
        if (!this.enabled) return null;
        
        const memory = performance.memory;
        return {
            usedMB: Math.round(memory.usedJSHeapSize / 1024 / 1024),
            totalMB: Math.round(memory.totalJSHeapSize / 1024 / 1024),
            limitMB: Math.round(memory.jsHeapSizeLimit / 1024 / 1024),
            usagePercent: (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100
        };
    }
    
    /**
     * Get memory usage trend
     * @returns {string} 'increasing', 'decreasing', 'stable'
     */
    getTrend() {
        if (this.samples.length < 5) return 'unknown';
        
        const recent = this.samples.slice(-5);
        const first = recent[0].usedJSHeapSize;
        const last = recent[recent.length - 1].usedJSHeapSize;
        const change = (last - first) / first;
        
        if (change > 0.05) return 'increasing';
        if (change < -0.05) return 'decreasing';
        return 'stable';
    }
}

// Global memory monitor
export const memoryMonitor = new MemoryMonitor();

/**
 * FPS counter
 */
export class FPSCounter {
    constructor() {
        this.frames = [];
        this.maxSamples = 60;
        this.lastFrame = performance.now();
    }
    
    /**
     * Update frame counter
     */
    update() {
        const now = performance.now();
        const delta = now - this.lastFrame;
        this.lastFrame = now;
        
        this.frames.push(delta);
        
        if (this.frames.length > this.maxSamples) {
            this.frames.shift();
        }
    }
    
    /**
     * Get current FPS
     * @returns {number} Current FPS
     */
    getFPS() {
        if (this.frames.length === 0) return 0;
        
        const avgDelta = this.frames.reduce((a, b) => a + b) / this.frames.length;
        return Math.round(1000 / avgDelta);
    }
    
    /**
     * Get frame time statistics
     * @returns {object} Frame time stats
     */
    getStats() {
        if (this.frames.length === 0) return null;
        
        const sorted = this.frames.slice().sort((a, b) => a - b);
        
        return {
            fps: this.getFPS(),
            avgFrameTime: this.frames.reduce((a, b) => a + b) / this.frames.length,
            minFrameTime: sorted[0],
            maxFrameTime: sorted[sorted.length - 1],
            medianFrameTime: sorted[Math.floor(sorted.length / 2)]
        };
    }
}

/**
 * Check if browser supports WebGL
 * @returns {boolean} WebGL support status
 */
export function hasWebGLSupport() {
    try {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        return context instanceof WebGLRenderingContext;
    } catch (e) {
        return false;
    }
}

/**
 * Check if device is mobile
 * @returns {boolean} Mobile device status
 */
export function isMobileDevice() {
    return /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

/**
 * Get device performance tier (rough estimate)
 * @returns {string} 'high', 'medium', 'low'
 */
export function getPerformanceTier() {
    // This is a simplified heuristic
    const cores = navigator.hardwareConcurrency || 1;
    const memory = navigator.deviceMemory || 1;
    const isMobile = isMobileDevice();
    
    if (isMobile) {
        if (memory >= 4 && cores >= 4) return 'medium';
        return 'low';
    } else {
        if (memory >= 8 && cores >= 8) return 'high';
        if (memory >= 4 && cores >= 4) return 'medium';
        return 'low';
    }
}

/**
 * Auto-tune settings based on performance
 * @returns {object} Recommended settings
 */
export function getPerformanceSettings() {
    const tier = getPerformanceTier();
    const hasWebGL = hasWebGLSupport();
    
    switch (tier) {
        case 'high':
            return {
                fftSize: 2048,
                spectrumFPS: 30,
                waterfallHeight: 600,
                useWebGL: hasWebGL,
                enableSmoothing: true,
                audioBufferSize: 2048
            };
            
        case 'medium':
            return {
                fftSize: 1024,
                spectrumFPS: 20,
                waterfallHeight: 400,
                useWebGL: hasWebGL,
                enableSmoothing: true,
                audioBufferSize: 4096
            };
            
        case 'low':
        default:
            return {
                fftSize: 512,
                spectrumFPS: 10,
                waterfallHeight: 200,
                useWebGL: false,
                enableSmoothing: false,
                audioBufferSize: 8192
            };
    }
}

export default {
    PerformanceMonitor,
    perfmon,
    throttle,
    debounce,
    requestAnimFrame,
    cancelAnimFrame,
    UIBatchUpdater,
    uiBatcher,
    MemoryMonitor,
    memoryMonitor,
    FPSCounter,
    hasWebGLSupport,
    isMobileDevice,
    getPerformanceTier,
    getPerformanceSettings
};