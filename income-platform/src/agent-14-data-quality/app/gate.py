# src/agent-14-data-quality/app/gate.py
"""Gate evaluator — determines if scoring is allowed for a portfolio."""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    portfolio_id: str
    status: str          # 'passed' | 'blocked' | 'pending'
    blocking_issue_count: int
    gate_passed_at: Optional[str] = None


def evaluate_gate(db: Session, portfolio_id: str) -> GateResult:
    """
    Evaluate the data quality gate for a portfolio.
    Blocks if any active position has a 'critical' open issue.
    """
    # Get active symbols in portfolio
    symbols_rows = db.execute(
        text("""
            SELECT DISTINCT symbol FROM platform_shared.positions
            WHERE portfolio_id = :pid AND quantity > 0
        """),
        {"pid": portfolio_id},
    ).fetchall()

    symbols = [r.symbol for r in symbols_rows]
    if not symbols:
        logger.debug(f"Portfolio {portfolio_id} has no active positions — gate passes vacuously")
        _upsert_gate(db, portfolio_id, "passed", 0)
        return GateResult(portfolio_id=portfolio_id, status="passed", blocking_issue_count=0)

    # Count critical open issues for those symbols
    critical_count = db.execute(
        text("""
            SELECT COUNT(*)
            FROM platform_shared.data_quality_issues i
            LEFT JOIN platform_shared.data_quality_exemptions e
                   ON e.symbol = i.symbol AND e.field_name = i.field_name
            WHERE i.symbol = ANY(:syms)
              AND i.severity = 'critical'
              AND i.status NOT IN ('resolved', 'unresolvable')
              AND e.id IS NULL
        """),
        {"syms": symbols},
    ).scalar() or 0

    status = "blocked" if critical_count > 0 else "passed"
    _upsert_gate(db, portfolio_id, status, critical_count)
    db.commit()

    logger.info(f"Gate {portfolio_id}: {status} ({critical_count} critical issues)")
    return GateResult(
        portfolio_id=portfolio_id,
        status=status,
        blocking_issue_count=critical_count,
    )


def _upsert_gate(db: Session, portfolio_id: str, status: str, blocking_count: int):
    db.execute(
        text("""
            INSERT INTO platform_shared.data_quality_gate
                (portfolio_id, gate_date, status, blocking_issue_count,
                 gate_passed_at)
            VALUES (
                :pid, CURRENT_DATE, :status, :cnt,
                CASE WHEN :status = 'passed' THEN NOW() ELSE NULL END
            )
            ON CONFLICT (portfolio_id, gate_date) DO UPDATE SET
                status = :status,
                blocking_issue_count = :cnt,
                gate_passed_at = CASE WHEN :status = 'passed' THEN NOW() ELSE NULL END
        """),
        {"pid": portfolio_id, "status": status, "cnt": blocking_count},
    )


def record_scoring_triggered(db: Session, portfolio_id: str):
    db.execute(
        text("""
            UPDATE platform_shared.data_quality_gate
            SET scoring_triggered_at = NOW()
            WHERE portfolio_id = :pid AND gate_date = CURRENT_DATE
        """),
        {"pid": portfolio_id},
    )
    db.commit()


def record_scoring_completed(db: Session, portfolio_id: str):
    db.execute(
        text("""
            UPDATE platform_shared.data_quality_gate
            SET scoring_completed_at = NOW()
            WHERE portfolio_id = :pid AND gate_date = CURRENT_DATE
        """),
        {"pid": portfolio_id},
    )
    # Also update data_refresh_log
    db.execute(
        text("""
            INSERT INTO platform_shared.data_refresh_log (portfolio_id, scores_recalculated_at, updated_at)
            VALUES (:pid, NOW(), NOW())
            ON CONFLICT (portfolio_id) DO UPDATE SET
                scores_recalculated_at = NOW(), updated_at = NOW()
        """),
        {"pid": portfolio_id},
    )
    db.commit()
