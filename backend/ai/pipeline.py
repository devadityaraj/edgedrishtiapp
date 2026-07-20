"""
Per-camera AI inference pipeline.
Reads frames from camera workers, runs enabled models, stores detection events,
draws overlays, and pushes annotated frames to the WebSocket broadcaster.
"""

import asyncio
import threading
import queue
import uuid
import base64
import logging
import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Callable

import cv2
import numpy as np

from backend.core.config import config
from backend.db.session import DatabaseManager
from backend.db.models import (
    Camera, AIModel, CameraModelLink, DetectionEvent, Notification, User, UserRole, SystemConfig
)
from backend.ai.registry import model_registry

logger = logging.getLogger(__name__)


def _check_roi(bbox: tuple, roi_zones: list) -> bool:
    """Return True if bbox center is inside any of the ROI zones (polygons)."""
    if not roi_zones:
        return True  
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    for zone in roi_zones:
        pts = np.array(zone, dtype=np.int32)
        if cv2.pointPolygonTest(pts, (cx, cy), False) >= 0:
            return True
    return False


def _check_schedule(schedule: dict) -> bool:
    """Return True if current time is within any configured time window."""
    if not schedule or not schedule.get("windows"):
        return True  
    now = datetime.now()
    day = now.strftime("%A").lower()  
    current_minutes = now.hour * 60 + now.minute
    for window in schedule["windows"]:
        if day not in window.get("days", [day]):
            continue
        start = window.get("start_minutes", 0)
        end = window.get("end_minutes", 1440)
        if start <= current_minutes <= end:
            return True
    return False


