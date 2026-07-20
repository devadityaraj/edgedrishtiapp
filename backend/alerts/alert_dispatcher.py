"""
EDGE Drishti - Alert Dispatcher System
Sends alerts via multiple channels (Telegram, In-App, Email)
With debouncing and alert grouping
"""

import asyncio
import httpx
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import json
from backend.db.models import AlertConfig, Alert, Camera
from backend.db.session import SessionLocal

logger = logging.getLogger(__name__)


class AlertChannel(str, Enum):
    TELEGRAM = "telegram"
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"  
    HIGH = "high"          
    MEDIUM = "medium"      
    LOW = "low"            


@dataclass
class AlertRule:
    """Defines when and how to send alerts"""
    id: str
    name: str
    threat_class: str  
    min_confidence: float = 0.7
    severity: AlertSeverity = AlertSeverity.HIGH
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.TELEGRAM, AlertChannel.IN_APP])
    debounce_seconds: int = 60  
    group_alerts: bool = True
    group_window: int = 300  # 5 minute window for grouping
    camera_ids: Optional[List[str]] = None  


@dataclass
class AlertPayload:
    """Alert data to be sent"""
    rule_id: str
    camera_id: str
    camera_name: str
    threat_class: str
    confidence: float
    severity: AlertSeverity
    bbox: tuple  
    timestamp: datetime
    frame_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertDebouncer:
    """Prevents duplicate alerts within time window"""

    def __init__(self):
        self.last_alerts: Dict[str, datetime] = {}
        self.lock = asyncio.Lock()

    async def should_send(self, alert_key: str, debounce_seconds: int) -> bool:
        """Check if alert should be sent based on debounce window"""
        async with self.lock:
            now = datetime.now()
            last_time = self.last_alerts.get(alert_key)

            if last_time and (now - last_time).total_seconds() < debounce_seconds:
                return False

            self.last_alerts[alert_key] = now
            
            self.last_alerts = {
                k: v for k, v in self.last_alerts.items()
                if (now - v).total_seconds() < debounce_seconds * 2
            }
            return True


class TelegramChannel:
    """Telegram alert channel"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    async def send(self, alert: AlertPayload) -> bool:
        """Send alert via Telegram"""
        try:
            message = self._format_message(alert)

            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                resp = await client.post(
                    f"{self.api_url}/sendMessage",
                    json=payload,
                    timeout=10.0
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {str(e)}")
            return False

    def _format_message(self, alert: AlertPayload) -> str:
        """Format alert for Telegram"""
        severity_emoji = {
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.HIGH: "⚠️",
            AlertSeverity.MEDIUM: "⏺️",
            AlertSeverity.LOW: "ℹ️"
        }

        emoji = severity_emoji.get(alert.severity, "📹")

        return f"""{emoji} <b>Security Alert</b>

<b>Camera:</b> {alert.camera_name}
<b>Threat:</b> {alert.threat_class.upper()}
<b>Confidence:</b> {alert.confidence:.1%}
<b>Severity:</b> {alert.severity.value.upper()}
<b>Time:</b> {alert.timestamp.strftime('%H:%M:%S')}

🎯 Location: {alert.bbox}
⚡ Action: Review footage and verify threat"""


class InAppChannel:
    """In-app alert notification channel"""

    def __init__(self, db_session):
        self.db = db_session

    async def send(self, alert: AlertPayload) -> bool:
        """Store alert in database for in-app display"""
        try:
            alert_record = Alert(
                rule_id=alert.rule_id,
                camera_id=alert.camera_id,
                threat_class=alert.threat_class,
                confidence=alert.confidence,
                severity=alert.severity.value,
                bbox_json=str(alert.bbox),
                metadata_json=json.dumps(alert.metadata),
                timestamp=alert.timestamp,
                is_read=False
            )
            self.db.add(alert_record)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"In-app alert save failed: {str(e)}")
            self.db.rollback()
            return False


class WebhookChannel:
    """Webhook alert channel for external integrations"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, alert: AlertPayload) -> bool:
        """Send alert via webhook"""
        try:
            payload = {
                "rule_id": alert.rule_id,
                "camera_id": alert.camera_id,
                "camera_name": alert.camera_name,
                "threat_class": alert.threat_class,
                "confidence": float(alert.confidence),
                "severity": alert.severity.value,
                "bbox": alert.bbox,
                "timestamp": alert.timestamp.isoformat(),
                "metadata": alert.metadata
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0
                )
                return resp.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Webhook send failed: {str(e)}")
            return False


