"""
Camera and detection event routes — Admin for write operations, any auth for reads.
"""

import uuid
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import Camera, CameraStatus, AIModel, CameraModelLink, DetectionEvent, Alert, AlertLog, Notification, User
from backend.security.auth_dep import get_current_user

router = APIRouter(prefix="/api", tags=["cameras"])


def _delete_camera_related_records(db: Session, camera_id: str) -> None:
    """Remove dependent rows for a camera without violating foreign-key constraints."""
    detection_ids_subq = (
        select(DetectionEvent.id)
        .where(DetectionEvent.camera_id == camera_id)
        .scalar_subquery()
    )

    try:
        db.query(AlertLog).filter(AlertLog.detection_event_id.in_(detection_ids_subq)).delete(synchronize_session=False)
    except Exception:
        pass

    try:
        db.query(Notification).filter(Notification.detection_event_id.in_(detection_ids_subq)).delete(synchronize_session=False)
    except Exception:
        pass

    try:
        db.query(Alert).filter(Alert.camera_id == camera_id).delete(synchronize_session=False)
    except Exception:
        pass

    try:
        db.query(DetectionEvent).filter(DetectionEvent.camera_id == camera_id).delete(synchronize_session=False)
    except Exception:
        pass

    try:
        db.query(CameraModelLink).filter(CameraModelLink.camera_id == camera_id).delete(synchronize_session=False)
    except Exception:
        pass


