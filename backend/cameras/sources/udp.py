"""
UDP/RTP stream source.
"""

from typing import Optional, Tuple
import cv2
import numpy as np
import logging
from .base import BaseCameraSource

logger = logging.getLogger(__name__)


class UDPSource(BaseCameraSource):
    """
    UDP/RTP stream source.
    connection_uri: udp://@0.0.0.0:1234 or udpsrc port=1234 format.
    Falls back to OpenCV's GStreamer pipeline if available.
    """

    def __init__(self, camera_id: str, name: str, connection_uri: str):
        super().__init__(camera_id, name, connection_uri)
        self._cap: Optional[cv2.VideoCapture] = None

    def _build_gst_pipeline(self) -> str:
        """Build GStreamer pipeline for UDP source"""
        uri = self.connection_uri
        
        if uri.isdigit():
            port = int(uri)
            return (
                f"udpsrc port={port} ! application/x-rtp,payload=96 ! "
                "rtph264depay ! h264parse ! decodebin ! "
                "videoconvert ! appsink"
            )
        # Otherwise use the URI directly (e.g. udp://@0.0.0.0:1234)
        return uri

    def connect(self) -> bool:
        try:
            uri = self.connection_uri
            
            if uri.startswith("udp://"):
                self._cap = cv2.VideoCapture(uri)
            else:
                
                pipeline = self._build_gst_pipeline()
                self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            if not self._cap.isOpened():
                
                self._cap = cv2.VideoCapture(uri)
            if not self._cap.isOpened():
                self.last_error = f"Could not open UDP stream: {uri}"
                self.is_connected = False
                return False
            self.is_connected = True
            self.last_error = None
            logger.info(f"UDP stream {self.name} connected")
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"UDP stream connect error: {e}")
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._cap or not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        if not ret:
            self.is_connected = False
            self.last_error = "UDP stream read failed"
        return ret, frame if ret else None

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
        self.is_connected = False
        logger.info(f"UDP stream {self.name} released")