class AlertDispatcher:
    """Central alert dispatcher managing all channels and rules"""

    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.channels: Dict[AlertChannel, Any] = {}
        self.debouncer = AlertDebouncer()
        self.alert_queue: asyncio.Queue = None
        self.alert_batch: List[AlertPayload] = []
        self.batch_timeout = 5  
        self.is_running = False

    def initialize(self, config: Dict[str, Any]):
        """Initialize dispatcher with configuration"""
        try:
            # Initialize Telegram channel if configured
            if "telegram_bot_token" in config and "telegram_chat_id" in config:
                self.channels[AlertChannel.TELEGRAM] = TelegramChannel(
                    config["telegram_bot_token"],
                    config["telegram_chat_id"]
                )
                logger.info("Telegram channel initialized")

            
            db = SessionLocal()
            self.channels[AlertChannel.IN_APP] = InAppChannel(db)
            logger.info("In-app channel initialized")

            # Initialize webhook if configured
            if "webhook_url" in config:
                self.channels[AlertChannel.WEBHOOK] = WebhookChannel(config["webhook_url"])
                logger.info("Webhook channel initialized")

            # Load alert rules from database
            self._load_rules()

            self.alert_queue = asyncio.Queue(maxsize=1000)
            self.is_running = True
            logger.info("Alert dispatcher initialized")

        except Exception as e:
            logger.error(f"Dispatcher initialization failed: {str(e)}")

    def _load_rules(self):
        """Load alert rules from database"""
        try:
            db = SessionLocal()
            configs = db.query(AlertConfig).filter(AlertConfig.is_active == True).all()

            for config in configs:
                rule = AlertRule(
                    id=config.id,
                    name=config.name,
                    threat_class=config.threat_class,
                    min_confidence=config.min_confidence,
                    severity=AlertSeverity(config.severity),
                    channels=[AlertChannel(ch) for ch in config.channels or ["telegram", "in_app"]],
                    debounce_seconds=config.debounce_seconds or 60,
                    group_alerts=config.group_alerts or True,
                )
                self.rules[config.id] = rule

            db.close()
            logger.info(f"Loaded {len(self.rules)} alert rules")

        except Exception as e:
            logger.error(f"Failed to load rules: {str(e)}")

    async def process_detection(self, detection: Any):
        """Process detection and send alerts if rules match"""
        try:
            for rule in self.rules.values():
                if rule.threat_class != detection.class_name:
                    continue

                if detection.confidence < rule.min_confidence:
                    continue

                
                if rule.camera_ids and detection.camera_id not in rule.camera_ids:
                    continue

                
                alert = AlertPayload(
                    rule_id=rule.id,
                    camera_id=detection.camera_id,
                    camera_name=self._get_camera_name(detection.camera_id),
                    threat_class=detection.class_name,
                    confidence=detection.confidence,
                    severity=rule.severity,
                    bbox=detection.bbox,
                    timestamp=detection.timestamp,
                    frame_index=detection.frame_index,
                    metadata=detection.metadata or {}
                )

                # Queue for sending
                await self.alert_queue.put((rule, alert))

        except Exception as e:
            logger.error(f"Detection processing failed: {str(e)}")

    async def dispatch_alerts(self):
        """Main alert dispatch loop"""
        while self.is_running:
            try:
                rule, alert = await asyncio.wait_for(
                    self.alert_queue.get(),
                    timeout=1.0
                )

                
                alert_key = f"{rule.id}:{alert.camera_id}"
                if not await self.debouncer.should_send(alert_key, rule.debounce_seconds):
                    continue

                
                for channel_type in rule.channels:
                    if channel_type in self.channels:
                        channel = self.channels[channel_type]
                        success = await channel.send(alert)
                        logger.debug(f"Alert sent to {channel_type}: {success}")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Alert dispatch error: {str(e)}")

    def _get_camera_name(self, camera_id: str) -> str:
        """Get camera name from ID"""
        try:
            db = SessionLocal()
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            return camera.name if camera else camera_id
        except:
            return camera_id

    def shutdown(self):
        """Shutdown dispatcher"""
        self.is_running = False
        logger.info("Alert dispatcher shutdown")



alert_dispatcher = AlertDispatcher()
