"""
EDGE Drishti — Camera Manager
Manages camera capture workers, per-camera frame queues, and health watchdog.
Each camera runs in its own daemon thread; frames are placed into an asyncio queue
and consumed by the AI pipeline and WebSocket broadcaster.
"""

import asyncio
import threading
import time
import uuid
import queue
import base64
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any, Callable

import cv2
import numpy as np

from backend.core.config import config
from backend.db.session import DatabaseManager
from backend.db.models import Camera, CameraStatus

logger = logging.getLogger(__name__)


SOURCE_MAP: Dict[str, type] = {}

def _build_source_map():
    global SOURCE_MAP
    try:
        from backend.cameras.sources.webcam import WebcamSource
        SOURCE_MAP["webcam"] = WebcamSource
    except Exception as e:
        logger.warning(f"Webcam source unavailable: {e}")
    try:
        from backend.cameras.sources.usb import USBCameraSource
        SOURCE_MAP["usb"] = USBCameraSource
        SOURCE_MAP["capture_card"] = USBCameraSource
    except Exception as e:
        logger.warning(f"USB source unavailable: {e}")
    try:
        from backend.cameras.sources.rtsp import RTSPSource
        SOURCE_MAP["rtsp"] = RTSPSource
    except Exception as e:
        logger.warning(f"RTSP source unavailable: {e}")
    try:
        from backend.cameras.sources.ip_camera import IPCameraSource
        SOURCE_MAP["ip"] = IPCameraSource
    except Exception as e:
        logger.warning(f"IP camera source unavailable: {e}")
    try:
        from backend.cameras.sources.http_stream import HTTPStreamSource
        SOURCE_MAP["http"] = HTTPStreamSource
    except Exception as e:
        logger.warning(f"HTTP stream source unavailable: {e}")
    try:
        from backend.cameras.sources.udp import UDPSource
        SOURCE_MAP["udp"] = UDPSource
    except Exception as e:
        logger.warning(f"UDP source unavailable: {e}")
    try:
        from backend.cameras.sources.local_file import LocalFileSource
        SOURCE_MAP["local_file"] = LocalFileSource
    except Exception as e:
        logger.warning(f"Local file source unavailable: {e}")
    try:
        from backend.cameras.sources.custom import CustomCameraSource
        SOURCE_MAP["custom"] = CustomCameraSource
    except Exception as e:
        logger.warning(f"Custom source unavailable: {e}")


_build_source_map()



