"""
Agent 11 — Smart Alert Service
External alert aggregator: reads scan_results (Agent 07), rebalancing_results (Agent 08),
income_projections (Agent 09), and nav_alerts (Agent 10).
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.detector.circuit_breaker import AlertData

logger = logging.getLogger(__name__)


def _aggregate_agent07(db: Session) -> list[AlertData]:
    """Aggregate VETO_FLAG alerts from Agent 07 scan_results.

    scan_results.items is a JSONB array of ScanItem dicts with keys:
    ticker, veto_flag, score, grade, etc.
    """
    sql = text(
        """
        SELECT item->>'ticker' AS symbol, sr.created_at
        FROM platform_shared.scan_results sr
        CROSS JOIN LATERAL jsonb_array_elements(sr.items) AS item
        WHERE (item->>'veto_flag')::boolean = true
          AND sr.created_at >= NOW() - INTERVAL '7 days'
        """
    )
    rows = db.execute(sql).fetchall()

    alerts: list[AlertData] = []
    for row in rows:
        alerts.append(
            AlertData(
                symbol=row.symbol,
                source_agent=7,
                alert_type="VETO_FLAG",
                severity="WARNING",
                details={"created_at": str(row.created_at)},
            )
        )
    logger.debug("Agent 07 aggregated %d VETO_FLAG alerts", len(alerts))
    return alerts


def _aggregate_agent08(db: Session) -> list[AlertData]:
    """Aggregate REBALANCE_VIOLATION alerts from Agent 08 rebalancing_results."""
    sql = text(
        """
        SELECT violations, created_at
        FROM platform_shared.rebalancing_results
        WHERE created_at >= NOW() - INTERVAL '7 days'
        """
    )
    rows = db.execute(sql).fetchall()

    alerts: list[AlertData] = []
    for row in rows:
        violations = row.violations
        if not violations:
            continue
        # violations may be a list or dict; normalise to list
        if isinstance(violations, dict):
            violations = [violations]
        elif not isinstance(violations, list):
            continue

        for violation in violations:
            if not isinstance(violation, dict):
                continue
            vtype = violation.get("violation_type", "")
            if vtype not in ("VETO", "BELOW_GRADE"):
                continue
            symbol = violation.get("symbol") or violation.get("ticker") or ""
            severity = "CRITICAL" if vtype == "VETO" else "WARNING"
            alerts.append(
                AlertData(
                    symbol=str(symbol),
                    source_agent=8,
                    alert_type="REBALANCE_VIOLATION",
                    severity=severity,
                    details={
                        "violation_type": vtype,
                        "created_at": str(row.created_at),
                        **{k: v for k, v in violation.items() if k not in ("violation_type",)},
                    },
                )
            )
    logger.debug("Agent 08 aggregated %d REBALANCE_VIOLATION alerts", len(alerts))
    return alerts


def _aggregate_agent09(db: Session) -> list[AlertData]:
    """Aggregate PROJECTION_DATA_GAP alerts from Agent 09 income_projections."""
    sql = text(
        """
        SELECT portfolio_id, positions_missing_data, total_projected_annual, computed_at
        FROM platform_shared.income_projections
        WHERE positions_missing_data > 0 AND computed_at >= NOW() - INTERVAL '7 days'
        """
    )
    rows = db.execute(sql).fetchall()

    alerts: list[AlertData] = []
    for row in rows:
        alerts.append(
            AlertData(
                symbol=str(row.portfolio_id),
                source_agent=9,
                alert_type="PROJECTION_DATA_GAP",
                severity="INFO",
                details={
                    "portfolio_id": str(row.portfolio_id),
                    "positions_missing_data": row.positions_missing_data,
                    "total_projected_annual": float(row.total_projected_annual) if row.total_projected_annual is not None else None,
                    "computed_at": str(row.computed_at),
                },
            )
        )
    logger.debug("Agent 09 aggregated %d PROJECTION_DATA_GAP alerts", len(alerts))
    return alerts


def _aggregate_agent10(db: Session) -> list[AlertData]:
    """Pass through unresolved nav_alerts from Agent 10."""
    sql = text(
        """
        SELECT symbol, alert_type, severity, details, created_at
        FROM platform_shared.nav_alerts
        WHERE resolved_at IS NULL
        """
    )
    rows = db.execute(sql).fetchall()

    alerts: list[AlertData] = []
    for row in rows:
        alerts.append(
            AlertData(
                symbol=row.symbol,
                source_agent=10,
                alert_type=row.alert_type,
                severity=row.severity,
                details=row.details if row.details else {},
            )
        )
    logger.debug("Agent 10 aggregated %d nav_alerts", len(alerts))
    return alerts


def aggregate_external_alerts(db: Session) -> list[AlertData]:
    """Aggregate alerts from all external agents (7, 8, 9, 10)."""
    alerts: list[AlertData] = []
    alerts.extend(_aggregate_agent07(db))
    alerts.extend(_aggregate_agent08(db))
    alerts.extend(_aggregate_agent09(db))
    alerts.extend(_aggregate_agent10(db))
    return alerts
