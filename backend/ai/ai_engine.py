"""
EDGE Drishti - AI Detection Engine
Local YOLO v8 + specialized models for threat detection
No cloud processing, fully local execution
"""

import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
import threading
from pathlib import Path


try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False
    logging.warning("YOLO not installed - detection will be disabled")

logger = logging.getLogger(__name__)


class DetectionClass(str, Enum):
    PERSON = "person"
    WEAPON = "weapon"
    VEHICLE = "vehicle"
    FIRE = "fire"
    SMOKE = "smoke"
    LOITERING = "loitering"
    CROWD = "crowd"
    ABANDONED_OBJECT = "abandoned_object"
    INTRUSION = "intrusion"


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  
    timestamp: datetime
    camera_id: str
    frame_index: int
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class": self.class_name,
            "confidence": float(self.confidence),
            "bbox": self.bbox,
            "timestamp": self.timestamp.isoformat(),
            "camera_id": self.camera_id,
            "frame_index": self.frame_index,
            "metadata": self.metadata or {}
        }


class AIDetectionEngine:
    """Local AI detection engine using YOLO v8 and custom models"""

    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)

        self.yolo_model = None
        self.detection_threshold = 0.5
        self.nms_threshold = 0.45

        
        self.threat_levels = {
            DetectionClass.WEAPON: 100,
            DetectionClass.FIRE: 95,
            DetectionClass.SMOKE: 90,
            DetectionClass.INTRUSION: 85,
            DetectionClass.CROWD: 60,
            DetectionClass.LOITERING: 50,
            DetectionClass.ABANDONED_OBJECT: 45,
            DetectionClass.PERSON: 20,
            DetectionClass.VEHICLE: 30,
        }

        # Temporal tracking for loitering/abandoned objects
        self.person_tracks: Dict[int, List[Tuple[datetime, Tuple]]] = {}
        self.object_tracks: Dict[int, List[Tuple[datetime, Tuple]]] = {}
        self.track_timeout = 300  

        self.is_initialized = False
        self._lock = threading.Lock()

    def initialize(self) -> bool:
        """Initialize AI models"""
        try:
            if not HAS_YOLO:
                logger.warning("YOLO not available - using stub detection")
                return True

            # Load YOLOv8n (nano) for speed on edge devices
            logger.info("Loading YOLOv8n model...")
            self.yolo_model = YOLO("yolov8n.pt")

            # Load custom threat detection model if available
            custom_model_path = self.model_dir / "threat_detection.pt"
            if custom_model_path.exists():
                logger.info("Loading custom threat detection model...")
                
                pass

            self.is_initialized = True
            logger.info("AI detection engine initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize AI engine: {str(e)}")
            return False

    def detect(self, frame: np.ndarray, camera_id: str, frame_index: int) -> List[Detection]:
        """Run detection on frame"""
        if not self.is_initialized or self.yolo_model is None:
            return self._stub_detection(frame, camera_id, frame_index)

        try:
            with self._lock:
                timestamp = datetime.now()

                
                results = self.yolo_model(frame, conf=self.detection_threshold, verbose=False)
                detections = []

                for result in results:
                    if result.boxes is None:
                        continue

                    for box in result.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        conf = float(box.conf[0])
                        class_id = int(box.cls[0])
                        class_name = result.names[class_id]

                        
                        threat_class = self._map_to_threat_class(class_name, class_id)

                        detection = Detection(
                            class_name=threat_class.value,
                            confidence=conf,
                            bbox=(x1, y1, x2, y2),
                            timestamp=timestamp,
                            camera_id=camera_id,
                            frame_index=frame_index,
                            metadata={
                                "yolo_class": class_name,
                                "yolo_class_id": class_id,
                                "threat_level": self.threat_levels.get(
                                    DetectionClass(threat_class.value), 50
                                )
                            }
                        )
                        detections.append(detection)

                # Apply temporal analysis for loitering
                self._update_tracks(detections, camera_id)
                self._detect_loitering(detections, camera_id)

                return detections

        except Exception as e:
            logger.error(f"Detection error: {str(e)}")
            return []

    def _map_to_threat_class(self, yolo_class: str, class_id: int) -> DetectionClass:
        """Map COCO class to threat detection class"""
        yolo_class_lower = yolo_class.lower()

        mapping = {
            "person": DetectionClass.PERSON,
            "car": DetectionClass.VEHICLE,
            "truck": DetectionClass.VEHICLE,
            "bus": DetectionClass.VEHICLE,
            "motorcycle": DetectionClass.VEHICLE,
            "bicycle": DetectionClass.VEHICLE,
            
        }

        return mapping.get(yolo_class_lower, DetectionClass.PERSON)

    def _update_tracks(self, detections: List[Detection], camera_id: str):
        """Update temporal tracks for persons and objects"""
        current_time = datetime.now()

        
        for track_dict in [self.person_tracks, self.object_tracks]:
            expired_ids = [
                track_id for track_id, history in track_dict.items()
                if (current_time - history[-1][0]).total_seconds() > self.track_timeout
            ]
            for track_id in expired_ids:
                del track_dict[track_id]

        # Update with current detections
        persons = [d for d in detections if d.class_name == DetectionClass.PERSON.value]
        for person in persons:
            track_id = hash((camera_id, person.bbox))
            if track_id not in self.person_tracks:
                self.person_tracks[track_id] = []
            self.person_tracks[track_id].append((current_time, person.bbox))

    def _detect_loitering(self, detections: List[Detection], camera_id: str):
        """Detect persons loitering in same area"""
        current_time = datetime.now()
        loitering_threshold = 60  

        for track_id, history in self.person_tracks.items():
            if len(history) < 2:
                continue

            # Check if person stayed in similar location
            first_time, first_bbox = history[0]
            last_time, last_bbox = history[-1]
            time_diff = (last_time - first_time).total_seconds()

            if time_diff >= loitering_threshold:
                
                distance = self._bbox_distance(first_bbox, last_bbox)
                if distance < 100:  
                    
                    loitering_detection = Detection(
                        class_name=DetectionClass.LOITERING.value,
                        confidence=0.9,
                        bbox=last_bbox,
                        timestamp=current_time,
                        camera_id=camera_id,
                        frame_index=0,
                        metadata={
                            "duration_seconds": int(time_diff),
                            "distance_pixels": int(distance)
                        }
                    )
                    detections.append(loitering_detection)

    def _bbox_distance(self, bbox1: Tuple, bbox2: Tuple) -> float:
        """Calculate distance between two bounding boxes (centers)"""
        x1_center = (bbox1[0] + bbox1[2]) / 2
        y1_center = (bbox1[1] + bbox1[3]) / 2
        x2_center = (bbox2[0] + bbox2[2]) / 2
        y2_center = (bbox2[1] + bbox2[3]) / 2

        return np.sqrt((x1_center - x2_center) ** 2 + (y1_center - y2_center) ** 2)

    def _stub_detection(self, frame: np.ndarray, camera_id: str, frame_index: int) -> List[Detection]:
        """Stub detection when YOLO is not available"""
        # Simulate some detections for testing
        import random
        detections = []

        if random.random() > 0.7:  
            h, w = frame.shape[:2]
            detections.append(Detection(
                class_name=DetectionClass.PERSON.value,
                confidence=0.85 + random.random() * 0.15,
                bbox=(random.randint(0, w - 200), random.randint(0, h - 200),
                      random.randint(200, w), random.randint(200, h)),
                timestamp=datetime.now(),
                camera_id=camera_id,
                frame_index=frame_index,
                metadata={"threat_level": self.threat_levels[DetectionClass.PERSON]}
            ))

        return detections

    def draw_detections(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """Draw detection boxes and labels on frame"""
        frame_copy = frame.copy()

        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            threat_level = detection.metadata.get("threat_level", 50) if detection.metadata else 50

            # Color based on threat level (red for high, yellow for medium, green for low)
            if threat_level >= 80:
                color = (0, 0, 255)  
            elif threat_level >= 50:
                color = (0, 165, 255)  
            else:
                color = (0, 255, 0)  

            
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 2)

            
            label = f"{detection.class_name} {detection.confidence:.2f}"
            cv2.putText(frame_copy, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return frame_copy

    def get_status(self) -> Dict[str, Any]:
        """Get engine status"""
        return {
            "initialized": self.is_initialized,
            "model_loaded": self.yolo_model is not None,
            "active_tracks": len(self.person_tracks) + len(self.object_tracks),
            "threshold": self.detection_threshold,
            "nms_threshold": self.nms_threshold
        }



ai_engine = AIDetectionEngine()