class CameraInferencePipeline:
    """
    Runs inference for a single camera.
    Pulls frames from the camera worker's queue, runs models, writes events to DB.
    """

    def __init__(self, camera_id: str, ws_broadcast_fn: Optional[Callable] = None):
        self.camera_id = camera_id
        self._ws_broadcast = ws_broadcast_fn
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_event_ts: Dict[str, float] = {}
        self._last_model_inference_ts: Dict[str, float] = {}
        
        # Video recording state (15s pre-buffer, event-based post-record)
        self._frame_history = deque()
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._recording_end_time: float = 0.0
        self._recording_start_time: float = 0.0
        self._current_recording_path: Optional[str] = None
        self._current_recording_event_id: Optional[str] = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"inference-{self.camera_id[:8]}",
            daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._video_writer:
            try:
                self._video_writer.release()
            except Exception:
                pass
            self._video_writer = None

    def _run(self):
        from backend.cameras.camera_manager import camera_manager
        logger.info(f"Inference pipeline started for camera {self.camera_id}")

        while not self._stop_event.is_set():
            worker = camera_manager.get_worker(self.camera_id)
            if worker is None or worker.status != "online":
                self._stop_event.wait(1.0)
                continue

            try:
                ts, jpeg_bytes, frame = worker.frame_queue.get(timeout=1.0)
            except (queue.Empty, ValueError, TypeError):
                continue

            
            now = time.time()
            self._frame_history.append((now, frame.copy()))
            while self._frame_history and now - self._frame_history[0][0] > 20.0:
                self._frame_history.popleft()

            try:
                enabled_models = self._get_enabled_models()
                all_detections = []

                
                yolo_keys = ["person", "object", "vehicle", "animal"]
                active_yolo_keys = [k for k in yolo_keys if k in enabled_models]

                # Map model keys to their specific COCO class IDs
                model_class_ids = {
                    "person": [0],
                    "vehicle": [1, 2, 3, 4, 5, 6, 7, 8],
                    "animal": [14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
                }

                
                yolo_detections_by_model = {k: [] for k in yolo_keys}

                if active_yolo_keys:
                    # Determine combined class list for YOLO
                    if "object" in active_yolo_keys:
                        
                        yolo_classes = None
                    else:
                        combined_classes = set()
                        for k in active_yolo_keys:
                            if k in model_class_ids:
                                combined_classes.update(model_class_ids[k])
                        yolo_classes = list(combined_classes)

                    
                    thresholds = []
                    device = "cpu"
                    for k in active_yolo_keys:
                        m_obj = model_registry.get_model(k)
                        if m_obj and m_obj.is_loaded:
                            device = getattr(m_obj, "device", "cpu")
                            link_config = enabled_models[k]
                            global_thresh = link_config.get("confidence_threshold")
                            sensitivity = link_config.get("sensitivity_config_json") or {}
                            thresh = 0.5
                            if global_thresh is not None:
                                thresh = float(global_thresh)
                            elif sensitivity.get("confidence_threshold"):
                                thresh = float(sensitivity["confidence_threshold"])
                            thresholds.append(thresh)

                    min_conf = min(thresholds) if thresholds else 0.5

                    
                    try:
                        from backend.ai.shared_yolo import SharedYOLOManager
                        from backend.ai.models.base_model import Detection
                        
                        yolo_model = SharedYOLOManager.get_model()
                        results = yolo_model.track(
                            frame,
                            persist=True,
                            classes=yolo_classes,
                            conf=min_conf,
                            device=device,
                            verbose=False
                        )

                        for r in results:
                            if r.boxes is None:
                                continue
                            for box in r.boxes:
                                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                                conf = float(box.conf[0])
                                cls_id = int(box.cls[0])
                                label = r.names.get(cls_id, f"class_{cls_id}")
                                track_id = int(box.id[0]) if box.id is not None else None

                                det = Detection(
                                    label=label,
                                    confidence=conf,
                                    bbox=(x1, y1, x2, y2),
                                    track_id=track_id,
                                    extra={"class_id": cls_id}
                                )

                                
                                if "object" in active_yolo_keys:
                                    yolo_detections_by_model["object"].append(det)
                                if "person" in active_yolo_keys and cls_id == 0:
                                    # Standardize label for person detection
                                    det_person = Detection(
                                        label="person",
                                        confidence=conf,
                                        bbox=(x1, y1, x2, y2),
                                        track_id=track_id
                                    )
                                    yolo_detections_by_model["person"].append(det_person)
                                if "vehicle" in active_yolo_keys and cls_id in model_class_ids["vehicle"]:
                                    yolo_detections_by_model["vehicle"].append(det)
                                if "animal" in active_yolo_keys and cls_id in model_class_ids["animal"]:
                                    yolo_detections_by_model["animal"].append(det)
                    except Exception as yolo_err:
                        logger.error(f"Unified YOLO inference pass failed: {yolo_err}")

                for model_key, link_config in enabled_models.items():
                    
                    fps_limit = link_config.get("fps_limit")
                    if fps_limit is not None:
                        last_ts = self._last_model_inference_ts.get(model_key, 0.0)
                        if now - last_ts < (1.0 / float(fps_limit)):
                            continue  

                    
                    schedule = link_config.get("schedule_json") or {}
                    roi_zones = link_config.get("roi_zones_json") or []
                    sensitivity = link_config.get("sensitivity_config_json") or {}
                    if not _check_schedule(schedule):
                        continue

                    self._last_model_inference_ts[model_key] = now

                    # Fetch/filter detections for this model
                    if model_key in yolo_keys:
                        raw_dets = yolo_detections_by_model[model_key]
                        global_thresh = link_config.get("confidence_threshold")
                        specific_thresh = 0.5
                        if global_thresh is not None:
                            specific_thresh = float(global_thresh)
                        elif sensitivity.get("confidence_threshold"):
                            specific_thresh = float(sensitivity["confidence_threshold"])

                        dets = []
                        for det in raw_dets:
                            if det.confidence < specific_thresh:
                                continue

                            # Perform class filtering for object, vehicle, animal
                            if model_key in ["object", "vehicle", "animal"]:
                                
                                global_allowed = link_config.get("allowed_classes")
                                if global_allowed is not None and isinstance(global_allowed, list):
                                    if det.label not in global_allowed:
                                        continue
                                
                                allowed_classes = sensitivity.get("classes")
                                if allowed_classes is not None and isinstance(allowed_classes, list):
                                    if det.label not in allowed_classes:
                                        continue

                            dets.append(det)
                    else:
                        # Non-YOLO models (fire_smoke, accident, etc.) run their own inference
                        model = model_registry.get_model(model_key)
                        if model is None or not model.is_loaded:
                            continue

                        global_thresh = link_config.get("confidence_threshold")
                        if global_thresh is not None:
                            model.set_confidence_threshold(float(global_thresh))
                        elif sensitivity.get("confidence_threshold"):
                            model.set_confidence_threshold(float(sensitivity["confidence_threshold"]))

                        dets = model.infer(frame)

                    for det in dets:
                        if _check_roi(det.bbox, roi_zones):
                            all_detections.append((model_key, det, link_config))

                if all_detections:
                    annotated = self._draw_overlays(frame.copy(), all_detections)
                    ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    annotated_jpeg = buf.tobytes() if ok else jpeg_bytes
                else:
                    annotated_jpeg = jpeg_bytes

                
                if self._ws_broadcast:
                    det_dicts = [d.to_dict() for _, d, _ in all_detections]
                    self._ws_broadcast(
                        self.camera_id, annotated_jpeg,
                        ts.isoformat(), det_dicts
                    )

                
                if all_detections:
                    self._persist_detections(all_detections, ts, annotated_jpeg, frame)

                
                self._handle_recording(frame, now)

            except Exception as e:
                logger.error(f"Inference error for camera {self.camera_id}: {e}")

    def _get_enabled_models(self) -> Dict[str, dict]:
        """Query DB for models enabled for this camera."""
        try:
            db = DatabaseManager.get_session()
            try:
                
                ai_master = db.query(SystemConfig).filter(SystemConfig.key == "ai_processing_enabled").first()
                if ai_master and ai_master.value_encrypted == "false":
                    return {}

                links = (
                    db.query(CameraModelLink, AIModel)
                    .join(AIModel, CameraModelLink.ai_model_id == AIModel.id)
                    .filter(CameraModelLink.camera_id == self.camera_id)
                    .filter(CameraModelLink.enabled == True)
                    .filter(AIModel.enabled_globally == True)
                    .all()
                )
                result = {}
                for link, model in links:
                    result[model.key] = {
                        "sensitivity_config_json": link.sensitivity_config_json,
                        "roi_zones_json": link.roi_zones_json,
                        "schedule_json": link.schedule_json,
                        "ai_model_id": model.id,
                        "display_name": model.display_name,
                        "fps_limit": model.config_json.get("fps_limit") if (isinstance(model.config_json, dict) and "fps_limit" in model.config_json) else 5,
                        "confidence_threshold": model.config_json.get("confidence_threshold") if (isinstance(model.config_json, dict) and "confidence_threshold" in model.config_json) else None,
                        "allowed_classes": model.config_json.get("allowed_classes") if isinstance(model.config_json, dict) else None,
                        "alerts_enabled": model.config_json.get("alerts_enabled", True) if isinstance(model.config_json, dict) else True,
                    }
                return result
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error fetching model config: {e}")
            return {}

    def _draw_overlays(self, frame: np.ndarray, detections: list) -> np.ndarray:
        COLOR_MAP = {
            "fire": (0, 0, 255), "smoke": (128, 128, 128),
            "fall_detected": (0, 165, 255), "person": (0, 255, 0),
            "face": (255, 165, 0),
        }
        for model_key, det, _ in detections:
            x1, y1, x2, y2 = det.bbox
            color = (0, 255, 255)
            for prefix, c in COLOR_MAP.items():
                if det.label.startswith(prefix):
                    color = c
                    break
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{det.label} {det.confidence:.2f}"
            cv2.putText(frame, label, (x1, max(y1 - 5, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return frame

    def _persist_detections(self, detections: list, ts: datetime, jpeg_bytes: bytes, frame: np.ndarray):
        """Write detection events to DB and create in-app notifications."""
        import time
        current_time = time.time()
        
        # Filter detections by throttling (10s lock per label)
        to_persist = []
        for item in detections:
            model_key, det, link_config = item
            label = det.label
            last_ts = self._last_event_ts.get(label, 0.0)
            if current_time - last_ts >= 10.0:
                to_persist.append(item)
                
        if not to_persist:
            return

        
        for _, det, _ in to_persist:
            self._last_event_ts[det.label] = current_time

        try:
            db = DatabaseManager.get_session()
            try:
                
                snap_dir = config.RECORDINGS_DIR / self.camera_id
                snap_dir.mkdir(parents=True, exist_ok=True)
                snap_filename = f"{ts.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                snap_path = snap_dir / snap_filename
                snap_path.write_bytes(jpeg_bytes)

                # Check if recording on event is enabled for this camera and if trigger models request it
                camera_obj = db.query(Camera).filter(Camera.id == self.camera_id).first()
                record_enabled = False
                if camera_obj and camera_obj.record_enabled:
                    rec_row = db.query(SystemConfig).filter(SystemConfig.key == "record_on_event").first()
                    global_record_enabled = rec_row is not None and rec_row.value_encrypted == "true"
                    record_enabled = global_record_enabled
                    if not record_enabled:
                        for model_key, det, link_config in to_persist:
                            sens = link_config.get("sensitivity_config_json") or {}
                            if sens.get("record_on_detect") is True:
                                record_enabled = True
                                break

                first_event_id = None
                if record_enabled:
                    record_duration = camera_obj.record_duration_seconds if camera_obj else 60
                    if self._video_writer is None:
                        
                        filename = f"event_{int(current_time)}.mp4"
                        filepath = snap_dir / filename
                        self._current_recording_path = str(filepath)
                        first_event_id = str(uuid.uuid4())
                        self._current_recording_event_id = first_event_id
                        self._recording_start_time = current_time
                        self._recording_end_time = current_time + record_duration
                        
                        try:
                            height, width = frame.shape[:2]
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            from backend.cameras.camera_manager import camera_manager
                            worker = camera_manager.get_worker(self.camera_id)
                            fps = worker.fps if (worker and worker.fps > 0.0) else 10.0
                            self._video_writer = cv2.VideoWriter(str(filepath), fourcc, fps, (width, height))
                            
                            
                            for _, hist_frame in self._frame_history:
                                self._video_writer.write(hist_frame)
                        except Exception as ve:
                            logger.error(f"Failed to initialize VideoWriter: {ve}")
                            self._video_writer = None
                            self._current_recording_path = None
                            self._current_recording_event_id = None
                    else:
                        
                        self._recording_end_time = max(self._recording_end_time, current_time + record_duration)

                for model_key, det, link_config in to_persist:
                    event_id = first_event_id if (first_event_id is not None) else str(uuid.uuid4())
                    first_event_id = None
                    
                    event = DetectionEvent(
                        id=event_id,
                        camera_id=self.camera_id,
                        ai_model_id=link_config.get("ai_model_id", ""),
                        event_type=det.label,
                        confidence=det.confidence,
                        timestamp=ts,
                        snapshot_path_encrypted=str(snap_path),
                        bounding_boxes_json=[det.to_dict()],
                        clip_path_encrypted=self._current_recording_path if (self._video_writer is not None) else None,
                        acknowledged=False,
                    )
                    db.add(event)
                    db.flush()

                    # Create in-app notification and trigger async alert dispatch only if enabled
                    if link_config.get("alerts_enabled", True):
                        users = db.query(User).filter(User.role.in_([UserRole.USER, UserRole.ADMIN])).all()
                        for user in users:
                            notif = Notification(
                                id=str(uuid.uuid4()),
                                user_id=user.id,
                                detection_event_id=event.id,
                                title=f"Alert: {det.label}",
                                message=f"{link_config.get('display_name', model_key)} detected on camera (confidence: {det.confidence:.0%})",
                                notification_type="alert",
                                read=False,
                                created_at=ts,
                            )
                            db.add(notif)

                        try:
                            from backend.alerts.dispatcher import alert_dispatcher
                            alert_dispatcher.queue_alert(event.id, det.label, det.confidence, self.camera_id, snap_path)
                        except Exception as ae:
                            logger.warning(f"Alert dispatch failed: {ae}")

                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to persist detections: {e}")

    def _handle_recording(self, frame: np.ndarray, now: float):
        if self._video_writer is not None:
            if now < self._recording_end_time:
                if now > self._recording_start_time:
                    try:
                        self._video_writer.write(frame)
                    except Exception as e:
                        logger.error(f"Error writing frame to video: {e}")
            else:
                logger.info(f"Video recording finished. Path: {self._current_recording_path}")
                try:
                    self._video_writer.release()
                except Exception:
                    pass
                self._video_writer = None
                
                
                if self._current_recording_event_id and self._current_recording_path:
                    try:
                        db = DatabaseManager.get_session()
                        try:
                            evt = db.query(DetectionEvent).filter(DetectionEvent.id == self._current_recording_event_id).first()
                            if evt:
                                evt.clip_path_encrypted = self._current_recording_path
                                db.commit()
                        finally:
                            db.close()
                    except Exception as dbe:
                        logger.error(f"Failed to update DetectionEvent with clip path: {dbe}")
                
                self._current_recording_path = None
                self._current_recording_event_id = None


class PipelineManager:
    """Manages all per-camera inference pipelines."""

    def __init__(self):
        self._pipelines: Dict[str, CameraInferencePipeline] = {}
        self._ws_broadcast: Optional[Callable] = None

    def set_ws_broadcast(self, fn: Callable):
        self._ws_broadcast = fn

    def start_pipeline(self, camera_id: str):
        if camera_id in self._pipelines:
            return
        pipeline = CameraInferencePipeline(camera_id, self._ws_broadcast)
        self._pipelines[camera_id] = pipeline
        pipeline.start()
        logger.info(f"Inference pipeline started: {camera_id}")

    def stop_pipeline(self, camera_id: str):
        pipeline = self._pipelines.pop(camera_id, None)
        if pipeline:
            pipeline.stop()

    def start_all(self):
        """Start inference for all currently running camera workers."""
        from backend.cameras.camera_manager import camera_manager
        for cam_id in camera_manager.get_all_workers():
            self.start_pipeline(cam_id)

    def shutdown(self):
        for pipeline in list(self._pipelines.values()):
            pipeline.stop()
        self._pipelines.clear()



pipeline_manager = PipelineManager()
