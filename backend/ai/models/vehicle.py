"""
Vehicle detection model using YOLOv8.
Detects vehicles (bicycle, car, motorcycle, airplane, bus, train, truck, boat).
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import numpy as np
import logging
import json
from .base_model import BaseAIModel, Detection

logger = logging.getLogger(__name__)


_CUSTOM_CONFIG = Path(__file__).parent.parent.parent.parent / "AImodels" / "yolo" / "config.json"


class VehicleDetectionModel(BaseAIModel):
    MODEL_KEY = "vehicle"
    DISPLAY_NAME = "Vehicle Detection"

    # COCO classes for vehicles:
    
    VEHICLE_CLASS_IDS = [1, 2, 3, 4, 5, 6, 7, 8]

    def __init__(self):
        super().__init__()
        self._model = None
        self.confidence_threshold = 0.5

    def load(self, device: str = "cpu", config: Optional[Dict[str, Any]] = None) -> bool:
        try:
            if _CUSTOM_CONFIG.exists():
                try:
                    with open(_CUSTOM_CONFIG) as f:
                        file_config = json.load(f)
                    self.confidence_threshold = file_config.get("confidence_threshold", 0.5)
                    self._logger.info(f"Vehicle config loaded from {_CUSTOM_CONFIG}")
                except Exception as e:
                    self._logger.warning(f"Failed to load config.json: {e}")

            from backend.ai.shared_yolo import SharedYOLOManager
            self._model = SharedYOLOManager.get_model()
            self._logger.info(f"Vehicle model loaded on {device}")

            self.device = device
            self.is_loaded = True
            if config:
                self.confidence_threshold = config.get("confidence_threshold", self.confidence_threshold)
            return True
        except ImportError:
            self._logger.warning("ultralytics not installed — VehicleDetection disabled")
            return False
        except Exception as e:
            self._logger.error(f"Failed to load vehicle model: {e}")
            return False

    def infer(self, frame: np.ndarray) -> List[Detection]:
        if not self.is_loaded or self._model is None:
            return []
        try:
            
            results = self._model(
                frame,
                classes=self.VEHICLE_CLASS_IDS,
                conf=self.confidence_threshold,
                device=self.device,
                verbose=False,
            )
            detections = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    label = r.names.get(cls_id, f"class_{cls_id}")
                    detections.append(Detection(
                        label=label,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                        extra={"class_id": cls_id},
                    ))
            return detections
        except Exception as e:
            self._logger.error(f"Vehicle detection error: {e}")
            return []

    def unload(self) -> None:
        self._model = None
        self.is_loaded = False
