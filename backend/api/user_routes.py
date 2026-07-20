"""
User API routes — accessible by role=user (and above).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from backend.db.session import get_db
from backend.db.models import (
    Camera, CameraStatus, DetectionEvent, Notification,
    LoginAttempt, TrustedDevice, User
)
from backend.security.auth_dep import get_current_user

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/cameras")
async def list_my_cameras(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List cameras (all cameras visible to users)."""
    cameras = db.query(Camera).all()
    return {"data": [_camera_dict(c) for c in cameras]}


@router.get("/cameras/{camera_id}/status")
async def get_camera_status(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    from backend.cameras.camera_manager import camera_manager
    worker = camera_manager.get_worker(camera_id)
    return {
        "data": {
            "id": camera.id,
            "status": camera.status.value,
            "fps": worker.fps if worker else 0,
            "last_seen_at": camera.last_seen_at.isoformat() if camera.last_seen_at else None,
        }
    }


@router.get("/events")
async def list_events(
    camera_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Paginated detection events feed."""
    q = db.query(DetectionEvent)
    if camera_id:
        q = q.filter(DetectionEvent.camera_id == camera_id)
    if event_type:
        q = q.filter(DetectionEvent.event_type == event_type)
    total = q.count()
    events = q.order_by(DetectionEvent.timestamp.desc()).offset(offset).limit(limit).all()
    return {
        "data": [_event_dict(e) for e in events],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post("/events/{event_id}/acknowledge")
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


@router.get("/notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.read == False)
    notifications = q.order_by(Notification.created_at.desc()).limit(limit).all()
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.read == False
    ).count()
    return {
        "data": [_notification_dict(n) for n in notifications],
        "unread_count": unread_count,
    }


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read = True
    db.commit()
    return {"success": True}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.read == False
    ).update({"read": True})
    db.commit()
    return {"success": True}


@router.get("/login-history")
async def get_my_login_history(
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.user_id == current_user.id)
        .order_by(LoginAttempt.timestamp.desc())
        .limit(limit)
        .all()
    )
    return {"data": [_attempt_dict(a) for a in attempts]}


@router.get("/trusted-devices")
async def list_trusted_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    devices = (
        db.query(TrustedDevice)
        .filter(TrustedDevice.user_id == current_user.id, TrustedDevice.revoked == False)
        .all()
    )
    return {
        "data": [
            {
                "id": d.id,
                "issued_at": d.issued_at.isoformat(),
                "expires_at": d.expires_at.isoformat(),
            }
            for d in devices
        ]
    }


@router.delete("/trusted-devices/{device_id}")
async def revoke_trusted_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(TrustedDevice).filter(
        TrustedDevice.id == device_id,
        TrustedDevice.user_id == current_user.id,
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.revoked = True
    db.commit()
    return {"success": True}


@router.get("/analytics")
async def get_analytics(
    camera_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Basic event count analytics per camera and event type."""
    from sqlalchemy import func
    q = db.query(
        DetectionEvent.camera_id,
        DetectionEvent.event_type,
        func.count(DetectionEvent.id).label("count"),
    )
    if camera_id:
        q = q.filter(DetectionEvent.camera_id == camera_id)
    rows = q.group_by(DetectionEvent.camera_id, DetectionEvent.event_type).all()
    return {
        "data": [
            {"camera_id": r.camera_id, "event_type": r.event_type, "count": r.count}
            for r in rows
        ]
    }



def _camera_dict(c: Camera) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "sourceType": c.source_type,
        "status": c.status.value if c.status else "offline",
        "lastSeenAt": c.last_seen_at.isoformat() if c.last_seen_at else None,
        "retentionDays": c.retention_days,
    }


def _event_dict(e: DetectionEvent) -> dict:
    return {
        "id": e.id,
        "cameraId": e.camera_id,
        "eventType": e.event_type,
        "confidence": e.confidence,
        "timestamp": e.timestamp.isoformat(),
        "snapshotPath": e.snapshot_path_encrypted,
        "boundingBoxes": e.bounding_boxes_json,
        "acknowledged": e.acknowledged,
    }


def _notification_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "type": n.notification_type,
        "read": n.read,
        "createdAt": n.created_at.isoformat(),
        "detectionEventId": n.detection_event_id,
    }


def _attempt_dict(a: LoginAttempt) -> dict:
    return {
        "id": a.id,
        "result": a.result,
        "timestamp": a.timestamp.isoformat(),
        "ipAddress": a.ip_address,
        "browserName": a.browser_name,
        "osName": a.os_name,
        "deviceType": a.device_type,
    }




@router.get("/recordings")
async def list_recordings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all available video recordings."""
    import os
    from backend.core.config import config
    
    events = (
        db.query(DetectionEvent)
        .filter(DetectionEvent.clip_path_encrypted.isnot(None))
        .order_by(DetectionEvent.timestamp.desc())
        .all()
    )
    
    data = []
    for e in events:
        path = e.clip_path_encrypted
        if not path or not os.path.exists(path):
            continue
            
        camera = db.query(Camera).filter(Camera.id == e.camera_id).first()
        camera_name = camera.name if camera else "Unknown Camera"
        
        file_size = os.path.getsize(path)
        duration = camera.record_duration_seconds if camera else 60
        
        data.append({
            "id": e.id,
            "cameraId": e.camera_id,
            "cameraName": camera_name,
            "eventType": e.event_type,
            "confidence": e.confidence,
            "timestamp": e.timestamp.isoformat(),
            "fileSize": file_size,
            "duration": duration,
            "url": f"/api/user/recordings/{e.id}/stream",
            "downloadUrl": f"/api/user/recordings/{e.id}/download",
        })
        
    return {"data": data}


@router.get("/recordings/{event_id}/stream")
async def stream_recording(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream a video recording."""
    import os
    from fastapi.responses import FileResponse
    
    event = db.query(DetectionEvent).filter(DetectionEvent.id == event_id).first()
    if not event or not event.clip_path_encrypted:
        raise HTTPException(status_code=404, detail="Recording not found")
        
    path = event.clip_path_encrypted
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Recording file not found on disk")
        
    return FileResponse(path, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})


@router.get("/recordings/{event_id}/download")
async def download_recording(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a video recording."""
    import os
    from fastapi.responses import FileResponse
    
    event = db.query(DetectionEvent).filter(DetectionEvent.id == event_id).first()
    if not event or not event.clip_path_encrypted:
        raise HTTPException(status_code=404, detail="Recording not found")
        
    path = event.clip_path_encrypted
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Recording file not found on disk")
        
    filename = os.path.basename(path)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=filename
    )


@router.delete("/recordings/{event_id}")
async def delete_recording(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a video recording (Master Admin only)."""
    import os
    from backend.db.models import MasterAdmin
    
    if not isinstance(current_user, MasterAdmin):
        raise HTTPException(status_code=403, detail="Only Master Admin is authorized to delete recordings")
        
    event = db.query(DetectionEvent).filter(DetectionEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Recording not found")
        
    path = event.clip_path_encrypted
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            logger.error(f"Failed to delete recording file {path}: {e}")
            
    event.clip_path_encrypted = None
    db.commit()
    return {"success": True}
