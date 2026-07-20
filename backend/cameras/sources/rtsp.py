"""
RTSP stream camera source.
"""

from typing import Optional, Tuple
import cv2
import numpy as np
import logging
from .base import BaseCameraSource

logger = logging.getLogger(__name__)


class RTSPSource(BaseCameraSource):
    """
    RTSP network stream source (IP cameras, NVRs, etc.).
    connection_uri: full RTSP URL, e.g. rtsp://user:pass@192.168.1.100:554/stream1
    """

    def __init__(self, camera_id: str, name: str, connection_uri: str):
        super().__init__(camera_id, name, connection_uri)
        self._cap: Optional[cv2.VideoCapture] = None

    def connect(self) -> bool:
        try:
            # Use FFMPEG backend for reliable RTSP support
            self._cap = cv2.VideoCapture(self.connection_uri, cv2.CAP_FFMPEG)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            # Set RTSP transport to TCP for stability
            self._cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
            if not self._cap.isOpened():
                self.last_error = f"Could not open RTSP stream: {self.connection_uri}"
                self.is_connected = False
                return False
            self.is_connected = True
            self.last_error = None
            logger.info(f"RTSP camera {self.name} connected: {self.connection_uri}")
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"RTSP connect error: {e}")
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._cap or not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        if not ret:
            self.is_connected = False
            self.last_error = "RTSP stream read failed"
        return ret, frame if ret else None

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
        self.is_connected = False
        logger.info(f"RTSP camera {self.name} released")
