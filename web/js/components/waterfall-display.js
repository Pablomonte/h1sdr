/**
 * High-performance waterfall display using Canvas 2D
 * Optimized for real-time spectrum history visualization
 */

class WaterfallDisplay {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        
        // Display parameters
        this.width = this.canvas.width;
        this.height = this.canvas.height;
        this.fftSize = 2048;
        this.sampleRate = 2400000; // Default 2.4 MSPS
        this.centerFrequency = 100e6; // Default 100 MHz
        
        // Waterfall buffer (circular buffer for efficiency)
        this.maxLines = 1000; // Maximum history lines
        this.waterfallData = [];
        this.currentLine = 0;
        
        // Color mapping
        this.colormap = 'jet';
        this.minIntensity = -80; // dB
        this.maxIntensity = -20; // dB
        this.colormapCache = new Map();
        
        // Display settings
        this.zoom = 1.0;
        this.panOffset = 0.0;
        this.autoScroll = true;
        this.scrollSpeed = 1; // pixels per frame
        
        // Performance optimization
        this.imageData = null;
        this.pixelBuffer = null;
        this.updateRate = 30; // Max updates per second
        this.lastUpdate = 0;
        
        // Mouse interaction
        this.mouseX = 0;
        this.mouseY = 0;
        this.isDragging = false;
        this.lastMouseX = 0;
        
        // Initialize
        this.initializeBuffers();
        this.generateColormap();
        this.setupEventListeners();
        this.startRenderLoop();
        