# ── Camera list (all authenticated users) ──────────────────────────────────────
@router.get("/cameras")
async def list_cameras(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cameras = db.query(Camera).all()
    from backend.cameras.camera_manager import camera_manager
    return {
        "data": [
            {
                "id": c.id,
                "name": c.name,
                "sourceType": c.source_type,
                "connectionUri": c.connection_uri_encrypted,
                "status": c.status.value if c.status else "offline",
                "lastSeenAt": c.last_seen_at.isoformat() if c.last_seen_at else None,
                "retentionDays": c.retention_days,
                "recordEnabled": c.record_enabled,
                "recordDurationSeconds": c.record_duration_seconds,
                "addedAt": c.added_at.isoformat() if c.added_at else None,
                "fps": camera_manager.get_worker(c.id).fps if camera_manager.get_worker(c.id) else 0,
            }
            for c in cameras
        ]
    }


@router.get("/cameras/{camera_id}")
async def get_camera(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {
        "data": {
            "id": camera.id,
            "name": camera.name,
            "sourceType": camera.source_type,
            "connectionUri": camera.connection_uri_encrypted,
            "status": camera.status.value if camera.status else "offline",
            "lastSeenAt": camera.last_seen_at.isoformat() if camera.last_seen_at else None,
            "retentionDays": camera.retention_days,
            "recordEnabled": camera.record_enabled,
            "recordDurationSeconds": camera.record_duration_seconds,
        }
    }


# ── Camera CRUD (admin only) ────────────────────────────────────────────────────
@router.post("/admin/cameras")
async def create_camera(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    name = payload.get("name")
    source_type = payload.get("sourceType", "rtsp")
    connection_uri = payload.get("connectionUri", "")
    retention_days = int(payload.get("retentionDays", 7))
    record_enabled = bool(payload.get("recordEnabled", False))
    record_duration_seconds = int(payload.get("recordDurationSeconds", 60))

    if source_type in ("webcam", "usb", "capture_card") and not connection_uri:
        connection_uri = "0"

    if not name or not connection_uri:
        raise HTTPException(status_code=400, detail="name and connectionUri are required")

    resolution = payload.get("resolution", "default")
    if resolution not in ("default", "4k", "2k", "1080", "720", "480", "240"):
        resolution = "default"

    if record_duration_seconds < 20:
        record_duration_seconds = 20

    camera = Camera(
        id=str(uuid.uuid4()),
        name=name,
        source_type=source_type,
        connection_uri_encrypted=connection_uri,
        added_by=current_user.id,
        retention_days=retention_days,
        resolution=resolution,
        record_enabled=record_enabled,
        record_duration_seconds=record_duration_seconds,
    )
    db.add(camera)

    # Create default model links for all globally enabled models
    models = db.query(AIModel).filter(AIModel.enabled_globally == True).all()
    for model in models:
        link = CameraModelLink(
            id=str(uuid.uuid4()),
            camera_id=camera.id,
            ai_model_id=model.id,
            enabled=True,
        )
        db.add(link)

    db.commit()
    db.refresh(camera)

    
    from backend.cameras.camera_manager import camera_manager
    camera_manager.add_camera(camera.id, camera.name, camera.source_type, connection_uri)

    
    from backend.ai.pipeline import pipeline_manager
    pipeline_manager.start_pipeline(camera.id)

    return {
        "data": {
            "id": camera.id,
            "name": camera.name,
            "sourceType": camera.source_type,
            "status": "offline",
            "retentionDays": camera.retention_days,
            "resolution": camera.resolution,
            "recordEnabled": camera.record_enabled,
            "recordDurationSeconds": camera.record_duration_seconds,
        }
    }


@router.put("/admin/cameras/{camera_id}")
async def update_camera(
    camera_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
        
    needs_restart = False
    if "name" in payload:
        camera.name = payload["name"]
    if "sourceType" in payload:
        camera.source_type = payload["sourceType"]
        needs_restart = True
    if "connectionUri" in payload:
        connection_uri = payload["connectionUri"]
        if camera.source_type in ("webcam", "usb", "capture_card") and not connection_uri:
            connection_uri = "0"
        camera.connection_uri_encrypted = connection_uri
        needs_restart = True
    if "resolution" in payload:
        resolution = payload["resolution"]
        if resolution not in ("default", "4k", "2k", "1080", "720", "480", "240"):
            resolution = "default"
        camera.resolution = resolution
        needs_restart = True
    if "recordEnabled" in payload:
        camera.record_enabled = bool(payload["recordEnabled"])
    if "recordDurationSeconds" in payload:
        camera.record_duration_seconds = max(20, int(payload["recordDurationSeconds"]))
    if "retentionDays" in payload:
        camera.retention_days = int(payload["retentionDays"])
        
    db.commit()
    
    if needs_restart:
        try:
            from backend.cameras.camera_manager import camera_manager
            from backend.ai.pipeline import pipeline_manager
            
            
            camera_manager.remove_camera(camera_id)
            pipeline_manager.stop_pipeline(camera_id)
            
            # Start with new settings
            camera_manager.add_camera(camera.id, camera.name, camera.source_type, camera.connection_uri_encrypted)
            pipeline_manager.start_pipeline(camera.id)
        except Exception:
            pass
            
    return {"success": True}


@router.delete("/admin/cameras/{camera_id}")
async def delete_camera(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    from backend.cameras.camera_manager import camera_manager
    camera_manager.remove_camera(camera_id)
    from backend.ai.pipeline import pipeline_manager
    pipeline_manager.stop_pipeline(camera_id)

    
    _delete_camera_related_records(db, camera_id)

    db.delete(camera)
    db.commit()
    return {"success": True}


@router.post("/admin/cameras/{camera_id}/restart")
async def restart_camera(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    from backend.cameras.camera_manager import camera_manager
    ok = camera_manager.restart_camera(camera_id)
    return {"success": ok}


# ── Camera model config (admin) ────────────────────────────────────────────────
@router.get("/admin/cameras/{camera_id}/models")
async def get_camera_models(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    links = (
        db.query(CameraModelLink, AIModel)
        .join(AIModel, CameraModelLink.ai_model_id == AIModel.id)
        .filter(CameraModelLink.camera_id == camera_id)
        .filter(AIModel.enabled_globally == True)
        .all()
    )
    return {
        "data": [
            {
                "linkId": link.id,
                "modelId": model.id,
                "modelKey": model.key,
                "displayName": model.display_name,
                "enabled": link.enabled,
                "sensitivityConfig": link.sensitivity_config_json,
                "roiZones": link.roi_zones_json,
                "schedule": link.schedule_json,
            }
            for link, model in links
        ]
    }


@router.put("/admin/cameras/{camera_id}/models/{model_id}")
async def update_camera_model(
    camera_id: str,
    model_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    link = (
        db.query(CameraModelLink)
        .filter(
            CameraModelLink.camera_id == camera_id,
            CameraModelLink.ai_model_id == model_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Camera-model link not found")
    if "enabled" in payload:
        link.enabled = bool(payload["enabled"])
    if "sensitivityConfig" in payload:
        link.sensitivity_config_json = payload["sensitivityConfig"]
    if "roiZones" in payload:
        link.roi_zones_json = payload["roiZones"]
    if "schedule" in payload:
        link.schedule_json = payload["schedule"]
    db.commit()
    return {"success": True}



@router.get("/detections")
async def get_detections(
    camera_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(DetectionEvent)
    if camera_id:
        q = q.filter(DetectionEvent.camera_id == camera_id)
    if event_type:
        q = q.filter(DetectionEvent.event_type == event_type)
    total = q.count()
    events = q.order_by(DetectionEvent.timestamp.desc()).offset(offset).limit(limit).all()
    return {
        "data": [
            {
                "id": e.id,
                "cameraId": e.camera_id,
                "eventType": e.event_type,
                "confidence": e.confidence,
                "timestamp": e.timestamp.isoformat(),
                "snapshotPath": e.snapshot_path_encrypted,
                "boundingBoxes": e.bounding_boxes_json,
                "acknowledged": e.acknowledged,
            }
            for e in events
        ],
        "total": total,
    }


@router.post("/detections/{event_id}/acknowledge")
async def acknowledge_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(DetectionEvent).filter(DetectionEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.acknowledged = True
    event.acknowledged_by = current_user.id
    db.commit()
    return {"success": True}



@router.get("/ai-models")
async def list_ai_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.db.models import UserRole, MasterAdmin
    # Detect if request is from master admin
    is_master = isinstance(current_user, MasterAdmin)
    if not is_master and hasattr(current_user, "role"):
        if current_user.role == UserRole.MASTER_ADMIN:
            is_master = True
        elif getattr(current_user.role, "value", None) == "master_admin":
            is_master = True

    query = db.query(AIModel)
    if not is_master:
        query = query.filter(AIModel.enabled_globally == True)

    models = query.all()
    from backend.ai.registry import model_registry
    return {
        "data": [
            {
                "id": m.id,
                "key": m.key,
                "displayName": m.display_name,
                "enabledGlobally": m.enabled_globally,
                "requiresGpu": m.requires_gpu,
                "fpsLimit": m.config_json.get("fps_limit") if isinstance(m.config_json, dict) else None,
                "confidenceThreshold": m.config_json.get("confidence_threshold") if isinstance(m.config_json, dict) else 0.5,
                "allowedClasses": m.config_json.get("allowed_classes") if isinstance(m.config_json, dict) else None,
                "alertsEnabled": m.config_json.get("alerts_enabled", True) if isinstance(m.config_json, dict) else True,
                "loaded": model_registry.get_model(m.key) is not None and
                          (model_registry.get_model(m.key).is_loaded if model_registry.get_model(m.key) else False),
            }
            for m in models
        ]
    }



def _require_admin(user: User):
    from backend.db.models import MasterAdmin
    if isinstance(user, MasterAdmin):
        return
        
    if user.role not in (None,) and hasattr(user.role, "value"):
        role_val = user.role.value
    else:
        role_val = str(user.role)
    if role_val not in ("admin", "master_admin", "UserRole.ADMIN", "UserRole.MASTER_ADMIN"):
        raise HTTPException(status_code=403, detail="Insufficient permissions — admin required")



from fastapi import UploadFile, File
import glob
import sys
import os

def detect_usb_devices() -> list:
    devices = []
    if sys.platform.startswith("linux"):
        
        paths = glob.glob("/sys/class/video4linux/video*")
        for path in sorted(paths):
            try:
                device_index = path.split("video")[-1]
                dev_path = f"/dev/video{device_index}"
                name_file = os.path.join(path, "name")
                if os.path.exists(name_file):
                    with open(name_file, "r") as f:
                        device_name = f.read().strip()
                else:
                    device_name = f"USB Video Device {device_index}"
                
                
                name_lower = device_name.lower()
                is_capture = any(kw in name_lower for kw in ("capture", "grabber", "hdmi", "card", "utv", "easycap", "fushicai", "ezcap"))
                dev_type = "capture_card" if is_capture else "camera"
                
                devices.append({
                    "id": dev_path,
                    "name": device_name,
                    "path": dev_path,
                    "type": dev_type
                })
            except Exception:
                pass
    else:
        
        # Since we cannot detect actual name, we just return index
        for i in range(5):
            try:
                import cv2
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        devices.append({
                            "id": str(i),
                            "name": f"USB Video Device (Index {i})",
                            "path": str(i),
                            "type": "camera"
                        })
                    cap.release()
            except Exception:
                pass
    return devices

@router.get("/admin/cameras/detect-usb")
async def detect_usb(
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return {"data": detect_usb_devices()}

@router.post("/admin/cameras/upload-video")
async def upload_camera_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    from pathlib import Path
    from backend.core.config import config
    
    upload_dir = config.BACKEND_DIR / ".data" / "local_videos"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    ext = Path(file.filename).suffix.lower()
    if ext not in (".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".ts"):
        raise HTTPException(status_code=400, detail="Unsupported video format")
        
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = upload_dir / filename
    
    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)
        
    return {"data": {"path": str(dest_path), "filename": file.filename}}
