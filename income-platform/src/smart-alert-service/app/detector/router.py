"""
Agent 11 — Smart Alert Service
Confirmation gate + router: deduplicates detected alerts against unified_alerts table
and manages PENDING → CONFIRMED → RESOLVED lifecycle.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.detector.circuit_breaker import AlertData

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    new_alerts: int = 0
    confirmed: int = 0
    resolved: int = 0
    symbols_scanned: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def process_alerts(db: Session, detected: list[AlertData]) -> ScanResult:
    """
    Confirm gate + lifecycle management.

    For each detected alert:
    - If no existing PENDING/CONFIRMED row: INSERT as PENDING (new_alert++)
    - If PENDING and seen again: UPDATE to CONFIRMED (confirmed++)
    - If CONFIRMED: touch updated_at (already confirmed, stays confirmed)

    For any PENDING/CONFIRMED row NOT in current detected set:
    - UPDATE to RESOLVED (resolved++)
    """
    result = ScanResult()

    # Build a set of (symbol, source_agent, alert_type) for detected alerts
    detected_keys = {
        (a.symbol, a.source_agent, a.alert_type) for a in detected
    }

    result.symbols_scanned = len({a.symbol for a in detected})

    # Fetch all currently open alerts (PENDING or CONFIRMED)
    open_rows = db.execute(
        text(
            """
            SELECT id, symbol, source_agent, alert_type, status
            FROM platform_shared.unified_alerts
            WHERE status IN ('PENDING', 'CONFIRMED')
            """
        )
    ).fetchall()

    open_keys: dict[tuple, int] = {
        (row.symbol, row.source_agent, row.alert_type): row.id
        for row in open_rows
    }
    open_status: dict[tuple, str] = {
        (row.symbol, row.source_agent, row.alert_type): row.status
        for row in open_rows
    }

    now = _now()

    # Process each detected alert
    for alert in detected:
        key = (alert.symbol, alert.source_agent, alert.alert_type)
        if key not in open_keys:
            # New alert — INSERT as PENDING
            db.execute(
                text(
                    """
                    INSERT INTO platform_shared.unified_alerts
                        (symbol, source_agent, alert_type, severity, status,
                         first_seen_at, details, notified, created_at, updated_at)
                    VALUES
                        (:symbol, :source_agent, :alert_type, :severity, 'PENDING',
                         :now, :details::jsonb, false, :now, :now)
                    """
                ),
                {
                    "symbol": alert.symbol,
                    "source_agent": alert.source_agent,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "now": now,
                    "details": _dict_to_json(alert.details),
                },
            )
            result.new_alerts += 1
            logger.debug("NEW alert PENDING: %s / %s / %s", alert.symbol, alert.source_agent, alert.alert_type)
        else:
            existing_status = open_status[key]
            alert_id = open_keys[key]
            if existing_status == "PENDING":
                # Second consecutive detection → CONFIRMED
                db.execute(
                    text(
                        """
                        UPDATE platform_shared.unified_alerts
                        SET status = 'CONFIRMED', confirmed_at = :now, updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    {"now": now, "id": alert_id},
                )
                result.confirmed += 1
                logger.debug("CONFIRMED alert id=%d: %s / %s", alert_id, alert.symbol, alert.alert_type)
            else:
                # Already CONFIRMED — just touch updated_at
                db.execute(
                    text(
                        """
                        UPDATE platform_shared.unified_alerts
                        SET updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    {"now": now, "id": alert_id},
                )

    # Resolve any open alerts that are no longer detected
    for key, alert_id in open_keys.items():
        if key not in detected_keys:
            db.execute(
                text(
                    """
                    UPDATE platform_shared.unified_alerts
                    SET status = 'RESOLVED', resolved_at = :now, updated_at = :now
                    WHERE id = :id
                    """
                ),
                {"now": now, "id": alert_id},
            )
            result.resolved += 1
            logger.debug("RESOLVED alert id=%d: %s / %s / %s", alert_id, key[0], key[1], key[2])

    db.commit()
    return result


def _dict_to_json(d: dict) -> str:
    """Convert a dict to a JSON string for parameterised insertion."""
    import json
    return json.dumps(d)
