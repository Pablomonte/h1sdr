/**
 * High-performance WebGL-based spectrum display
 * Optimized for real-time SDR spectrum visualization
 */

class SpectrumDisplay {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.gl = this.canvas.getContext('webgl') || this.canvas.getContext('experimental-webgl');
        
        if (!this.gl) {
            throw new Error('WebGL not supported');
        }
        
        // Display parameters
        this.width = this.canvas.width;
        this.height = this.canvas.height;
        this.fftSize = 2048;
        this.sampleRate = 2400000; // Default 2.4 MSPS
        this.centerFrequency = 100e6; // Default 100 MHz
        
        // Data buffers
        this.spectrumData = new Float32Array(this.fftSize);
        this.frequencyData = new Float32Array(this.fftSize);
        this.smoothingFactor = 0.3;
        this.previousSpectrum = new Float32Array(this.fftSize);
        
        // Display settings
        this.minPower = -100; // dB
        this.maxPower = -20;  // dB
        this.zoom = 1.0;
        this.panOffset = 0.0;
        
        // WebGL resources
        this.shaderProgram = null;
        this.vertexBuffer = null;
        this.colorBuffer = null;
        this.gridProgram = null;
        this.gridBuffer = null;
        
        // Mouse interaction
        this.mouseX = 0;
        this.mouseY = 0;
        this.isDragging = false;
        this.lastMouseX = 0;
        
        // Performance monitoring
        this.frameCount = 0;
        this.lastTime = performance.now();
        this.fps = 0;
        
