"""
USB capture device source.
Enumerated separately from webcams; uses DirectShow on Windows, V4L2 on Linux.
"""

from typing import Optional, Tuple
import cv2
import numpy as np
import logging
import sys
from .base import BaseCameraSource

logger = logging.getLogger(__name__)


class USBCameraSource(BaseCameraSource):
    """
    USB capture device (e.g., capture cards, external USB cameras).
    connection_uri: device path or index, e.g. "/dev/video2" or "2"
    On Windows, integer index is used. On Linux, /dev/videoN path supported.
    """

    def __init__(self, camera_id: str, name: str, connection_uri: str, **kwargs):
        super().__init__(camera_id, name, connection_uri, **kwargs)
        self._cap: Optional[cv2.VideoCapture] = None

    def _parse_source(self):
        uri = self.connection_uri.strip()
        if uri.startswith("/dev/"):
            return uri  
        try:
            return int(uri)
        except ValueError:
            return uri  

    def connect(self) -> bool:
        try:
            source = self._parse_source()
            if sys.platform == "win32" and isinstance(source, int):
                self._cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            else:
                self._cap = cv2.VideoCapture(source)
            if not self._cap.isOpened():
                self.last_error = f"Could not open USB camera: {self.connection_uri}"
                self.is_connected = False
                return False
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            self._apply_resolution(self._cap)
            self.is_connected = True
            self.last_error = None
            logger.info(f"USB camera {self.name} connected: {self.connection_uri}")
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"USB camera connect error: {e}")
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._cap or not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        if not ret:
            self.is_connected = False
            self.last_error = "Frame read failed"
        return ret, frame if ret else None

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
        self.is_connected = False
        logger.info(f"USB camera {self.name} released")
