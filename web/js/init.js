/**
 * Simple initialization script to get the interface working
 */

console.log('H1SDR WebSDR - Starting initialization...');

// Global notification function
function showNotification(message, type = 'info') {
    // Simple notification system
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        color: white;
        border-radius: 4px;
        font-family: Arial, sans-serif;
        z-index: 1000;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Fade in
    setTimeout(() => notification.style.opacity = '1', 10);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            if (notification.parentNode) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// Make it globally accessible
window.showNotification = showNotification;

// Simple function to hide loading overlay
function hideLoadingOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.opacity = '0';
        setTimeout(() => {
            overlay.style.display = 'none';
        }, 500);
        console.log('Loading overlay hidden');
    }
}

// Simple function to show error
function showError(message) {
    const errorModal = document.getElementById('error-modal');
    const errorMessage = document.getElementById('error-message');
    
    if (errorModal && errorMessage) {
        errorMessage.textContent = message;
        errorModal.classList.remove('hidden');
    } else {
        alert(message); // Fallback
    }
}

// Basic initialization
document.addEventListener('DOMContentLoaded', async () => {
    console.log('DOM loaded - initializing H1SDR...');
    
    try {
        // Wait a moment to simulate loading
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Initialize basic components
        await initializeBasicComponents();
        
        // Hide loading overlay
        hideLoadingOverlay();
        
        // Initialize spectrum visualization
        initializeSpectrumVisualization();
        
        // Initialize frequency and modulation controls
        initializeFrequencyControls();
        initializeGainControls();
        initializeBandwidthControls();
        initializeDemodulationControls();
        initializeBandPresets();
        
        // Initialize spectrum and waterfall controls
        initializeSpectrumControls();
        // initializeWaterfallControls(); // DISABLED for performance
        
        // Initialize audio controls
        initializeAudioControls();
        
        // Initialize resizable layout
        initializeResizableLayout();
        
        // Check initial SDR status
        try {
            const statusResponse = await fetch('/api/sdr/status');
            if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                if (statusData.success && statusData.data) {
                    updateSDRStatus(statusData.data.running, statusData.data);
                    
                    // Update button states
                    const startBtn = document.getElementById('sdr-start');
                    const stopBtn = document.getElementById('sdr-stop');
                    if (startBtn && stopBtn) {
                        startBtn.disabled = statusData.data.running;
                        stopBtn.disabled = !statusData.data.running;
                    }
                }
            }
        } catch (error) {
            console.warn('Could not check initial SDR status:', error);
        }
        
        console.log('✅ H1SDR WebSDR initialized successfully');
        
    } catch (error) {
        console.error('Initialization failed:', error);
        showError('Failed to initialize H1SDR WebSDR: ' + error.message);
        hideLoadingOverlay();
    }
});

async function initializeBasicComponents() {
    console.log('🚀 Initializing basic components...');
    
    // Setup basic UI handlers
    setupBasicUIHandlers();
    
    // Test API connection
    const apiOk = await testAPIConnection();
    if (!apiOk) {
        throw new Error('API connection failed - check server status');
    }
    
    console.log('✅ Basic components initialized');
}


function setupBasicUIHandlers() {
    // Handle modal close buttons
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-close') || e.target.id === 'error-ok') {
            const modal = e.target.closest('.modal');
            if (modal) {
                modal.classList.add('hidden');
            }
        }
    });
    
    // Handle SDR start/stop buttons
    const sdrStartBtn = document.getElementById('sdr-start');
    const sdrStopBtn = document.getElementById('sdr-stop');
    
    if (sdrStartBtn) {
        sdrStartBtn.addEventListener('click', async () => {
            try {
                sdrStartBtn.disabled = true;
                sdrStartBtn.textContent = 'Starting...';
                
                const response = await fetch('/api/sdr/start', { method: 'POST' });
                const result = await response.json();
                
                if (result.success) {
                    sdrStartBtn.disabled = true;
                    sdrStopBtn.disabled = false;
                    sdrStartBtn.textContent = 'Start SDR';
                    console.log('SDR started successfully:', result.data);
                    updateSDRStatus(true, result.data);
                } else {
                    const errorMsg = result.message || result.detail || 'Failed to start SDR';
                    if (errorMsg.includes('already running')) {
                        // SDR is already running, sync UI
                        console.log('SDR already running, syncing UI state');
                        const statusResponse = await fetch('/api/sdr/status');
                        const statusResult = await statusResponse.json();
                        if (statusResult.success) {
                            updateSDRStatus(true, statusResult.data);
                            sdrStartBtn.disabled = true;
                            sdrStopBtn.disabled = false;
                            return; // Exit without error
                        }
                    }
                    throw new Error(errorMsg);
                }
                
            } catch (error) {
                console.error('SDR start error:', error);
                showError('Failed to start SDR: ' + error.message);
                sdrStartBtn.textContent = 'Start SDR';
            } finally {
                sdrStartBtn.disabled = false;
            }
        });
        
        // Check SDR status and sync UI
        setTimeout(async () => {
            console.log('Checking SDR status...');
            try {
                const response = await fetch('/api/sdr/status');
                const result = await response.json();
                
                if (result.success && result.data.running) {
                    console.log('SDR already running, syncing UI...');
                    updateSDRStatus(true, result.data);
                    sdrStartBtn.disabled = true;
                    sdrStopBtn.disabled = false;
                } else {
                    console.log('SDR stopped, auto-starting...');
                    sdrStartBtn.click();
                }
            } catch (error) {
                console.error('Status check failed, trying auto-start:', error);
                sdrStartBtn.click();
            }
        }, 1500);
    }
    
    if (sdrStopBtn) {
        sdrStopBtn.addEventListener('click', async () => {
            try {
                sdrStopBtn.disabled = true;
                sdrStopBtn.textContent = 'Stopping...';
                
                const response = await fetch('/api/sdr/stop', { method: 'POST' });
                const result = await response.json();
                
                if (result.success) {
                    sdrStartBtn.disabled = false;
                    sdrStopBtn.disabled = true;
                    sdrStopBtn.textContent = 'Stop SDR';
                    console.log('SDR stopped successfully');
                    updateSDRStatus(false);
                } else {
                    throw new Error(result.message || 'Failed to stop SDR');
                }
                
            } catch (error) {
                console.error('SDR stop error:', error);
                showError('Failed to stop SDR: ' + error.message);
                sdrStopBtn.textContent = 'Stop SDR';
            } finally {
                sdrStopBtn.disabled = false;
            }
        });
    }
    
    console.log('Basic UI handlers setup');
}