class CameraWorker:
    """
    Runs in a daemon thread; continuously reads frames from a source,
    JPEG-encodes them, and pushes into a thread-safe queue consumed by
    the AI pipeline and WS broadcaster.
    """

    BACKOFF_SCHEDULE = [5, 10, 20, 40, 80, 120, 300]  

    def __init__(self, camera_id: str, name: str, source_type: str, connection_uri: str, resolution: str = "default"):
        self.camera_id = camera_id
        self.name = name
        self.source_type = source_type
        self.connection_uri = connection_uri
        self.resolution = resolution

        # Frame queue: (timestamp, jpeg_bytes)
        self.frame_queue: queue.Queue = queue.Queue(maxsize=6)
        self.latest_frame_bytes: Optional[bytes] = None
        self.latest_frame_ts: Optional[datetime] = None

        self.status: str = "offline"
        self.last_seen_at: Optional[datetime] = None
        self.reconnect_attempts: int = 0
        self.last_error: Optional[str] = None
        self.fps: float = 0.0
        self._fps_counter = 0
        self._fps_ts = time.time()

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._source = None

        
        self._on_status_change: Optional[Callable] = None

    def start(self, on_status_change: Optional[Callable] = None):
        self._on_status_change = on_status_change
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"cam-{self.camera_id[:8]}",
            daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=8)
        # Safety-cleanup: only release if the worker thread didn't already do it.
        # Calling cap.release() while V4L2 ioctl is in-flight causes the
        # 'ioctl(VIDIOC_QBUF): Bad file descriptor' kernel message.
        # _source is set to None by the thread's own cleanup after release().
        if self._source is not None:
            try:
                self._source.release()
            except Exception:
                pass
            self._source = None
        self._update_status("offline")

    def get_latest_jpeg(self) -> Optional[bytes]:
        return self.latest_frame_bytes

    def _build_source(self):
        src_cls = SOURCE_MAP.get(self.source_type)
        if not src_cls:
            logger.error(f"Unknown source type '{self.source_type}' for camera {self.name}")
            return None
        return src_cls(self.camera_id, self.name, self.connection_uri, resolution=self.resolution)

    def _update_status(self, status: str, error: Optional[str] = None):
        self.status = status
        self.last_error = error
        if status == "online":
            self.last_seen_at = datetime.utcnow()
        if self._on_status_change:
            try:
                self._on_status_change(self.camera_id, status, error)
            except Exception:
                pass

    def _should_retry_connection(self, source_type: str, error: Optional[str] = None) -> bool:
        if source_type in {"webcam", "usb", "capture_card", "local_file"}:
            return False

        error_text = (error or "").lower()
        if any(token in error_text for token in [
            "camera index out of range",
            "can't open camera",
            "inappropriate ioctl",
            "device not found",
            "no such file",
            "videoio",
        ]):
            return False

        return True

    def _run(self):
        backoff_idx = 0
        while not self._stop_event.is_set():
            
            self._update_status("reconnecting")
            source = self._build_source()
            if source is None:
                time.sleep(30)
                continue
            self._source = source
            connected = source.connect()
            if not connected:
                self.reconnect_attempts += 1
                error_text = source.last_error or "Connection failed"
                if not self._should_retry_connection(self.source_type, error_text):
                    self._update_status("offline", error_text)
                    logger.warning(f"Camera {self.name} unavailable ({error_text}); leaving offline")
                    return

                wait = self.BACKOFF_SCHEDULE[min(backoff_idx, len(self.BACKOFF_SCHEDULE) - 1)]
                backoff_idx += 1
                self._update_status("error", error_text)
                logger.warning(
                    f"Camera {self.name} failed to connect (attempt {self.reconnect_attempts}), "
                    f"retrying in {wait}s"
                )
                for _ in range(wait * 10):
                    if self._stop_event.is_set():
                        return
                    time.sleep(0.1)
                continue

            
            backoff_idx = 0
            self.reconnect_attempts = 0
            self._update_status("online")
            logger.info(f"Camera {self.name} online")
            consecutive_failures = 0

            while not self._stop_event.is_set():
                ret, frame = source.read_frame()
                if not ret or frame is None:
                    if self.source_type == "local_file":
                        logger.info(f"Local file {self.name} finished playback. Stopping worker thread.")
                        source.release()
                        self._source = None
                        self._update_status("offline")
                        return
                    consecutive_failures += 1
                    if consecutive_failures > 10:
                        logger.warning(f"Camera {self.name}: too many consecutive failures, reconnecting")
                        break
                    time.sleep(0.05)
                    continue

                consecutive_failures = 0
                self.last_seen_at = datetime.utcnow()
                ts = datetime.utcnow()

                
                ok, buf = cv2.imencode(
                    ".jpg", frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 75]
                )
                if not ok:
                    continue

                jpeg_bytes = buf.tobytes()
                self.latest_frame_bytes = jpeg_bytes
                self.latest_frame_ts = ts

                # Non-blocking put (drop old frame if queue full)
                try:
                    self.frame_queue.put_nowait((ts, jpeg_bytes, frame))
                except queue.Full:
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self.frame_queue.put_nowait((ts, jpeg_bytes, frame))
                    except queue.Full:
                        pass

                
                self._fps_counter += 1
                now = time.time()
                if now - self._fps_ts >= 1.0:
                    self.fps = self._fps_counter / (now - self._fps_ts)
                    self._fps_counter = 0
                    self._fps_ts = now

            # Cleanup after inner loop exits (only if not already released)
            if self._source is not None:
                source.release()
                self._source = None
            if not self._stop_event.is_set():
                self._update_status("offline")

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "source_type": self.source_type,
            "status": self.status,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "reconnect_attempts": self.reconnect_attempts,
            "fps": round(self.fps, 1),
            "last_error": self.last_error,
        }



