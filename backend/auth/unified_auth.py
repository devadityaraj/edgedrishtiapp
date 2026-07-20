"""
Unified authentication route that auto-detects user vs admin based on database record.
This replaces the need for manual role selection on the frontend.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from backend.db import get_db, User, Session as DBSession, UserRole, TrustedDevice, LoginAttempt, Admin
from backend.security import (
    hash_password, verify_password, generate_secure_token
)
from backend.security.lockout import LockoutStateMachine, LoginAttemptResult, IPBasedLockout
from backend.security.fingerprint import fingerprint_manager
from backend.security.tokens import TokenManager
from backend.api.schemas import LoginRequest, LoginResponse, ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies"""
    if request.client:
        return request.client.host
    return "unknown"


def _is_localhost(request: Request) -> bool:
    """Check if request originated from localhost or via the admin mDNS hostname.
    
    Considers a request 'local' if:
      - The TCP client IP is a loopback/localhost address, OR
      - The Host header is 'edgedrishti-admin.local' (our loopback-bound mDNS name)
    """
    client_host = request.client.host if request.client else ""
    host_header = request.headers.get("host", "").split(":")[0].lower()
    return (
        client_host in ("127.0.0.1", "localhost", "::1")
        or host_header == "edgedrishti-admin.local"
    )


@router.get("/check-localhost")
async def check_localhost(request: Request):
    """Check if request is from localhost (for showing master admin link)"""
    is_localhost = _is_localhost(request)
    return {"is_localhost": is_localhost}



