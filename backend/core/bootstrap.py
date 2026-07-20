"""
Bootstrap module for first-run setup.
Detects first boot, initializes database, seeds default data.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from backend.core.config import config
from backend.db.models import (
    MasterAdmin, AIModel, SystemConfig, Base
)
from backend.db.session import DatabaseManager
from backend.security import generate_recovery_key, hash_recovery_key, generate_secure_token

logger = logging.getLogger(__name__)


class BootstrapManager:
    """Handles first-run initialization"""
    
    @staticmethod
    def is_first_boot(db: Session) -> bool:
        """
        Check if this is the first boot (no master admin exists).
        
        Args:
            db: Database session
            
        Returns:
            True if no master admin exists
        """
        master_admin = db.query(MasterAdmin).first()
        return master_admin is None
    
    @staticmethod
    def bootstrap_database() -> None:
        """
        Initialize database for first run.
        Creates tables, seeds default AI models, and generates TLS certificate.
        """
        db = DatabaseManager.get_session()
        
        try:
            
            from sqlalchemy import text
            try:
                db.execute(text("SELECT failed_attempt_count FROM master_admin LIMIT 1"))
            except Exception:
                logger.info("Upgrading master_admin table schema (adding lockout columns)")
                try:
                    db.execute(text("ALTER TABLE master_admin ADD COLUMN failed_attempt_count INTEGER DEFAULT 0 NOT NULL"))
                except Exception:
                    pass
                try:
                    db.execute(text("ALTER TABLE master_admin ADD COLUMN lockout_until DATETIME"))
                except Exception:
                    pass
                try:
                    db.execute(text("ALTER TABLE master_admin ADD COLUMN last_login_at DATETIME"))
                except Exception:
                    pass
                db.commit()
                
            # Generate TLS certificate if not exists (always ensure on startup)
            from backend.security import tls_manager
            tls_manager.ensure_tls_certificate(
                str(config.TLS_CERT_PATH),
                str(config.TLS_KEY_PATH)
            )

            # Check if first boot
            if BootstrapManager.is_first_boot(db):
                logger.info("First boot detected - initializing database")
                
                
                BootstrapManager._seed_ai_models(db)
                
                
                BootstrapManager._seed_system_config(db)
                
                logger.info("First boot initialization complete")
            else:
                logger.info("Database already initialized")

            # Upgrade cameras schema if needed
            try:
                db.execute(text("SELECT resolution FROM cameras LIMIT 1"))
            except Exception:
                logger.info("Upgrading cameras table schema (adding resolution)")
                try:
                    db.execute(text("ALTER TABLE cameras ADD COLUMN resolution TEXT DEFAULT 'default' NOT NULL"))
                except Exception:
                    pass
                db.commit()

            try:
                db.execute(text("SELECT record_enabled FROM cameras LIMIT 1"))
            except Exception:
                logger.info("Upgrading cameras table schema (adding record_enabled)")
                try:
                    db.execute(text("ALTER TABLE cameras ADD COLUMN record_enabled BOOLEAN DEFAULT 0 NOT NULL"))
                except Exception:
                    pass
                db.commit()

            try:
                db.execute(text("SELECT record_duration_seconds FROM cameras LIMIT 1"))
            except Exception:
                logger.info("Upgrading cameras table schema (adding record_duration_seconds)")
                try:
                    db.execute(text("ALTER TABLE cameras ADD COLUMN record_duration_seconds INTEGER DEFAULT 60 NOT NULL"))
                except Exception:
                    pass
                db.commit()

            # Upgrade camera model link schema if needed
            try:
                db.execute(text("SELECT fps_limit FROM camera_model_links LIMIT 1"))
            except Exception:
                logger.info("Upgrading camera_model_links table schema (adding fps_limit)")
                try:
                    db.execute(text("ALTER TABLE camera_model_links ADD COLUMN fps_limit INTEGER"))
                except Exception:
                    pass
                db.commit()

            
            from backend.db.models import AIModel
            models = db.query(AIModel).all()
            for model in models:
                cfg = dict(model.config_json) if isinstance(model.config_json, dict) else {}
                if "fps_limit" not in cfg:
                    cfg["fps_limit"] = 5
                if model.key == "object":
                    cfg["allowed_classes"] = [
                        "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
                        "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
                        "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
                        "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl",
                        "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
                        "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet",
                        "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
                        "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
                        "hair dryer", "toothbrush"
                    ]
                elif model.key == "vehicle" and "allowed_classes" not in cfg:
                    cfg["allowed_classes"] = ["bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"]
                elif model.key == "animal" and "allowed_classes" not in cfg:
                    cfg["allowed_classes"] = ["bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"]
                model.config_json = cfg
            db.commit()

            
            master = db.query(MasterAdmin).first()
            if master:
                from backend.db.models import User, UserRole, AccountStatus
                shadow = db.query(User).filter(User.id == master.id).first()
                if not shadow:
                    logger.info("Creating shadow User entry for Master Admin to satisfy foreign keys")
                    shadow = User(
                        id=master.id,
                        username=master.username,
                        password_hash=master.password_hash,
                        salt=master.salt,
                        role=UserRole.MASTER_ADMIN,
                        status=AccountStatus.ACTIVE
                    )
                    db.add(shadow)
                    db.commit()
        
        except Exception as e:
            logger.error(f"Bootstrap error: {e}", exc_info=True)
            raise
        
        finally:
            db.close()
    
    @staticmethod
    def _seed_ai_models(db: Session) -> None:
        """Seed default AI models into database"""
        models = [
            {
                "key": "person",
                "display_name": "Person Detection",
                "version": "1.0",
                "requires_gpu": False,
                "config": {"confidence_threshold": 0.5, "fps_limit": 5}
            },
            {
                "key": "fire_smoke",
                "display_name": "Fire/Smoke Detection",
                "version": "1.0",
                "requires_gpu": False,
                "config": {"confidence_threshold": 0.6, "fps_limit": 5}
            },
            {
                "key": "accident",
                "display_name": "Accident Detection",
                "version": "1.0",
                "requires_gpu": True,
                "config": {"confidence_threshold": 0.5, "fps_limit": 5}
            },
            {
                "key": "object",
                "display_name": "Object Detection",
                "version": "1.0",
                "requires_gpu": False,
                "config": {
                    "confidence_threshold": 0.5,
                    "fps_limit": 5,
                    "allowed_classes": [
                        "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
                        "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
                        "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
                        "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl",
                        "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
                        "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet",
                        "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
                        "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
                        "hair dryer", "toothbrush"
                    ]
                }
            },
            {
                "key": "vehicle",
                "display_name": "Vehicle Detection",
                "version": "1.0",
                "requires_gpu": False,
                "config": {
                    "confidence_threshold": 0.5,
                    "fps_limit": 5,
                    "allowed_classes": ["bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"]
                }
            },
            {
                "key": "animal",
                "display_name": "Animal Detection",
                "version": "1.0",
                "requires_gpu": False,
                "config": {
                    "confidence_threshold": 0.5,
                    "fps_limit": 5,
                    "allowed_classes": ["bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"]
                }
            },
            {
                "key": "face",
                "display_name": "Face Matching",
                "version": "1.0",
                "requires_gpu": True,
                "config": {"confidence_threshold": 0.6, "fps_limit": 5}
            },
        ]
        
        for model_data in models:
            existing = db.query(AIModel).filter(AIModel.key == model_data["key"]).first()
            if not existing:
                model = AIModel(
                    id=generate_secure_token(18),
                    key=model_data["key"],
                    display_name=model_data["display_name"],
                    version=model_data["version"],
                    requires_gpu=model_data["requires_gpu"],
                    config_json=model_data["config"],
                    enabled_globally=True
                )
                db.add(model)
        
        db.commit()
        logger.info("Default AI models seeded")
    
    @staticmethod
    def _seed_system_config(db: Session) -> None:
        """Seed default system configuration"""
        default_configs = [
            {"key": "retention_days", "value": str(config.DEFAULT_RETENTION_DAYS)},
            {"key": "theme", "value": "dark"},
            {"key": "inference_device", "value": "auto"},
            {"key": "gpu_fallback", "value": "true"},
            {"key": "ai_processing_enabled", "value": "true"},
        ]
        
        for config_data in default_configs:
            existing = db.query(SystemConfig).filter(SystemConfig.key == config_data["key"]).first()
            if not existing:
                sys_config = SystemConfig(
                    id=generate_secure_token(18),
                    key=config_data["key"],
                    value_encrypted=config_data["value"]  
                )
                db.add(sys_config)
        
        db.commit()
        logger.info("System config seeded")
    
    @staticmethod
    def setup_master_admin(
        db: Session,
        username: str,
        password_hash: str,
        password_salt: str
    ) -> tuple:
        """
        Create master admin account (first-boot setup).
        
        Args:
            db: Database session
            username: Master admin username
            password_hash: Hashed password
            password_salt: Password salt
            
        Returns:
            Tuple of (master_admin, recovery_key_plaintext)
        """
        from backend.security import generate_secure_token, hash_recovery_key
        
        
        recovery_key = generate_recovery_key()
        recovery_key_hash, recovery_key_salt = hash_recovery_key(recovery_key)
        
        
        master_admin = MasterAdmin(
            id=generate_secure_token(18),
            username=username,
            password_hash=password_hash,
            salt=password_salt,
            recovery_key_hash=recovery_key_hash,
            recovery_key_salt=recovery_key_salt,
            recovery_key_created_at=datetime.utcnow(),
            recovery_key_used=False,
            hostname=config.PUBLIC_HOST,
            port=config.PUBLIC_PORT
        )
        
        db.add(master_admin)
        
        
        from backend.db.models import User, UserRole, AccountStatus
        shadow = User(
            id=master_admin.id,
            username=username,
            password_hash=password_hash,
            salt=password_salt,
            role=UserRole.MASTER_ADMIN,
            status=AccountStatus.ACTIVE
        )
        db.add(shadow)
        db.commit()
        logger.info(f"Master admin and shadow User created: {username}")
        
        return master_admin, recovery_key
    
    @staticmethod
    def check_database_health(db: Session) -> bool:
        """
        Quick health check on database.
        
        Args:
            db: Database session
            
        Returns:
            True if healthy
        """
        try:
            
            db.query(MasterAdmin).count()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
