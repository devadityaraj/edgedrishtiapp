"""
IP camera source — generic HTTP MJPEG stream.
"""

from typing import Optional, Tuple
import cv2
import numpy as np
import logging
from .base import BaseCameraSource

logger = logging.getLogger(__name__)


class IPCameraSource(BaseCameraSource):
    """
    Generic IP camera via HTTP MJPEG stream.
    connection_uri: HTTP URL, e.g. http://192.168.1.50/video.cgi
    """

    def __init__(self, camera_id: str, name: str, connection_uri: str):
        super().__init__(camera_id, name, connection_uri)
        self._cap: Optional[cv2.VideoCapture] = None

    def connect(self) -> bool:
        try:
            self._cap = cv2.VideoCapture(self.connection_uri)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            if not self._cap.isOpened():
                self.last_error = f"Could not open IP camera: {self.connection_uri}"
                self.is_connected = False
                return False
            self.is_connected = True
            self.last_error = None
            logger.info(f"IP camera {self.name} connected")
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"IP camera connect error: {e}")
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._cap or not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        if not ret:
            self.is_connected = False
            self.last_error = "IP camera stream read failed"
        return ret, frame if ret else None

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
        self.is_connected = False
        logger.info(f"IP camera {self.name} released")