function updateSDRStatus(isRunning, sdrData = null) {
    // Update status indicators
    const statusDots = document.querySelectorAll('.status-dot');
    statusDots.forEach(dot => {
        if (isRunning) {
            dot.classList.add('connected');
            dot.classList.remove('error');
        } else {
            dot.classList.remove('connected');
        }
    });
    
    // Update status text
    const sdrStatus = document.getElementById('sdr-status');
    if (sdrStatus) {
        sdrStatus.textContent = isRunning ? 'RTL-SDR: Online' : 'RTL-SDR: Offline';
        sdrStatus.className = isRunning ? 'status-indicator online' : 'status-indicator offline';
    }
    
    // Also update any other status texts
    const statusTexts = document.querySelectorAll('#sdr-status-text, .status-indicator span');
    statusTexts.forEach(text => {
        if (text.id !== 'sdr-status' && (text.textContent.includes('SDR') || text.textContent.includes('Stopped') || text.textContent.includes('Running'))) {
            text.textContent = isRunning ? 'Running' : 'Stopped';
        }
    });
    
    // Update frequency display if SDR data available
    if (isRunning && sdrData) {
        // Update global frequency variable
        if (sdrData.center_frequency) {
            window.currentFrequency = sdrData.center_frequency;
            
            // Update frequency control display
            if (window.updateFrequencyDisplay) {
                window.updateFrequencyDisplay(sdrData.center_frequency / 1e6);
            }
        }
        
        const freqDisplays = document.querySelectorAll('#current-freq, .frequency-display');
        freqDisplays.forEach(display => {
            const freqMHz = (sdrData.center_frequency / 1e6).toFixed(4);
            display.textContent = `${freqMHz} MHz`;
        });
        
        // Update other parameters
        if (sdrData.gain !== undefined) {
            const gainDisplays = document.querySelectorAll('.gain-display, #gain-display');
            gainDisplays.forEach(display => {
                display.textContent = `${sdrData.gain}`;
            });
            
            // Update gain slider
            const gainSlider = document.getElementById('gain-slider');
            if (gainSlider) {
                gainSlider.value = sdrData.gain;
            }
        }
        
        if (sdrData.sample_rate !== undefined) {
            const rateDisplays = document.querySelectorAll('.rate-display');
            rateDisplays.forEach(display => {
                const rateMHz = (sdrData.sample_rate / 1e6).toFixed(1);
                display.textContent = `${rateMHz} MSPS`;
            });
        }
    }
    
    console.log(`SDR status updated: ${isRunning ? 'running' : 'stopped'}`, sdrData);
}

