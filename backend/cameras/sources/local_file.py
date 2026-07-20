"""
Local video file source — MP4, AVI, MKV, etc.
Supports looping for continuous playback in testing scenarios.
"""

from typing import Optional, Tuple
from pathlib import Path
import cv2
import numpy as np
import logging
from .base import BaseCameraSource

logger = logging.getLogger(__name__)


class LocalFileSource(BaseCameraSource):
    """
    Local video file source.
    connection_uri: absolute path to video file (MP4, AVI, MKV, MOV, etc.)
    """

    SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".ts"}

    def __init__(self, camera_id: str, name: str, connection_uri: str, loop: bool = False):
        super().__init__(camera_id, name, connection_uri)
        self._cap: Optional[cv2.VideoCapture] = None
        self._loop = loop
        self._path = Path(connection_uri)

    def connect(self) -> bool:
        try:
            if not self._path.exists():
                self.last_error = f"File not found: {self._path}"
                self.is_connected = False
                return False
            if self._path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                logger.warning(f"Potentially unsupported file extension: {self._path.suffix}")
            self._cap = cv2.VideoCapture(str(self._path))
            if not self._cap.isOpened():
                self.last_error = f"Could not open video file: {self._path}"
                self.is_connected = False
                return False
            self.is_connected = True
            self.last_error = None
            logger.info(f"Local file {self.name} opened: {self._path}")
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"Local file connect error: {e}")
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._cap or not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        if not ret:
            if self._loop:
                
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
            if not ret:
                self.is_connected = False
                self.last_error = "End of video file (no loop)"
        return ret, frame if ret else None

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
        self.is_connected = False
        logger.info(f"Local file {self.name} released")
