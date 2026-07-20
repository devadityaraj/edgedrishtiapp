"""
AI Model Registry — loads, tracks, and manages all detection models.
Gracefully handles missing optional dependencies (torch, face_recognition, etc.)
"""

import logging
from typing import Dict, Optional, List, Any
from .models.base_model import BaseAIModel, Detection

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Singleton registry for all AI detection models."""

    def __init__(self):
        self._models: Dict[str, BaseAIModel] = {}
        self._device: str = "cpu"
        self._loaded: bool = False

    def initialize(self, device: str = "cpu"):
        """Load all enabled models. Called once at startup."""
        self._device = device
        logger.info(f"Initializing AI model registry on device: {device}")

        
        self._try_register("person")
        self._try_register("object")
        self._try_register("fire_smoke")
        self._try_register("accident")
        self._try_register("face")
        self._try_register("vehicle")
        self._try_register("animal")

        
        try:
            from .models.custom_model_loader import discover_custom_models
            for key, loader in discover_custom_models().items():
                self._models[key] = loader
                ok = loader.load(device=device)
                if ok:
                    logger.info(f"Custom model loaded: {key}")
                else:
                    logger.warning(f"Custom model failed to load: {key}")
        except Exception as e:
            logger.error(f"Custom model discovery error: {e}")

        self._loaded = True
        loaded_keys = [k for k, m in self._models.items() if m.is_loaded]
        logger.info(f"Registry ready. Loaded models: {loaded_keys}")

    def _try_register(self, key: str):
        """Import, instantiate, and load a built-in model by key."""
        try:
            model = self._instantiate(key)
            if model is None:
                return
            ok = model.load(device=self._device)
            self._models[key] = model
            if ok:
                logger.info(f"Model '{key}' loaded ✓")
            else:
                logger.warning(f"Model '{key}' failed to load (may be missing deps) — disabled")
        except Exception as e:
            logger.error(f"Error registering model '{key}': {e}")

    def _instantiate(self, key: str) -> Optional[BaseAIModel]:
        if key == "person":
            from .models.person import PersonDetectionModel
            return PersonDetectionModel()
        elif key == "object":
            from .models.object_detection import ObjectDetectionModel
            return ObjectDetectionModel()
        elif key == "fire_smoke":
            from .models.fire_smoke import FireSmokeDetectionModel
            return FireSmokeDetectionModel()
        elif key == "accident":
            from .models.accident import AccidentDetectionModel
            return AccidentDetectionModel()
        elif key == "face":
            from .models.face_match import FaceMatchModel
            m = FaceMatchModel()
            # Load enrolled faces from DB
            self._refresh_face_embeddings(m)
            return m
        elif key == "vehicle":
            from .models.vehicle import VehicleDetectionModel
            return VehicleDetectionModel()
        elif key == "animal":
            from .models.animal import AnimalDetectionModel
            return AnimalDetectionModel()
        return None

    def _refresh_face_embeddings(self, face_model):
        """Load encrypted embeddings from DB and populate the face model."""
        try:
            from backend.db.session import DatabaseManager
            from backend.db.models import Face
            import numpy as np
            import json, base64

            db = DatabaseManager.get_session()
            try:
                faces = db.query(Face).all()
                enrolled = {}
                for f in faces:
                    if not f.embedding_encrypted:
                        continue
                    try:
                        raw = base64.b64decode(f.embedding_encrypted)
                        embedding = np.frombuffer(raw, dtype=np.float32)
                        enrolled.setdefault(f.label, []).append(embedding)
                    except Exception:
                        pass
                face_model.load_enrolled_faces(enrolled)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not load face embeddings: {e}")

    def get_model(self, key: str) -> Optional[BaseAIModel]:
        return self._models.get(key)

    def get_all(self) -> Dict[str, BaseAIModel]:
        return dict(self._models)

    def get_loaded_keys(self) -> List[str]:
        return [k for k, m in self._models.items() if m.is_loaded]

    def reload_model(self, key: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Unload and reload a model (e.g. after config change)."""
        model = self._models.get(key)
        if model:
            model.unload()
        self._try_register(key)
        model = self._models.get(key)
        return model.is_loaded if model else False

    def unload_all(self):
        for model in self._models.values():
            try:
                model.unload()
            except Exception:
                pass
        self._models.clear()
        self._loaded = False

    def refresh_face_embeddings(self):
        """Public method to reload face embeddings after new enrollment."""
        face_model = self._models.get("face")
        if face_model:
            self._refresh_face_embeddings(face_model)



model_registry = ModelRegistry()
