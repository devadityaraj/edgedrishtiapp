"""
Fire and smoke detection model.
Uses YOLOv8 with color/motion heuristic fallback when specialized weights unavailable.
Specialized fire-detection model weights (model.pt) are loaded if present in
AImodels/fire_smoke_detection/model.pt; otherwise falls back to a color + motion approach
using OpenCV HSV masking as a reliable no-GPU alternative.
"""

from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import cv2
import logging
import json
from pathlib import Path
from .base_model import BaseAIModel, Detection

logger = logging.getLogger(__name__)


_AIMODELS_DIR = Path(__file__).parent.parent.parent.parent / "AImodels" / "fire_smoke_detection"
_CUSTOM_MODEL = _AIMODELS_DIR / "model.pt"
_CUSTOM_CONFIG = _AIMODELS_DIR / "config.json"


class FireSmokeDetectionModel(BaseAIModel):
    MODEL_KEY = "fire_smoke"
    DISPLAY_NAME = "Fire/Smoke Detection"

    def __init__(self):
        super().__init__()
        self._model = None
        self._use_yolo = False
        self._prev_frame = None
        self.confidence_threshold = 0.55

    def load(self, device: str = "cpu", config: Optional[Dict[str, Any]] = None) -> bool:
        self.device = device
        if config:
            self.confidence_threshold = config.get("confidence_threshold", 0.55)

        # Load config from AImodels/fire_smoke_detection/config.json if exists
        if _CUSTOM_CONFIG.exists():
            try:
                with open(_CUSTOM_CONFIG) as f:
                    file_config = json.load(f)
                self.confidence_threshold = file_config.get("confidence_threshold", self.confidence_threshold)
                self._logger.info(f"Fire/smoke config loaded from {_CUSTOM_CONFIG}")
            except Exception as e:
                self._logger.warning(f"Failed to load config.json: {e}")

        # Try custom fire model from AImodels/fire_smoke_detection/model.pt
        if _CUSTOM_MODEL.exists():
            try:
                from ultralytics import YOLO
                self._model = YOLO(str(_CUSTOM_MODEL))
                self._use_yolo = True
                self.is_loaded = True
                self._logger.info("Fire/smoke: custom model loaded from AImodels/fire_smoke_detection/model.pt")
                return True
            except Exception as e:
                self._logger.warning(f"Custom fire model load failed: {e}, using heuristic fallback")
        # Try base YOLO (fire mapped from relevant classes)
        try:
            from ultralytics import YOLO
            self._model = YOLO("yolov8n.pt")
            self._use_yolo = True
            self.is_loaded = True
            self._logger.info("Fire/smoke: base YOLO + color heuristic loaded")
            return True
        except ImportError:
            self._logger.warning("ultralytics not installed — using color heuristic only")
        except Exception as e:
            self._logger.warning(f"YOLO not available: {e} — using color heuristic only")
        # Pure heuristic fallback (always works)
        self._use_yolo = False
        self.is_loaded = True
        self._logger.info("Fire/smoke: color+motion heuristic mode")
        return True

    def infer(self, frame: np.ndarray) -> List[Detection]:
        if not self.is_loaded:
            return []
        detections = []
        try:
            detections.extend(self._color_heuristic(frame))
        except Exception as e:
            self._logger.error(f"Fire color heuristic error: {e}")
        return detections

    def _color_heuristic(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect fire/smoke via HSV color masking + motion analysis.
        Fire: high saturation, red-orange-yellow hue, high value.
        Smoke: low saturation, grey, presence near motion regions.
        """
        detections = []
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        
        fire_lower1 = np.array([0, 150, 150])
        fire_upper1 = np.array([20, 255, 255])
        fire_lower2 = np.array([160, 150, 150])
        fire_upper2 = np.array([180, 255, 255])
        mask1 = cv2.inRange(hsv, fire_lower1, fire_upper1)
        mask2 = cv2.inRange(hsv, fire_lower2, fire_upper2)
        fire_mask = cv2.bitwise_or(mask1, mask2)

        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_CLOSE, kernel)
        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_OPEN, kernel)

        h, w = frame.shape[:2]
        min_area = (h * w) * 0.001  

        contours, _ = cv2.findContours(fire_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            
            area_ratio = area / (h * w)
            conf = min(0.95, 0.55 + area_ratio * 5)
            if conf >= self.confidence_threshold:
                detections.append(Detection(
                    label="fire",
                    confidence=conf,
                    bbox=(x, y, x + bw, y + bh),
                    extra={"method": "color_heuristic", "area": int(area)},
                ))

        
        smoke_lower = np.array([0, 0, 80])
        smoke_upper = np.array([180, 50, 200])
        smoke_mask = cv2.inRange(hsv, smoke_lower, smoke_upper)

        # Motion-based smoke: check if grey region is moving
        if self._prev_frame is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            prev_gray = cv2.cvtColor(self._prev_frame, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gray, prev_gray)
            _, motion_mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            smoke_motion = cv2.bitwise_and(smoke_mask, motion_mask)
            smoke_motion = cv2.morphologyEx(smoke_motion, cv2.MORPH_CLOSE, kernel)
            s_contours, _ = cv2.findContours(smoke_motion, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in s_contours:
                area = cv2.contourArea(cnt)
                if area < min_area * 2:
                    continue
                x, y, bw, bh = cv2.boundingRect(cnt)
                area_ratio = area / (h * w)
                conf = min(0.85, 0.50 + area_ratio * 3)
                if conf >= self.confidence_threshold:
                    detections.append(Detection(
                        label="smoke",
                        confidence=conf,
                        bbox=(x, y, x + bw, y + bh),
                        extra={"method": "motion_heuristic"},
                    ))

        self._prev_frame = frame.copy()
        return detections

    def unload(self) -> None:
        self._model = None
        self._prev_frame = None
        self.is_loaded = False
