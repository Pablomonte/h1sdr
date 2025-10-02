#!/usr/bin/env python3
"""
H1SDR WebSDR Main Server v2.0
FastAPI-based web interface with plugin supervisor architecture
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
from .controllers.sdr_controller_v2 import WebSDRControllerV2
from .utils.logging_config import setup_logging, get_logger
from .utils.error_handler import error_handler

# Setup structured logging (v2.0)
log_config = setup_logging(
    log_dir=Path("logs") if config.enable_logging else None,
    console_level="DEBUG" if config.debug else config.log_level,
    file_level="DEBUG",
    enable_json=config.enable_json_logs,
    component_levels={
        'controllers.sdr_controller_v2': 'INFO',
        'pipeline.plugin_supervisor': 'INFO',
        'plugins': 'INFO',
        'uvicorn.access': 'WARNING',  # Reduce HTTP access log noise
    }
)
logger = get_logger(__name__)

# Global instances - v2.0 with plugin supervisor
websocket_manager = WebSocketManager()
sdr_controller = WebSDRControllerV2()  # v2.0 with plugin architecture


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting H1SDR WebSDR server v2.0...")
    logger.info("Plugin-based architecture with supervisor pattern")

    # Startup
    try:
        # Initialize SDR controller v2.0
        await sdr_controller.initialize()
        logger.info("SDR controller v2.0 initialized")
        logger.info(f"Active plugins: {len(sdr_controller.plugins)}")

        # Start background tasks
        asyncio.create_task(spectrum_streaming_task())
        logger.info("Background tasks started")

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down H1SDR WebSDR server v2.0...")
    try:
        await sdr_controller.cleanup()
        await websocket_manager.cleanup()
        logger.info("Cleanup completed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


# Create FastAPI application
app = FastAPI(
    title="H1SDR WebSDR v2.0",
    description="Multi-band Software Defined Radio with Plugin Architecture",
    version="2.0.0",
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
            content=f"""
            <html>
                <head><title>H1SDR WebSDR v2.0</title></head>
                <body>
                    <h1>H1SDR WebSDR v2.0</h1>
                    <p>Plugin-based architecture with supervisor pattern</p>
                    <p>Frontend not yet built. Check <a href="/api/docs">/api/docs</a> for API documentation.</p>
                    <h2>Available Bands ({len(EXTENDED_RADIO_BANDS)}):</h2>
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
    """Health check endpoint with v2.0 info"""
    status = await sdr_controller.get_status()
    return {
        "status": "ok",
        "version": "2.0.0",
        "architecture": "plugin-supervisor",
        "sdr_connected": sdr_controller.is_connected,
        "active_connections": len(websocket_manager.active_connections),
        "plugins": len(sdr_controller.plugins) if sdr_controller.plugins else 0,
        "plugin_supervisor": status.get('plugin_supervisor', {})
    }


# SDR Status
@app.get("/api/sdr/status")
async def get_sdr_status():
    """Get current SDR status with plugin info"""
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
            "message": "SDR v2.0 started successfully",
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


# Plugin management endpoints (new in v2.0)
@app.get("/api/plugins")
async def get_plugins():
    """Get list of active plugins"""
    try:
        plugins_info = [
            {
                'name': p.name,
                'enabled': p.enabled,
                'stats': p.get_stats()
            }
            for p in sdr_controller.plugins
        ]
        return {
            "success": True,
            "data": plugins_info
        }
    except Exception as e:
        logger.error(f"Error getting plugins: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plugins/{plugin_name}/enable")
async def enable_plugin(plugin_name: str):
    """Enable a specific plugin"""
    try:
        for plugin in sdr_controller.plugins:
            if plugin.name == plugin_name:
                plugin.enable()
                return {
                    "success": True,
                    "message": f"Plugin {plugin_name} enabled"
                }
        raise HTTPException(status_code=404, detail="Plugin not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling plugin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plugins/{plugin_name}/disable")
async def disable_plugin(plugin_name: str):
    """Disable a specific plugin"""
    try:
        for plugin in sdr_controller.plugins:
            if plugin.name == plugin_name:
                plugin.disable()
                return {
                    "success": True,
                    "message": f"Plugin {plugin_name} disabled"
                }
        raise HTTPException(status_code=404, detail="Plugin not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling plugin: {e}")
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
    """Background task for streaming spectrum data with v2.0 controller"""
    logger.info("Starting spectrum streaming task (v2.0 with plugin supervisor)")

    while True:
        try:
            if sdr_controller.is_running and len(websocket_manager.spectrum_clients) > 0:
                # Get spectrum data from SDR controller v2.0
                spectrum_data = await sdr_controller.get_spectrum_data()
                if spectrum_data:
                    # Broadcast to all spectrum clients
                    await websocket_manager.broadcast_spectrum(spectrum_data)

            # Get and broadcast audio data if there are audio clients
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
    """Main entry point for the WebSDR server v2.0"""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Update web dependencies in requirements
    logger.info("Starting H1SDR WebSDR Server v2.0")
    logger.info("Architecture: Plugin Supervisor Pattern")
    logger.info(f"Server will be available at: http://{config.host}:{config.port}")
    logger.info(f"API documentation at: http://{config.host}:{config.port}/api/docs")
    logger.info(f"Available bands: {len(EXTENDED_RADIO_BANDS)}")

    # Run server
    uvicorn.run(
        "src.web_sdr.main_v2:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        reload_dirs=["src"] if config.reload else None,
        access_log=config.debug,
        log_level="info" if not config.debug else "debug"
    )


if __name__ == "__main__":
    main()
