"""
Master Admin API routes — all endpoints require localhost (enforced by MasterAdminMiddleware in app.py).
"""

import uuid
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Body
from sqlalchemy.orm import Session

from backend.db.session import get_db, DatabaseManager
from backend.db.models import (
    MasterAdmin, User, Admin, Camera, AIModel, AlertContact, AuditLog,
    SystemConfig, Face, UserRole
)
from backend.security.hashing import hash_password, hash_pin
from backend.security.tokens import get_current_user_from_token
from backend.core.config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/master", tags=["master-admin"])


def _require_master(request: Request, db: Session = Depends(get_db)) -> MasterAdmin:
    """Dependency: validate master admin session token."""
    token = request.headers.get("X-Session-Token") or (
        request.headers.get("Authorization", "").replace("Bearer ", "") or None
    )
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = get_current_user_from_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid session")
    master = db.query(MasterAdmin).first()
    if not master or user.id != master.id:
        raise HTTPException(status_code=403, detail="Master admin access required")
    return master



@router.get("/config")
async def get_config(
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    rows = db.query(SystemConfig).all()
    conf = {r.key: r.value_encrypted for r in rows}
    return {
        "data": {
            "hostname": master.hostname,
            "port": master.port,
            "inference_device": conf.get("inference_device", "auto"),
            "retention_days": conf.get("retention_days", "7"),
            "theme": conf.get("theme", "dark"),
            "record_on_event": conf.get("record_on_event", "false") == "true",
            "ai_processing_enabled": conf.get("ai_processing_enabled", "true") == "true",
        }
    }


@router.patch("/config")
async def update_config(
    payload: dict = Body(...),
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    if "hostname" in payload:
        master.hostname = payload["hostname"]
    if "port" in payload:
        master.port = int(payload["port"])
    for key in ("inference_device", "retention_days", "theme", "record_on_event", "ai_processing_enabled"):
        if key in payload:
            val = str(payload[key]).lower() if key in ("record_on_event", "ai_processing_enabled") else str(payload[key])
            row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if row:
                row.value_encrypted = val
            else:
                db.add(SystemConfig(id=str(uuid.uuid4()), key=key, value_encrypted=val))
    db.commit()
    return {"success": True}



@router.get("/audit")
async def get_audit_log(
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    total = db.query(AuditLog).count()
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.sequence_number.desc())
        .offset(offset).limit(limit).all()
    )
    return {
        "data": [_audit_dict(r) for r in rows],
        "total": total,
    }


@router.post("/audit/verify")
async def verify_audit_chain(
    master: MasterAdmin = Depends(_require_master),
):
    from backend.audit.logger import audit_logger
    result = audit_logger.verify_chain()
    return {"data": result}



@router.get("/admins")
async def list_admins(
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
    return {"data": [_user_dict(u) for u in admins]}


@router.post("/admins")
async def create_admin(
    payload: dict = Body(...),
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    username = payload.get("username")
    password = payload.get("password")
    pin = payload.get("pin")
    if not username or not password or not pin:
        raise HTTPException(status_code=400, detail="username, password, and pin are required")
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    pwd_hash, pwd_salt = hash_password(password)
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=pwd_hash,
        salt=pwd_salt,
        role=UserRole.ADMIN,
        status="active",
    )
    db.add(user)
    db.flush()
    pin_hash, pin_salt = hash_pin(pin)
    db.add(Admin(id=user.id, pin_hash=pin_hash, pin_salt=pin_salt))
    db.commit()
    return {"data": _user_dict(user)}


@router.delete("/admins/{user_id}")
async def delete_admin(
    user_id: str,
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.ADMIN).first()
    if not user:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    admin = db.query(Admin).filter(Admin.id == user_id).first()
    if admin:
        db.delete(admin)
        
    db.delete(user)
    db.commit()
    return {"success": True}


@router.post("/admins/{user_id}/reset-password")
async def reset_admin_password(
    user_id: str,
    payload: dict = Body(...),
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    new_pwd = payload.get("newPassword")
    if not new_pwd:
        raise HTTPException(status_code=400, detail="newPassword required")
    pwd_hash, pwd_salt = hash_password(new_pwd)
    user.password_hash = pwd_hash
    user.salt = pwd_salt
    db.commit()
    return {"success": True}



@router.get("/recovery-key/status")
async def recovery_key_status(
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    m = db.query(MasterAdmin).first()
    return {
        "data": {
            "created_at": m.recovery_key_created_at.isoformat() if m.recovery_key_created_at else None,
            "used": m.recovery_key_used,
        }
    }


@router.post("/recovery-key/regenerate")
async def regenerate_recovery_key(
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    from backend.security.hashing import generate_recovery_key, hash_recovery_key
    m = db.query(MasterAdmin).first()
    new_key = generate_recovery_key()
    new_hash, new_salt = hash_recovery_key(new_key)
    m.recovery_key_hash = new_hash
    m.recovery_key_salt = new_salt
    m.recovery_key_created_at = datetime.utcnow()
    m.recovery_key_used = False
    db.commit()
    return {"data": {"recovery_key": new_key}}



@router.get("/contacts")
async def list_contacts(
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    contacts = db.query(AlertContact).all()
    return {"data": [_contact_dict(c) for c in contacts]}


@router.post("/contacts")
async def create_contact(
    payload: dict = Body(...),
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    contact = AlertContact(
        id=str(uuid.uuid4()),
        name=payload.get("name", ""),
        channel=payload.get("channel", "telegram"),
        bot_token=payload.get("bot_token"),
        chat_id=payload.get("chat_id"),
        enabled=True,
    )
    db.add(contact)
    db.commit()
    return {"data": _contact_dict(contact)}


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: str,
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    contact = db.query(AlertContact).filter(AlertContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"success": True}


@router.post("/contacts/{contact_id}/test")
async def test_contact(
    contact_id: str,
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    contact = db.query(AlertContact).filter(AlertContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if contact.channel == "telegram":
        from backend.alerts.channels.telegram_channel import test_telegram_connection
        result = test_telegram_connection(contact.bot_token, contact.chat_id)
        return {"data": result}
    return {"data": {"success": False, "message": f"No test for channel: {contact.channel}"}}



@router.get("/faces")
async def list_faces(
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    faces = db.query(Face).all()
    return {
        "data": [
            {"id": f.id, "label": f.label, "enrolled_at": f.enrolled_at.isoformat()}
            for f in faces
        ]
    }


@router.post("/faces")
async def enroll_face(
    label: Optional[str] = Query(None),
    images: List[UploadFile] = File(...),
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    """Enroll faces by uploading multiple images (associated with a label, or auto-naming from filenames)."""
    import cv2
    import numpy as np
    import re
    from pathlib import Path

    enrolled_count = 0
    errors = []

    from backend.ai.registry import model_registry
    face_model = model_registry.get_model("face")

    for image in images:
        try:
            
            img_label = label
            if not img_label:
                # Auto extract from filename
                stem = Path(image.filename).stem
                # Replace underscores/hyphens with spaces and remove trailing numbers
                cleaned = stem.replace("_", " ").replace("-", " ")
                img_label = re.sub(r'[\s_]*\d+$', '', cleaned).strip()
                if not img_label:
                    img_label = "Unknown Enrolled"

            data = await image.read()
            arr = np.frombuffer(data, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                errors.append(f"{image.filename}: Invalid image data")
                continue

            embedding = None
            if face_model and face_model.is_loaded and face_model._backend == "face_recognition":
                import face_recognition
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                locs = face_recognition.face_locations(rgb)
                if not locs:
                    errors.append(f"{image.filename}: No face detected")
                    continue
                encs = face_recognition.face_encodings(rgb, locs)
                if not encs:
                    errors.append(f"{image.filename}: Could not extract face embedding")
                    continue
                embedding = encs[0].astype(np.float32)
            elif face_model and face_model.is_loaded and face_model._backend == "insightface":
                faces = face_model._insightface_app.get(frame)
                if not faces or faces[0].normed_embedding is None:
                    errors.append(f"{image.filename}: No face or embedding found with InsightFace")
                    continue
                embedding = faces[0].normed_embedding.astype(np.float32)
            else:
                errors.append(f"{image.filename}: Face matching backend (face_recognition/insightface) not active/loaded")
                continue

            emb_b64 = base64.b64encode(embedding.tobytes()).decode()
            sample_dir = config.RECORDINGS_DIR.parent / "faces"
            sample_dir.mkdir(parents=True, exist_ok=True)
            sample_path = sample_dir / f"{img_label.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.jpg"
            cv2.imwrite(str(sample_path), frame)

            face = Face(
                id=str(uuid.uuid4()),
                label=img_label,
                embedding_encrypted=emb_b64,
                sample_image_path=str(sample_path),
            )
            db.add(face)
            enrolled_count += 1
        except Exception as e:
            errors.append(f"{image.filename}: Error - {str(e)}")

    if enrolled_count > 0:
        db.commit()
        model_registry.refresh_face_embeddings()

    if enrolled_count == 0 and errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    return {
        "success": True,
        "data": {
            "enrolled_count": enrolled_count,
            "errors": errors
        }
    }


@router.delete("/faces/{face_id}")
async def delete_face(
    face_id: str,
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    face = db.query(Face).filter(Face.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    db.delete(face)
    db.commit()
    from backend.ai.registry import model_registry
    model_registry.refresh_face_embeddings()
    return {"success": True}



@router.post("/lockdown")
async def activate_lockdown(
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    """Disable all non-master accounts immediately."""
    from backend.db.models import AccountStatus
    db.query(User).filter(User.role != UserRole.ADMIN).update({"status": AccountStatus.DISABLED})
    db.commit()
    return {"success": True, "message": "All user accounts disabled"}


@router.post("/lockdown/release")
async def release_lockdown(
    master: MasterAdmin = Depends(_require_master),
    db: Session = Depends(get_db),
):
    """Re-enable all accounts that were disabled by lockdown."""
    from backend.db.models import AccountStatus
    db.query(User).filter(User.status == AccountStatus.DISABLED).update({"status": AccountStatus.ACTIVE})
    db.commit()
    return {"success": True, "message": "All accounts re-enabled"}



@router.get("/hardware")
async def hardware_report(
    master: MasterAdmin = Depends(_require_master),
):
    from backend.system.hardware_scan import get_hardware_report
    return {"data": get_hardware_report()}



@router.post("/backup")
async def create_backup(
    master: MasterAdmin = Depends(_require_master),
):
    """Export DB file as downloadable backup."""
    from fastapi.responses import FileResponse
    db_path = config.DATABASE_PATH
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")
    filename = f"edge_drishti_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return FileResponse(
        str(db_path),
        filename=filename,
        media_type="application/octet-stream",
    )



def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role.value if u.role else "user",
        "status": u.status.value if u.status else "active",
        "lastLoginAt": u.last_login_at.isoformat() if u.last_login_at else None,
        "createdAt": u.created_at.isoformat() if u.created_at else None,
        "failedAttemptCount": u.failed_attempt_count,
    }


def _audit_dict(r: AuditLog) -> dict:
    return {
        "id": r.id,
        "sequence": r.sequence_number,
        "actorId": r.actor_id,
        "actorRole": r.actor_role,
        "action": r.action,
        "targetType": r.target_type,
        "targetId": r.target_id,
        "detail": r.detail,
        "ipAddress": r.ip_address,
        "timestamp": r.timestamp.isoformat(),
        "rowHash": r.row_hash,
    }


def _contact_dict(c: AlertContact) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "channel": c.channel,
        "chatId": c.chat_id,
        "enabled": c.enabled,
        "addedAt": c.added_at.isoformat() if c.added_at else None,
    }
