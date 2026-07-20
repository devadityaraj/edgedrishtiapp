"""
Custom model loader plugin.
Discovers .pt files in backend/.data/models/custom/ and loads them via YOLO or TorchScript.
Register custom models through the Master Admin panel.
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import numpy as np
import logging
from .base_model import BaseAIModel, Detection

logger = logging.getLogger(__name__)

CUSTOM_MODELS_DIR = Path(__file__).parent.parent.parent.parent / "AImodels" / "custom"


class CustomModelLoader(BaseAIModel):
    """
    Plugin loader for custom YOLO (.pt) or TorchScript models.
    Model key matches the filename without extension, e.g. 'loitering' for loitering.pt
    """

    def __init__(self, model_key: str, model_path: str, display_name: str = ""):
        super().__init__()
        self.MODEL_KEY = model_key
        self.DISPLAY_NAME = display_name or f"Custom: {model_key}"
        self._model_path = Path(model_path)
        self._model = None
        self._model_type: str = "unknown"

    def load(self, device: str = "cpu", config: Optional[Dict[str, Any]] = None) -> bool:
        self.device = device
        if config:
            self.confidence_threshold = config.get("confidence_threshold", 0.5)

        if not self._model_path.exists():
            self._logger.error(f"Custom model file not found: {self._model_path}")
            return False

        
        try:
            from ultralytics import YOLO
            self._model = YOLO(str(self._model_path))
            self._model_type = "yolo"
            self.is_loaded = True
            self._logger.info(f"Custom model loaded (YOLO): {self._model_path.name}")
            return True
        except ImportError:
            pass
        except Exception as e:
            self._logger.warning(f"YOLO load failed for {self._model_path.name}: {e}, trying TorchScript")

        
        try:
            import torch
            self._model = torch.jit.load(str(self._model_path), map_location=device)
            self._model.eval()
            self._model_type = "torchscript"
            self.is_loaded = True
            self._logger.info(f"Custom model loaded (TorchScript): {self._model_path.name}")
            return True
        except ImportError:
            self._logger.warning("torch not installed — custom model cannot be loaded")
            return False
        except Exception as e:
            self._logger.error(f"Failed to load custom model {self._model_path.name}: {e}")
            return False

    def infer(self, frame: np.ndarray) -> List[Detection]:
        if not self.is_loaded or self._model is None:
            return []
        try:
            if self._model_type == "yolo":
                return self._infer_yolo(frame)
            elif self._model_type == "torchscript":
                return self._infer_torchscript(frame)
        except Exception as e:
            self._logger.error(f"Custom model inference error: {e}")
        return []

    def _infer_yolo(self, frame: np.ndarray) -> List[Detection]:
        results = self._model(frame, conf=self.confidence_threshold, device=self.device, verbose=False)
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
                    label=f"{self.MODEL_KEY}:{label}",
                    confidence=conf,
                    bbox=(x1, y1, x2, y2),
                    extra={"model": self.MODEL_KEY, "class_id": cls_id},
                ))
        return detections

    def _infer_torchscript(self, frame: np.ndarray) -> List[Detection]:
        import torch
        import cv2
        
        img = cv2.resize(frame, (640, 640))
        img = img[:, :, ::-1].transpose(2, 0, 1)  
        tensor = torch.from_numpy(img.copy()).float().unsqueeze(0) / 255.0
        if self.device == "cuda":
            tensor = tensor.cuda()
        with torch.no_grad():
            out = self._model(tensor)
        # Minimal post-processing (assumes NMS output: [N, 6] with x1y1x2y2 conf cls)
        detections = []
        if isinstance(out, (list, tuple)):
            out = out[0]
        if hasattr(out, "numpy"):
            out = out.cpu().numpy()
        for row in out:
            if len(row) >= 6:
                x1, y1, x2, y2, conf, cls_id = row[:6]
                if float(conf) >= self.confidence_threshold:
                    detections.append(Detection(
                        label=f"{self.MODEL_KEY}:class_{int(cls_id)}",
                        confidence=float(conf),
                        bbox=(int(x1), int(y1), int(x2), int(y2)),
                    ))
        return detections

    def unload(self) -> None:
        self._model = None
        self.is_loaded = False


def discover_custom_models() -> Dict[str, "CustomModelLoader"]:
    """
    Scan the custom models directory and return a dict of {key: loader_instance}.
    Called by the model registry on startup.
    """
    CUSTOM_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    found = {}
    for pt_file in CUSTOM_MODELS_DIR.glob("*.pt"):
        key = f"custom_{pt_file.stem}"
        found[key] = CustomModelLoader(key, str(pt_file), display_name=f"Custom: {pt_file.stem}")
        logger.info(f"Discovered custom model: {pt_file.name} → key={key}")
    return found


# Type alias for the plan
from typing import Dict  # noqa: F811
