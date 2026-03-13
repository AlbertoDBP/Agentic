"""
Agent 10 — NAV Erosion Monitor
API: /monitor/* endpoints.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NavAlert
from app.monitor import snapshot_reader
from app.monitor.detector import AlertResult, detect_violations
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor", tags=["monitor"])


# ── POST /monitor/scan ────────────────────────────────────────────────────────

@router.post("/scan")
async def scan(
    dry_run: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    """Scan all symbols with recent nav_snapshots. Detect violations, upsert alerts."""
    snapshots = await snapshot_reader.get_recent_snapshots(settings.snapshot_lookback_days)
    symbols = [s["symbol"] for s in snapshots if s.get("symbol")]
    scores = await snapshot_reader.get_income_scores(symbols if symbols else None)

    violations: list[AlertResult] = detect_violations(snapshots, scores)

    scanned_at = datetime.now(timezone.utc).isoformat()
    alerts_new = 0
    alerts_resolved = 0
    alert_summaries: list[dict] = []

    # Track which (symbol, alert_type) combos fired in this scan
    fired_keys: set[tuple[str, str]] = {(v.symbol, v.alert_type) for v in violations}

    if not dry_run:
        # Resolve previously active alerts whose condition no longer fires
        active_alerts = (
            db.query(NavAlert)
            .filter(NavAlert.resolved_at.is_(None))
            .all()
        )
        for active in active_alerts:
            if (active.symbol, active.alert_type) not in fired_keys:
                active.resolved_at = datetime.now(timezone.utc)
                active.updated_at = datetime.now(timezone.utc)
                alerts_resolved += 1

        # Upsert violations
        for v in violations:
            existing = (
                db.query(NavAlert)
                .filter(
                    NavAlert.symbol == v.symbol,
                    NavAlert.alert_type == v.alert_type,
                    NavAlert.resolved_at.is_(None),
                )
                .first()
            )
            if existing:
                # Update existing active alert
                existing.severity = v.severity
                existing.details = v.details
                existing.score_at_alert = v.score_at_alert
                existing.erosion_rate_used = v.erosion_rate_used
                existing.threshold_used = v.threshold_used
                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Insert new alert
                new_alert = NavAlert(
                    symbol=v.symbol,
                    alert_type=v.alert_type,
                    severity=v.severity,
                    details=v.details,
                    score_at_alert=v.score_at_alert,
                    erosion_rate_used=v.erosion_rate_used,
                    threshold_used=v.threshold_used,
                )
                db.add(new_alert)
                alerts_new += 1

        db.commit()
    else:
        alerts_new = len(violations)

    for v in violations:
        summary: dict[str, Any] = {
            "symbol": v.symbol,
            "alert_type": v.alert_type,
            "severity": v.severity,
        }
        if v.erosion_rate_used is not None:
            summary["erosion_rate_used"] = v.erosion_rate_used
        if v.threshold_used is not None:
            summary["threshold_used"] = v.threshold_used
        if v.details.get("erosion_rate_30d") is not None:
            summary["erosion_rate_30d"] = v.details["erosion_rate_30d"]
        alert_summaries.append(summary)

    return {
        "symbols_scanned": len(snapshots),
        "alerts_new": alerts_new,
        "alerts_resolved": alerts_resolved,
        "alerts": alert_summaries,
        "scanned_at": scanned_at,
    }


# ── GET /monitor/alerts ───────────────────────────────────────────────────────

@router.get("/alerts")
def list_alerts(
    severity: Optional[str] = Query(default=None, description="WARNING or CRITICAL"),
    alert_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    """Return active (unresolved) alerts with optional filtering."""
    q = db.query(NavAlert).filter(NavAlert.resolved_at.is_(None))
    if severity:
        q = q.filter(NavAlert.severity == severity)
    if alert_type:
        q = q.filter(NavAlert.alert_type == alert_type)
    q = q.order_by(NavAlert.created_at.desc()).limit(limit)
    rows = q.all()
    return {
        "alerts": [_alert_to_dict(r) for r in rows],
        "total": len(rows),
    }


# ── GET /monitor/alerts/{symbol} ─────────────────────────────────────────────

@router.get("/alerts/{symbol}")
def get_alerts_for_symbol(
    symbol: str,
    db: Session = Depends(get_db),
) -> dict:
    """Return all alerts (active + resolved) for a symbol, latest first."""
    rows = (
        db.query(NavAlert)
        .filter(NavAlert.symbol == symbol.upper())
        .order_by(NavAlert.created_at.desc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No alerts found for symbol '{symbol}'")
    return {
        "symbol": symbol.upper(),
        "alerts": [_alert_to_dict(r) for r in rows],
        "total": len(rows),
    }


# ── POST /monitor/alerts/{alert_id}/resolve ───────────────────────────────────

@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Mark an alert resolved (sets resolved_at=NOW())."""
    alert = db.get(NavAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    alert.resolved_at = datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)

    return {
        "message": "Alert resolved",
        "alert_id": alert_id,
        "resolved_at": str(alert.resolved_at),
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _alert_to_dict(alert: NavAlert) -> dict:
    return {
        "id": alert.id,
        "symbol": alert.symbol,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "details": alert.details,
        "score_at_alert": float(alert.score_at_alert) if alert.score_at_alert is not None else None,
        "erosion_rate_used": float(alert.erosion_rate_used) if alert.erosion_rate_used is not None else None,
        "threshold_used": float(alert.threshold_used) if alert.threshold_used is not None else None,
        "resolved_at": str(alert.resolved_at) if alert.resolved_at else None,
        "created_at": str(alert.created_at),
        "updated_at": str(alert.updated_at),
    }
