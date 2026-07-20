import importlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.camera_routes import _delete_camera_related_records
from backend.db.models import (
    AIModel,
    Alert,
    AlertLog,
    Base,
    Camera,
    CameraModelLink,
    DetectionEvent,
    Notification,
    User,
    UserRole,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_delete_camera_related_records_cleans_up_foreign_key_rows(db_session):
    user = User(id="user-1", username="tester", password_hash="hash", role=UserRole.USER)
    camera = Camera(
        id="cam-1",
        name="Test Camera",
        source_type="webcam",
        connection_uri_encrypted="0",
    )
    ai_model = AIModel(id="model-1", key="person", display_name="Person", version="1.0")
    db_session.add_all([user, camera, ai_model])
    db_session.flush()

    detection_event = DetectionEvent(
        id="event-1",
        camera_id=camera.id,
        ai_model_id=ai_model.id,
        event_type="person",
        confidence=0.95,
    )
    db_session.add(detection_event)
    db_session.add(
        AlertLog(id="alert-log-1", detection_event_id=detection_event.id, channel="in_app", success=True)
    )
    db_session.add(
        Notification(
            id="notification-1",
            user_id="user-1",
            detection_event_id=detection_event.id,
            title="Alert",
            message="Alert body",
        )
    )
    db_session.add(
        Alert(id="alert-1", camera_id=camera.id, threat_class="person", confidence=0.95)
    )
    db_session.add(
        CameraModelLink(id="link-1", camera_id=camera.id, ai_model_id=ai_model.id, enabled=True)
    )
    db_session.commit()

    event_id = detection_event.id

    _delete_camera_related_records(db_session, camera.id)
    db_session.delete(camera)
    db_session.commit()

    assert db_session.query(Camera).filter(Camera.id == camera.id).first() is None
    assert db_session.query(DetectionEvent).filter(DetectionEvent.camera_id == camera.id).count() == 0
    assert db_session.query(AlertLog).filter(AlertLog.detection_event_id == event_id).count() == 0
    assert db_session.query(Notification).filter(Notification.detection_event_id == event_id).count() == 0
    assert db_session.query(Alert).filter(Alert.camera_id == camera.id).count() == 0
    assert db_session.query(CameraModelLink).filter(CameraModelLink.camera_id == camera.id).count() == 0


def test_webcam_source_module_imports():
    module = importlib.import_module("backend.cameras.sources.webcam")
    assert module.WebcamSource is not None
