"""
Authentication routes for regular users.
Handles login, logout, and session management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from backend.db import get_db, User, Session as DBSession, UserRole, TrustedDevice, LoginAttempt
from backend.security import (
    hash_password, verify_password, generate_recovery_key,
    hash_recovery_key, generate_secure_token
)
from backend.security.lockout import LockoutStateMachine, LoginAttemptResult, IPBasedLockout
from backend.security.fingerprint import fingerprint_manager, BrowserFingerprint
from backend.security.tokens import TokenManager, SessionManager
from backend.api.schemas import (
    LoginRequest, LoginResponse, LogoutRequest, LogoutResponse,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/login", response_model=LoginResponse)
async def login_user(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    User login with optional device trust (24h skip-login).
    
    Implements:
    - Full lockout state machine
    - Device fingerprinting
    - Browser data tracking
    - ECDH key exchange for session encryption
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
    
    
    user = db.query(User).filter(User.username == login_data.username).first()
    username_found = user is not None
    
    # Check if user exists and account state
    if user:
        # Check if account is disabled
        if user.status.value == "disabled":
            logger.warning(f"Disabled user login attempt: {login_data.username}")
            _log_login_attempt(
                db, login_data.username, "user", "account_disabled",
                client_ip, user_agent, login_data.browser_data or {}
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
                db, login_data.username, "user", "locked_temporary",
                client_ip, user_agent, login_data.browser_data or {}
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
                db, login_data.username, "user", "failed",
                client_ip, user_agent, login_data.browser_data or {}
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
    else:
        
        result, new_failed_count, new_lockout_until = LockoutStateMachine.process_failed_login_attempt(
            0,  
            username_found=False
        )
        
        if result == LoginAttemptResult.LOCKED_TEMPORARY:
            IPBasedLockout.lock_ip(client_ip)
        
        _log_login_attempt(
            db, login_data.username, "user", "username_not_found",
            client_ip, user_agent, login_data.browser_data or {}
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    
    
    user.failed_attempt_count = 0
    user.lockout_until = None
    user.last_login_at = datetime.utcnow()
    
    
    session_data = TokenManager.generate_session_token(user.id, "user")
    db_session = DBSession(
        id=generate_secure_token(18),
        user_id=user.id,
        role=UserRole.USER,
        token_hash=session_data["token_hash"],
        issued_at=datetime.fromisoformat(session_data["issued_at"]),
        expires_at=datetime.fromisoformat(session_data["expires_at"]),
        is_trusted_device=False,
        revoked=False
    )
    db.add(db_session)
    
    # Handle trusted device if requested
    trusted_device_token = None
    if login_data.remember_device:
        
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
        db, login_data.username, "user", "success",
        client_ip, user_agent, login_data.browser_data or {}
    )
    
    db.commit()
    logger.info(f"User logged in: {user.username}")
    
    return LoginResponse(
        success=True,
        user_id=user.id,
        username=user.username,
        role="user",
        session_token=session_data["token"],
        redirect_url="/user/dashboard",
        trusted_device_token=trusted_device_token,
        expires_in=30 * 60  
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout_user(
    request: Request,
    logout_data: LogoutRequest,
    db: Session = Depends(get_db)
):
    """Logout and optionally revoke trusted device"""
    # Get session token from header
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization"
        )
    
    token = auth_header[7:]
    token_hash = TokenManager.hash_token(token)
    
    
    session = db.query(DBSession).filter(DBSession.token_hash == token_hash).first()
    if session:
        session.revoked = True
        
        
        if logout_data.revoke_trusted_device and session.device_fingerprint_id:
            trusted_device = db.query(TrustedDevice).filter(
                TrustedDevice.id == session.device_fingerprint_id
            ).first()
            if trusted_device:
                trusted_device.revoked = True
        
        db.commit()
    
    return LogoutResponse(success=True, message="Logged out successfully")


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
