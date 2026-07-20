"""
Base camera source interface.
All camera adapters must implement this abstract class.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class BaseCameraSource(ABC):
    """
    Abstract base class for all camera/stream sources.
    Implement this to add a new camera type without touching core code.
    """

    def __init__(self, camera_id: str, name: str, connection_uri: str, resolution: str = "default"):
        self.camera_id = camera_id
        self.name = name
        self.connection_uri = connection_uri
        self.resolution = resolution
        self.is_connected = False
        self.last_error: Optional[str] = None

    def _apply_resolution(self, cap: cv2.VideoCapture) -> None:
        if not self.resolution or self.resolution == "default":
            return
            
        res_map = {
            "4k": (3840, 2160),
            "2k": (2560, 1440),
            "1080": (1920, 1080),
            "720": (1280, 720),
            "480": (640, 480),
            "240": (320, 240)
        }
        if self.resolution not in res_map:
            return
            
        target_w, target_h = res_map[self.resolution]
        
        default_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        default_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        
        if target_w > default_w or target_h > default_h:
            logger.info(f"Target resolution {self.resolution} ({target_w}x{target_h}) is higher than incoming {int(default_w)}x{int(default_h)}, using default.")
            return
            
        logger.info(f"Setting resolution for camera {self.name} to {self.resolution} ({target_w}x{target_h})")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_h)

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the camera/source.
        Returns True on success, False on failure.
        Sets self.is_connected and self.last_error accordingly.
        """
        pass

    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a single frame from the source.
        Returns (success: bool, frame: Optional[np.ndarray])
        Frame is None if success is False.
        """
        pass

    @abstractmethod
    def release(self) -> None:
        """Release all resources (close connections, files, etc.)."""
        pass

    def get_info(self) -> dict:
        """Return metadata about this source."""
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "source_type": self.__class__.__name__,
            "connection_uri": self.connection_uri,
            "is_connected": self.is_connected,
            "last_error": self.last_error,
        }