class CameraManager:
    """Central registry and lifecycle manager for all camera workers."""

    def __init__(self):
        self._workers: Dict[str, CameraWorker] = {}
        self._lock = threading.Lock()
        self._ws_callback: Optional[Callable] = None

    def set_ws_callback(self, callback: Callable):
        """Register WebSocket broadcast callback: fn(camera_id, status, error)"""
        self._ws_callback = callback

    def _on_status_change(self, camera_id: str, status: str, error: Optional[str]):
        """Persist status to DB and notify WS clients"""
        try:
            db = DatabaseManager.get_session()
            try:
                cam = db.query(Camera).filter(Camera.id == camera_id).first()
                if cam:
                    cam.status = status
                    if status == "online":
                        cam.last_seen_at = datetime.utcnow()
                    if error:
                        cam.last_error = error
                    if status in ("online", "offline", "error", "reconnecting"):
                        from backend.db.models import CameraStatus as CS
                        cam.status = CS(status) if status in [e.value for e in CS] else CS.OFFLINE
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error persisting camera status: {e}")

        if self._ws_callback:
            try:
                self._ws_callback(camera_id, status, error)
            except Exception:
                pass

    def load_from_db(self):
        """Load and start all cameras stored in DB on startup."""
        try:
            db = DatabaseManager.get_session()
            try:
                cameras = db.query(Camera).all()
                for cam in cameras:
                    uri = cam.connection_uri_encrypted  # NOTE: decrypt if encrypted
                    self.add_camera(
                        camera_id=cam.id,
                        name=cam.name,
                        source_type=cam.source_type,
                        connection_uri=uri,
                        resolution=getattr(cam, 'resolution', 'default') or 'default'
                    )
                logger.info(f"Loaded {len(cameras)} cameras from DB")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to load cameras from DB: {e}")

    def add_camera(self, camera_id: str, name: str, source_type: str, connection_uri: str, resolution: str = 'default') -> CameraWorker:
        with self._lock:
            if camera_id in self._workers:
                logger.warning(f"Camera {camera_id} already running; restarting")
                self._workers[camera_id].stop()
            worker = CameraWorker(camera_id, name, source_type, connection_uri, resolution=resolution)
            self._workers[camera_id] = worker
            worker.start(on_status_change=self._on_status_change)
            logger.info(f"Camera worker started: {name} ({source_type})")
            return worker

    def remove_camera(self, camera_id: str) -> bool:
        with self._lock:
            worker = self._workers.pop(camera_id, None)
        if worker:
            worker.stop()
            logger.info(f"Camera worker stopped: {worker.name}")
            return True
        return False

    def restart_camera(self, camera_id: str) -> bool:
        with self._lock:
            worker = self._workers.get(camera_id)
        if not worker:
            return False
        resolution = getattr(worker, 'resolution', 'default')
        worker.stop()
        new_worker = CameraWorker(
            worker.camera_id,
            worker.name,
            worker.source_type,
            worker.connection_uri,
            resolution=resolution,
        )
        with self._lock:
            self._workers[camera_id] = new_worker
        new_worker.start(on_status_change=self._on_status_change)
        return True

    def get_worker(self, camera_id: str) -> Optional[CameraWorker]:
        return self._workers.get(camera_id)

    def get_all_workers(self) -> Dict[str, CameraWorker]:
        return dict(self._workers)

    def get_latest_jpeg(self, camera_id: str) -> Optional[bytes]:
        w = self._workers.get(camera_id)
        return w.get_latest_jpeg() if w else None

    def get_status_all(self) -> list:
        return [w.to_dict() for w in self._workers.values()]

    def shutdown(self):
        logger.info("Shutting down all camera workers...")
        with self._lock:
            ids = list(self._workers.keys())
        for cid in ids:
            self.remove_camera(cid)
        logger.info("All camera workers stopped")



camera_manager = CameraManager()
