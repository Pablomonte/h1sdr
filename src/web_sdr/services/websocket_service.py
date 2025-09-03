"""
WebSocket Service - Manages WebSocket connections and data broadcasting
High-performance WebSocket management for real-time streaming
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections for different data streams"""
    
    def __init__(self):
        # Different client lists for different data types
        self.spectrum_clients: List[WebSocket] = []
        self.audio_clients: List[WebSocket] = []
        self.waterfall_clients: List[WebSocket] = []
        
        # Unified connection tracking
        self.active_connections: Set[WebSocket] = set()
        
        # Performance tracking
        self.message_counts = {
            'spectrum': 0,
            'audio': 0,
            'waterfall': 0
        }
        
        self.client_stats = {}
        
    @property
    def total_clients(self) -> int:
        """Total number of active clients"""
        return len(self.active_connections)
    
    # Spectrum WebSocket management
    async def connect_spectrum(self, websocket: WebSocket):
        """Connect a spectrum client"""
        await websocket.accept()
        self.spectrum_clients.append(websocket)
        self.active_connections.add(websocket)
        
        client_id = id(websocket)
        self.client_stats[client_id] = {
            'type': 'spectrum',
            'connected_at': asyncio.get_event_loop().time(),
            'messages_sent': 0,
            'bytes_sent': 0
        }
        
        logger.info(f"Spectrum client connected: {client_id} (total: {len(self.spectrum_clients)})")
        
        # Send initial status
        await self._send_safe(websocket, {
            'type': 'connection_status',
            'status': 'connected',
            'stream_type': 'spectrum',
            'client_id': client_id
        })
    
    def disconnect_spectrum(self, websocket: WebSocket):
        """Disconnect a spectrum client"""
        client_id = id(websocket)
        
        if websocket in self.spectrum_clients:
            self.spectrum_clients.remove(websocket)
        
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
        if client_id in self.client_stats:
            del self.client_stats[client_id]
        
        logger.info(f"Spectrum client disconnected: {client_id} (remaining: {len(self.spectrum_clients)})")
    
    # Audio WebSocket management
    async def connect_audio(self, websocket: WebSocket):
        """Connect an audio client"""
        await websocket.accept()
        self.audio_clients.append(websocket)
        self.active_connections.add(websocket)
        
        client_id = id(websocket)
        self.client_stats[client_id] = {
            'type': 'audio',
            'connected_at': asyncio.get_event_loop().time(),
            'messages_sent': 0,
            'bytes_sent': 0
        }
        
        logger.info(f"Audio client connected: {client_id} (total: {len(self.audio_clients)})")
        
        await self._send_safe(websocket, {
            'type': 'connection_status',
            'status': 'connected',
            'stream_type': 'audio',
            'client_id': client_id
        })
    
    def disconnect_audio(self, websocket: WebSocket):
        """Disconnect an audio client"""
        client_id = id(websocket)
        
        if websocket in self.audio_clients:
            self.audio_clients.remove(websocket)
        
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
        if client_id in self.client_stats:
            del self.client_stats[client_id]
        
        logger.info(f"Audio client disconnected: {client_id} (remaining: {len(self.audio_clients)})")
    
    # Waterfall WebSocket management
    async def connect_waterfall(self, websocket: WebSocket):
        """Connect a waterfall client"""
        await websocket.accept()
        self.waterfall_clients.append(websocket)
        self.active_connections.add(websocket)
        
        client_id = id(websocket)
        self.client_stats[client_id] = {
            'type': 'waterfall',
            'connected_at': asyncio.get_event_loop().time(),
            'messages_sent': 0,
            'bytes_sent': 0
        }
        
        logger.info(f"Waterfall client connected: {client_id} (total: {len(self.waterfall_clients)})")
        
        await self._send_safe(websocket, {
            'type': 'connection_status',
            'status': 'connected',
            'stream_type': 'waterfall',
            'client_id': client_id
        })
    
    def disconnect_waterfall(self, websocket: WebSocket):
        """Disconnect a waterfall client"""
        client_id = id(websocket)
        
        if websocket in self.waterfall_clients:
            self.waterfall_clients.remove(websocket)
        
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
        if client_id in self.client_stats:
            del self.client_stats[client_id]
        
        logger.info(f"Waterfall client disconnected: {client_id} (remaining: {len(self.waterfall_clients)})")
    
    # Broadcasting methods
    async def broadcast_spectrum(self, data: Dict[str, Any]):
        """Broadcast spectrum data to all spectrum clients"""
        if not self.spectrum_clients:
            return
        
        message = json.dumps(data)
        message_size = len(message.encode('utf-8'))
        
        # Send to all clients concurrently
        tasks = []
        for websocket in self.spectrum_clients.copy():  # Copy to avoid modification during iteration
            tasks.append(self._send_with_stats(websocket, message, message_size, 'spectrum'))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            self.message_counts['spectrum'] += 1
    
    async def broadcast_audio(self, data: Dict[str, Any]):
        """Broadcast audio data to all audio clients"""
        if not self.audio_clients:
            return
        
        message = json.dumps(data)
        message_size = len(message.encode('utf-8'))
        
        tasks = []
        for websocket in self.audio_clients.copy():
            tasks.append(self._send_with_stats(websocket, message, message_size, 'audio'))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            self.message_counts['audio'] += 1
    
    async def broadcast_waterfall(self, data: Dict[str, Any]):
        """Broadcast waterfall data to all waterfall clients"""
        if not self.waterfall_clients:
            return
        
        message = json.dumps(data)
        message_size = len(message.encode('utf-8'))
        
        tasks = []
        for websocket in self.waterfall_clients.copy():
            tasks.append(self._send_with_stats(websocket, message, message_size, 'waterfall'))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            self.message_counts['waterfall'] += 1
    
    # Helper methods
    async def _send_safe(self, websocket: WebSocket, data: Dict[str, Any]) -> bool:
        """Send data to websocket with error handling"""
        try:
            if isinstance(data, dict):
                message = json.dumps(data)
            else:
                message = str(data)
            
            await websocket.send_text(message)
            return True
        except WebSocketDisconnect:
            # Client disconnected, remove from appropriate lists
            self._handle_disconnect(websocket)
            return False
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            self._handle_disconnect(websocket)
            return False
    
    async def _send_with_stats(self, websocket: WebSocket, message: str, size: int, stream_type: str) -> bool:
        """Send message with statistics tracking"""
        try:
            await websocket.send_text(message)
            
            # Update client stats
            client_id = id(websocket)
            if client_id in self.client_stats:
                self.client_stats[client_id]['messages_sent'] += 1
                self.client_stats[client_id]['bytes_sent'] += size
            
            return True
            
        except WebSocketDisconnect:
            self._handle_disconnect(websocket)
            return False
        except Exception as e:
            logger.error(f"Error sending {stream_type} message: {e}")
            self._handle_disconnect(websocket)
            return False
    
    def _handle_disconnect(self, websocket: WebSocket):
        """Handle client disconnection for all stream types"""
        # Remove from all client lists
        if websocket in self.spectrum_clients:
            self.spectrum_clients.remove(websocket)
        if websocket in self.audio_clients:
            self.audio_clients.remove(websocket)
        if websocket in self.waterfall_clients:
            self.waterfall_clients.remove(websocket)
        
        # Remove from active connections
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Clean up stats
        client_id = id(websocket)
        if client_id in self.client_stats:
            del self.client_stats[client_id]
    
    # Broadcasting utilities
    async def broadcast_status_update(self, status_data: Dict[str, Any]):
        """Broadcast status update to all clients"""
        message = {
            'type': 'status_update',
            'data': status_data,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        # Send to all client types
        tasks = []
        for websocket in self.active_connections.copy():
            tasks.append(self._send_safe(websocket, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def broadcast_error(self, error_message: str, error_type: str = "general"):
        """Broadcast error message to all clients"""
        message = {
            'type': 'error',
            'error_type': error_type,
            'message': error_message,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        tasks = []
        for websocket in self.active_connections.copy():
            tasks.append(self._send_safe(websocket, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    # Statistics and monitoring
    def get_statistics(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics"""
        return {
            'total_clients': self.total_clients,
            'spectrum_clients': len(self.spectrum_clients),
            'audio_clients': len(self.audio_clients),
            'waterfall_clients': len(self.waterfall_clients),
            'message_counts': self.message_counts.copy(),
            'client_details': {
                client_id: {
                    'type': stats['type'],
                    'uptime_seconds': asyncio.get_event_loop().time() - stats['connected_at'],
                    'messages_sent': stats['messages_sent'],
                    'bytes_sent': stats['bytes_sent']
                }
                for client_id, stats in self.client_stats.items()
            }
        }
    
    async def send_ping_to_all(self):
        """Send ping to all clients to keep connections alive"""
        ping_message = {
            'type': 'ping',
            'timestamp': asyncio.get_event_loop().time()
        }
        
        tasks = []
        for websocket in self.active_connections.copy():
            tasks.append(self._send_safe(websocket, ping_message))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            failed_count = sum(1 for result in results if not result)
            if failed_count > 0:
                logger.debug(f"Ping failed for {failed_count} clients")
    
    async def cleanup(self):
        """Cleanup all WebSocket connections"""
        logger.info("Cleaning up WebSocket connections...")
        
        # Send disconnect message to all clients
        disconnect_message = {
            'type': 'server_disconnect',
            'message': 'Server shutting down',
            'timestamp': asyncio.get_event_loop().time()
        }
        
        tasks = []
        for websocket in self.active_connections.copy():
            tasks.append(self._send_safe(websocket, disconnect_message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Clear all client lists
        self.spectrum_clients.clear()
        self.audio_clients.clear()
        self.waterfall_clients.clear()
        self.active_connections.clear()
        self.client_stats.clear()
        
        logger.info("WebSocket cleanup completed")