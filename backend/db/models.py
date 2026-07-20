"""
SQLAlchemy ORM models for EDGE Drishti.
All sensitive fields encrypted at rest where applicable.
"""

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Float, Text, JSON,
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

Base = declarative_base()


def _uuid():
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    MASTER_ADMIN = "master_admin"


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"


class CameraStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class AlertStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"
    PENDING = "pending"


class User(Base):
    """User account (both regular users and admins if role-based)"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(255))
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)

    
    failed_attempt_count = Column(Integer, default=0)
    lockout_until = Column(DateTime, nullable=True)

    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    total_active_time_seconds = Column(Integer, default=0)

    
    disabled_reason = Column(String(500), nullable=True)
    disabled_at = Column(DateTime, nullable=True)

    
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan",
                            foreign_keys="Session.user_id")
    trusted_devices = relationship("TrustedDevice", back_populates="user", cascade="all, delete-orphan")
    login_attempts = relationship("LoginAttempt", back_populates="user", foreign_keys="LoginAttempt.user_id")

    __table_args__ = (
        Index("idx_user_status", "status"),
        Index("idx_user_role", "role"),
    )


class Admin(Base):
    """Admin account with PIN"""
    __tablename__ = "admins"

    id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    pin_hash = Column(String(255), nullable=False)
    pin_salt = Column(String(255))

    user = relationship("User", foreign_keys=[id], primaryjoin="Admin.id==User.id")


class MasterAdmin(Base):
    """Singleton master admin account"""
    __tablename__ = "master_admin"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(255))

    
    recovery_key_hash = Column(String(255), nullable=True)
    recovery_key_salt = Column(String(255), nullable=True)
    recovery_key_created_at = Column(DateTime, nullable=True)
    recovery_key_used = Column(Boolean, default=False)

    
    failed_attempt_count = Column(Integer, default=0, nullable=False)
    lockout_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)

    
    hostname = Column(String(255), default="0.0.0.0")
    port = Column(Integer, default=8443)
    created_at = Column(DateTime, default=datetime.utcnow)

    
    failed_attempt_count = Column(Integer, default=0)
    lockout_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)


class Session(Base):
    """Active user session"""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(SQLEnum(UserRole), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_trusted_device = Column(Boolean, default=False)
    device_fingerprint_id = Column(String(36), ForeignKey("trusted_devices.id"), nullable=True)
    revoked = Column(Boolean, default=False, index=True)

    user = relationship("User", back_populates="sessions", foreign_keys=[user_id])


class TrustedDevice(Base):
    """Trusted device for 24-hour skip-login"""
    __tablename__ = "trusted_devices"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    device_fingerprint_hash = Column(String(255), nullable=False)
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked = Column(Boolean, default=False)

    user = relationship("User", back_populates="trusted_devices")


class LoginAttempt(Base):
    """Append-only login attempt log"""
    __tablename__ = "login_attempts"

    id = Column(String(36), primary_key=True, default=_uuid)
    attempted_username = Column(String(255), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    role_context = Column(String(50), nullable=False)
    result = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text)
    browser_name = Column(String(100))
    browser_version = Column(String(50))
    os_name = Column(String(100))
    os_version = Column(String(50))
    device_type = Column(String(50))
    screen_resolution = Column(String(50))
    timezone = Column(String(50))
    language = Column(String(50))
    platform_string = Column(String(255))
    referrer = Column(Text)
    extra_fingerprint_json = Column(JSON)

    user = relationship("User", back_populates="login_attempts", foreign_keys=[user_id])

    __table_args__ = (
        Index("idx_login_attempt_user", "user_id"),
        Index("idx_login_attempt_ip", "ip_address"),
    )


class Camera(Base):
    """Video source/camera configuration"""
    __tablename__ = "cameras"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False, index=True)
    source_type = Column(String(50), nullable=False)
    connection_uri_encrypted = Column(Text, nullable=False)
    resolution = Column(String(20), default="default", nullable=False)
    record_enabled = Column(Boolean, default=False, nullable=False)
    record_duration_seconds = Column(Integer, default=60, nullable=False)
    status = Column(SQLEnum(CameraStatus), default=CameraStatus.OFFLINE, nullable=False)

    added_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)
    retention_days = Column(Integer, default=7)
    last_error = Column(String(500))
    reconnect_attempts = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_camera_status", "status"),
    )


class AIModel(Base):
    """AI detection model registry"""
    __tablename__ = "ai_models"

    id = Column(String(36), primary_key=True, default=_uuid)
    key = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False, default="1.0")
    enabled_globally = Column(Boolean, default=True)
    requires_gpu = Column(Boolean, default=False)
    config_json = Column(JSON)


class CameraModelLink(Base):
    """Per-camera AI model settings"""
    __tablename__ = "camera_model_links"

    id = Column(String(36), primary_key=True, default=_uuid)
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=False, index=True)
    ai_model_id = Column(String(36), ForeignKey("ai_models.id"), nullable=False, index=True)
    enabled = Column(Boolean, default=True)
    sensitivity_config_json = Column(JSON)
    roi_zones_json = Column(JSON)
    schedule_json = Column(JSON)
    fps_limit = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_camera_model_link", "camera_id", "ai_model_id"),
    )


class DetectionEvent(Base):
    """AI detection event"""
    __tablename__ = "detection_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=False, index=True)
    ai_model_id = Column(String(36), ForeignKey("ai_models.id"), nullable=True)
    event_type = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    snapshot_path_encrypted = Column(Text)
    clip_path_encrypted = Column(Text)
    bounding_boxes_json = Column(JSON)

    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("idx_detection_camera", "camera_id"),
        Index("idx_detection_timestamp", "timestamp"),
    )


class Face(Base):
    """Enrolled face identity for matching"""
    __tablename__ = "faces"

    id = Column(String(36), primary_key=True, default=_uuid)
    label = Column(String(255), nullable=False, index=True)
    embedding_encrypted = Column(Text, nullable=False)
    enrolled_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    sample_image_path = Column(String(500))


class AlertContact(Base):
    """External alert destination (Telegram, etc.)"""
    __tablename__ = "alert_contacts"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    channel = Column(String(50), nullable=False)
    
    bot_token = Column(String(500), nullable=True)
    chat_id = Column(String(100), nullable=True)
    enabled = Column(Boolean, default=True)
    added_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)


class AlertLog(Base):
    """Alert delivery log"""
    __tablename__ = "alert_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    detection_event_id = Column(String(36), ForeignKey("detection_events.id"), nullable=False, index=True)
    contact_id = Column(String(36), ForeignKey("alert_contacts.id"), nullable=True)
    channel = Column(String(50), nullable=False)
    success = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    error_text = Column(Text)


class AuditLog(Base):
    """Hash-chained audit log for tampering detection"""
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    sequence_number = Column(Integer, nullable=False, unique=True, index=True)
    actor_id = Column(String(36), nullable=True)
    actor_role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50))
    target_id = Column(String(36))
    detail = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    
    prev_row_hash = Column(String(64))
    row_hash = Column(String(64), index=True)

    __table_args__ = (
        Index("idx_audit_actor", "actor_id"),
        Index("idx_audit_timestamp", "timestamp"),
    )


class SystemConfig(Base):
    """System configuration"""
    __tablename__ = "system_config"

    id = Column(String(36), primary_key=True, default=_uuid)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value_encrypted = Column(Text)


class Notification(Base):
    """In-app notification for users"""
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    detection_event_id = Column(String(36), ForeignKey("detection_events.id"), nullable=True)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    notification_type = Column(String(50), default="alert")
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_notification_user", "user_id"),
    )


class AlertConfig(Base):
    """Alert configuration rule"""
    __tablename__ = "alert_configs"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    threat_class = Column(String(100), nullable=False)
    min_confidence = Column(Float, default=0.7)
    severity = Column(String(50), default="high")
    channels = Column(JSON)  # list of channels e.g., ["telegram", "in_app"]
    debounce_seconds = Column(Integer, default=60)
    group_alerts = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True, index=True)


class Alert(Base):
    """Alert record for in-app history"""
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=_uuid)
    rule_id = Column(String(36), ForeignKey("alert_configs.id"), nullable=True)
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=False)
    threat_class = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    severity = Column(String(50), default="high")
    bbox_json = Column(Text)
    metadata_json = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    is_read = Column(Boolean, default=False, index=True)

