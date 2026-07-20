"""
Base AI model interface.
All detection models must implement this abstract class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Detection:
    """A single detection result from any model."""
    __slots__ = ("label", "confidence", "bbox", "track_id", "extra")

    def __init__(
        self,
        label: str,
        confidence: float,
        bbox: tuple,  # (x1, y1, x2, y2) pixels
        track_id: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.label = label
        self.confidence = confidence
        self.bbox = bbox
        self.track_id = track_id
        self.extra = extra or {}

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": round(float(self.confidence), 4),
            "bbox": list(self.bbox),
            "track_id": self.track_id,
            "extra": self.extra,
        }


class BaseAIModel(ABC):
    """Abstract base for all EDGE Drishti AI detection models."""

    
    MODEL_KEY: str = "base"
    DISPLAY_NAME: str = "Base Model"

    def __init__(self):
        self.is_loaded: bool = False
        self.device: str = "cpu"
        self.confidence_threshold: float = 0.5
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def load(self, device: str = "cpu", config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Load model weights. Return True on success.
        Must set self.is_loaded = True on success.
        Must NOT raise — log and return False instead.
        """
        pass

    @abstractmethod
    def infer(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference on a BGR OpenCV frame.
        Returns a list of Detection objects (empty list = no detections).
        Must NOT raise — log errors and return [] instead.
        """
        pass

    def unload(self) -> None:
        """Release model weights and free memory. Override if needed."""
        self.is_loaded = False

    def set_confidence_threshold(self, threshold: float) -> None:
        self.confidence_threshold = max(0.01, min(1.0, threshold))

    def get_info(self) -> dict:
        return {
            "key": self.MODEL_KEY,
            "name": self.DISPLAY_NAME,
            "is_loaded": self.is_loaded,
            "device": self.device,
            "confidence_threshold": self.confidence_threshold,
        }
