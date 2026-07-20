"""
Admin API routes — admin and master_admin roles only.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import User, Admin, AIModel, LoginAttempt, UserRole, AccountStatus
from backend.security.auth_dep import get_current_user
from backend.security.hashing import hash_password, hash_pin

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(user: User):
    from backend.db.models import MasterAdmin
    if isinstance(user, MasterAdmin):
        return
        
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role not in ("admin", "master_admin", "UserRole.ADMIN", "UserRole.MASTER_ADMIN"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")



@router.get("/users")
async def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    users = db.query(User).filter(User.role == UserRole.USER).all()
    return {"data": [_user_dict(u) for u in users]}


@router.post("/users")
async def create_user(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    username = payload.get("username")
    password = payload.get("password")
    role = payload.get("role", "user")

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    # hash_password returns (hash, salt)
    pwd_hash, pwd_salt = hash_password(password)

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=pwd_hash,
        salt=pwd_salt,
        role=UserRole(role),
        status=AccountStatus.ACTIVE,
        created_by=current_user.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"data": _user_dict(user)}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    db.delete(user)
    db.commit()
    return {"success": True}


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    new_password = payload.get("newPassword")
    if not new_password:
        raise HTTPException(status_code=400, detail="newPassword required")
    pwd_hash, pwd_salt = hash_password(new_password)
    user.password_hash = pwd_hash
    user.salt = pwd_salt
    db.commit()
    return {"success": True}


@router.post("/users/{user_id}/re-enable")
async def reenable_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = AccountStatus.ACTIVE
    user.failed_attempt_count = 0
    user.lockout_until = None
    db.commit()
    return {"success": True}


@router.get("/users/{user_id}/login-history")
async def get_user_login_history(
    user_id: str,
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    attempts = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.user_id == user_id)
        .order_by(LoginAttempt.timestamp.desc())
        .limit(limit)
        .all()
    )
    return {
        "data": [
            {
                "id": a.id,
                "result": a.result,
                "timestamp": a.timestamp.isoformat(),
                "ipAddress": a.ip_address,
                "browserName": a.browser_name,
                "osName": a.os_name,
                "deviceType": a.device_type,
            }
            for a in attempts
        ]
    }



@router.get("/ai-models")
async def list_ai_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    models = db.query(AIModel).all()
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
            }
            for m in models
        ]
    }


@router.post("/ai-models/{model_id}/toggle")
async def toggle_ai_model(
    model_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    model = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if "enabled" in payload:
        model.enabled_globally = bool(payload["enabled"])
        
    if "fpsLimit" in payload or "allowedClasses" in payload or "confidenceThreshold" in payload or "alertsEnabled" in payload:
        cfg = dict(model.config_json) if isinstance(model.config_json, dict) else {}
        if "fpsLimit" in payload:
            fps_val = payload["fpsLimit"]
            if fps_val is None or str(fps_val).lower() == "unlimited" or str(fps_val) == "":
                cfg["fps_limit"] = None
            else:
                cfg["fps_limit"] = int(fps_val)
        if "allowedClasses" in payload:
            classes_val = payload["allowedClasses"]
            if classes_val is None or not isinstance(classes_val, list):
                cfg["allowed_classes"] = None
            else:
                cfg["allowed_classes"] = [str(c).lower().strip() for c in classes_val]
        if "confidenceThreshold" in payload:
            thresh_val = payload["confidenceThreshold"]
            if thresh_val is None or thresh_val == "":
                cfg["confidence_threshold"] = 0.5
            else:
                cfg["confidence_threshold"] = float(thresh_val)
        if "alertsEnabled" in payload:
            cfg["alerts_enabled"] = bool(payload["alertsEnabled"])
        model.config_json = cfg
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(model, "config_json")

    db.commit()
    return {"success": True}



@router.get("/cameras/status")
async def cameras_status(
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    from backend.cameras.camera_manager import camera_manager
    return {"data": camera_manager.get_status_all()}



@router.get("/system/stats")
async def system_stats(
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    from backend.system.resource_monitor import resource_monitor
    return {"data": resource_monitor.get_stats()}



def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role.value if u.role else "user",
        "status": u.status.value if u.status else "active",
        "lastLoginAt": u.last_login_at.isoformat() if u.last_login_at else None,
        "failedAttemptCount": u.failed_attempt_count,
        "createdAt": u.created_at.isoformat() if u.created_at else None,
    }