async function testAPIConnection() {
    try {
        const response = await fetch('/api/health');
        if (response.ok) {
            const data = await response.json();
            console.log('API connection successful:', data);
            
            // Update status indicator if it exists
            const statusDot = document.querySelector('.status-dot');
            if (statusDot) {
                statusDot.classList.add('connected');
            }
            
            return true;
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (error) {
        console.warn('API connection failed:', error);
        return false;
    }
}

// Initialize spectrum visualization with clean WebSocket connection
function initializeSpectrumVisualization() {
    console.log('🔗 Initializing spectrum visualization...');
    
    const canvas = document.getElementById('spectrum-canvas');
    if (!canvas) {
        console.error('❌ Spectrum canvas not found');
        return;
    }
    
    console.log('✅ Canvas found:', canvas.width, 'x', canvas.height);
    
    // Rendering state
    let animationFrameId = null;
    let latestSpectrumData = null;
    let isDrawing = false;
    
    // Spectrum display parameters
    let spectrumZoom = 1.0;
    let spectrumPan = 0.0;
    let minPower = -80;  // Reducido para mejor visualización con ganancia baja
    let maxPower = -10;  // Ajustado para centrar el rango dinámico
    
    // WebSocket connections
    const ws = new WebSocket(`ws://${window.location.host}/ws/spectrum`);
    const audioWs = new WebSocket(`ws://${window.location.host}/ws/audio`);
    
    ws.onopen = () => {
        console.log('🔗 Spectrum WebSocket connected');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        // Debug: Log first message to see structure
        if (!window.DEBUG_WS_LOGGED) {
            console.log('🔍 WebSocket message structure:', Object.keys(data));
            if (data.spectrum) {
                console.log('🔍 Spectrum array length:', data.spectrum.length);
                console.log('🔍 Sample spectrum values:', data.spectrum.slice(0, 10));
            }
            window.DEBUG_WS_LOGGED = true;
        }
        
        if (data.type === 'spectrum' && data.spectrum && data.spectrum.length > 0) {
            drawSpectrum(canvas, data.spectrum);
            
            // Update waterfall display if available (DISABLED for performance)
            // if (waterfallDisplay && waterfallDisplay.addSpectrumLine) {
            //     waterfallDisplay.addSpectrumLine(new Float32Array(data.spectrum));
            //     waterfallDisplay.render();
            // }
        } else if (data.type === 'connection_status') {
            console.log('📡 WebSocket connection status:', data);
        } else {
            console.warn('❌ Unexpected WebSocket message:', data.type, Object.keys(data));
        }
    };
    
    ws.onerror = (error) => {
        console.error('❌ Spectrum WebSocket error:', error);
    };
    
    // Audio WebSocket handlers
    audioWs.onopen = () => {
        console.log('🔊 Audio WebSocket connected');
    };
    
    audioWs.onmessage = (event) => {
        try {
            console.log('🔊 Raw WebSocket message received:', typeof event.data, event.data.constructor.name);
            
            // Check if data is binary
            if (event.data instanceof ArrayBuffer) {
                console.log('🔊 Received binary data:', event.data.byteLength, 'bytes');
                // Handle binary audio data here if needed
                return;
            }
            
            // Try to parse as JSON
            const audioData = JSON.parse(event.data);
            console.log('🔊 Parsed audio data:', audioData.type, Object.keys(audioData));
            
            if (audioData.type === 'audio' && audioData.samples) {
                console.log(`🔊 WebSocket audio received: ${audioData.samples.length} samples, rate=${audioData.sample_rate}`);
                
                if (audioService) {
                    console.log('🔊 Calling audioService.playAudioBuffer...');
                    audioService.playAudioBuffer(new Float32Array(audioData.samples), audioData.sample_rate);
                } else {
                    console.error('🔊 AudioService not available!');
                }
            } else if (audioData.type === 'connection_status') {
                console.log('🔊 Audio WebSocket connection status:', audioData);
            } else {
                console.log('🔊 WebSocket message:', audioData.type, Object.keys(audioData));
            }
        } catch (error) {
            console.error('❌ Error processing audio data:', error, 'Raw data:', event.data.substring(0, 200));
        }
    };
    
    audioWs.onerror = (error) => {
        console.error('❌ Audio WebSocket error:', error);
    };
    
    audioWs.onclose = (event) => {
        console.log('🔌 Audio WebSocket disconnected:', event.code, event.reason);
    };
    
    // Drawing functions
    function drawSpectrum(canvas, spectrum) {
        latestSpectrumData = spectrum;
        
        if (animationFrameId) {
            cancelAnimationFrame(animationFrameId);
        }
        
        animationFrameId = requestAnimationFrame(() => {
            renderSpectrum(canvas);
        });
    }
    
    function renderSpectrum(canvas) {
        if (isDrawing || !latestSpectrumData) return;
        
        isDrawing = true;
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        const spectrum = latestSpectrumData;
        
        // Clear with dark background
        ctx.fillStyle = '#16213e';
        ctx.fillRect(0, 0, width, height);
        
        // Draw grid
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        
        // Horizontal lines
        for (let i = 0; i <= 4; i++) {
            const y = (i / 4) * height;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }
        
        // Vertical lines  
        for (let i = 0; i <= 8; i++) {
            const x = (i / 8) * width;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        
        // Draw spectrum with glow effect
        if (spectrum && spectrum.length > 0) {
            // Get zoom, pan, and power range from global parameters
            const currentZoom = (window.H1SDR_spectrum && window.H1SDR_spectrum.zoom) || spectrumZoom || 1.0;
            const currentPan = (window.H1SDR_spectrum && window.H1SDR_spectrum.pan) || spectrumPan || 0.0;
            const currentMinPower = (window.H1SDR_spectrum && window.H1SDR_spectrum.minPower) || minPower || -80;
            const currentMaxPower = (window.H1SDR_spectrum && window.H1SDR_spectrum.maxPower) || maxPower || -10;
            
            // Debug logging (remove in production)
            if (currentZoom > 1.0) {
                console.log(`🔍 Rendering with zoom: ${currentZoom}x, pan: ${currentPan}`);
            }
            
            // Apply zoom and pan calculations
            const zoomedLength = Math.floor(spectrum.length / currentZoom);
            const panOffset = Math.floor((spectrum.length - zoomedLength) * (currentPan + 1) / 2);
            const startIndex = Math.max(0, Math.min(spectrum.length - zoomedLength, panOffset));
            const endIndex = Math.min(spectrum.length, startIndex + zoomedLength);
            
            const stepX = width / (endIndex - startIndex);
            
            // Draw glow (wider, semi-transparent)
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(0, 255, 136, 0.3)';
            ctx.lineWidth = 4;
            
            for (let i = startIndex; i < endIndex; i++) {
                const powerRange = currentMaxPower - currentMinPower;
                const normalized = Math.max(0, Math.min(1, (spectrum[i] - currentMinPower) / powerRange));
                const x = (i - startIndex) * stepX;
                const y = height - (normalized * height);
                
                if (i === startIndex) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
            ctx.stroke();
            
            // Draw main line (brighter)
            ctx.beginPath();
            ctx.strokeStyle = '#00ff88';
            ctx.lineWidth = 2;
            
            for (let i = startIndex; i < endIndex; i++) {
                const powerRange = currentMaxPower - currentMinPower;
                const normalized = Math.max(0, Math.min(1, (spectrum[i] - currentMinPower) / powerRange));
                const x = (i - startIndex) * stepX;
                const y = height - (normalized * height);
                
                if (i === startIndex) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
            ctx.stroke();
            
            // Add frequency labels with zoom info
            ctx.fillStyle = '#a0a0a0';
            ctx.font = '14px Arial';
            
            // Show actual center frequency
            const centerFreq = window.currentFrequency ? (window.currentFrequency / 1e6) : 100.0;
            ctx.fillText(`${centerFreq.toFixed(4)} MHz`, 10, height - 10);
            
            // Calculate and show frequency range
            const sampleRate = 2400000; // 2.4 MSPS
            const bandwidth = sampleRate / currentZoom;
            const startFreq = centerFreq - (bandwidth / 2e6);
            const endFreq = centerFreq + (bandwidth / 2e6);
            
            // Show frequency range at bottom corners
            ctx.font = '12px Arial';
            ctx.fillStyle = '#888';
            ctx.textAlign = 'left';
            ctx.fillText(`${startFreq.toFixed(3)}`, 10, height - 30);
            ctx.textAlign = 'right';
            ctx.fillText(`${endFreq.toFixed(3)}`, width - 10, height - 30);
            
            // Center title
            ctx.textAlign = 'center';
            ctx.fillStyle = '#a0a0a0';
            ctx.font = '14px Arial';
            const zoomText = currentZoom > 1.0 ? `~ Live H1SDR Spectrum (${currentZoom.toFixed(1)}x zoom) ~` : '~ Live H1SDR Spectrum ~';
            ctx.fillText(zoomText, width/2, 25);
        }
        
        isDrawing = false;
    }
    
    // Initialize waterfall display (DISABLED for performance)
    let waterfallDisplay = null;
    // try {
    //     if (typeof WaterfallDisplay !== 'undefined') {
    //         waterfallDisplay = new WaterfallDisplay('waterfall-canvas');
    //         console.log('🌊 Waterfall display initialized');
    //     }
    // } catch (error) {
    //     console.warn('⚠️ Waterfall display initialization failed:', error);
    // }
    
    // Initialize audio service
    let audioService = null;
    try {
        if (typeof AudioService !== 'undefined') {
            audioService = new AudioService();
            audioService.initialize();
            console.log('🔊 Audio service initialized');
        }
    } catch (error) {
        console.warn('⚠️ Audio service initialization failed:', error);
    }
    
    // Add click-to-tune functionality
    function setupClickToTune() {
        let isMouseDown = false;
        
        canvas.addEventListener('mousedown', (event) => {
            isMouseDown = true;
        });
        
        canvas.addEventListener('mouseup', (event) => {
            if (isMouseDown) {
                const rect = canvas.getBoundingClientRect();
                const x = event.clientX - rect.left;
                const frequency = calculateFrequencyFromClick(x);
                
                if (frequency > 0) {
                    console.log(`🎯 Click-to-tune: ${(frequency/1e6).toFixed(4)} MHz`);
                    tuneToFrequency(frequency);
                }
            }
            isMouseDown = false;
        });
        
        canvas.addEventListener('mouseleave', () => {
            isMouseDown = false;
        });
        
        // Add visual feedback for hover
        canvas.addEventListener('mousemove', (event) => {
            if (!isMouseDown) {
                const rect = canvas.getBoundingClientRect();
                const x = event.clientX - rect.left;
                const frequency = calculateFrequencyFromClick(x);
                
                if (frequency > 0) {
                    canvas.title = `Click to tune to ${(frequency/1e6).toFixed(4)} MHz`;
                }
            }
        });
        
        // Change cursor to indicate clickable area
        canvas.style.cursor = 'crosshair';
    }
    
    function calculateFrequencyFromClick(clickX) {
        if (!latestSpectrumData || !window.currentFrequency) return 0;
        
        const width = canvas.width;
        const spectrum = latestSpectrumData;
        
        // Get current display parameters
        const currentZoom = (window.H1SDR_spectrum && window.H1SDR_spectrum.zoom) || 1.0;
        const currentPan = (window.H1SDR_spectrum && window.H1SDR_spectrum.pan) || 0.0;
        
        // Calculate the frequency range being displayed
        const sampleRate = 2400000; // 2.4 MSPS default
        const centerFreq = window.currentFrequency || 100e6;
        
        // Apply zoom and pan to get visible frequency range
        const totalBandwidth = sampleRate / currentZoom;
        const startFreq = centerFreq - totalBandwidth/2 + (currentPan * totalBandwidth/2);
        const endFreq = startFreq + totalBandwidth;
        
        // Convert click position to frequency
        const normalizedX = clickX / width;
        const clickFreq = startFreq + (normalizedX * (endFreq - startFreq));
        
        return clickFreq;
    }
    
    async function tuneToFrequency(frequency) {
        try {
            const response = await fetch(`/api/sdr/tune?frequency=${frequency}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ Tuned to frequency:', result);
                
                // Update global frequency
                window.currentFrequency = frequency;
                
                // Update frequency controls if they exist
                if (window.updateFrequencyDisplay && typeof window.updateFrequencyDisplay === 'function') {
                    window.updateFrequencyDisplay(frequency / 1e6);
                }
                
                // Show notification
                showNotification(`Tuned to ${(frequency/1e6).toFixed(4)} MHz`, 'success');
                
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (error) {
            console.error('❌ Failed to tune frequency:', error);
            showNotification('Failed to tune frequency', 'error');
        }
    }
    
    
    // Initialize click-to-tune
    setupClickToTune();

    // Store references for debugging and controls
    window.H1SDR_spectrum = { 
        canvas, 
        ws,
        audioWs,
        audioService,
        drawSpectrum,
        waterfallDisplay,
        zoom: 1.0,
        pan: 0.0,
        minPower: -80,  // Ajustado para mejor visualización
        maxPower: -10,   // Centrado para ganancia reducida
        tuneToFrequency,
        calculateFrequencyFromClick
    };
}

// Initialize frequency controls
function initializeFrequencyControls() {
    console.log('🎛️ Initializing frequency controls...');
    
    const freqInput = document.getElementById('frequency-input');
    const freqSlider = document.getElementById('frequency-slider');
    const freqDisplay = document.getElementById('frequency-display');
    const tuneUpBtn = document.getElementById('tune-up');
    const tuneDownBtn = document.getElementById('tune-down');
    
    let currentFrequency = 100.0; // MHz
    let tuneTimer = null; // Debounce timer
    window.currentFrequency = currentFrequency * 1e6; // Also store in Hz globally
    
    function updateFrequencyDisplay(freq) {
        if (freqDisplay) {
            freqDisplay.textContent = `${freq.toFixed(4)} MHz`;
        }
        if (freqInput && freqInput !== document.activeElement) {
            // Only update input if it's not being typed in
            freqInput.value = freq.toFixed(4);
        }
        if (freqSlider) {
            // Map 88-108 MHz for FM band, extend as needed
            const sliderValue = ((freq - 88) / (108 - 88)) * 100;
            freqSlider.value = Math.max(0, Math.min(100, sliderValue));
        }
        currentFrequency = freq;
        window.currentFrequency = freq * 1e6;
    }
    
    // Make updateFrequencyDisplay globally accessible for click-to-tune
    window.updateFrequencyDisplay = updateFrequencyDisplay;
    
    function setFrequency(freq, immediate = false) {
        // Validate frequency range (24-1766 MHz for RTL-SDR V4)
        freq = Math.max(24, Math.min(1766, parseFloat(freq)));
        
        if (isNaN(freq)) return;
        
        currentFrequency = freq;
        window.currentFrequency = freq * 1e6;
        updateFrequencyDisplay(freq);
        
        // Debounce API calls unless immediate is true
        if (tuneTimer) {
            clearTimeout(tuneTimer);
        }
        
        if (immediate) {
            tuneSDRFrequency(freq * 1e6);
        } else {
            tuneTimer = setTimeout(() => {
                tuneSDRFrequency(freq * 1e6);
            }, 300); // 300ms debounce
        }
    }
    
    // Frequency input field - only update on Enter or blur
    if (freqInput) {
        let lastValidValue = currentFrequency;
        
        freqInput.addEventListener('focus', (e) => {
            lastValidValue = parseFloat(e.target.value) || currentFrequency;
            e.target.select(); // Select all text for easy replacement
        });
        
        freqInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const freq = parseFloat(e.target.value);
                if (!isNaN(freq) && freq >= 24 && freq <= 1766) {
                    setFrequency(freq, true);
                    e.target.blur();
                } else {
                    // Restore last valid value
                    e.target.value = lastValidValue.toFixed(4);
                    showNotification('Frequency must be between 24-1766 MHz', 'error');
                }
            } else if (e.key === 'Escape') {
                e.target.value = lastValidValue.toFixed(4);
                e.target.blur();
            }
        });
        
        freqInput.addEventListener('blur', (e) => {
            const freq = parseFloat(e.target.value);
            if (!isNaN(freq) && freq >= 24 && freq <= 1766) {
                setFrequency(freq, true);
            } else {
                e.target.value = currentFrequency.toFixed(4);
            }
        });
        
        // Add arrow key support
        freqInput.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                setFrequency(currentFrequency + 0.1, true);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                setFrequency(currentFrequency - 0.1, true);
            }
        });
    }
    
    // Frequency slider
    if (freqSlider) {
        freqSlider.addEventListener('input', (e) => {
            const sliderPercent = parseFloat(e.target.value);
            const freq = 88 + (sliderPercent / 100) * (108 - 88); // FM band range
            setFrequency(freq);
        });
    }
    
    // Tune buttons with variable step size
    let stepSize = 0.1; // Default 100 kHz
    
    if (tuneUpBtn) {
        tuneUpBtn.addEventListener('click', () => {
            setFrequency(currentFrequency + stepSize, true);
        });
    }
    
    if (tuneDownBtn) {
        tuneDownBtn.addEventListener('click', () => {
            setFrequency(currentFrequency - stepSize, true);
        });
    }
    
    // Quick tune buttons - create better layout
    const quickTuneButtons = document.querySelectorAll('.quick-tune-btn');
    quickTuneButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const step = parseFloat(e.target.dataset.step);
            if (!isNaN(step)) {
                stepSize = Math.abs(step) / 1000; // Convert kHz to MHz
                if (step > 0) {
                    setFrequency(currentFrequency + stepSize, true);
                } else {
                    setFrequency(currentFrequency + step / 1000, true);
                }
                
                // Update button states to show active step
                quickTuneButtons.forEach(b => b.classList.remove('active'));
                if (Math.abs(step) === Math.abs(stepSize * 1000)) {
                    e.target.classList.add('active');
                }
            }
        });
    });
    
    // Add mouse wheel support to frequency input and display
    const addWheelSupport = (element) => {
        if (!element) return;
        element.addEventListener('wheel', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Determine step size based on modifier keys
            let wheelStep = stepSize;
            if (e.ctrlKey) {
                wheelStep = 1.0; // 1 MHz steps with Ctrl
            } else if (e.shiftKey) {
                wheelStep = 0.01; // 10 kHz steps with Shift
            } else if (e.altKey) {
                wheelStep = 0.001; // 1 kHz steps with Alt
            }
            
            const delta = e.deltaY < 0 ? wheelStep : -wheelStep;
            console.log(`🖱️ Wheel: ${delta > 0 ? '+' : ''}${delta.toFixed(3)} MHz`);
            setFrequency(currentFrequency + delta, true);
        }, { passive: false });
    };
    
    addWheelSupport(freqInput);
    addWheelSupport(freqDisplay);
    
    // Also add wheel support to the spectrum canvas for frequency tuning
    const spectrumCanvas = document.getElementById('spectrum-canvas');
    if (spectrumCanvas) {
        spectrumCanvas.addEventListener('wheel', (e) => {
            // Only handle wheel if not over other controls
            if (e.target === spectrumCanvas) {
                e.preventDefault();
                e.stopPropagation();
                
                let wheelStep = 0.1; // Default 100 kHz
                if (e.ctrlKey) wheelStep = 1.0; // 1 MHz with Ctrl
                if (e.shiftKey) wheelStep = 0.01; // 10 kHz with Shift
                
                const delta = e.deltaY < 0 ? wheelStep : -wheelStep;
                setFrequency(currentFrequency + delta, true);
            }
        }, { passive: false });
    }
    
    // Add keyboard shortcuts for frequency control
    document.addEventListener('keydown', (e) => {
        // Only handle if no input is focused
        if (document.activeElement.tagName === 'INPUT' || 
            document.activeElement.tagName === 'TEXTAREA') {
            return;
        }
        
        switch(e.key) {
            case 'PageUp':
                e.preventDefault();
                setFrequency(currentFrequency + 1, true); // +1 MHz
                break;
            case 'PageDown':
                e.preventDefault();
                setFrequency(currentFrequency - 1, true); // -1 MHz
                break;
            case '+':
            case '=':
                e.preventDefault();
                setFrequency(currentFrequency + stepSize, true);
                break;
            case '-':
            case '_':
                e.preventDefault();
                setFrequency(currentFrequency - stepSize, true);
                break;
        }
    });
    
    // Initialize with current frequency from SDR
    (async () => {
        try {
            const statusResponse = await fetch('/api/sdr/status');
            if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                if (statusData.success && statusData.data.center_frequency) {
                    const sdrFreqMHz = statusData.data.center_frequency / 1e6;
                    currentFrequency = sdrFreqMHz;
                    window.currentFrequency = statusData.data.center_frequency;
                    updateFrequencyDisplay(sdrFreqMHz);
                    console.log(`📡 Initialized frequency from SDR: ${sdrFreqMHz.toFixed(4)} MHz`);
                } else {
                    updateFrequencyDisplay(currentFrequency);
                }
            } else {
                updateFrequencyDisplay(currentFrequency);
            }
        } catch (error) {
            console.warn('Could not get initial frequency from SDR:', error);
            updateFrequencyDisplay(currentFrequency);
        }
    })();
    
    console.log('✅ Frequency controls initialized');
}

// Initialize gain controls
function initializeGainControls() {
    console.log('🔧 Initializing gain controls...');
    
    const gainSlider = document.getElementById('gain-slider');
    const gainDisplay = document.getElementById('gain-display');
    
    if (gainSlider && gainDisplay) {
        function updateGain() {
            const gainValue = parseFloat(gainSlider.value);
            gainDisplay.textContent = `${gainValue.toFixed(1)}`;
            
            // Update SDR gain via API
            tuneSDRGain(gainValue);
            
            console.log(`🔧 Gain set to: ${gainValue} dB`);
        }
        
        gainSlider.addEventListener('input', updateGain);
        
        // Set initial value to lower gain for better visualization
        gainSlider.value = '15.0';
        const initialGain = 15.0;
        gainDisplay.textContent = `${initialGain.toFixed(1)}`;
        
        console.log(`🔧 Initial gain: ${initialGain} dB`);
    } else {
        console.warn('⚠️ Gain controls not found in DOM');
    }
    
    console.log('✅ Gain controls initialized');
}

// Initialize bandwidth controls  
function initializeBandwidthControls() {
    console.log('📊 Initializing bandwidth controls...');
    
    const bandwidthSelect = document.getElementById('bandwidth-select');
    const bandwidthDisplay = document.getElementById('bandwidth-display');
    
    const bandwidthOptions = {
        '200000': '200 kHz',
        '1000000': '1 MHz', 
        '2400000': '2.4 MHz',
        '3200000': '3.2 MHz'
    };
    
    let currentBandwidth = 2400000; // Default 2.4 MHz
    
    function updateBandwidthDisplay(bandwidth) {
        const bwMHz = (bandwidth / 1e6).toFixed(1);
        if (bandwidthDisplay) {
            bandwidthDisplay.textContent = `${bwMHz} MHz`;
        }
    }
    
    function setBandwidth(bandwidth) {
        currentBandwidth = parseInt(bandwidth);
        updateBandwidthDisplay(currentBandwidth);
        
        // Send bandwidth to SDR via API
        updateSDRBandwidth(currentBandwidth);
    }
    
    // Bandwidth selector
    if (bandwidthSelect) {
        // Populate bandwidth options
        Object.keys(bandwidthOptions).forEach(bw => {
            const option = document.createElement('option');
            option.value = bw;
            option.textContent = bandwidthOptions[bw];
            if (parseInt(bw) === currentBandwidth) {
                option.selected = true;
            }
            bandwidthSelect.appendChild(option);
        });
        
        bandwidthSelect.addEventListener('change', (e) => {
            setBandwidth(e.target.value);
        });
    }
    
    // Initialize display
    updateBandwidthDisplay(currentBandwidth);
    
    console.log('✅ Bandwidth controls initialized');
}

// Initialize demodulation controls
function initializeDemodulationControls() {
    console.log('📻 Initializing demodulation controls...');
    
    const demodButtons = document.querySelectorAll('.demod-btn');
    const demodDisplay = document.getElementById('demod-display');
    
    const demodModes = {
        'SPECTRUM': 'Spectrum',
        'AM': 'AM',
        'FM': 'FM', 
        'USB': 'USB',
        'LSB': 'LSB',
        'CW': 'CW'
    };
    
    let currentDemod = 'SPECTRUM';
    
    function updateDemodDisplay(mode) {
        if (demodDisplay) {
            demodDisplay.textContent = demodModes[mode] || mode;
        }
        
        // Update button states
        demodButtons.forEach(btn => {
            if (btn.dataset.mode === mode) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
    
    function setDemodulation(mode) {
        if (mode in demodModes) {
            currentDemod = mode;
            updateDemodDisplay(currentDemod);
            
            // Send demodulation mode to SDR via API
            updateSDRDemodulation(currentDemod);
            
            // Update audio controls state
            if (typeof updateAudioControlsState === 'function') {
                updateAudioControlsState();
            }
            
            console.log(`📻 Demodulation set to: ${demodModes[mode]}`);
        }
    }
    
    // Demodulation buttons
    demodButtons.forEach(btn => {
        const mode = btn.dataset.mode;
        if (mode) {
            btn.addEventListener('click', () => {
                setDemodulation(mode);
            });
        }
    });
    
    // Initialize with current mode
    updateDemodDisplay(currentDemod);
    
    console.log('✅ Demodulation controls initialized');
}

// API functions for SDR control
async function tuneSDRFrequency(frequencyHz) {
    try {
        const response = await fetch(`/api/sdr/tune?frequency=${frequencyHz}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`🎯 Tuned to ${(frequencyHz/1e6).toFixed(4)} MHz`);
            
            // Update global frequency immediately
            window.currentFrequency = frequencyHz;
            
            // Get actual frequency from SDR to ensure sync
            try {
                const statusResponse = await fetch('/api/sdr/status');
                if (statusResponse.ok) {
                    const statusData = await statusResponse.json();
                    if (statusData.success && statusData.data) {
                        updateSDRStatus(true, statusData.data);
                    }
                }
            } catch (e) {
                console.warn('Could not verify frequency after tune:', e);
            }
            
            return result;
        } else {
            const errorText = await response.text();
            console.error('Failed to tune frequency:', response.statusText, errorText);
            showNotification(`Failed to tune to ${(frequencyHz/1e6).toFixed(4)} MHz`, 'error');
        }
    } catch (error) {
        console.error('Error tuning frequency:', error);
        showNotification('Network error while tuning', 'error');
    }
}

// Tune SDR gain via API
async function tuneSDRGain(gain) {
    try {
        const currentFreq = window.currentFrequency || 100.0e6;
        const response = await fetch(`/api/sdr/tune?frequency=${currentFreq}&gain=${gain}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`🔧 SDR gain set to ${gain} dB`);
            return result;
        } else {
            console.error('Failed to set gain:', response.statusText);
        }
    } catch (error) {
        console.error('Error setting gain:', error);
    }
}

async function updateSDRBandwidth(sampleRate) {
    try {
        const response = await fetch(`/api/sdr/bandwidth?sample_rate=${sampleRate}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`📊 Sample rate set to ${(sampleRate/1e6).toFixed(1)} MHz`);
            return result;
        } else {
            console.error('Failed to set bandwidth:', response.statusText);
        }
    } catch (error) {
        console.error('Error setting bandwidth:', error);
    }
}

async function updateSDRDemodulation(mode) {
    try {
        const response = await fetch('/api/sdr/demod', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`📻 Demodulation set to ${mode}`);
            
            // Start/stop audio based on demodulation mode
            if (window.H1SDR_spectrum && window.H1SDR_spectrum.audioService) {
                if (mode === 'SPECTRUM') {
                    window.H1SDR_spectrum.audioService.stopAudio();
                } else {
                    window.H1SDR_spectrum.audioService.startAudio();
                }
            }
            
            return result;
        } else {
            console.error('Failed to set demodulation:', response.statusText);
        }
    } catch (error) {
        console.error('Error setting demodulation:', error);
    }
}

// Initialize band presets
async function initializeBandPresets() {
    console.log('🎚️ Initializing band presets...');
    
    const bandSelect = document.getElementById('band-select');
    const bandButtons = document.querySelectorAll('.band-btn');
    
    try {
        // Fetch available bands from API
        const response = await fetch('/api/bands');
        if (!response.ok) {
            throw new Error('Failed to fetch bands');
        }
        
        const result = await response.json();
        const bands = result.data;
        
        console.log(`📻 Loaded ${Object.keys(bands).length} band presets`);
        
        // Populate band selector dropdown
        if (bandSelect) {
            // Clear existing options
            bandSelect.innerHTML = '<option value="">Select Band...</option>';
            
            // Add band options organized by category
            const categories = {
                'Radio Astronomy': [],
                'Amateur Radio': [],
                'Broadcast': [],
                'Aviation': [],
                'Marine': [],
                'Satellite': [],
                'Other': []
            };
            
            // Categorize bands
            Object.entries(bands).forEach(([key, band]) => {
                const category = band.category || 'Other';
                if (categories[category]) {
                    categories[category].push({ key, ...band });
                } else {
                    categories['Other'].push({ key, ...band });
                }
            });
            
            // Add options by category
            Object.entries(categories).forEach(([category, categoryBands]) => {
                if (categoryBands.length > 0) {
                    const optgroup = document.createElement('optgroup');
                    optgroup.label = category;
                    
                    categoryBands.forEach(band => {
                        const option = document.createElement('option');
                        option.value = band.key;
                        option.textContent = `${band.name} (${(band.center_freq/1e6).toFixed(2)} MHz)`;
                        optgroup.appendChild(option);
                    });
                    
                    bandSelect.appendChild(optgroup);
                }
            });
        }
        
        // Band selector change handler
        if (bandSelect) {
            bandSelect.addEventListener('change', async (e) => {
                const bandKey = e.target.value;
                if (bandKey) {
                    await tuneToBand(bandKey);
                }
            });
        }
        
        // Quick band buttons (for popular frequencies)
        bandButtons.forEach(btn => {
            const bandKey = btn.dataset.band;
            if (bandKey) {
                btn.addEventListener('click', () => {
                    tuneToBand(bandKey);
                    // Update dropdown selection
                    if (bandSelect) {
                        bandSelect.value = bandKey;
                    }
                });
            }
        });
        
        // Add special quick-tune buttons for radio astronomy
        addQuickTuneButtons(bands);
        
        console.log('✅ Band presets initialized');
        
    } catch (error) {
        console.error('❌ Failed to initialize band presets:', error);
    }
}

// Add quick tune buttons for important frequencies
function addQuickTuneButtons(bands) {
    const quickTuneContainer = document.getElementById('quick-tune-container');
    if (!quickTuneContainer) return;
    
    // Important frequencies for radio astronomy
    const quickFreqs = [
        { name: 'H1 Line', freq: 1420.405751, color: '#ff6b6b' },
        { name: 'OH 1665', freq: 1665.4018, color: '#4ecdc4' },
        { name: 'H2O 22G', freq: 22235.08, color: '#45b7d1' },
        { name: 'FM 100', freq: 100.0, color: '#96ceb4' }
    ];
    
    quickFreqs.forEach(({ name, freq, color }) => {
        const btn = document.createElement('button');
        btn.className = 'btn quick-tune-btn';
        btn.style.backgroundColor = color;
        btn.style.color = 'white';
        btn.style.margin = '2px';
        btn.textContent = name;
        btn.title = `${freq} MHz`;
        
        btn.addEventListener('click', () => {
            tuneSDRFrequency(freq * 1e6);
            // Update frequency display
            updateFrequencyDisplayFromValue(freq);
        });
        
        quickTuneContainer.appendChild(btn);
    });
}

// Function to tune to a specific band
async function tuneToBand(bandKey) {
    try {
        const response = await fetch(`/api/bands/${bandKey}/tune`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            const band = result.data;
            
            if (band && band.frequency) {
                console.log(`🎯 Tuned to ${result.message}: ${(band.frequency/1e6).toFixed(4)} MHz`);
                
                // Update frequency display
                updateFrequencyDisplayFromValue(band.frequency / 1e6);
                
                // Update demodulation if specified
                if (band.default_demod) {
                    updateDemodulationDisplay(band.default_demod);
                }
            } else {
                console.error('Invalid band data received:', result);
            }
            
            return result;
        } else {
            // Handle specific error cases
            const errorText = await response.text();
            let errorMessage = response.statusText;
            
            try {
                const errorData = JSON.parse(errorText);
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                    
                    // Check if it's a frequency range error
                    if (errorMessage.includes('outside RTL-SDR range')) {
                        console.warn(`⚠️ ${bandKey}: ${errorMessage}`);
                        showError(`Cannot tune to this band: ${errorMessage}`);
                        return;
                    }
                }
            } catch (e) {
                // errorText is not JSON, use as-is
                errorMessage = errorText || errorMessage;
            }
            
            console.error('Failed to tune to band:', errorMessage);
            showError(`Failed to tune to band: ${errorMessage}`);
        }
    } catch (error) {
        console.error('Error tuning to band:', error);
    }
}

// Helper function to update frequency display from external calls
function updateFrequencyDisplayFromValue(freqMHz) {
    // Validate frequency value
    if (isNaN(freqMHz) || freqMHz <= 0) {
        console.error('Invalid frequency value:', freqMHz);
        return;
    }
    
    const freqDisplay = document.getElementById('frequency-display');
    const freqInput = document.getElementById('frequency-input');
    
    if (freqDisplay) {
        freqDisplay.textContent = `${freqMHz.toFixed(4)} MHz`;
    }
    if (freqInput) {
        freqInput.value = freqMHz.toFixed(4);
    }
}

// Helper function to update demod display from external calls  
function updateDemodulationDisplay(mode) {
    const demodDisplay = document.getElementById('demod-display');
    const demodButtons = document.querySelectorAll('.demod-btn');
    
    if (demodDisplay) {
        const demodModes = {
            'SPECTRUM': 'Spectrum',
            'AM': 'AM',
            'FM': 'FM', 
            'USB': 'USB',
            'LSB': 'LSB',
            'CW': 'CW'
        };
        demodDisplay.textContent = demodModes[mode] || mode;
    }
    
    // Update button states
    demodButtons.forEach(btn => {
        if (btn.dataset.mode === mode) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

// Initialize spectrum visualization controls
function initializeSpectrumControls() {
    console.log('🎛️ Initializing spectrum visualization controls...');
    
    // Get control elements
    const spectrumZoom = document.getElementById('spectrum-zoom');
    const zoomDisplay = document.getElementById('zoom-display');
    const spanSelect = document.getElementById('span-select');
    const resetZoomBtn = document.getElementById('reset-zoom');
    
    // Zoom control
    if (spectrumZoom && zoomDisplay) {
        function updateZoom() {
            const zoomValue = parseInt(spectrumZoom.value);
            zoomDisplay.textContent = `${zoomValue}x`;
            
            // Update global zoom parameter
            if (window.H1SDR_spectrum) {
                window.H1SDR_spectrum.zoom = zoomValue;
            }
            
            console.log(`🔍 Spectrum zoom: ${zoomValue}x`);
        }
        
        spectrumZoom.addEventListener('input', updateZoom);
        updateZoom(); // Set initial value
    }
    
    // Span control (bandwidth/frequency span)
    if (spanSelect) {
        spanSelect.addEventListener('change', (e) => {
            const spanHz = parseInt(e.target.value);
            const spanMHz = spanHz / 1e6;
            
            console.log(`📊 Spectrum span: ${spanMHz} MHz`);
            
            // Call API to set sample rate
            updateSDRBandwidth(spanHz);
        });
        
        // Set default span
        spanSelect.value = '2400000'; // 2.4 MHz default
    }
    
    // Reset zoom button
    if (resetZoomBtn) {
        resetZoomBtn.addEventListener('click', () => {
            if (spectrumZoom) {
                spectrumZoom.value = '1';
                zoomDisplay.textContent = '1x';
            }
            
            // Reset spectrum display
            if (window.H1SDR_spectrum) {
                window.H1SDR_spectrum.zoom = 1;
                window.H1SDR_spectrum.pan = 0;
            }
            
            console.log('🔄 Spectrum zoom reset');
        });
    }
    
    // Intensity (power range) controls
    const intensityMin = document.getElementById('intensity-min');
    const intensityMax = document.getElementById('intensity-max');
    const intensityMinDisplay = document.getElementById('intensity-min-display');
    const intensityMaxDisplay = document.getElementById('intensity-max-display');
    const autoScaleBtn = document.getElementById('auto-scale');
    
    if (intensityMin && intensityMinDisplay) {
        function updateMinIntensity() {
            const minValue = parseInt(intensityMin.value);
            intensityMinDisplay.textContent = `${minValue}`;
            
            // Update global power range parameter
            if (!window.H1SDR_spectrum) {
                window.H1SDR_spectrum = {};
            }
            window.H1SDR_spectrum.minPower = minValue;
            
            // Update spectrum display if available
            if (window.spectrumDisplay && window.H1SDR_spectrum.maxPower !== undefined) {
                window.spectrumDisplay.setPowerRange(minValue, window.H1SDR_spectrum.maxPower);
            }
            
            console.log(`📊 Spectrum min power: ${minValue} dB`);
        }
        
        intensityMin.addEventListener('input', updateMinIntensity);
        updateMinIntensity(); // Set initial value
    }
    
    if (intensityMax && intensityMaxDisplay) {
        function updateMaxIntensity() {
            const maxValue = parseInt(intensityMax.value);
            intensityMaxDisplay.textContent = `${maxValue}`;
            
            // Update global power range parameter
            if (!window.H1SDR_spectrum) {
                window.H1SDR_spectrum = {};
            }
            window.H1SDR_spectrum.maxPower = maxValue;
            
            // Update spectrum display if available
            if (window.spectrumDisplay && window.H1SDR_spectrum.minPower !== undefined) {
                window.spectrumDisplay.setPowerRange(window.H1SDR_spectrum.minPower, maxValue);
            }
            
            console.log(`📊 Spectrum max power: ${maxValue} dB`);
        }
        
        intensityMax.addEventListener('input', updateMaxIntensity);
        updateMaxIntensity(); // Set initial value
    }
    
    // Auto scale button
    if (autoScaleBtn) {
        autoScaleBtn.addEventListener('click', () => {
            // Reset to optimal values for current gain (15dB)
            if (intensityMin) {
                intensityMin.value = '-80';
                intensityMinDisplay.textContent = '-80';
            }
            if (intensityMax) {
                intensityMax.value = '-10';
                intensityMaxDisplay.textContent = '-10';
            }
            
            // Update global parameters
            if (!window.H1SDR_spectrum) {
                window.H1SDR_spectrum = {};
            }
            window.H1SDR_spectrum.minPower = -80;
            window.H1SDR_spectrum.maxPower = -10;
            
            // Update spectrum display immediately
            if (window.spectrumDisplay) {
                window.spectrumDisplay.setPowerRange(-80, -10);
            }
            
            console.log('🔄 Spectrum power range auto-scaled to -80 to -10 dB');
        });
    }
    
    console.log('✅ Spectrum controls initialized');
}

// Initialize waterfall controls  
function initializeWaterfallControls() {
    console.log('🌊 Initializing waterfall controls...');
    
    const colormapSelect = document.getElementById('colormap-select');
    
    // Colormap selection - only waterfall-specific functionality
    if (colormapSelect) {
        colormapSelect.addEventListener('change', (e) => {
            const colormap = e.target.value;
            console.log(`🎨 Waterfall colormap: ${colormap}`);
            
            // Update waterfall display if available
            if (window.H1SDR_spectrum && window.H1SDR_spectrum.waterfallDisplay) {
                window.H1SDR_spectrum.waterfallDisplay.setColormap(colormap);
            }
        });
        
        // Set default colormap
        colormapSelect.value = 'jet';
    } else {
        console.warn('⚠️ Colormap selector not found');
    }
    
    console.log('✅ Waterfall controls initialized');
}

// Initialize audio controls
function initializeAudioControls() {
    console.log('🔊 Initializing audio controls...');
    
    const playBtn = document.getElementById('audio-play');
    const stopBtn = document.getElementById('audio-stop');
    const volumeSlider = document.getElementById('volume-slider');
    const volumeDisplay = document.getElementById('volume-display');
    const squelchSlider = document.getElementById('squelch-slider');
    
    // Get audio service reference
    const audioService = window.H1SDR_spectrum?.audioService;
    
    if (playBtn) {
        playBtn.addEventListener('click', async () => {
            if (audioService) {
                try {
                    await audioService.startAudio();
                    playBtn.disabled = true;
                    stopBtn.disabled = false;
                    playBtn.innerHTML = '<span class="icon">⏸</span> Playing';
                    console.log('🔊 Audio started');
                    showNotification('Audio started', 'success');
                } catch (error) {
                    console.error('Failed to start audio:', error);
                    showNotification('Failed to start audio: ' + error.message, 'error');
                }
            } else {
                console.error('AudioService not available');
                showNotification('Audio service not available', 'error');
            }
        });
    }
    
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            if (audioService) {
                audioService.stopAudio();
                playBtn.disabled = false;
                stopBtn.disabled = true;
                playBtn.innerHTML = '<span class="icon">▶</span> Play Audio';
                console.log('🔊 Audio stopped');
                showNotification('Audio stopped', 'info');
            }
        });
    }
    
    if (volumeSlider && volumeDisplay) {
        volumeSlider.addEventListener('input', (e) => {
            const volume = parseFloat(e.target.value) / 100;
            if (audioService) {
                audioService.setVolume(volume);
            }
            volumeDisplay.textContent = `${e.target.value}%`;
            console.log(`🔊 Volume: ${e.target.value}%`);
        });
        
        // Set initial volume
        const initialVolume = parseFloat(volumeSlider.value) / 100;
        if (audioService) {
            audioService.setVolume(initialVolume);
        }
        volumeDisplay.textContent = `${volumeSlider.value}%`;
    }
    
    if (squelchSlider) {
        squelchSlider.addEventListener('input', (e) => {
            const squelch = parseFloat(e.target.value);
            if (audioService) {
                audioService.setSquelch(squelch);
            }
            console.log(`🔊 Squelch: ${squelch}`);
        });
    }
    
    // Connect to mode selector for automatic updates
    const modeSelect = document.getElementById('mode-select');
    if (modeSelect) {
        modeSelect.addEventListener('change', () => {
            console.log('🔊 Mode changed, updating audio controls...');
            setTimeout(updateAudioControlsState, 50);
        });
        console.log('🔊 Connected to mode selector');
    }
    
    // Enable audio controls if demodulation is active
    // Use timeout to ensure DOM is ready
    setTimeout(() => {
        updateAudioControlsState();
    }, 100);
    
    console.log('✅ Audio controls initialized');
}

function updateAudioControlsState() {
    const playBtn = document.getElementById('audio-play');
    const stopBtn = document.getElementById('audio-stop');
    const volumeSlider = document.getElementById('volume-slider');
    
    // Check if we're in an audio demodulation mode
    const demodSelect = document.getElementById('mode-select');
    const isAudioMode = demodSelect && demodSelect.value !== 'SPECTRUM';
    
    console.log(`🔊 Audio controls update: mode=${demodSelect?.value}, audioMode=${isAudioMode}`);
    console.log(`🔊 Elements found: playBtn=${!!playBtn}, stopBtn=${!!stopBtn}, volumeSlider=${!!volumeSlider}`);
    
    if (playBtn && stopBtn) {
        // Force enable for debugging - remove this later
        playBtn.disabled = false; // !isAudioMode;
        stopBtn.disabled = true; // Will be enabled when audio starts
        
        if (isAudioMode) {
            playBtn.title = 'Start audio playback';
            console.log('🔊 Audio controls enabled');
        } else {
            playBtn.title = 'Audio enabled for testing - mode: ' + (demodSelect?.value || 'unknown');
            console.log('🔊 Audio controls forced enabled for debugging');
        }
    } else {
        console.error('🔊 Audio buttons not found in DOM');
    }
    
    if (volumeSlider) {
        volumeSlider.disabled = false; // !isAudioMode;
    }
}

// SDR Configuration endpoint
async function getSDRConfiguration() {
    try {
        const response = await fetch('/api/sdr/config');
        if (response.ok) {
            const config = await response.json();
            console.log('📡 SDR Configuration:', config);
            return config;
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (error) {
        console.error('❌ Failed to get SDR configuration:', error);
        return null;
    }
}

async function updateSDRConfiguration(config) {
    try {
        const response = await fetch('/api/sdr/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('✅ SDR configuration updated:', result);
            
            // Show notification
            if (window.showNotification) {
                window.showNotification('SDR configuration updated', 'success');
            }
            
            return result;
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (error) {
        console.error('❌ Failed to update SDR configuration:', error);
        if (window.showNotification) {
            window.showNotification('Failed to update SDR configuration', 'error');
        }
        return null;
    }
}

// Initialize resizable layout
function initializeResizableLayout() {
    console.log('🔄 Initializing resizable layout...');
    
    const resizeDivider = document.getElementById('resize-divider');
    const controlsPanel = document.getElementById('controls-panel');
    const spectrumPanel = document.getElementById('spectrum-panel');
    
    if (!resizeDivider || !controlsPanel || !spectrumPanel) {
        console.warn('⚠️ Resizable layout elements not found');
        return;
    }
    
    let isResizing = false;
    let startY = 0;
    let startControlsHeight = 0;
    let startSpectrumHeight = 0;
    
    function startResize(e) {
        isResizing = true;
        startY = e.clientY || e.touches[0].clientY;
        startControlsHeight = controlsPanel.offsetHeight;
        startSpectrumHeight = spectrumPanel.offsetHeight;
        
        resizeDivider.classList.add('resizing');
        document.body.style.cursor = 'row-resize';
        document.body.style.userSelect = 'none';
        
        // Add event listeners to document to handle mouse/touch events outside divider
        document.addEventListener('mousemove', handleResize);
        document.addEventListener('mouseup', stopResize);
        document.addEventListener('touchmove', handleResize);
        document.addEventListener('touchend', stopResize);
        
        e.preventDefault();
    }
    
    function handleResize(e) {
        if (!isResizing) return;
        
        const currentY = e.clientY || e.touches[0].clientY;
        const deltaY = currentY - startY;
        
        const newControlsHeight = Math.max(80, Math.min(400, startControlsHeight + deltaY));
        const totalHeight = window.innerHeight - 120; // Account for header
        const newSpectrumHeight = Math.max(200, totalHeight - newControlsHeight - 6); // 6px for divider
        
        controlsPanel.style.height = `${newControlsHeight}px`;
        spectrumPanel.style.height = `${newSpectrumHeight}px`;
        
        // Update canvas if needed
        const canvas = document.getElementById('spectrum-canvas');
        if (canvas && window.spectrumDisplay) {
            // Trigger resize on next frame
            setTimeout(() => {
                if (window.spectrumDisplay.resize) {
                    window.spectrumDisplay.resize();
                }
            }, 16);
        }
        
        e.preventDefault();
    }
    
    function stopResize() {
        if (!isResizing) return;
        
        isResizing = false;
        resizeDivider.classList.remove('resizing');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        
        // Remove event listeners
        document.removeEventListener('mousemove', handleResize);
        document.removeEventListener('mouseup', stopResize);
        document.removeEventListener('touchmove', handleResize);
        document.removeEventListener('touchend', stopResize);
        
        console.log(`🔄 Layout resized - Controls: ${controlsPanel.offsetHeight}px, Spectrum: ${spectrumPanel.offsetHeight}px`);
    }
    
    // Mouse events
    resizeDivider.addEventListener('mousedown', startResize);
    
    // Touch events for mobile
    resizeDivider.addEventListener('touchstart', startResize, { passive: false });
    
    // Double-click to reset to default sizes
    resizeDivider.addEventListener('dblclick', () => {
        controlsPanel.style.height = '160px';
        spectrumPanel.style.height = 'calc(100vh - 280px)';
        
        // Trigger canvas resize
        setTimeout(() => {
            if (window.spectrumDisplay && window.spectrumDisplay.resize) {
                window.spectrumDisplay.resize();
            }
        }, 100);
        
        console.log('🔄 Layout reset to default sizes');
    });
    
    console.log('✅ Resizable layout initialized');
}


// Export for debugging
window.H1SDRInit = {
    hideLoadingOverlay,
    showError,
    initializeBasicComponents,
    testAPIConnection,
    initializeSpectrumVisualization,
    initializeFrequencyControls,
    initializeGainControls,
    initializeBandwidthControls,
    initializeDemodulationControls,
    initializeBandPresets,
    initializeSpectrumControls,
    initializeWaterfallControls,
    initializeAudioControls,
    initializeResizableLayout,
    updateAudioControlsState,
    tuneToBand,
    tuneSDRFrequency,
    tuneSDRGain,
    updateSDRBandwidth,
    updateSDRDemodulation
};

// Initialization already handled above in the DOMContentLoaded listener