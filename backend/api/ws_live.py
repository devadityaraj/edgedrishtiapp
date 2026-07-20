"""
WebSocket live endpoints:
  /ws/live — multiplexed: subscribe to camera frames, detection events, system stats
"""

import asyncio
import base64
import json
import logging
import uuid
from typing import Dict, Set, Optional
from datetime import datetime
from threading import Lock

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


class _WsConnection:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.subscribed_cameras: Set[str] = set()
        self.subscribed_events: bool = True
        self.subscribed_system: bool = False


_connections: Dict[str, _WsConnection] = {}
_conn_lock = Lock()


def _get_conn(client_id: str) -> Optional[_WsConnection]:
    return _connections.get(client_id)



def ws_frame_broadcast(camera_id: str, jpeg_bytes: bytes, timestamp: str, detections: list):
    """
    Thread-safe: called from inference thread to push an annotated frame to
    all WebSocket clients subscribed to this camera.
    """
    frame_b64 = base64.b64encode(jpeg_bytes).decode()
    msg = json.dumps({
        "type": "frame",
        "camera_id": camera_id,
        "timestamp": timestamp,
        "frame": frame_b64,
        "detections": detections,
    })
    with _conn_lock:
        dead = []
        for cid, conn in list(_connections.items()):
            if camera_id in conn.subscribed_cameras:
                try:
                    asyncio.run_coroutine_threadsafe(
                        _safe_send(conn.ws, msg),
                        _get_event_loop()
                    )
                except Exception:
                    dead.append(cid)
        for cid in dead:
            _connections.pop(cid, None)


_loop: Optional[asyncio.AbstractEventLoop] = None

def _get_event_loop():
    global _loop
    if _loop is None or _loop.is_closed():
        raise RuntimeError("WebSocket event loop is not initialized")
    return _loop


async def _safe_send(ws: WebSocket, msg: str):
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_text(msg)
    except Exception:
        pass


async def _broadcast_system_stats():
    """Periodically broadcast system stats to subscribed clients."""
    from backend.system.resource_monitor import resource_monitor
    while True:
        await asyncio.sleep(2)
        stats = resource_monitor.get_stats()
        msg = json.dumps({"type": "system_stats", "data": stats})
        with _conn_lock:
            for conn in list(_connections.values()):
                if conn.subscribed_system:
                    asyncio.create_task(_safe_send(conn.ws, msg))



@router.websocket("/ws/live")
async def ws_live(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    Multiplexed WebSocket endpoint.

    After connecting, send JSON control messages:
      {"type": "subscribe_camera", "camera_id": "<id>"}
      {"type": "unsubscribe_camera", "camera_id": "<id>"}
      {"type": "subscribe_system"}
      {"type": "ping"}

    The server will push:
      {"type": "frame", "camera_id": ..., "frame": "<base64 jpeg>", "detections": [...]}
      {"type": "alert", "data": {...}}
      {"type": "system_stats", "data": {...}}
      {"type": "pong"}
    """
    
    try:
        from backend.security.tokens import get_current_user_from_token
        user = get_current_user_from_token(token)
        if user is None:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    client_id = str(uuid.uuid4())
    conn = _WsConnection(websocket)

    with _conn_lock:
        _connections[client_id] = conn

    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.get_running_loop()

    
    global _stats_task_started
    if not _stats_task_started:
        asyncio.create_task(_broadcast_system_stats())
        _stats_task_started = True

    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "client_id": client_id,
            "user": user.username,
        }))

        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(raw)
            except asyncio.TimeoutError:
                
                await _safe_send(websocket, json.dumps({"type": "ping"}))
                continue
            except Exception:
                break

            msg_type = msg.get("type")

            if msg_type == "subscribe_camera":
                cam_id = msg.get("camera_id")
                if cam_id:
                    conn.subscribed_cameras.add(cam_id)
                    await websocket.send_text(json.dumps({
                        "type": "subscribed_camera",
                        "camera_id": cam_id,
                    }))

            elif msg_type == "unsubscribe_camera":
                cam_id = msg.get("camera_id")
                conn.subscribed_cameras.discard(cam_id)

            elif msg_type == "subscribe_system":
                conn.subscribed_system = True

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                }))

            
            elif msg_type == "get_latest_frame":
                cam_id = msg.get("camera_id")
                if cam_id:
                    from backend.cameras.camera_manager import camera_manager
                    jpeg = camera_manager.get_latest_jpeg(cam_id)
                    if jpeg:
                        await websocket.send_text(json.dumps({
                            "type": "frame",
                            "camera_id": cam_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "frame": base64.b64encode(jpeg).decode(),
                            "detections": [],
                        }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WS error: {e}")
    finally:
        with _conn_lock:
            _connections.pop(client_id, None)


_stats_task_started = False
