"""
Face matching model.
Detects faces in frames and matches against enrolled embeddings in the database.
Supports face_recognition (dlib-based), InsightFace, and OpenCV Haar fallback.
"""

from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import cv2
import logging
from .base_model import BaseAIModel, Detection

logger = logging.getLogger(__name__)

# ── Try to import face recognition backends ─────────────────────────────────
_face_recognition = None
_insightface = None
_HAS_FACE_RECOGNITION = False
_HAS_INSIGHTFACE = False

try:
    import face_recognition as _face_recognition
    _HAS_FACE_RECOGNITION = True
except ImportError:
    pass

if not _HAS_FACE_RECOGNITION:
    try:
        import insightface as _insightface
        _HAS_INSIGHTFACE = True
    except ImportError:
        pass


_HAAR_CASCADE = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


class FaceMatchModel(BaseAIModel):
    MODEL_KEY = "face"
    DISPLAY_NAME = "Face Matching"

    def __init__(self):
        super().__init__()
        self.confidence_threshold = 0.6
        self._backend: str = "haar"
        self._insightface_app = None
        self._haar = None
        # label → list of embeddings (from enrolled DB)
        self._enrolled: Dict[str, List[np.ndarray]] = {}
        self.is_loaded = False

    def load(self, device: str = "cpu", config: Optional[Dict[str, Any]] = None) -> bool:
        self.device = device
        if config:
            self.confidence_threshold = config.get("confidence_threshold", 0.6)

        if _HAS_FACE_RECOGNITION:
            self._backend = "face_recognition"
            self.is_loaded = True
            self._logger.info("Face matching: using face_recognition (dlib) backend")
        elif _HAS_INSIGHTFACE:
            try:
                from insightface.app import FaceAnalysis
                self._insightface_app = FaceAnalysis(
                    name="buffalo_sc",
                    providers=["CUDAExecutionProvider" if device == "cuda" else "CPUExecutionProvider"]
                )
                self._insightface_app.prepare(ctx_id=0 if device == "cuda" else -1)
                self._backend = "insightface"
                self.is_loaded = True
                self._logger.info("Face matching: using InsightFace backend")
            except Exception as e:
                self._logger.warning(f"InsightFace load failed: {e}, falling back to Haar")
                self._backend = "haar"
                try:
                    if not hasattr(cv2, "CascadeClassifier"):
                        raise AttributeError("module 'cv2' has no attribute 'CascadeClassifier'")
                    self._haar = cv2.CascadeClassifier(_HAAR_CASCADE)
                    self.is_loaded = True
                except Exception as ex:
                    self._logger.warning(f"Haar cascade initialization failed: {ex}. Face Matching disabled.")
                    self.is_loaded = False
                    return False
        else:
            self._backend = "haar"
            try:
                if not hasattr(cv2, "CascadeClassifier"):
                    raise AttributeError("module 'cv2' has no attribute 'CascadeClassifier' (OpenCV installation may be broken or missing DLLs)")
                self._haar = cv2.CascadeClassifier(_HAAR_CASCADE)
                self.is_loaded = True
                self._logger.info("Face matching: using OpenCV Haar cascade (no embeddings — detection only)")
            except Exception as e:
                self._logger.warning(f"OpenCV Haar cascade initialization failed: {e}. Face Matching disabled.")
                self.is_loaded = False
                return False

        return self.is_loaded

    def load_enrolled_faces(self, enrolled: Dict[str, List[np.ndarray]]):
        """Load enrolled face embeddings: {label: [embedding_array, ...]}"""
        self._enrolled = enrolled
        self._logger.info(f"Loaded {len(enrolled)} enrolled face identities")

    def infer(self, frame: np.ndarray) -> List[Detection]:
        if not self.is_loaded:
            return []
        try:
            if self._backend == "face_recognition":
                return self._infer_face_recognition(frame)
            elif self._backend == "insightface":
                return self._infer_insightface(frame)
            else:
                return self._infer_haar(frame)
        except Exception as e:
            self._logger.error(f"Face match inference error: {e}")
            return []

    def _infer_face_recognition(self, frame: np.ndarray) -> List[Detection]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = _face_recognition.face_locations(rgb, model="hog")
        if not locations:
            return []
        encodings = _face_recognition.face_encodings(rgb, locations)
        detections = []
        for (top, right, bottom, left), encoding in zip(locations, encodings):
            label, conf = "unknown_face", 0.5
            if self._enrolled:
                best_label, best_conf = self._match_embedding(encoding)
                if best_conf >= self.confidence_threshold:
                    label, conf = best_label, best_conf
            detections.append(Detection(
                label=f"face:{label}",
                confidence=conf,
                bbox=(left, top, right, bottom),
                extra={"identity": label, "backend": "face_recognition"},
            ))
        return detections

    def _infer_insightface(self, frame: np.ndarray) -> List[Detection]:
        faces = self._insightface_app.get(frame)
        detections = []
        for face in faces:
            box = face.bbox.astype(int)
            x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
            det_score = float(face.det_score)
            label, conf = "unknown_face", det_score
            if self._enrolled and face.normed_embedding is not None:
                best_label, best_conf = self._match_embedding(face.normed_embedding)
                if best_conf >= self.confidence_threshold:
                    label, conf = best_label, best_conf
            detections.append(Detection(
                label=f"face:{label}",
                confidence=conf,
                bbox=(x1, y1, x2, y2),
                extra={"identity": label, "backend": "insightface"},
            ))
        return detections

    def _infer_haar(self, frame: np.ndarray) -> List[Detection]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._haar.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
        detections = []
        for (x, y, w, h) in faces:
            detections.append(Detection(
                label="face:unknown",
                confidence=0.7,
                bbox=(x, y, x + w, y + h),
                extra={"identity": "unknown", "backend": "haar"},
            ))
        return detections

    def _match_embedding(self, embedding: np.ndarray) -> Tuple[str, float]:
        """Compare embedding against all enrolled identities."""
        best_label = "unknown_face"
        best_conf = 0.0
        for label, stored_embeddings in self._enrolled.items():
            for stored in stored_embeddings:
                try:
                    if _HAS_FACE_RECOGNITION and self._backend == "face_recognition":
                        dist = _face_recognition.face_distance([stored], embedding)[0]
                        conf = max(0.0, 1.0 - dist)
                    else:
                        
                        norm_e = embedding / (np.linalg.norm(embedding) + 1e-8)
                        norm_s = stored / (np.linalg.norm(stored) + 1e-8)
                        conf = float(np.dot(norm_e, norm_s))
                    if conf > best_conf:
                        best_conf = conf
                        best_label = label
                except Exception:
                    pass
        return best_label, best_conf

    def unload(self) -> None:
        self._insightface_app = None
        self._enrolled.clear()
        self.is_loaded = False
