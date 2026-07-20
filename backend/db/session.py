"""
Database session and engine management.
Handles SQLite engine creation with encryption support.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from pathlib import Path
import logging

from backend.core.config import config
from backend.db.models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database engine and sessions"""
    
    _engine = None
    _SessionLocal = None
    
    @classmethod
    def init_db(cls) -> None:
        """Initialize database engine and create tables"""
        
        config.DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        
        
        
        cls._engine = create_engine(
            f"sqlite:///{config.DATABASE_PATH}",
            connect_args={"check_same_thread": False},
            echo=config.LOG_LEVEL == "DEBUG"
        )
        
        # Enable foreign keys and WAL mode for SQLite
        @event.listens_for(cls._engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
        
        
        cls._SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=cls._engine
        )
        
        
        Base.metadata.create_all(bind=cls._engine)
        logger.info(f"Database initialized at {config.DATABASE_PATH}")
    
    @classmethod
    def get_engine(cls):
        """Get SQLAlchemy engine"""
        if cls._engine is None:
            cls.init_db()
        return cls._engine
    
    @classmethod
    def get_session(cls) -> Session:
        """Get a new database session"""
        if cls._SessionLocal is None:
            cls.init_db()
        return cls._SessionLocal()
    
    @classmethod
    def close_db(cls) -> None:
        """Close all sessions"""
        if cls._engine:
            cls._engine.dispose()
    
    @classmethod
    def reset_db(cls) -> None:
        """Reset database (for testing)"""
        if cls._engine:
            Base.metadata.drop_all(bind=cls._engine)
            Base.metadata.create_all(bind=cls._engine)
            logger.warning("Database reset")


# Dependency for FastAPI
def get_db() -> Session:
    """Dependency injection for database session"""
    db = DatabaseManager.get_session()
    try:
        yield db
    finally:
        db.close()



DatabaseManager.init_db()

# Expose SessionLocal for backward compatibility
SessionLocal = DatabaseManager.get_session