        this.initWebGL();
        this.setupEventListeners();
        this.startRenderLoop();
    }
    
    initWebGL() {
        // Enable WebGL extensions
        this.gl.getExtension('OES_standard_derivatives');
        
        // Create shader programs
        this.createSpectrumShaders();
        this.createGridShaders();
        
        // Set up buffers
        this.setupBuffers();
        
        // Configure WebGL state
        this.gl.enable(this.gl.BLEND);
        this.gl.blendFunc(this.gl.SRC_ALPHA, this.gl.ONE_MINUS_SRC_ALPHA);
        this.gl.clearColor(0.0, 0.0, 0.0, 1.0);
        
        console.log('WebGL spectrum display initialized');
    }
    
    createSpectrumShaders() {
        const vertexShaderSource = `
            attribute vec2 a_position;
            attribute float a_power;
            
            uniform vec2 u_resolution;
            uniform float u_minPower;
            uniform float u_maxPower;
            uniform float u_zoom;
            uniform float u_panOffset;
            
            varying float v_power;
            
            void main() {
                // Normalize power to 0-1 range
                v_power = (a_power - u_minPower) / (u_maxPower - u_minPower);
                
                // Apply zoom and pan
                float x = (a_position.x + u_panOffset) * u_zoom;
                float y = v_power;
                
                // Convert to clip space
                vec2 clipSpace = ((vec2(x, y) / u_resolution) * 2.0 - 1.0);
                clipSpace.y *= -1.0; // Flip Y axis
                
                gl_Position = vec4(clipSpace, 0.0, 1.0);
            }
        `;
        
        const fragmentShaderSource = `
            precision mediump float;
            
            varying float v_power;
            
            uniform float u_minPower;
            uniform float u_maxPower;
            
            void main() {
                // Enhanced color mapping with better contrast
                float intensity = clamp(v_power, 0.0, 1.0);
                
                // Apply gamma correction for better visual contrast
                intensity = pow(intensity, 0.7);
                
                // Enhanced rainbow spectrum coloring with better contrast
                vec3 color;
                if (intensity < 0.2) {
                    // Deep blue to bright blue (noise floor)
                    color = mix(vec3(0.0, 0.0, 0.3), vec3(0.0, 0.3, 0.8), intensity * 5.0);
                } else if (intensity < 0.4) {
                    // Blue to cyan (weak signals)
                    color = mix(vec3(0.0, 0.3, 0.8), vec3(0.0, 0.8, 1.0), (intensity - 0.2) * 5.0);
                } else if (intensity < 0.6) {
                    // Cyan to green (medium signals)
                    color = mix(vec3(0.0, 0.8, 1.0), vec3(0.0, 1.0, 0.3), (intensity - 0.4) * 5.0);
                } else if (intensity < 0.8) {
                    // Green to yellow (strong signals)
                    color = mix(vec3(0.0, 1.0, 0.3), vec3(1.0, 1.0, 0.0), (intensity - 0.6) * 5.0);
                } else {
                    // Yellow to red (very strong signals)
                    color = mix(vec3(1.0, 1.0, 0.0), vec3(1.0, 0.2, 0.0), (intensity - 0.8) * 5.0);
                }
                
                // Higher alpha for better visibility
                gl_FragColor = vec4(color, 0.9);
            }
        `;
        
        this.shaderProgram = this.createShaderProgram(vertexShaderSource, fragmentShaderSource);
        
        // Get shader locations
        this.spectrumUniforms = {
            resolution: this.gl.getUniformLocation(this.shaderProgram, 'u_resolution'),
            minPower: this.gl.getUniformLocation(this.shaderProgram, 'u_minPower'),
            maxPower: this.gl.getUniformLocation(this.shaderProgram, 'u_maxPower'),
            zoom: this.gl.getUniformLocation(this.shaderProgram, 'u_zoom'),
            panOffset: this.gl.getUniformLocation(this.shaderProgram, 'u_panOffset')
        };
        
        this.spectrumAttributes = {
            position: this.gl.getAttribLocation(this.shaderProgram, 'a_position'),
            power: this.gl.getAttribLocation(this.shaderProgram, 'a_power')
        };
    }
    
    createGridShaders() {
        const vertexShaderSource = `
            attribute vec2 a_position;
            uniform vec2 u_resolution;
            
            void main() {
                vec2 clipSpace = ((a_position / u_resolution) * 2.0 - 1.0);
                clipSpace.y *= -1.0;
                gl_Position = vec4(clipSpace, 0.0, 1.0);
            }
        `;
        
        const fragmentShaderSource = `
            precision mediump float;
            
            void main() {
                gl_FragColor = vec4(0.3, 0.3, 0.3, 0.5);
            }
        `;
        
        this.gridProgram = this.createShaderProgram(vertexShaderSource, fragmentShaderSource);
        this.gridUniforms = {
            resolution: this.gl.getUniformLocation(this.gridProgram, 'u_resolution')
        };
        this.gridAttributes = {
            position: this.gl.getAttribLocation(this.gridProgram, 'a_position')
        };
    }
    
    createShaderProgram(vertexSource, fragmentSource) {
        const vertexShader = this.compileShader(this.gl.VERTEX_SHADER, vertexSource);
        const fragmentShader = this.compileShader(this.gl.FRAGMENT_SHADER, fragmentSource);
        
        const program = this.gl.createProgram();
        this.gl.attachShader(program, vertexShader);
        this.gl.attachShader(program, fragmentShader);
        this.gl.linkProgram(program);
        
        if (!this.gl.getProgramParameter(program, this.gl.LINK_STATUS)) {
            console.error('Shader program linking failed:', this.gl.getProgramInfoLog(program));
            return null;
        }
        
        return program;
    }
    
    compileShader(type, source) {
        const shader = this.gl.createShader(type);
        this.gl.shaderSource(shader, source);
        this.gl.compileShader(shader);
        
        if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
            console.error('Shader compilation failed:', this.gl.getShaderInfoLog(shader));
            this.gl.deleteShader(shader);
            return null;
        }
        
        return shader;
    }
    
    setupBuffers() {
        // Vertex buffer for spectrum line
        this.vertexBuffer = this.gl.createBuffer();
        this.powerBuffer = this.gl.createBuffer();
        
        // Grid buffer for frequency markers
        this.gridBuffer = this.gl.createBuffer();
        this.updateGridLines();
    }
    
    updateGridLines() {
        const gridLines = [];
        const frequencyStep = this.sampleRate / 10; // 10 major divisions
        
        for (let i = 0; i <= 10; i++) {
            const x = (i / 10) * this.width;
            
            // Vertical lines
            gridLines.push(x, 0, x, this.height);
        }
        
        // Horizontal lines
        const powerStep = (this.maxPower - this.minPower) / 10;
        for (let i = 0; i <= 10; i++) {
            const y = (i / 10) * this.height;
            gridLines.push(0, y, this.width, y);
        }
        
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.gridBuffer);
        this.gl.bufferData(this.gl.ARRAY_BUFFER, new Float32Array(gridLines), this.gl.STATIC_DRAW);
    }
    
    updateSpectrum(spectrumData, frequencyData) {
        if (spectrumData.length !== this.fftSize) {
            console.warn('Spectrum data size mismatch');
            return;
        }
        
        // Apply exponential smoothing
        for (let i = 0; i < this.fftSize; i++) {
            this.spectrumData[i] = this.smoothingFactor * spectrumData[i] + 
                                  (1 - this.smoothingFactor) * this.previousSpectrum[i];
            this.previousSpectrum[i] = this.spectrumData[i];
        }
        
        // Auto-scale power range for better contrast
        this.autoScalePowerRange(this.spectrumData);
        
        this.frequencyData.set(frequencyData);
        this.updateVertexBuffers();
    }
    
    updateVertexBuffers() {
        // Create vertex positions
        const vertices = new Float32Array(this.fftSize * 2);
        const powers = new Float32Array(this.fftSize);
        
        for (let i = 0; i < this.fftSize; i++) {
            // X position (frequency)
            vertices[i * 2] = (i / (this.fftSize - 1)) * this.width;
            // Y position will be calculated in vertex shader based on power
            vertices[i * 2 + 1] = 0;
            
            // Power value
            powers[i] = this.spectrumData[i];
        }
        
        // Update vertex buffer
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.vertexBuffer);
        this.gl.bufferData(this.gl.ARRAY_BUFFER, vertices, this.gl.DYNAMIC_DRAW);
        
        // Update power buffer
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.powerBuffer);
        this.gl.bufferData(this.gl.ARRAY_BUFFER, powers, this.gl.DYNAMIC_DRAW);
    }
    
    render() {
        // Resize canvas if needed
        this.resizeCanvas();
        
        // Clear canvas
        this.gl.viewport(0, 0, this.width, this.height);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);
        
        // Render grid
        this.renderGrid();
        
        // Render spectrum
        this.renderSpectrum();
        
        // Update FPS counter
        this.updateFPS();
    }
    
    renderGrid() {
        this.gl.useProgram(this.gridProgram);
        
        // Set uniforms
        this.gl.uniform2f(this.gridUniforms.resolution, this.width, this.height);
        
        // Bind grid buffer
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.gridBuffer);
        this.gl.enableVertexAttribArray(this.gridAttributes.position);
        this.gl.vertexAttribPointer(this.gridAttributes.position, 2, this.gl.FLOAT, false, 0, 0);
        
        // Draw grid lines
        this.gl.drawArrays(this.gl.LINES, 0, 44); // 22 lines * 2 points each
    }
    
    renderSpectrum() {
        this.gl.useProgram(this.shaderProgram);
        
        // Set uniforms
        this.gl.uniform2f(this.spectrumUniforms.resolution, this.width, this.height);
        this.gl.uniform1f(this.spectrumUniforms.minPower, this.minPower);
        this.gl.uniform1f(this.spectrumUniforms.maxPower, this.maxPower);
        this.gl.uniform1f(this.spectrumUniforms.zoom, this.zoom);
        this.gl.uniform1f(this.spectrumUniforms.panOffset, this.panOffset);
        
        // Bind vertex buffer
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.vertexBuffer);
        this.gl.enableVertexAttribArray(this.spectrumAttributes.position);
        this.gl.vertexAttribPointer(this.spectrumAttributes.position, 2, this.gl.FLOAT, false, 0, 0);
        
        // Bind power buffer
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.powerBuffer);
        this.gl.enableVertexAttribArray(this.spectrumAttributes.power);
        this.gl.vertexAttribPointer(this.spectrumAttributes.power, 1, this.gl.FLOAT, false, 0, 0);
        
        // Draw spectrum as line strip
        this.gl.drawArrays(this.gl.LINE_STRIP, 0, this.fftSize);
    }
    
    resizeCanvas() {
        const rect = this.canvas.getBoundingClientRect();
        const displayWidth = rect.width * window.devicePixelRatio;
        const displayHeight = rect.height * window.devicePixelRatio;
        
        if (this.canvas.width !== displayWidth || this.canvas.height !== displayHeight) {
            this.canvas.width = displayWidth;
            this.canvas.height = displayHeight;
            this.width = displayWidth;
            this.height = displayHeight;
            
            this.updateGridLines();
        }
    }
    
    setupEventListeners() {
        // Mouse events for panning and zooming
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
            
            this.updateCursorInfo();
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
            this.dispatchEvent(new CustomEvent('frequencyClick', {
                detail: { frequency: frequency }
            }));
        });
    }
    
    getFrequencyFromX(x) {
        const normalizedX = x / this.width;
        const frequencyOffset = (normalizedX - 0.5) * this.sampleRate;
        return this.centerFrequency + frequencyOffset;
    }
    
    updateCursorInfo() {
        const rect = this.canvas.getBoundingClientRect();
        const x = this.mouseX - rect.left;
        const y = this.mouseY - rect.top;
        
        const frequency = this.getFrequencyFromX(x);
        const power = this.maxPower - (y / this.height) * (this.maxPower - this.minPower);
        
        // Update cursor info display
        const freqElement = document.getElementById('cursor-frequency');
        const powerElement = document.getElementById('cursor-power');
        
        if (freqElement) {
            freqElement.textContent = `Frequency: ${(frequency / 1e6).toFixed(4)} MHz`;
        }
        if (powerElement) {
            powerElement.textContent = `Power: ${power.toFixed(1)} dB`;
        }
    }
    
    updateFPS() {
        this.frameCount++;
        const currentTime = performance.now();
        
        if (currentTime - this.lastTime >= 1000) {
            this.fps = Math.round((this.frameCount * 1000) / (currentTime - this.lastTime));
            this.frameCount = 0;
            this.lastTime = currentTime;
            
            const fpsElement = document.getElementById('spectrum-fps');
            if (fpsElement) {
                fpsElement.textContent = `FPS: ${this.fps}`;
            }
        }
    }
    
    startRenderLoop() {
        const renderFrame = () => {
            this.render();
            requestAnimationFrame(renderFrame);
        };
        requestAnimationFrame(renderFrame);
    }
    
    // Configuration methods
    setZoom(zoom) {
        this.zoom = Math.max(0.1, Math.min(100, zoom));
    }
    
    resetZoom() {
        this.zoom = 1.0;
        this.panOffset = 0.0;
    }
    
    setPowerRange(minPower, maxPower) {
        this.minPower = minPower;
        this.maxPower = maxPower;
    }
    
    autoScalePowerRange(spectrumData, margin = 5) {
        if (!spectrumData || spectrumData.length === 0) return;
        
        // Calculate min/max from actual spectrum data
        let min = Math.min(...spectrumData);
        let max = Math.max(...spectrumData);
        
        // Apply margin and avoid too small ranges
        const range = max - min;
        if (range < 10) {
            // Expand small ranges
            const center = (max + min) / 2;
            min = center - 15;
            max = center + 15;
        } else {
            min = min - margin;
            max = max + margin;
        }
        
        // Smoothly adjust to avoid rapid changes
        const alpha = 0.1; // Smoothing factor
        this.minPower = this.minPower * (1 - alpha) + min * alpha;
        this.maxPower = this.maxPower * (1 - alpha) + max * alpha;
    }
    
    setFrequencyRange(centerFreq, sampleRate) {
        this.centerFrequency = centerFreq;
        this.sampleRate = sampleRate;
        this._update_frequency_array();
        this.updateGridLines();
    }
    
    _update_frequency_array() {
        // Generate frequency array
        for (let i = 0; i < this.fftSize; i++) {
            const binFreq = (i - this.fftSize / 2) * (this.sampleRate / this.fftSize);
            this.frequencyData[i] = this.centerFrequency + binFreq;
        }
    }
    
    // Event emitter methods
    dispatchEvent(event) {
        this.canvas.dispatchEvent(event);
    }
    
    addEventListener(type, listener) {
        this.canvas.addEventListener(type, listener);
    }
}

// Export for module use
window.SpectrumDisplay = SpectrumDisplay;