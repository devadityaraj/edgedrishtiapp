"""
Accident / fall detection model.
Uses temporal motion analysis: sudden large bounding-box area changes,
rapid acceleration of person centroids, or detection of horizontal person poses
indicate potential falls or accidents.
No specialized weights required — works on top of person detection.
"""

from typing import List, Optional, Dict, Any, Deque
from collections import deque, defaultdict
from datetime import datetime
from pathlib import Path
import numpy as np
import logging
import json
from .base_model import BaseAIModel, Detection

logger = logging.getLogger(__name__)


_AIMODELS_DIR = Path(__file__).parent.parent.parent.parent / "AImodels" / "accident_detection"
_CUSTOM_MODEL = _AIMODELS_DIR / "model.pt"
_CUSTOM_CONFIG = _AIMODELS_DIR / "config.json"


class AccidentDetectionModel(BaseAIModel):
    MODEL_KEY = "accident"
    DISPLAY_NAME = "Accident/Fall Detection"

    # Number of frames to buffer for temporal analysis
    TRACK_BUFFER = 30

    def __init__(self):
        super().__init__()
        self._person_model = None
        self.confidence_threshold = 0.55
        # track_id → deque of (timestamp, bbox, aspect_ratio)
        self._tracks: Dict[int, Deque] = defaultdict(lambda: deque(maxlen=self.TRACK_BUFFER))
        self._frame_count = 0

    def load(self, device: str = "cpu", config: Optional[Dict[str, Any]] = None) -> bool:
        self.device = device
        if config:
            self.confidence_threshold = config.get("confidence_threshold", 0.55)

        # Load config from AImodels/accident_detection/config.json if exists
        if _CUSTOM_CONFIG.exists():
            try:
                with open(_CUSTOM_CONFIG) as f:
                    file_config = json.load(f)
                self.confidence_threshold = file_config.get("confidence_threshold", self.confidence_threshold)
                self._logger.info(f"Accident config loaded from {_CUSTOM_CONFIG}")
            except Exception as e:
                self._logger.warning(f"Failed to load config.json: {e}")

        try:
            from ultralytics import YOLO

            # Load custom model from AImodels/accident_detection/model.pt if exists
            if _CUSTOM_MODEL.exists():
                self._person_model = YOLO(str(_CUSTOM_MODEL))
                self._logger.info(f"Accident model loaded from AImodels/accident_detection/model.pt on {device}")
            else:
                self._person_model = YOLO("yolov8n.pt")
                self._logger.info(f"Accident detection model loaded (default yolov8n) on {device}")

            self.is_loaded = True
            return True
        except ImportError:
            self._logger.warning("ultralytics not installed — AccidentDetection disabled")
            return False
        except Exception as e:
            self._logger.error(f"Failed to load accident model: {e}")
            return False

    def infer(self, frame: np.ndarray) -> List[Detection]:
        if not self.is_loaded or self._person_model is None:
            return []
        self._frame_count += 1
        detections = []
        try:
            results = self._person_model.track(
                frame,
                persist=True,
                classes=[0],
                conf=0.4,
                device=self.device,
                verbose=False,
            )
            now = datetime.utcnow()
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    track_id = int(box.id[0]) if box.id is not None else None
                    if track_id is None:
                        continue

                    w = x2 - x1
                    h = y2 - y1
                    if h == 0:
                        continue
                    aspect = w / h  # > 1.5 → person is horizontal (fallen)
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2

                    self._tracks[track_id].append({
                        "ts": now,
                        "bbox": (x1, y1, x2, y2),
                        "aspect": aspect,
                        "cx": cx,
                        "cy": cy,
                        "area": w * h,
                    })

                    det = self._analyze_track(track_id, x1, y1, x2, y2, conf)
                    if det:
                        detections.append(det)

        except Exception as e:
            self._logger.error(f"Accident detection error: {e}")
        return detections

    def _analyze_track(self, track_id: int, x1: int, y1: int, x2: int, y2: int, conf: float) -> Optional[Detection]:
        track = self._tracks[track_id]
        if len(track) < 5:
            return None

        current = track[-1]
        prev = track[-5]

        # Heuristic 1: person becomes horizontal (aspect ratio > 1.5 suddenly)
        was_vertical = prev["aspect"] < 1.0
        now_horizontal = current["aspect"] > 1.5
        if was_vertical and now_horizontal:
            fall_conf = min(0.95, conf + 0.2)
            if fall_conf >= self.confidence_threshold:
                return Detection(
                    label="fall_detected",
                    confidence=fall_conf,
                    bbox=(x1, y1, x2, y2),
                    track_id=track_id,
                    extra={"trigger": "aspect_ratio_change", "prev_aspect": round(prev["aspect"], 2), "curr_aspect": round(current["aspect"], 2)},
                )

        # Heuristic 2: sudden large downward movement (centroid drops fast)
        if len(track) >= 10:
            older = track[-10]
            dy = current["cy"] - older["cy"]
            dt = (current["ts"] - older["ts"]).total_seconds()
            if dt > 0:
                velocity_y = dy / dt  
                if velocity_y > 200 and current["aspect"] > 1.0:
                    fall_conf = min(0.90, conf + 0.15)
                    if fall_conf >= self.confidence_threshold:
                        return Detection(
                            label="fall_detected",
                            confidence=fall_conf,
                            bbox=(x1, y1, x2, y2),
                            track_id=track_id,
                            extra={"trigger": "rapid_descent", "velocity_px_s": round(velocity_y, 1)},
                        )

        return None

    def unload(self) -> None:
        self._person_model = None
        self._tracks.clear()
        self.is_loaded = False
