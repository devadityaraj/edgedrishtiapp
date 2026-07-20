"""
Pydantic request/response schemas for API validation and documentation.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class RoleEnum(str, Enum):
    USER = "user"
    ADMIN = "admin"
    MASTER_ADMIN = "master_admin"


class StatusEnum(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"






class LoginRequest(BaseModel):
    """User/Admin login request"""
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)
    pin: Optional[str] = None
    role: RoleEnum = RoleEnum.USER
    remember_device: bool = False
    browser_data: Optional[Dict[str, Any]] = None  
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "user@example.com",
                "password": "password123",
                "role": "user",
                "remember_device": True,
                "browser_data": {
                    "browserName": "Chrome",
                    "osName": "Windows",
                    "deviceType": "desktop"
                }
            }
        }


class MasterAdminLoginRequest(BaseModel):
    """Master admin login or recovery request"""
    username: Optional[str] = None
    password: Optional[str] = None
    recovery_key: Optional[str] = None
    role: RoleEnum = RoleEnum.MASTER_ADMIN
    browser_data: Optional[Dict[str, Any]] = None


class MasterAdminSetupRequest(BaseModel):
    """First-boot master admin setup"""
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class MasterAdminRecoverRequest(BaseModel):
    """Master admin credential recovery using recovery key"""
    recovery_key: str = Field(..., min_length=32)
    new_username: str = Field(..., min_length=3, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)


class LoginResponse(BaseModel):
    """Successful login response"""
    success: bool
    user_id: str
    username: str
    role: RoleEnum
    session_token: str
    redirect_url: str
    trusted_device_token: Optional[str] = None
    expires_in: int  


class LogoutRequest(BaseModel):
    """Logout request"""
    revoke_trusted_device: bool = False


class LogoutResponse(BaseModel):
    """Logout response"""
    success: bool
    message: str


class EncryptedPayload(BaseModel):
    """Wrapper for encrypted request/response bodies"""
    encrypted_data: str = Field(..., description="Base64-encoded AES-256-GCM encrypted data")
    nonce: Optional[str] = None  


class KeyExchangeRequest(BaseModel):
    """ECDH key exchange to establish session encryption"""
    public_key: str = Field(..., description="Base64-encoded X25519 public key (32 bytes)")


class KeyExchangeResponse(BaseModel):
    """Key exchange response"""
    public_key: str = Field(..., description="Base64-encoded X25519 public key (32 bytes)")
    session_id: str






class UserInfo(BaseModel):
    """User information"""
    id: str
    username: str
    role: RoleEnum
    status: StatusEnum
    created_at: datetime
    last_login_at: Optional[datetime]
    total_active_time_seconds: int
    disabled_reason: Optional[str] = None
    disabled_at: Optional[datetime] = None


class UserCreateRequest(BaseModel):
    """Create a new user (admin only)"""
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    role: RoleEnum = RoleEnum.USER


class UserUpdateRequest(BaseModel):
    """Update user"""
    username: Optional[str] = None
    status: Optional[StatusEnum] = None
    disabled_reason: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    """Change password"""
    old_password: Optional[str] = None
    new_password: str = Field(..., min_length=8)


class AdminPINRequest(BaseModel):
    """Admin PIN operations"""
    pin: str = Field(..., pattern="^\\d{4,8}$")


class ResetPasswordRequest(BaseModel):
    """Reset user password (admin only)"""
    user_id: str
    new_password: str = Field(..., min_length=8)


class UnlockAccountRequest(BaseModel):
    """Unlock a disabled/locked account"""
    user_id: str


class ThemePreference(BaseModel):
    """User theme preference"""
    theme: str = Field(..., enum=["light", "dark"])


class UserSettingsUpdate(BaseModel):
    """Update user settings"""
    theme: Optional[str] = None






class CameraSourceType(str, Enum):
    WEBCAM = "webcam"
    USB = "usb"
    CAPTURE_CARD = "capture_card"
    IP_CAMERA = "ip_camera"
    RTSP = "rtsp"
    UDP = "udp"
    HTTP_STREAM = "http_stream"
    LOCAL_FILE = "local_file"
    CUSTOM = "custom"


class CameraCreateRequest(BaseModel):
    """Create a new camera"""
    name: str = Field(..., min_length=1, max_length=255)
    source_type: CameraSourceType
    connection_uri: str  
    retention_days: int = Field(default=7, ge=1, le=365)
    resolution: str = Field(default='default')
    record_enabled: bool = Field(default=False)
    record_duration_seconds: int = Field(default=60, ge=20, le=3600)


class CameraUpdateRequest(BaseModel):
    """Update camera settings"""
    name: Optional[str] = None
    connection_uri: Optional[str] = None
    retention_days: Optional[int] = None
    resolution: Optional[str] = None
    record_enabled: Optional[bool] = None
    record_duration_seconds: Optional[int] = Field(default=None, ge=20, le=3600)
    status: Optional[str] = None


class CameraInfo(BaseModel):
    """Camera information"""
    id: str
    name: str
    source_type: CameraSourceType
    status: str
    added_at: datetime
    last_seen_at: Optional[datetime]
    retention_days: int
    resolution: str
    record_enabled: bool
    record_duration_seconds: int
    last_error: Optional[str] = None


class CameraListResponse(BaseModel):
    """List of cameras"""
    cameras: List[CameraInfo]
    total: int






class AIModelInfo(BaseModel):
    """AI model information"""
    id: str
    key: str
    display_name: str
    version: str
    enabled_globally: bool
    requires_gpu: bool


class CameraModelConfig(BaseModel):
    """Per-camera AI model configuration"""
    camera_id: str
    ai_model_id: str
    enabled: bool
    sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    roi_zones: Optional[List[List[int]]] = None  
    schedule: Optional[Dict[str, Any]] = None  






class DetectionEventInfo(BaseModel):
    """Detection event information"""
    id: str
    camera_id: str
    event_type: str
    confidence: float
    timestamp: datetime
    acknowledged: bool
    bounding_boxes: Optional[List[Dict[str, float]]] = None


class DetectionEventListResponse(BaseModel):
    """List of detection events"""
    events: List[DetectionEventInfo]
    total: int






class AlertContactCreate(BaseModel):
    """Create alert contact"""
    channel: str = Field(..., enum=["telegram", "email"])
    destination: str  


class AlertContactInfo(BaseModel):
    """Alert contact information"""
    id: str
    channel: str
    destination_masked: str  # Masked for display
    active: bool


class AlertTestRequest(BaseModel):
    """Test alert channel"""
    contact_id: str
    test_message: Optional[str] = None






class AuditLogEntry(BaseModel):
    """Audit log entry"""
    id: str
    actor_id: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    timestamp: datetime
    detail: Optional[Dict[str, Any]] = None


class AuditLogListResponse(BaseModel):
    """Audit log list"""
    entries: List[AuditLogEntry]
    total: int






class HardwareInfo(BaseModel):
    """Hardware compatibility report"""
    os: str  
    gpu_available: bool
    gpu_type: Optional[str]  
    cuda_available: bool
    rocm_available: bool
    cpu_cores: int
    ram_gb: float
    inference_device: str  
    recommendations: List[str]


class SystemStats(BaseModel):
    """Live system statistics"""
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    gpu_percent: Optional[float] = None
    gpu_memory_percent: Optional[float] = None
    active_cameras: int
    active_models: int
    total_detections_today: int
    uptime_seconds: int


class SystemConfigUpdate(BaseModel):
    """Update system configuration"""
    hostname: Optional[str] = None
    port: Optional[int] = None
    theme: Optional[str] = None
    inference_device: Optional[str] = None






class RecoveryKeyResponse(BaseModel):
    """Recovery key display (one-time after setup)"""
    recovery_key: str = Field(..., description="Save this key in a secure location")
    warning: str = "This key will never be displayed again"


class BackupExportRequest(BaseModel):
    """Request backup export"""
    include_recordings: bool = False
    include_events: bool = True


class BackupInfo(BaseModel):
    """Backup information"""
    timestamp: datetime
    size_bytes: int
    includes_recordings: bool
    includes_events: bool






class ErrorResponse(BaseModel):
    """API error response"""
    error: str
    message: str
    code: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)






class LiveFrameMessage(BaseModel):
    """WebSocket message for live camera frame"""
    type: str = "frame"
    camera_id: str
    frame_base64: str
    timestamp: datetime
    detections: Optional[List[Dict[str, Any]]] = None


class LiveEventMessage(BaseModel):
    """WebSocket message for detection event"""
    type: str = "event"
    event_id: str
    camera_id: str
    event_type: str
    confidence: float
    timestamp: datetime


class LiveSystemStatsMessage(BaseModel):
    """WebSocket message for system stats"""
    type: str = "system_stats"
    stats: SystemStats
    timestamp: datetime
