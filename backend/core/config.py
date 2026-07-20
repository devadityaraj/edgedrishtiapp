"""
Core configuration module for EDGE Drishti.
Loads runtime configuration from environment, .env, or defaults.
"""

import os
from pathlib import Path
from typing import Optional
import json

class Config:
    """Main configuration class"""
    
    
    BASE_DIR = Path(__file__).parent.parent.parent
    BACKEND_DIR = BASE_DIR / "backend"
    DATABASE_DIR = BACKEND_DIR / ".data"
    RECORDINGS_DIR = BACKEND_DIR / ".data" / "recordings"
    MODELS_DIR = BACKEND_DIR / ".data" / "models"
    LOGS_DIR = BACKEND_DIR / ".data" / "logs"
    CERTS_DIR = BACKEND_DIR / ".data" / "certs"
    EXPORTS_DIR = BACKEND_DIR / ".data" / "exports"
    
    
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    
    DATABASE_PATH = DATABASE_DIR / "app.db"
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
    
    
    PUBLIC_HOST = os.getenv("PUBLIC_HOST", "0.0.0.0")
    PUBLIC_PORT = int(os.getenv("PUBLIC_PORT", 8443))
    MASTER_HOST = "127.0.0.1"
    MASTER_PORT = int(os.getenv("MASTER_PORT", 8444))
    
    
    TLS_CERT_PATH = CERTS_DIR / "cert.pem"
    TLS_KEY_PATH = CERTS_DIR / "key.pem"
    
    
    SECRET_KEY = os.getenv("SECRET_KEY", "edge-drishti-dev-key-change-in-prod")
    SESSION_TIMEOUT_MINUTES = 30
    TRUSTED_DEVICE_HOURS = 24
    
    
    LOCKOUT_THRESHOLD = 3  
    LOCKOUT_DURATION_SECONDS = 30
    MAX_FAILED_ATTEMPTS_DISABLE = 5  
    
    
    GPU_FALLBACK_TO_CPU = True
    INFERENCE_CONFIDENCE_THRESHOLD = 0.5
    DEFAULT_INFERENCE_DEVICE = "auto"  
    
    
    CAMERA_RECONNECT_BACKOFF_SECONDS = 5
    CAMERA_RECONNECT_MAX_ATTEMPTS = 10
    CAMERA_FRAME_TIMEOUT_SECONDS = 30
    
    
    DEFAULT_RETENTION_DAYS = 7
    
    
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    
    FIRE_SMOKE_CONFIDENCE = 0.6
    PERSON_CONFIDENCE = 0.5
    OBJECT_CONFIDENCE = 0.5
    ACCIDENT_CONFIDENCE = 0.5
    FACE_MATCH_CONFIDENCE = 0.6
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables"""
        return cls()


config = Config()
