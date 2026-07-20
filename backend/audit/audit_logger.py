"""
EDGE Drishti - Audit Logger
Comprehensive logging of all security-sensitive operations
Immutable audit trail for compliance
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum
import logging
from backend.db.models import AuditLog
from backend.db.session import SessionLocal

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    SESSION_EXPIRED = "session_expired"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"

    
    USER_CREATED = "user_created"
    USER_DELETED = "user_deleted"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_LOCKED = "user_locked"
    USER_UNLOCKED = "user_unlocked"

    
    CAMERA_ADDED = "camera_added"
    CAMERA_REMOVED = "camera_removed"
    CAMERA_ENABLED = "camera_enabled"
    CAMERA_DISABLED = "camera_disabled"
    CAMERA_UPDATED = "camera_updated"

    
    ALERT_SENT = "alert_sent"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    ALERT_RULE_CHANGED = "alert_rule_changed"

    
    ENCRYPTION_KEY_ROTATED = "encryption_key_rotated"
    CONFIG_CHANGED = "config_changed"
    SYSTEM_REBOOTED = "system_rebooted"
    FAILURE_ATTEMPT = "failure_attempt"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

    
    FOOTAGE_VIEWED = "footage_viewed"
    FOOTAGE_EXPORTED = "footage_exported"
    FOOTAGE_DELETED = "footage_deleted"
    DETECTION_VIEWED = "detection_viewed"


class AuditLogger:
    """Central audit logger for compliance and security"""

    def __init__(self):
        self.session = SessionLocal()

    def log(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
        action_details: Optional[Dict[str, Any]] = None,
        result: str = "success",
        error_message: Optional[str] = None
    ) -> bool:
        """
        Log a security audit event

        Args:
            event_type: Type of event
            user_id: User performing the action
            camera_id: Related camera if applicable
            ip_address: Source IP address
            user_agent: User agent string
            action_details: Additional event details
            result: 'success' or 'failure'
            error_message: Error message if failed
        """
        try:
            
            if action_details:
                action_details = self._sanitize_details(action_details)

            audit_record = AuditLog(
                event_type=event_type.value,
                user_id=user_id,
                camera_id=camera_id,
                ip_address=ip_address,
                user_agent=user_agent,
                action_details=json.dumps(action_details or {}),
                result=result,
                error_message=error_message,
                timestamp=datetime.now()
            )

            self.session.add(audit_record)
            self.session.commit()

            
            log_message = f"[{event_type.value}] User: {user_id}, IP: {ip_address}, Result: {result}"
            if error_message:
                log_message += f", Error: {error_message}"
            logger.info(log_message)

            return True

        except Exception as e:
            logger.error(f"Audit log failed: {str(e)}")
            self.session.rollback()
            return False

    def log_login(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        error: Optional[str] = None,
        method: str = "password"
    ) -> bool:
        """Log login attempt"""
        return self.log(
            event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action_details={"method": method},
            result="success" if success else "failure",
            error_message=error
        )

    def log_logout(
        self,
        user_id: str,
        ip_address: str,
        session_duration_seconds: int
    ) -> bool:
        """Log logout"""
        return self.log(
            event_type=AuditEventType.LOGOUT,
            user_id=user_id,
            ip_address=ip_address,
            action_details={"session_duration": session_duration_seconds},
            result="success"
        )

    def log_user_action(
        self,
        event_type: AuditEventType,
        user_id: str,
        target_user_id: Optional[str],
        ip_address: str,
        changes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Log user management actions"""
        return self.log(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            action_details={
                "target_user": target_user_id,
                "changes": changes
            },
            result="success"
        )

    def log_camera_action(
        self,
        event_type: AuditEventType,
        camera_id: str,
        user_id: str,
        ip_address: str,
        changes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Log camera management actions"""
        return self.log(
            event_type=event_type,
            user_id=user_id,
            camera_id=camera_id,
            ip_address=ip_address,
            action_details={"changes": changes},
            result="success"
        )

    def log_alert(
        self,
        alert_id: str,
        camera_id: str,
        threat_type: str,
        confidence: float,
        user_id: Optional[str] = None
    ) -> bool:
        """Log alert event"""
        return self.log(
            event_type=AuditEventType.ALERT_SENT,
            user_id=user_id,
            camera_id=camera_id,
            action_details={
                "alert_id": alert_id,
                "threat_type": threat_type,
                "confidence": confidence
            },
            result="success"
        )

    def log_security_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str],
        ip_address: str,
        details: Dict[str, Any],
        severity: str = "high"
    ) -> bool:
        """Log security-relevant events"""
        return self.log(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            action_details={
                **details,
                "severity": severity
            },
            result="success"
        )

    def log_failed_attempt(
        self,
        event_type: AuditEventType,
        user_id: Optional[str],
        ip_address: str,
        reason: str
    ) -> bool:
        """Log failed security attempts"""
        return self.log(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            action_details={"reason": reason},
            result="failure",
            error_message=reason
        )

    def get_audit_trail(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """Retrieve audit trail records"""
        try:
            query = self.session.query(AuditLog)

            if user_id:
                query = query.filter(AuditLog.user_id == user_id)

            if event_type:
                query = query.filter(AuditLog.event_type == event_type)

            records = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset).all()

            return [
                {
                    "timestamp": rec.timestamp.isoformat(),
                    "event_type": rec.event_type,
                    "user_id": rec.user_id,
                    "camera_id": rec.camera_id,
                    "ip_address": rec.ip_address,
                    "result": rec.result,
                    "details": json.loads(rec.action_details)
                }
                for rec in records
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve audit trail: {str(e)}")
            return []

    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from audit details"""
        sensitive_keys = ["password", "token", "secret", "api_key", "key"]
        sanitized = {}

        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value

        return sanitized

    def __del__(self):
        """Cleanup database session"""
        if self.session:
            self.session.close()



audit_logger = AuditLogger()