@router.post("/login", response_model=LoginResponse)
async def unified_login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Unified login endpoint that auto-detects user vs admin.
    
    Flow:
    1. Check IP lockout
    2. Query User table for username
    3. If found, verify password and auto-detect role from User.role field
    4. If not found, check Admin table (admins may also be in User table with role=admin)
    5. Return appropriate redirect based on detected role
    
    The frontend doesn't need to know the role - backend handles it automatically.
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    
    
    is_ip_locked, ip_lock_message = IPBasedLockout.is_ip_locked(client_ip)
    if is_ip_locked:
        logger.warning(f"IP locked: {client_ip} - {ip_lock_message}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Invalid credentials"
        )
    
    # Guard: if no users exist, block logins
    if db.query(User).count() == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active user accounts found in the database. Please register a user account through the Master Admin console first."
        )
    
    
    user = db.query(User).filter(User.username == login_data.username).first()
    
    if not user:
        
        result, new_failed_count, new_lockout_until = LockoutStateMachine.process_failed_login_attempt(
            0,
            username_found=False
        )
        
        if result == LoginAttemptResult.LOCKED_TEMPORARY:
            IPBasedLockout.lock_ip(client_ip)
        
        _log_login_attempt(
            db, login_data.username, "unknown", "username_not_found",
            client_ip, user_agent, login_data.browser_data or {}
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Account exists - check if disabled
    if user.status.value == "disabled":
        logger.warning(f"Disabled account login attempt: {login_data.username}")
        _log_login_attempt(
            db, login_data.username, user.role.value if user.role else "user", 
            "account_disabled", client_ip, user_agent, login_data.browser_data or {}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    
    lockout_status, lockout_msg = LockoutStateMachine.check_lockout_status(
        user.failed_attempt_count,
        user.lockout_until,
        user.status.value == "disabled"
    )
    
    if lockout_status == LoginAttemptResult.LOCKED_TEMPORARY:
        logger.warning(f"Account locked: {login_data.username}")
        IPBasedLockout.lock_ip(client_ip)
        _log_login_attempt(
            db, login_data.username, user.role.value if user.role else "user",
            "locked_temporary", client_ip, user_agent, login_data.browser_data or {}
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Invalid credentials"
        )
    
    
    if not verify_password(login_data.password, user.password_hash):
        
        result, new_failed_count, new_lockout_until = LockoutStateMachine.process_failed_login_attempt(
            user.failed_attempt_count,
            username_found=True
        )
        
        user.failed_attempt_count = new_failed_count
        user.lockout_until = new_lockout_until
        
        if result == LoginAttemptResult.ACCOUNT_DISABLED:
            user.status = "disabled"
            user.disabled_reason = "Too many failed login attempts"
            user.disabled_at = datetime.utcnow()
            logger.warning(f"Account disabled due to failed attempts: {login_data.username}")
        
        if result == LoginAttemptResult.LOCKED_TEMPORARY:
            IPBasedLockout.lock_ip(client_ip)
        
        db.commit()
        _log_login_attempt(
            db, login_data.username, user.role.value if user.role else "user",
            "failed", client_ip, user_agent, login_data.browser_data or {}
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    
    # Auto-detect role from user record
    detected_role = user.role.value if user.role else "user"
    
    # Verify PIN if user is an admin
    if detected_role == "admin":
        if not login_data.pin:
            _log_login_attempt(
                db, login_data.username, "admin", "failed",
                client_ip, user_agent, login_data.browser_data or {}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="PIN required for administrator accounts"
            )
        
        from backend.security.hashing import verify_pin
        admin_record = db.query(Admin).filter(Admin.id == user.id).first()
        if not admin_record or not verify_pin(login_data.pin, admin_record.pin_hash):
            
            result, new_failed_count, new_lockout_until = LockoutStateMachine.process_failed_login_attempt(
                user.failed_attempt_count,
                username_found=True
            )
            user.failed_attempt_count = new_failed_count
            user.lockout_until = new_lockout_until
            
            if result == LoginAttemptResult.ACCOUNT_DISABLED:
                user.status = "disabled"
                user.disabled_reason = "Too many failed PIN attempts"
                user.disabled_at = datetime.utcnow()
                logger.warning(f"Account disabled due to failed PIN attempts: {login_data.username}")
                
            if result == LoginAttemptResult.LOCKED_TEMPORARY:
                IPBasedLockout.lock_ip(client_ip)
                
            db.commit()
            _log_login_attempt(
                db, login_data.username, "admin", "failed_pin",
                client_ip, user_agent, login_data.browser_data or {}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

    
    user.failed_attempt_count = 0
    user.lockout_until = None
    user.last_login_at = datetime.utcnow()
    
    
    session_data = TokenManager.generate_session_token(user.id, detected_role)
    db_session = DBSession(
        id=generate_secure_token(18),
        user_id=user.id,
        role=UserRole[detected_role.upper()],
        token_hash=session_data["token_hash"],
        issued_at=datetime.fromisoformat(session_data["issued_at"]),
        expires_at=datetime.fromisoformat(session_data["expires_at"]),
        is_trusted_device=False,
        revoked=False
    )
    db.add(db_session)
    
    # Handle trusted device if requested (only for user role)
    trusted_device_token = None
    if login_data.remember_device and detected_role == "user":
        
        fingerprint = fingerprint_manager.create_fingerprint(
            client_ip, user_agent, login_data.browser_data or {}
        )
        fingerprint_hash = fingerprint_manager.hash_fingerprint(fingerprint)
        
        
        trust_data = TokenManager.generate_trusted_device_token(user.id, fingerprint_hash)
        
        trusted_device = TrustedDevice(
            id=generate_secure_token(18),
            user_id=user.id,
            device_fingerprint_hash=fingerprint_hash,
            issued_at=datetime.fromisoformat(trust_data["issued_at"]),
            expires_at=datetime.fromisoformat(trust_data["expires_at"]),
            revoked=False
        )
        db.add(trusted_device)
        trusted_device_token = trust_data["token"]
        db_session.is_trusted_device = True
        db_session.device_fingerprint_id = trusted_device.id
    
    
    _log_login_attempt(
        db, login_data.username, detected_role, "success",
        client_ip, user_agent, login_data.browser_data or {}
    )
    
    db.commit()
    logger.info(f"User logged in: {user.username} (role: {detected_role})")
    
    
    redirect_url = {
        "user": "/user/dashboard",
        "admin": "/admin/dashboard",
        "master_admin": "/master-admin/dashboard"
    }.get(detected_role, "/user/dashboard")
    
    return LoginResponse(
        success=True,
        user_id=user.id,
        username=user.username,
        role=detected_role,
        session_token=session_data["token"],
        redirect_url=redirect_url,
        trusted_device_token=trusted_device_token,
        expires_in=30 * 60  
    )


def _log_login_attempt(
    db: Session,
    username: str,
    role: str,
    result: str,
    ip_address: str,
    user_agent: str,
    browser_data: dict
) -> None:
    """Log a login attempt to database"""
    user = db.query(User).filter(User.username == username).first()
    
    attempt = LoginAttempt(
        id=generate_secure_token(18),
        attempted_username=username,
        user_id=user.id if user else None,
        role_context=role,
        result=result,
        timestamp=datetime.utcnow(),
        ip_address=ip_address,
        user_agent=user_agent,
        browser_name=browser_data.get("browserName"),
        browser_version=browser_data.get("browserVersion"),
        os_name=browser_data.get("osName"),
        os_version=browser_data.get("osVersion"),
        device_type=browser_data.get("deviceType"),
        screen_resolution=browser_data.get("screenResolution"),
        timezone=browser_data.get("timezone"),
        language=browser_data.get("language"),
        platform_string=browser_data.get("platformString"),
        referrer=browser_data.get("referrer"),
        extra_fingerprint_json=browser_data.get("extra")
    )
    
    db.add(attempt)
    db.commit()
