"""
Shared YOLO model manager to cache loaded YOLO weights and avoid duplicate memory allocation.
"""

import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class SharedYOLOManager:
    _loaded_models: Dict[str, Any] = {}

    @classmethod
    def get_model(cls) -> Any:
        """Get or load the shared YOLO model instance.
        First checks if custom model exists in AImodels/yolo/model.pt.
        Otherwise falls back to yolov8n.pt (downloads automatically if not present).
        """
        from ultralytics import YOLO
        
        path_key = "shared_yolo_instance"
        if path_key not in cls._loaded_models:
            # Check for custom YOLO model inside AImodels/yolo/model.pt
            custom_path = Path(__file__).parent.parent.parent / "AImodels" / "yolo" / "model.pt"
            if custom_path.exists():
                logger.info(f"Loading custom shared YOLO weights from: {custom_path}")
                cls._loaded_models[path_key] = YOLO(str(custom_path))
            else:
                logger.info("Loading default shared YOLO weights (yolov8n.pt)")
                cls._loaded_models[path_key] = YOLO("yolov8n.pt")
        return cls._loaded_models[path_key]
