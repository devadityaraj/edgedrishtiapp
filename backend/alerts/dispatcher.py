"""
Alert Dispatcher — receives detection events, deduplicates, and sends to all configured channels.
Supports Telegram and in-app notifications. Email is a stub interface.
"""

import threading
import queue
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# How long (seconds) to suppress repeat alerts for the same (camera, event_type) pair
_DEBOUNCE_SECONDS = 60


class AlertDispatcher:
    """Sends alerts to all active alert contacts."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue(maxsize=500)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # (camera_id, event_type) → last_sent timestamp
        self._debounce: Dict[tuple, datetime] = {}

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="alert-dispatcher", daemon=True)
        self._thread.start()
        logger.info("Alert dispatcher started")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def queue_alert(
        self,
        event_id: str,
        event_type: str,
        confidence: float,
        camera_id: str,
        snapshot_path: Optional[Path] = None,
    ):
        """Non-blocking enqueue of an alert to dispatch."""
        try:
            self._queue.put_nowait({
                "event_id": event_id,
                "event_type": event_type,
                "confidence": confidence,
                "camera_id": camera_id,
                "snapshot_path": snapshot_path,
                "queued_at": datetime.utcnow(),
            })
        except queue.Full:
            logger.warning("Alert queue full — dropping alert")

    def _run(self):
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            self._dispatch(item)

    def _dispatch(self, item: dict):
        camera_id = item["camera_id"]
        event_type = item["event_type"]
        debounce_key = (camera_id, event_type)
        now = datetime.utcnow()

        
        last_sent = self._debounce.get(debounce_key)
        if last_sent and (now - last_sent).total_seconds() < _DEBOUNCE_SECONDS:
            return

        self._debounce[debounce_key] = now

        try:
            from backend.db.session import DatabaseManager
            from backend.db.models import AlertContact, AlertLog

            db = DatabaseManager.get_session()
            try:
                contacts = db.query(AlertContact).filter(AlertContact.enabled == True).all()
                camera_name = self._get_camera_name(db, camera_id)

                for contact in contacts:
                    try:
                        success = self._send_to_contact(contact, item, camera_name)
                        log = AlertLog(
                            id=str(uuid.uuid4()),
                            detection_event_id=item["event_id"],
                            contact_id=contact.id,
                            channel=contact.channel,
                            sent_at=now,
                            success=success,
                        )
                        db.add(log)
                    except Exception as e:
                        logger.error(f"Alert send to {contact.id} failed: {e}")

                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Alert dispatch error: {e}")

    def _get_camera_name(self, db, camera_id: str) -> str:
        try:
            from backend.db.models import Camera
            cam = db.query(Camera).filter(Camera.id == camera_id).first()
            return cam.name if cam else camera_id
        except Exception:
            return camera_id

    def _send_to_contact(self, contact, item: dict, camera_name: str) -> bool:
        channel = getattr(contact, "channel", "telegram")
        if channel == "telegram":
            return self._send_telegram(contact, item, camera_name)
        return False

    def _send_telegram(self, contact, item: dict, camera_name: str) -> bool:
        try:
            from backend.alerts.channels.telegram_channel import send_telegram_alert
            return send_telegram_alert(
                bot_token=contact.bot_token,
                chat_id=contact.chat_id,
                camera_name=camera_name,
                event_type=item["event_type"],
                confidence=item["confidence"],
                snapshot_path=item.get("snapshot_path"),
            )
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False



alert_dispatcher = AlertDispatcher()
