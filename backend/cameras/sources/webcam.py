"""
Webcam camera source — standard built-in or USB webcam via OpenCV index.
"""

from typing import Optional, Tuple
import cv2
import numpy as np
import logging
from .base import BaseCameraSource

logger = logging.getLogger(__name__)


class WebcamSource(BaseCameraSource):
    """
    Supports built-in webcams and simple USB cameras addressed by device index.
    connection_uri should be a string-encoded integer: "0", "1", etc.
    """

    def __init__(self, camera_id: str, name: str, connection_uri: str, **kwargs):
        super().__init__(camera_id, name, connection_uri, **kwargs)
        self._cap: Optional[cv2.VideoCapture] = None
        try:
            self._index = int(connection_uri)
        except ValueError:
            self._index = 0
            logger.warning(f"Invalid webcam index '{connection_uri}', defaulting to 0")

    def connect(self) -> bool:
        try:
            self._cap = cv2.VideoCapture(self._index)
            if not self._cap.isOpened():
                self.last_error = f"Could not open webcam index {self._index}"
                self.is_connected = False
                return False
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            self._apply_resolution(self._cap)
            self.is_connected = True
            self.last_error = None
            logger.info(f"Webcam {self.name} (index={self._index}) connected")
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"Webcam connect error: {e}")
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
        logger.info(f"Webcam {self.name} released")
