"""
Authentication routes for Master Admin (localhost-only).
Handles setup wizard, recovery key, and master admin login.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from backend.db import get_db, MasterAdmin, User, Session as DBSession, UserRole
from backend.core.bootstrap import BootstrapManager
from backend.security import (
    hash_password, verify_password, verify_recovery_key,
    generate_recovery_key, hash_recovery_key, generate_secure_token
)
from backend.security.lockout import LockoutStateMachine, LoginAttemptResult
from backend.api.schemas import (
    MasterAdminSetupRequest, MasterAdminLoginRequest, MasterAdminRecoverRequest,
    LoginResponse, RecoveryKeyResponse, ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth/master", tags=["master-admin"])


import socket

def _get_local_ips():
    ips = {"127.0.0.1", "::1", "localhost"}
    try:
        hostname = socket.gethostname()
        ips.add(socket.gethostbyname(hostname))
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return ips

_LOCAL_IPS = _get_local_ips()



def check_localhost_only(request: Request):
    """Ensure only the host machine (or edgedrishti-admin.local) can access master admin"""
    client_ip = request.client.host if request.client else "unknown"
    host_header = request.headers.get("host", "").split(":")[0].lower()
    is_local_ip   = client_ip in _LOCAL_IPS
    is_admin_host = host_header == "edgedrishti-admin.local"
    if not (is_local_ip or is_admin_host):
        logger.warning(f"Master admin access attempt from non-host IP: {client_ip} (host: {host_header})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master admin panel only accessible from localhost/host machine"
        )



@router.post("/setup", response_model=RecoveryKeyResponse)
async def setup_master_admin(
    request: Request,
    setup_data: MasterAdminSetupRequest,
    db: Session = Depends(get_db)
):
    """
    First-boot Master Admin setup.
    Only available when no Master Admin exists and from localhost.
    """
    check_localhost_only(request)
    
    # Check if master admin already exists
    existing_master = db.query(MasterAdmin).first()
    if existing_master:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Master admin already configured"
        )
    
    
    if len(setup_data.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters"
        )
    
    
    password_hash, password_salt = hash_password(setup_data.password)
    
    
    master_admin, recovery_key = BootstrapManager.setup_master_admin(
        db, setup_data.username, password_hash, password_salt
    )
    
    logger.info(f"Master admin account created: {setup_data.username}")
    
    return RecoveryKeyResponse(
        recovery_key=recovery_key,
        warning="Save this key in a secure location. It will never be displayed again."
    )


@router.post("/login", response_model=LoginResponse)
async def login_master_admin(
    request: Request,
    login_data: MasterAdminLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Master Admin login with standard credentials.
    Localhost-only access.
    """
    check_localhost_only(request)
    
    
    master_admin = db.query(MasterAdmin).first()
    if not master_admin:
        logger.warning("Master admin login attempt before setup")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    
    lockout_status, lockout_msg = LockoutStateMachine.check_lockout_status(
        master_admin.failed_attempt_count,
        master_admin.lockout_until,
        False
    )
    
    if lockout_status == LoginAttemptResult.LOCKED_TEMPORARY:
        logger.warning(f"Master admin account locked: {lockout_msg}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Invalid credentials"
        )
    
    # Verify credentials (username + password, no PIN required at login)
    if not login_data.username or not login_data.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required"
        )
    
    if login_data.username != master_admin.username:
        
        result, new_failed_count, new_lockout_until = LockoutStateMachine.process_failed_login_attempt(
            master_admin.failed_attempt_count,
            username_found=False
        )
        master_admin.failed_attempt_count = new_failed_count
        master_admin.lockout_until = new_lockout_until
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not verify_password(login_data.password, master_admin.password_hash):
        
        result, new_failed_count, new_lockout_until = LockoutStateMachine.process_failed_login_attempt(
            master_admin.failed_attempt_count,
            username_found=True
        )
        master_admin.failed_attempt_count = new_failed_count
        master_admin.lockout_until = new_lockout_until
        
        if result == LoginAttemptResult.ACCOUNT_DISABLED:
            logger.error(f"Master admin account disabled due to failed attempts")
        
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    
    master_admin.failed_attempt_count = 0
    master_admin.lockout_until = None
    master_admin.last_login_at = datetime.utcnow()
    
    
    session_token = generate_secure_token(32)
    session_token_hash = __import__("hashlib").sha256(session_token.encode()).hexdigest()
    
    db_session = DBSession(
        id=generate_secure_token(18),
        user_id=master_admin.id,
        role=UserRole.MASTER_ADMIN,
        token_hash=session_token_hash,
        issued_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=8),  
        is_trusted_device=False,
        revoked=False
    )
    db.add(db_session)
    db.commit()
    
    logger.info(f"Master admin logged in: {master_admin.username}")
    
    return LoginResponse(
        success=True,
        user_id=master_admin.id,
        username=master_admin.username,
        role="master_admin",
        session_token=session_token,
        redirect_url="/master-admin/dashboard",
        expires_in=8 * 3600  
    )


@router.post("/recover", response_model=LoginResponse)
async def recover_master_admin(
    request: Request,
    recover_data: MasterAdminRecoverRequest,
    db: Session = Depends(get_db)
):
    """
    Recover master admin access using recovery key.
    Changes username/password and generates new recovery key.
    Localhost-only access.
    """
    check_localhost_only(request)
    
    master_admin = db.query(MasterAdmin).first()
    if not master_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid recovery key"
        )
    
    
    if not master_admin.recovery_key_hash or not verify_recovery_key(
        recover_data.recovery_key, master_admin.recovery_key_hash
    ):
        logger.warning("Invalid recovery key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid recovery key"
        )
    
    # Check if recovery key was already used
    if master_admin.recovery_key_used:
        logger.warning("Attempt to reuse recovery key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Recovery key has already been used"
        )
    
    
    new_password_hash, new_password_salt = hash_password(recover_data.new_password)
    new_recovery_key = generate_recovery_key()
    new_recovery_key_hash, new_recovery_key_salt = hash_recovery_key(new_recovery_key)
    
    master_admin.username = recover_data.new_username
    master_admin.password_hash = new_password_hash
    master_admin.salt = new_password_salt
    master_admin.recovery_key_hash = new_recovery_key_hash
    master_admin.recovery_key_salt = new_recovery_key_salt
    master_admin.recovery_key_created_at = datetime.utcnow()
    master_admin.recovery_key_used = True
    master_admin.failed_attempt_count = 0
    master_admin.lockout_until = None
    
    
    shadow = db.query(User).filter(User.id == master_admin.id).first()
    if shadow:
        shadow.username = recover_data.new_username
        shadow.password_hash = new_password_hash
        shadow.salt = new_password_salt
    
    # Create session for immediate login
    session_token = generate_secure_token(32)
    session_token_hash = __import__("hashlib").sha256(session_token.encode()).hexdigest()
    
    db_session = DBSession(
        id=generate_secure_token(18),
        user_id=master_admin.id,
        role=UserRole.MASTER_ADMIN,
        token_hash=session_token_hash,
        issued_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=8),
        is_trusted_device=False,
        revoked=False
    )
    db.add(db_session)
    db.commit()
    
    logger.warning(f"Master admin credentials reset via recovery key")
    
    
    
    
    return LoginResponse(
        success=True,
        user_id=master_admin.id,
        username=master_admin.username,
        role="master_admin",
        session_token=session_token,
        redirect_url="/master-admin/dashboard",
        expires_in=8 * 3600
    )
