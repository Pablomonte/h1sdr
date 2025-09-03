#!/usr/bin/env python3
"""
H1SDR WebSDR Main Server
FastAPI-based web interface for multi-band SDR with demodulation
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles  
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

# Import our modules
from .config import config, EXTENDED_RADIO_BANDS, DEMOD_MODES
from .services.websocket_service import WebSocketManager
from .controllers.sdr_controller import WebSDRController

# Setup logging
logging.basicConfig(
    level=logging.INFO if not config.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
websocket_manager = WebSocketManager()
sdr_controller = WebSDRController()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting H1SDR WebSDR server...")
    
    # Startup
    try:
        # Initialize SDR controller
        await sdr_controller.initialize()
        logger.info("SDR controller initialized")
        
        # Start background tasks
        asyncio.create_task(spectrum_streaming_task())
        logger.info("Background tasks started")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down H1SDR WebSDR server...")
    try:
        await sdr_controller.cleanup()
        await websocket_manager.cleanup()
        logger.info("Cleanup completed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Create FastAPI application
app = FastAPI(
    title="H1SDR WebSDR",
    description="Multi-band Software Defined Radio with Web Interface",
    version="1.0.0",
    docs_url="/api/docs" if config.debug else None,
    redoc_url="/api/redoc" if config.debug else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=config.cors_credentials,
    allow_methods=config.cors_methods,
    allow_headers=config.cors_headers,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount static files - serve all web assets
web_dir = Path(__file__).parent.parent.parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

# Root endpoint - serve main HTML
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve main WebSDR interface"""
    html_file = web_dir / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(), status_code=200)
    else:
        return HTMLResponse(
            content="""
            <html>
                <head><title>H1SDR WebSDR</title></head>
                <body>
                    <h1>H1SDR WebSDR</h1>
                    <p>Frontend not yet built. Check <a href="/api/docs">/api/docs</a> for API documentation.</p>
                    <h2>Available Bands:</h2>
                    <ul>""" + 
                    "".join([f"<li>{band['name']} - {band['description']}</li>" 
                            for band in EXTENDED_RADIO_BANDS.values()]) +
                    """</ul>
                </body>
            </html>
            """, 
            status_code=200
        )

# API Health check
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "sdr_connected": sdr_controller.is_connected,
        "active_connections": len(websocket_manager.active_connections)
    }