        console.log('Waterfall display initialized');
    }
    
    initializeBuffers() {
        // Resize canvas to match display size
        this.resizeCanvas();
        
        // Initialize image data buffer
        this.imageData = this.ctx.createImageData(this.width, this.height);
        this.pixelBuffer = new Uint32Array(this.imageData.data.buffer);
        
        // Initialize waterfall data buffer
        this.waterfallData = new Array(this.maxLines);
        for (let i = 0; i < this.maxLines; i++) {
            this.waterfallData[i] = new Float32Array(this.fftSize);
        }
    }
    
    generateColormap() {
        const cache = [];
        const steps = 256;
        
        for (let i = 0; i < steps; i++) {
            const intensity = i / (steps - 1);
            const color = this.getColormapColor(intensity, this.colormap);
            
            // Convert to ABGR format for Uint32Array
            const abgr = (255 << 24) | // Alpha
                        (color.b << 16) | // Blue
                        (color.g << 8) |  // Green
                        color.r;          // Red
            
            cache.push(abgr);
        }
        
        this.colormapCache.set(this.colormap, cache);
    }
    
    getColormapColor(intensity, colormap) {
        intensity = Math.max(0, Math.min(1, intensity));
        
        // Apply gamma correction for better visual contrast
        intensity = Math.pow(intensity, 0.7);
        
        switch (colormap) {
            case 'jet':
                return this.jetColormap(intensity);
            case 'viridis':
                return this.viridisColormap(intensity);
            case 'plasma':
                return this.plasmaColormap(intensity);
            case 'cool':
                return this.coolColormap(intensity);
            case 'hot':
                return this.hotColormap(intensity);
            default:
                return { r: 255, g: 255, b: 255 };
        }
    }
    
    jetColormap(x) {
        const r = Math.max(0, Math.min(255, 255 * (1.5 - Math.abs(4 * x - 3))));
        const g = Math.max(0, Math.min(255, 255 * (1.5 - Math.abs(4 * x - 2))));
        const b = Math.max(0, Math.min(255, 255 * (1.5 - Math.abs(4 * x - 1))));
        return { r: Math.floor(r), g: Math.floor(g), b: Math.floor(b) };
    }
    
    viridisColormap(x) {
        // Simplified viridis approximation
        const r = Math.floor(255 * (0.267 + 0.529 * x + 0.204 * x * x));
        const g = Math.floor(255 * (0.004 + 0.729 * x + 0.267 * x * x));
        const b = Math.floor(255 * (0.329 + 0.567 * x - 0.896 * x * x));
        return { r: Math.max(0, Math.min(255, r)), 
                g: Math.max(0, Math.min(255, g)), 
                b: Math.max(0, Math.min(255, b)) };
    }
    
    plasmaColormap(x) {
        // Simplified plasma approximation
        const r = Math.floor(255 * (0.050 + 0.950 * x));
        const g = Math.floor(255 * (0.030 + 0.570 * x + 0.400 * x * x));
        const b = Math.floor(255 * (0.525 + 0.580 * x - 1.105 * x * x));
        return { r: Math.max(0, Math.min(255, r)), 
                g: Math.max(0, Math.min(255, g)), 
                b: Math.max(0, Math.min(255, b)) };
    }
    
    coolColormap(x) {
        const r = Math.floor(255 * x);
        const g = Math.floor(255 * (1 - x));
        const b = 255;
        return { r, g, b };
    }
    
    hotColormap(x) {
        let r, g, b;
        if (x < 0.4) {
            r = Math.floor(255 * (x / 0.4));
            g = 0;
            b = 0;
        } else if (x < 0.8) {
            r = 255;
            g = Math.floor(255 * ((x - 0.4) / 0.4));
            b = 0;
        } else {
            r = 255;
            g = 255;
            b = Math.floor(255 * ((x - 0.8) / 0.2));
        }
        return { r, g, b };
    }
    
    addSpectrumLine(spectrumData) {
        if (spectrumData.length !== this.fftSize) {
            console.warn('Spectrum data size mismatch');
            return;
        }
        
        // Store spectrum data in circular buffer
        this.waterfallData[this.currentLine].set(spectrumData);
        this.currentLine = (this.currentLine + 1) % this.maxLines;
        
        // Trigger render update
        this.needsUpdate = true;
    }
    
    render() {
        const now = performance.now();
        
        // Throttle updates for performance
        if (now - this.lastUpdate < 1000 / this.updateRate) {
            return;
        }
        
        this.lastUpdate = now;
        
        // Resize canvas if needed
        this.resizeCanvas();
        
        // Clear canvas
        this.ctx.fillStyle = '#000000';
        this.ctx.fillRect(0, 0, this.width, this.height);
        
        // Render waterfall
        this.renderWaterfall();
        
        // Render frequency scale
        this.renderFrequencyScale();
    }
    
    renderWaterfall() {
        if (!this.colormapCache.has(this.colormap)) {
            this.generateColormap();
        }
        
        const colorCache = this.colormapCache.get(this.colormap);
        const visibleLines = Math.min(this.height, this.maxLines);
        
        // Calculate zoom and pan parameters
        const startBin = Math.floor((this.panOffset + this.fftSize / 2 - this.fftSize / (2 * this.zoom)));
        const endBin = Math.ceil(startBin + this.fftSize / this.zoom);
        const binStart = Math.max(0, startBin);
        const binEnd = Math.min(this.fftSize, endBin);
        
        // Render each visible line
        for (let y = 0; y < visibleLines; y++) {
            const lineIndex = (this.currentLine - y - 1 + this.maxLines) % this.maxLines;
            const spectrumLine = this.waterfallData[lineIndex];
            
            if (!spectrumLine || spectrumLine.every(val => val === 0)) {
                continue; // Skip empty lines
            }
            
            // Render spectrum line
            for (let x = 0; x < this.width; x++) {
                const binIndex = Math.floor(binStart + (x / this.width) * (binEnd - binStart));
                
                if (binIndex >= 0 && binIndex < this.fftSize) {
                    const power = spectrumLine[binIndex];
                    const normalizedPower = (power - this.minIntensity) / (this.maxIntensity - this.minIntensity);
                    const colorIndex = Math.floor(Math.max(0, Math.min(255, normalizedPower * 255)));
                    
                    const pixelIndex = y * this.width + x;
                    this.pixelBuffer[pixelIndex] = colorCache[colorIndex];
                }
            }
        }
        
        // Update canvas with pixel data
        this.ctx.putImageData(this.imageData, 0, 0);
    }
    
    renderFrequencyScale() {
        const ctx = this.ctx;
        ctx.save();
        
        // Set text style
        ctx.fillStyle = '#ffffff';
        ctx.font = '12px monospace';
        ctx.textAlign = 'center';
        
        // Calculate frequency step
        const frequencySpan = this.sampleRate / this.zoom;
        const startFreq = this.centerFrequency - frequencySpan / 2 + this.panOffset;
        const freqStep = frequencySpan / 10; // 10 divisions
        
        // Draw frequency markers
        for (let i = 0; i <= 10; i++) {
            const frequency = startFreq + i * freqStep;
            const x = (i / 10) * this.width;
            
            // Draw tick mark
            ctx.strokeStyle = '#ffffff';
            ctx.beginPath();
            ctx.moveTo(x, this.height - 15);
            ctx.lineTo(x, this.height - 5);
            ctx.stroke();
            
            // Draw frequency label
            const freqMHz = frequency / 1e6;
            const label = freqMHz >= 1000 ? 
                         `${(freqMHz / 1000).toFixed(2)}G` : 
                         `${freqMHz.toFixed(2)}M`;
            
            ctx.fillText(label, x, this.height - 20);
        }
        
        ctx.restore();
    }
    
    resizeCanvas() {
        const rect = this.canvas.getBoundingClientRect();
        const displayWidth = Math.floor(rect.width * window.devicePixelRatio);
        const displayHeight = Math.floor(rect.height * window.devicePixelRatio);
        
        if (this.canvas.width !== displayWidth || this.canvas.height !== displayHeight) {
            this.canvas.width = displayWidth;
            this.canvas.height = displayHeight;
            this.width = displayWidth;
            this.height = displayHeight;
            
            // Reinitialize buffers
            this.imageData = this.ctx.createImageData(this.width, this.height);
            this.pixelBuffer = new Uint32Array(this.imageData.data.buffer);
            
            // Reset transform
            this.ctx.resetTransform();
            this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        }
    }
    
    setupEventListeners() {
        // Mouse events for panning
        this.canvas.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.lastMouseX = e.clientX;
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
            
            if (this.isDragging) {
                const deltaX = e.clientX - this.lastMouseX;
                this.panOffset += deltaX * (this.sampleRate / this.width) / this.zoom;
                this.lastMouseX = e.clientX;
            }
        });
        
        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
        });
        
        // Zoom with mouse wheel
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
            this.zoom = Math.max(0.1, Math.min(100, this.zoom * zoomFactor));
        });
        
        // Click to tune
        this.canvas.addEventListener('click', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const frequency = this.getFrequencyFromX(x);
            
            // Emit frequency change event
            this.canvas.dispatchEvent(new CustomEvent('frequencyClick', {
                detail: { frequency: frequency }
            }));
        });
    }
    
    getFrequencyFromX(x) {
        const normalizedX = x / this.width;
        const frequencySpan = this.sampleRate / this.zoom;
        const startFreq = this.centerFrequency - frequencySpan / 2 + this.panOffset;
        return startFreq + normalizedX * frequencySpan;
    }
    
    startRenderLoop() {
        const renderFrame = () => {
            this.render();
            requestAnimationFrame(renderFrame);
        };
        requestAnimationFrame(renderFrame);
    }
    
    // Configuration methods
    setColormap(colormap) {
        if (['jet', 'viridis', 'plasma', 'cool', 'hot'].includes(colormap)) {
            this.colormap = colormap;
            this.generateColormap();
        }
    }
    
    setIntensityRange(minIntensity, maxIntensity) {
        this.minIntensity = minIntensity;
        this.maxIntensity = maxIntensity;
    }
    
    setZoom(zoom) {
        this.zoom = Math.max(0.1, Math.min(100, zoom));
    }
    
    resetZoom() {
        this.zoom = 1.0;
        this.panOffset = 0.0;
    }
    
    setFrequencyRange(centerFreq, sampleRate) {
        this.centerFrequency = centerFreq;
        this.sampleRate = sampleRate;
    }
    
    autoScale() {
        // Enhanced auto-scale with better contrast
        const recentLines = Math.min(50, this.maxLines);
        let minPower = Infinity;
        let maxPower = -Infinity;
        const powerSamples = [];
        
        for (let i = 0; i < recentLines; i++) {
            const lineIndex = (this.currentLine - i - 1 + this.maxLines) % this.maxLines;
            const line = this.waterfallData[lineIndex];
            
            if (line && !line.every(val => val === 0)) {
                for (let j = 0; j < this.fftSize; j++) {
                    powerSamples.push(line[j]);
                    minPower = Math.min(minPower, line[j]);
                    maxPower = Math.max(maxPower, line[j]);
                }
            }
        }
        
        if (minPower !== Infinity && maxPower !== -Infinity) {
            // Use percentile-based scaling for better contrast
            powerSamples.sort((a, b) => a - b);
            const len = powerSamples.length;
            
            // Use 5th and 95th percentiles for better dynamic range
            const p5 = powerSamples[Math.floor(len * 0.05)];
            const p95 = powerSamples[Math.floor(len * 0.95)];
            
            // Smoothly adjust to avoid rapid changes
            const alpha = 0.1;
            this.minIntensity = this.minIntensity * (1 - alpha) + p5 * alpha;
            this.maxIntensity = this.maxIntensity * (1 - alpha) + p95 * alpha;
        }
    }
    
    clearHistory() {
        for (let i = 0; i < this.maxLines; i++) {
            this.waterfallData[i].fill(0);
        }
        this.currentLine = 0;
    }
    
    // Event emitter methods
    addEventListener(type, listener) {
        this.canvas.addEventListener(type, listener);
    }
}

// Export for module use
window.WaterfallDisplay = WaterfallDisplay;