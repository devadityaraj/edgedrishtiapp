"""
EDGE Drishti - WebSocket Real-Time Streaming Manager
Live camera feeds and alert streaming via WebSocket
"""

import asyncio
import json
import cv2
import base64
from typing import Dict, Set, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StreamSubscriber:
    """Represents a WebSocket connection subscribing to streams"""

    def __init__(self, client_id: str, websocket):
        self.client_id = client_id
        self.websocket = websocket
        self.subscribed_cameras: Set[str] = set()
        self.subscribed_alerts: bool = False
        self.created_at = datetime.now()


class WebSocketManager:
    """Central WebSocket connection manager for real-time streaming"""

    def __init__(self):
        self.active_connections: Dict[str, StreamSubscriber] = {}
        self.connection_lock = asyncio.Lock()
        self.max_frame_size = 65000  # JPEG frame size limit for WebSocket
        self.compression_quality = 70  

    async def connect(self, client_id: str, websocket) -> bool:
        """Register new WebSocket connection"""
        try:
            async with self.connection_lock:
                if client_id in self.active_connections:
                    logger.warning(f"Duplicate connection attempt: {client_id}")
                    return False

                subscriber = StreamSubscriber(client_id, websocket)
                self.active_connections[client_id] = subscriber
                logger.info(f"WebSocket connected: {client_id}")
                return True
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            return False

    async def disconnect(self, client_id: str):
        """Unregister WebSocket connection"""
        try:
            async with self.connection_lock:
                if client_id in self.active_connections:
                    del self.active_connections[client_id]
                    logger.info(f"WebSocket disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Disconnection error: {str(e)}")

    async def subscribe_camera(self, client_id: str, camera_id: str) -> bool:
        """Subscribe client to camera stream"""
        try:
            async with self.connection_lock:
                if client_id in self.active_connections:
                    self.active_connections[client_id].subscribed_cameras.add(camera_id)
                    logger.debug(f"Client {client_id} subscribed to camera {camera_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Subscribe camera error: {str(e)}")
            return False

    async def unsubscribe_camera(self, client_id: str, camera_id: str) -> bool:
        """Unsubscribe client from camera stream"""
        try:
            async with self.connection_lock:
                if client_id in self.active_connections:
                    self.active_connections[client_id].subscribed_cameras.discard(camera_id)
                    logger.debug(f"Client {client_id} unsubscribed from camera {camera_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Unsubscribe camera error: {str(e)}")
            return False

    async def subscribe_alerts(self, client_id: str) -> bool:
        """Subscribe client to alert stream"""
        try:
            async with self.connection_lock:
                if client_id in self.active_connections:
                    self.active_connections[client_id].subscribed_alerts = True
                    logger.debug(f"Client {client_id} subscribed to alerts")
                    return True
            return False
        except Exception as e:
            logger.error(f"Subscribe alerts error: {str(e)}")
            return False

    async def broadcast_frame(
        self,
        camera_id: str,
        frame: bytes,
        timestamp: datetime,
        detections: Optional[list] = None
    ):
        """Broadcast frame to all subscribed clients"""
        try:
            # Encode frame to JPEG if it's raw frame
            if isinstance(frame, bytes):
                jpeg_data = frame
            else:
                
                success, jpeg_data = cv2.imencode(
                    '.jpg',
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, self.compression_quality]
                )
                if not success:
                    logger.error("Failed to encode frame")
                    return

            # Encode to base64 for WebSocket transmission
            frame_b64 = base64.b64encode(jpeg_data).decode('utf-8')

            
            message = {
                "type": "frame",
                "camera_id": camera_id,
                "timestamp": timestamp.isoformat(),
                "frame": frame_b64,
                "frame_size": len(jpeg_data),
                "detections": detections or []
            }

            
            disconnected_clients = []
            async with self.connection_lock:
                for client_id, subscriber in self.active_connections.items():
                    if camera_id in subscriber.subscribed_cameras:
                        try:
                            await subscriber.websocket.send_json(message)
                        except Exception as e:
                            logger.warning(f"Failed to send frame to {client_id}: {str(e)}")
                            disconnected_clients.append(client_id)

            
            for client_id in disconnected_clients:
                await self.disconnect(client_id)

        except Exception as e:
            logger.error(f"Broadcast frame error: {str(e)}")

    async def broadcast_alert(self, alert_data: dict):
        """Broadcast alert to all subscribed clients"""
        try:
            message = {
                "type": "alert",
                "data": alert_data
            }

            disconnected_clients = []
            async with self.connection_lock:
                for client_id, subscriber in self.active_connections.items():
                    if subscriber.subscribed_alerts:
                        try:
                            await subscriber.websocket.send_json(message)
                        except Exception as e:
                            logger.warning(f"Failed to send alert to {client_id}: {str(e)}")
                            disconnected_clients.append(client_id)

            
            for client_id in disconnected_clients:
                await self.disconnect(client_id)

        except Exception as e:
            logger.error(f"Broadcast alert error: {str(e)}")

    async def broadcast_status(self, status_data: dict):
        """Broadcast system status to all connected clients"""
        try:
            message = {
                "type": "status",
                "data": status_data
            }

            disconnected_clients = []
            async with self.connection_lock:
                for client_id, subscriber in self.active_connections.items():
                    try:
                        await subscriber.websocket.send_json(message)
                    except Exception as e:
                        logger.warning(f"Failed to send status to {client_id}: {str(e)}")
                        disconnected_clients.append(client_id)

            
            for client_id in disconnected_clients:
                await self.disconnect(client_id)

        except Exception as e:
            logger.error(f"Broadcast status error: {str(e)}")

    async def send_command_response(
        self,
        client_id: str,
        command_id: str,
        success: bool,
        result: Optional[dict] = None
    ):
        """Send command response to specific client"""
        try:
            message = {
                "type": "command_response",
                "command_id": command_id,
                "success": success,
                "result": result or {}
            }

            async with self.connection_lock:
                if client_id in self.active_connections:
                    await self.active_connections[client_id].websocket.send_json(message)
                    return True

            return False
        except Exception as e:
            logger.error(f"Send command response error: {str(e)}")
            return False

    def get_stats(self) -> dict:
        """Get WebSocket manager statistics"""
        return {
            "total_connections": len(self.active_connections),
            "active_subscribers": sum(
                1 for sub in self.active_connections.values()
                if sub.subscribed_cameras or sub.subscribed_alerts
            ),
            "total_camera_subscriptions": sum(
                len(sub.subscribed_cameras)
                for sub in self.active_connections.values()
            ),
            "alert_subscribers": sum(
                1 for sub in self.active_connections.values()
                if sub.subscribed_alerts
            )
        }

    async def receive_message(self, client_id: str, message: dict) -> Optional[dict]:
        """
        Process received WebSocket message

        Returns response to send back to client
        """
        try:
            msg_type = message.get("type")

            if msg_type == "subscribe_camera":
                camera_id = message.get("camera_id")
                success = await self.subscribe_camera(client_id, camera_id)
                return {
                    "type": "subscribe_response",
                    "success": success,
                    "camera_id": camera_id
                }

            elif msg_type == "unsubscribe_camera":
                camera_id = message.get("camera_id")
                success = await self.unsubscribe_camera(client_id, camera_id)
                return {
                    "type": "unsubscribe_response",
                    "success": success,
                    "camera_id": camera_id
                }

            elif msg_type == "subscribe_alerts":
                success = await self.subscribe_alerts(client_id)
                return {
                    "type": "subscribe_alerts_response",
                    "success": success
                }

            elif msg_type == "get_status":
                return {
                    "type": "status",
                    "data": self.get_stats()
                }

            elif msg_type == "ping":
                return {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }

            else:
                logger.warning(f"Unknown message type: {msg_type}")
                return {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                }

        except Exception as e:
            logger.error(f"Message processing error: {str(e)}")
            return {
                "type": "error",
                "message": str(e)
            }



ws_manager = WebSocketManager()
