"""
HTTP/HTTPS stream source.
"""

from typing import Optional, Tuple
import cv2
import numpy as np
import logging
from .base import BaseCameraSource

logger = logging.getLogger(__name__)


class HTTPStreamSource(BaseCameraSource):
    """
    HTTP or HTTPS video stream source (MJPEG, HLS, or direct MP4/stream URLs).
    connection_uri: full HTTP/HTTPS URL
    """

    def __init__(self, camera_id: str, name: str, connection_uri: str):
        super().__init__(camera_id, name, connection_uri)
        self._cap: Optional[cv2.VideoCapture] = None

    def connect(self) -> bool:
        try:
            self._cap = cv2.VideoCapture(self.connection_uri)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            if not self._cap.isOpened():
                self.last_error = f"Could not open HTTP stream: {self.connection_uri}"
                self.is_connected = False
                return False
            self.is_connected = True
            self.last_error = None
            logger.info(f"HTTP stream {self.name} connected")
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"HTTP stream connect error: {e}")
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._cap or not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        if not ret:
            self.is_connected = False
            self.last_error = "HTTP stream read failed"
        return ret, frame if ret else None

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
        self.is_connected = False
        logger.info(f"HTTP stream {self.name} released")
