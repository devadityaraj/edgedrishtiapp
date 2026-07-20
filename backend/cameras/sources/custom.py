"""
Custom camera source plugin.
Power users can subclass CustomCameraSource to implement arbitrary sources.
"""

from typing import Optional, Tuple
import numpy as np
import logging
from .base import BaseCameraSource

logger = logging.getLogger(__name__)


class CustomCameraSource(BaseCameraSource):
    """
    Custom camera source base for plugin implementations.
    
    To add a new custom source:
    1. Subclass this class in a new file under cameras/sources/
    2. Override connect(), read_frame(), and release()
    3. Register it in camera_manager.py SOURCE_MAP
    
    connection_uri format is entirely up to the implementer.
    """

    def __init__(self, camera_id: str, name: str, connection_uri: str):
        super().__init__(camera_id, name, connection_uri)

    def connect(self) -> bool:
        logger.warning(
            f"CustomCameraSource.connect() called on base class for {self.name}. "
            "Subclass this and implement connect()."
        )
        self.last_error = "Custom source not implemented"
        return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        return False, None

    def release(self) -> None:
        self.is_connected = False
