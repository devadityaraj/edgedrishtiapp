"""EDGE Drishti database module"""
from .models import (
    Base, User, Admin, MasterAdmin, Session,
    TrustedDevice, LoginAttempt, Camera, AIModel,
    CameraModelLink, DetectionEvent, Face, AlertContact,
    AlertLog, AuditLog, SystemConfig, Notification,
    UserRole, AccountStatus, CameraStatus, AlertStatus,
    AlertConfig, Alert
)
from .session import DatabaseManager, get_db

__all__ = [
    "Base", "User", "Admin", "MasterAdmin", "Session",
    "TrustedDevice", "LoginAttempt", "Camera", "AIModel",
    "CameraModelLink", "DetectionEvent", "Face", "AlertContact",
    "AlertLog", "AuditLog", "SystemConfig", "Notification",
    "UserRole", "AccountStatus", "CameraStatus", "AlertStatus",
    "AlertConfig", "Alert",
    "DatabaseManager", "get_db"
]