# SDR Status
@app.get("/api/sdr/status")
async def get_sdr_status():
    """Get current SDR status"""
    try:
        status = await sdr_controller.get_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        logger.error(f"Error getting SDR status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# SDR Control
@app.post("/api/sdr/start")
async def start_sdr(device_index: int = 0):
    """Start SDR with specified device"""
    try:
        result = await sdr_controller.start(device_index=device_index)
        return {
            "success": True,
            "message": "SDR started successfully",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error starting SDR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sdr/stop")
async def stop_sdr():
    """Stop SDR"""
    try:
        await sdr_controller.stop()
        return {
            "success": True,
            "message": "SDR stopped successfully"
        }
    except Exception as e:
        logger.error(f"Error stopping SDR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sdr/tune")
async def tune_frequency(frequency: float, gain: float = None):
    """Tune to specific frequency"""
    try:
        result = await sdr_controller.tune(frequency=frequency, gain=gain)
        return {
            "success": True,
            "message": f"Tuned to {frequency/1e6:.4f} MHz",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error tuning frequency: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Band Presets
@app.get("/api/bands")
async def get_bands():
    """Get available radio bands"""
    return {
        "success": True,
        "data": EXTENDED_RADIO_BANDS
    }

@app.get("/api/bands/{band_key}")
async def get_band(band_key: str):
    """Get specific band information"""
    if band_key not in EXTENDED_RADIO_BANDS:
        raise HTTPException(status_code=404, detail="Band not found")
    
    return {
        "success": True,
        "data": EXTENDED_RADIO_BANDS[band_key]
    }

@app.post("/api/bands/{band_key}/tune")
async def tune_to_band(band_key: str):
    """Tune to a preset band"""
    if band_key not in EXTENDED_RADIO_BANDS:
        raise HTTPException(status_code=404, detail="Band not found")
    
    band = EXTENDED_RADIO_BANDS[band_key]
    try:
        result = await sdr_controller.tune(
            frequency=band['center_freq'],
            gain=band['typical_gain']
        )
        return {
            "success": True,
            "message": f"Tuned to {band['name']}",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error tuning to band {band_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Demodulation modes
@app.get("/api/modes")
async def get_demod_modes():
    """Get available demodulation modes"""
    return {
        "success": True,
        "data": DEMOD_MODES
    }

@app.get("/api/sdr/config")
async def get_sdr_config():
    """Get current SDR configuration"""
    return {
        "sample_rate": config.rtlsdr_sample_rate,
        "fft_size": config.fft_size,
        "gain": sdr_controller.current_gain if sdr_controller.is_running else config.rtlsdr_gain,
        "frequency": sdr_controller.current_frequency if sdr_controller.is_running else config.default_frequency,
        "ppm_correction": config.ppm_correction,
        "device_index": config.rtlsdr_device_index,
        "is_running": sdr_controller.is_running,
        "demod_mode": sdr_controller.demod_mode if hasattr(sdr_controller, 'demod_mode') else "SPECTRUM",
        "audio_sample_rate": config.audio_sample_rate
    }

@app.post("/api/sdr/config")
async def update_sdr_config(new_config: dict):
    """Update SDR configuration"""
    try:
        # Update configuration values
        if "sample_rate" in new_config:
            config.rtlsdr_sample_rate = new_config["sample_rate"]
        if "fft_size" in new_config:
            config.fft_size = new_config["fft_size"]
        if "ppm_correction" in new_config:
            config.ppm_correction = new_config["ppm_correction"]
        if "device_index" in new_config:
            config.rtlsdr_device_index = new_config["device_index"]
        if "audio_sample_rate" in new_config:
            config.audio_sample_rate = new_config["audio_sample_rate"]
        
        # If SDR is running and critical params changed, restart it
        restart_required = False
        if sdr_controller.is_running:
            if any(key in new_config for key in ["sample_rate", "device_index", "ppm_correction"]):
                restart_required = True
                current_freq = sdr_controller.current_frequency
                current_gain = sdr_controller.current_gain
                
                await sdr_controller.stop()
                await sdr_controller.start(frequency=current_freq, gain=current_gain)
        
        return {
            "success": True,
            "message": "Configuration updated",
            "restarted": restart_required,
            "config": await get_sdr_config()
        }
    except Exception as e:
        logger.error(f"Error updating SDR config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sdr/bandwidth")
async def set_sample_rate(sample_rate: float):
    """Set SDR sample rate (requires restart for now)"""
    try:
        # Update configuration
        old_sample_rate = config.rtlsdr_sample_rate
        config.rtlsdr_sample_rate = sample_rate
        
        # If SDR is running, restart it with new sample rate
        if sdr_controller.is_running:
            current_freq = sdr_controller.current_frequency
            current_gain = sdr_controller.current_gain
            
            # Stop current SDR
            await sdr_controller.stop()
            
            # Restart with new sample rate
            await sdr_controller.start(
                frequency=current_freq,
                gain=current_gain
            )
            
            logger.info(f"Sample rate changed from {old_sample_rate/1e6:.1f} MHz to {sample_rate/1e6:.1f} MHz")
            
            return {
                "success": True,
                "message": f"Sample rate changed to {sample_rate/1e6:.1f} MHz",
                "data": {
                    "sample_rate": sample_rate,
                    "restarted": True
                }
            }
        else:
            # Just update config if SDR not running
            return {
                "success": True,
                "message": f"Sample rate set to {sample_rate/1e6:.1f} MHz",
                "data": {
                    "sample_rate": sample_rate,
                    "restarted": False
                }
            }
    except Exception as e:
        logger.error(f"Error setting sample rate: {e}")
        # Restore old sample rate on error
        config.rtlsdr_sample_rate = old_sample_rate
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/demod/set")
async def set_demodulation(mode: str, bandwidth: int = None):
    """Set demodulation mode and bandwidth"""
    if mode not in DEMOD_MODES:
        raise HTTPException(status_code=400, detail="Invalid demodulation mode")
    
    try:
        result = await sdr_controller.set_demodulation(mode=mode, bandwidth=bandwidth)
        return {
            "success": True,
            "message": f"Demodulation set to {mode}",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error setting demodulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoints
@app.websocket("/ws/spectrum")
async def websocket_spectrum(websocket: WebSocket):
    """WebSocket endpoint for real-time spectrum data"""
    await websocket_manager.connect_spectrum(websocket)
    try:
        while True:
            # Keep connection alive and handle client messages
            try:
                message = await websocket.receive_text()
                # Handle any client commands if needed
                logger.debug(f"Received spectrum WS message: {message}")
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"Error in spectrum WebSocket: {e}")
    finally:
        websocket_manager.disconnect_spectrum(websocket)

@app.websocket("/ws/audio")
async def websocket_audio(websocket: WebSocket):
    """WebSocket endpoint for real-time audio data"""
    await websocket_manager.connect_audio(websocket)
    try:
        while True:
            try:
                message = await websocket.receive_text()
                logger.debug(f"Received audio WS message: {message}")
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"Error in audio WebSocket: {e}")
    finally:
        websocket_manager.disconnect_audio(websocket)

@app.websocket("/ws/waterfall")
async def websocket_waterfall(websocket: WebSocket):
    """WebSocket endpoint for waterfall data"""
    await websocket_manager.connect_waterfall(websocket)
    try:
        while True:
            try:
                message = await websocket.receive_text()
                logger.debug(f"Received waterfall WS message: {message}")
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"Error in waterfall WebSocket: {e}")
    finally:
        websocket_manager.disconnect_waterfall(websocket)

# Background tasks
async def spectrum_streaming_task():
    """Background task for streaming spectrum data"""
    logger.info("Starting spectrum streaming task")
    
    while True:
        try:
            if sdr_controller.is_running and len(websocket_manager.spectrum_clients) > 0:
                # Get spectrum data from SDR
                spectrum_data = await sdr_controller.get_spectrum_data()
                if spectrum_data:
                    # Broadcast to all spectrum clients
                    await websocket_manager.broadcast_spectrum(spectrum_data)
                    
                    # Also send to waterfall clients (DISABLED for performance)
                    # if len(websocket_manager.waterfall_clients) > 0:
                    #     waterfall_data = {
                    #         'type': 'waterfall_line',
                    #         'frequencies': spectrum_data['frequencies'],
                    #         'spectrum': spectrum_data['spectrum'],
                    #         'timestamp': spectrum_data['timestamp']
                    #     }
                    #     await websocket_manager.broadcast_waterfall(waterfall_data)
            
            # Get and broadcast audio data if there are audio clients and demod is active
            if sdr_controller.is_running and len(websocket_manager.audio_clients) > 0:
                audio_data = await sdr_controller.get_audio_data()
                if audio_data:
                    await websocket_manager.broadcast_audio(audio_data)
            
            # Control streaming rate
            await asyncio.sleep(1.0 / config.spectrum_fps)
            
        except Exception as e:
            logger.error(f"Error in spectrum streaming task: {e}")
            await asyncio.sleep(1.0)

# Signal handlers
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

# Main entry point
def main():
    """Main entry point for the WebSDR server"""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Update web dependencies in requirements
    logger.info("Starting H1SDR WebSDR Server")
    logger.info(f"Server will be available at: http://{config.host}:{config.port}")
    logger.info(f"API documentation at: http://{config.host}:{config.port}/api/docs")
    logger.info(f"Available bands: {len(EXTENDED_RADIO_BANDS)}")
    
    # Run server
    uvicorn.run(
        "src.web_sdr.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        reload_dirs=["src"] if config.reload else None,
        access_log=config.debug,
        log_level="info" if not config.debug else "debug"
    )

if __name__ == "__main__":
    main()