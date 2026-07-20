"""
Telegram alert channel.
Sends alert messages (with optional snapshot photo) via the Telegram Bot API.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def send_telegram_alert(
    bot_token: str,
    chat_id: str,
    camera_name: str,
    event_type: str,
    confidence: float,
    snapshot_path: Optional[Path] = None,
) -> bool:
    """
    Send an alert to a Telegram chat.
    Uses httpx (already installed) for synchronous HTTP requests.
    Returns True on success.
    """
    if not bot_token or not chat_id:
        logger.warning("Telegram bot_token or chat_id not configured")
        return False

    import httpx
    from datetime import datetime

    base_url = f"https://api.telegram.org/bot{bot_token}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icon = {
        "fire": "🔥", "smoke": "💨", "fall_detected": "⚠️",
        "person": "👤", "face": "🪪",
    }.get(event_type.split(":")[0], "🚨")

    text = (
        f"{icon} *EDGE Drishti Alert*\n"
        f"📷 Camera: *{camera_name}*\n"
        f"🏷️ Event: `{event_type}`\n"
        f"📊 Confidence: {confidence:.0%}\n"
        f"🕐 Time: {timestamp}"
    )

    try:
        with httpx.Client(timeout=15.0) as client:
            # Try to send photo with caption
            if snapshot_path and Path(snapshot_path).exists():
                with open(snapshot_path, "rb") as photo:
                    resp = client.post(
                        f"{base_url}/sendPhoto",
                        data={
                            "chat_id": chat_id,
                            "caption": text,
                            "parse_mode": "Markdown",
                        },
                        files={"photo": photo},
                    )
                if resp.status_code == 200:
                    return True
                logger.warning(f"Telegram sendPhoto failed ({resp.status_code}), falling back to text")

            
            resp = client.post(
                f"{base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            if resp.status_code == 200:
                return True
            logger.error(f"Telegram sendMessage failed: {resp.status_code} {resp.text}")
            return False

    except Exception as e:
        logger.error(f"Telegram send exception: {e}")
        return False


def test_telegram_connection(bot_token: str, chat_id: str) -> dict:
    """Test Telegram bot connectivity. Returns {success, message}."""
    import httpx
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
            if resp.status_code != 200:
                return {"success": False, "message": f"Invalid bot token (HTTP {resp.status_code})"}
            bot_info = resp.json().get("result", {})

            
            test_resp = client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"✅ *EDGE Drishti* — Test connection successful!\nBot: @{bot_info.get('username', 'unknown')}",
                    "parse_mode": "Markdown",
                },
            )
            if test_resp.status_code == 200:
                return {"success": True, "message": f"Test message sent to chat {chat_id}"}
            return {"success": False, "message": f"Bot valid but chat ID invalid: {test_resp.text}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
