"""
Append-only, hash-chained audit logger.
Every sensitive action is logged as a row; each row's hash covers the previous row's hash
(forming a chain). Any tampering of a row can be detected by verifying the chain.

Usage:
    audit_logger.log(actor_id, actor_role, action, target_type, target_id, detail)
    result = audit_logger.verify_chain()
"""

import hashlib
import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)
_lock = threading.Lock()


class AuditLogger:
    """Thread-safe hash-chained audit logger persisting to the AuditLog DB table."""

    def __init__(self):
        self._last_hash: Optional[str] = None

    def _compute_row_hash(self, prev_hash: str, row_data: dict) -> str:
        combined = prev_hash + json.dumps(row_data, sort_keys=True, default=str)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _get_last_row(self, db) -> Optional[object]:
        from backend.db.models import AuditLog
        return (
            db.query(AuditLog)
            .order_by(AuditLog.sequence_number.desc())
            .first()
        )

    def log(
        self,
        actor_id: Optional[str],
        actor_role: str,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        detail: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log an audit event. Thread-safe and non-blocking (fire-and-forget)."""
        threading.Thread(
            target=self._write,
            args=(actor_id, actor_role, action, target_type, target_id, detail, ip_address),
            daemon=True
        ).start()

    def _write(
        self,
        actor_id, actor_role, action, target_type, target_id, detail, ip_address
    ):
        with _lock:
            try:
                from backend.db.session import DatabaseManager
                from backend.db.models import AuditLog

                db = DatabaseManager.get_session()
                try:
                    last_row = self._get_last_row(db)
                    prev_hash = last_row.row_hash if last_row else "0" * 64
                    next_seq = (last_row.sequence_number + 1) if last_row else 1

                    row_data = {
                        "seq": next_seq,
                        "ts": datetime.utcnow().isoformat(),
                        "actor_id": actor_id,
                        "actor_role": actor_role,
                        "action": action,
                        "target_type": target_type,
                        "target_id": target_id,
                        "detail": detail,
                        "ip_address": ip_address,
                    }
                    row_hash = self._compute_row_hash(prev_hash, row_data)

                    entry = AuditLog(
                        id=str(uuid.uuid4()),
                        sequence_number=next_seq,
                        actor_id=actor_id,
                        actor_role=actor_role,
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        detail=detail,
                        ip_address=ip_address,
                        timestamp=datetime.utcnow(),
                        prev_row_hash=prev_hash,
                        row_hash=row_hash,
                    )
                    db.add(entry)
                    db.commit()
                    self._last_hash = row_hash
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Audit log write failed: {e}")

    def verify_chain(self) -> dict:
        """
        Walk all audit rows in sequence order and verify the hash chain.
        Returns a report with first_broken_seq (if any) and total rows checked.
        """
        try:
            from backend.db.session import DatabaseManager
            from backend.db.models import AuditLog

            db = DatabaseManager.get_session()
            try:
                rows = (
                    db.query(AuditLog)
                    .order_by(AuditLog.sequence_number.asc())
                    .all()
                )
                prev_hash = "0" * 64
                broken_at = None
                for row in rows:
                    row_data = {
                        "seq": row.sequence_number,
                        "ts": row.timestamp.isoformat(),
                        "actor_id": row.actor_id,
                        "actor_role": row.actor_role,
                        "action": row.action,
                        "target_type": row.target_type,
                        "target_id": row.target_id,
                        "detail": row.detail,
                        "ip_address": row.ip_address,
                    }
                    expected = self._compute_row_hash(prev_hash, row_data)
                    if expected != row.row_hash:
                        broken_at = row.sequence_number
                        break
                    prev_hash = row.row_hash
                return {
                    "total_rows": len(rows),
                    "chain_intact": broken_at is None,
                    "first_broken_sequence": broken_at,
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Chain verification error: {e}")
            return {"error": str(e)}



audit_logger = AuditLogger()
