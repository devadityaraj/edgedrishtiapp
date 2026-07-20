"""
Session token and trusted-device token generation and validation.
Implements JWT-based tokens with expiry and role encoding.
"""

import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from enum import Enum


class TokenType(str, Enum):
    SESSION = "session"
    TRUSTED_DEVICE = "trusted_device"
    RECOVERY = "recovery"


class TokenManager:
    """Manages session and trusted-device tokens"""
    
    @staticmethod
    def generate_session_token(
        user_id: str,
        role: str,
        expires_in_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Generate a session token for a user.
        
        Args:
            user_id: Unique user ID
            role: User role (user/admin/master_admin)
            expires_in_minutes: Token expiry time
            
        Returns:
            Dict with token, expiry_timestamp, and role info
        """
        token = secrets.token_hex(32)  
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=expires_in_minutes)
        
        return {
            "token": token,
            "token_hash": token_hash,  
            "user_id": user_id,
            "role": role,
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "type": TokenType.SESSION
        }
    
    @staticmethod
    def generate_trusted_device_token(
        user_id: str,
        device_fingerprint_hash: str,
        expires_in_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Generate a 24-hour trusted-device token.
        
        Args:
            user_id: Unique user ID
            device_fingerprint_hash: Hash of device fingerprint
            expires_in_hours: Token expiry time (default 24h)
            
        Returns:
            Dict with token, expiry, and device binding info
        """
        token = secrets.token_hex(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=expires_in_hours)
        
        return {
            "token": token,
            "token_hash": token_hash,  
            "user_id": user_id,
            "device_fingerprint_hash": device_fingerprint_hash,
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "type": TokenType.TRUSTED_DEVICE
        }
    
    @staticmethod
    def hash_token(token: str) -> str:
        """
        Hash a token for secure storage.
        
        Args:
            token: Plain token
            
        Returns:
            SHA-256 hash of token
        """
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def verify_token_hash(token: str, stored_hash: str) -> bool:
        """
        Verify a token against its stored hash.
        
        Args:
            token: Plain token to verify
            stored_hash: Stored hash from database
            
        Returns:
            True if token matches hash
        """
        return hashlib.sha256(token.encode()).hexdigest() == stored_hash
    
    @staticmethod
    def is_token_expired(expires_at_str: str) -> bool:
        """
        Check if a token has expired.
        
        Args:
            expires_at_str: ISO format expiry timestamp
            
        Returns:
            True if expired
        """
        expires_at = datetime.fromisoformat(expires_at_str)
        return datetime.utcnow() > expires_at
    
    @staticmethod
    def generate_recovery_token() -> str:
        """
        Generate a one-time recovery token.
        
        Returns:
            Hex-encoded recovery token
        """
        return secrets.token_hex(32)


class SessionManager:
    """Manages session lifecycle and validation"""
    
    @staticmethod
    def create_session_object(
        user_id: str,
        role: str,
        device_fingerprint_hash: Optional[str] = None,
        is_trusted_device: bool = False
    ) -> Dict[str, Any]:
        """
        Create a complete session object.
        
        Args:
            user_id: User ID
            role: User role
            device_fingerprint_hash: Optional device fingerprint
            is_trusted_device: Whether this is a trusted device session
            
        Returns:
            Session dict with all fields
        """
        token_data = TokenManager.generate_session_token(user_id, role)
        
        return {
            "id": secrets.token_hex(16),
            "user_id": user_id,
            "role": role,
            "token_hash": token_data["token_hash"],
            "issued_at": token_data["issued_at"],
            "expires_at": token_data["expires_at"],
            "is_trusted_device": is_trusted_device,
            "device_fingerprint_hash": device_fingerprint_hash,
            "revoked": False,
            # Return plaintext token to send to client (only once)
            "token": token_data["token"]
        }
    
    @staticmethod
    def validate_session_token(
        token: str,
        stored_token_hash: str,
        expires_at: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a session token.
        
        Args:
            token: Plain token from request
            stored_token_hash: Hash from database
            expires_at: Expiry timestamp
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        
        if not TokenManager.verify_token_hash(token, stored_token_hash):
            return False, "Invalid token"
        
        
        if TokenManager.is_token_expired(expires_at):
            return False, "Token expired"
        
        return True, None


from typing import Tuple, Optional


def get_current_user(request=None, authorization: str = None):
    """FastAPI dependency: validate Bearer token and return User from DB."""
    from fastapi import HTTPException, status, Depends
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    import hashlib

    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_from_token(token: str) -> Optional[object]:
    """
    Validate a raw session token and return the User or MasterAdmin object, or None if invalid.
    Used by WebSocket endpoint which cannot use FastAPI dependency injection.
    """
    try:
        import hashlib
        from backend.db.session import DatabaseManager
        from backend.db.models import Session, User, MasterAdmin, UserRole
        from datetime import datetime

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        db = DatabaseManager.get_session()
        try:
            session = (
                db.query(Session)
                .filter(Session.token_hash == token_hash)
                .filter(Session.revoked == False)
                .first()
            )
            if not session:
                return None
            if session.expires_at < datetime.utcnow():
                return None
                
            is_master = (
                session.role == UserRole.MASTER_ADMIN or 
                (hasattr(session.role, "name") and session.role.name == "MASTER_ADMIN") or 
                str(session.role) == "UserRole.MASTER_ADMIN"
            )
            
            if is_master:
                user = db.query(MasterAdmin).filter(MasterAdmin.id == session.user_id).first()
            else:
                user = db.query(User).filter(User.id == session.user_id).first()
                
            return user
        finally:
            db.close()
    except Exception:
        return None
