"""Alert management endpoints — Agent 11."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.database import get_db
from app.detector.aggregator import aggregate_external_alerts
from app.detector.circuit_breaker import detect_circuit_breaker_alerts
from app.detector.router import process_alerts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/scan")
def scan_alerts(
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> dict:
    """Run full detection + aggregation cycle."""
    # 1. Circuit-breaker (own agent 11 detections)
    cb_alerts = detect_circuit_breaker_alerts(db)

    # 2. External aggregation (agents 7, 8, 9, 10)
    ext_alerts = aggregate_external_alerts(db)

    all_alerts = cb_alerts + ext_alerts

    # 3. Confirmation gate + routing
    scan_result = process_alerts(db, all_alerts)

    return {
        "symbols_scanned": scan_result.symbols_scanned,
        "alerts_new": scan_result.new_alerts,
        "alerts_confirmed": scan_result.confirmed,
        "alerts_resolved": scan_result.resolved,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("")
def list_alerts(
    severity: Optional[str] = Query(default=None),
    source_agent: Optional[int] = Query(default=None),
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> list[dict]:
    """List active (PENDING + CONFIRMED) alerts with optional filters."""
    conditions = ["status IN ('PENDING', 'CONFIRMED')"]
    params: dict[str, Any] = {"limit": limit}

    if severity is not None:
        conditions.append("severity = :severity")
        params["severity"] = severity
    if source_agent is not None:
        conditions.append("source_agent = :source_agent")
        params["source_agent"] = source_agent
    if symbol is not None:
        conditions.append("symbol = :symbol")
        params["symbol"] = symbol

    where_clause = " AND ".join(conditions)
    sql = text(
        f"""
        SELECT id, symbol, source_agent, alert_type, severity, status,
               first_seen_at, confirmed_at, resolved_at, details,
               notified, created_at, updated_at
        FROM platform_shared.unified_alerts
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )
    rows = db.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


@router.get("/{symbol}")
def get_symbol_alerts(
    symbol: str,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> list[dict]:
    """Full alert history for a symbol (all statuses, latest first)."""
    sql = text(
        """
        SELECT id, symbol, source_agent, alert_type, severity, status,
               first_seen_at, confirmed_at, resolved_at, details,
               notified, created_at, updated_at
        FROM platform_shared.unified_alerts
        WHERE symbol = :symbol
        ORDER BY created_at DESC
        """
    )
    rows = db.execute(sql, {"symbol": symbol}).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No alerts found for symbol '{symbol}'")
    return [_row_to_dict(row) for row in rows]


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> dict:
    """Manually resolve an alert by ID."""
    # Check it exists
    row = db.execute(
        text(
            "SELECT id, status FROM platform_shared.unified_alerts WHERE id = :id"
        ),
        {"id": alert_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    now = datetime.now(timezone.utc)
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
    db.commit()
    return {"alert_id": alert_id, "status": "RESOLVED", "resolved_at": now.isoformat()}


def _row_to_dict(row) -> dict:
    """Convert a SQLAlchemy Row to a plain dict."""
    return {
        "id": row.id,
        "symbol": row.symbol,
        "source_agent": row.source_agent,
        "alert_type": row.alert_type,
        "severity": row.severity,
        "status": row.status,
        "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "details": row.details,
        "notified": row.notified,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
