"""
FastAPI dependency for Bearer token authentication.
Import get_current_user wherever you need authenticated endpoints.
"""

import hashlib
import logging
from datetime import datetime
from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

from backend.db.session import get_db
from backend.db.models import Session, User
from sqlalchemy.orm import Session as DBSession

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: DBSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency. Validates Bearer token from Authorization header.
    Returns the authenticated User object or raises 401.
    """
    token = None
    if credentials:
        token = credentials.credentials
    if not token:
        
        token = request.headers.get("X-Session-Token")
    if not token:
        # Try token query param (useful for HTML5 video tags)
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = (
        db.query(Session)
        .filter(Session.token_hash == token_hash, Session.revoked == False)
        .first()
    )
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    if session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expired")

    from backend.db.models import MasterAdmin, UserRole

    is_master = (
        session.role == UserRole.MASTER_ADMIN or 
        (hasattr(session.role, "name") and session.role.name == "MASTER_ADMIN") or 
        str(session.role) == "UserRole.MASTER_ADMIN"
    )

    if is_master:
        user = db.query(MasterAdmin).filter(MasterAdmin.id == session.user_id).first()
    else:
        user = db.query(User).filter(User.id == session.user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    if not is_master and hasattr(user, "status") and user.status.value == "disabled":
        raise HTTPException(status_code=403, detail="Account disabled")

    return user
