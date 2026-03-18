"""
Admin Panel — JSON API for the frontend dashboard.

Routes:
  GET /api/dashboard  → aggregated metrics, portfolios, allocation, quality, income-by-month
"""
from __future__ import annotations

import calendar
import logging
from datetime import date

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from sqlalchemy import text

from app.database import engine

logger = logging.getLogger("admin.api_dashboard")
router = APIRouter(prefix="/api")


def _db():
    if not engine:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return engine


@router.get("/dashboard")
def get_dashboard():
    """Return all data needed by the frontend dashboard in a single call."""
    try:
        with _db().connect() as conn:

            # ── 1. Aggregate metrics ──────────────────────────────────────────
            row = conn.execute(text("""
                SELECT
                    COALESCE(SUM(po.total_value), 0)   AS total_value,
                    COALESCE(SUM(p.annual_income), 0)  AS annual_income,
                    COUNT(p.id)                         AS positions_count
                FROM platform_shared.portfolios po
                LEFT JOIN platform_shared.positions p
                       ON p.portfolio_id = po.id AND p.status = 'ACTIVE'
                WHERE po.status = 'ACTIVE'
            """)).fetchone()
            total_value     = float(row.total_value)     if row else 0.0
            annual_income   = float(row.annual_income)   if row else 0.0
            positions_count = int(row.positions_count)   if row else 0
            blended_yield   = round((annual_income / total_value) * 100, 2) if total_value > 0 else 0.0

            # Active alerts (unified_alerts not RESOLVED)
            alert_count = conn.execute(text("""
                SELECT COUNT(*) FROM platform_shared.unified_alerts
                WHERE status <> 'RESOLVED'
            """)).scalar()
            active_alerts = int(alert_count or 0)

            # Pending proposals
            proposal_count = conn.execute(text("""
                SELECT COUNT(*) FROM platform_shared.proposals
                WHERE status NOT IN ('rejected', 'executed_aligned', 'executed_override')
            """)).scalar()
            pending_proposals = int(proposal_count or 0)

            # ── 2. Per-portfolio summaries ────────────────────────────────────
            p_rows = conn.execute(text("""
                SELECT
                    po.id,
                    po.portfolio_name                   AS name,
                    COALESCE(a.account_type, 'Unknown') AS account_type,
                    COALESCE(a.broker, '')              AS broker,
                    COALESCE(po.total_value, 0)         AS total_value,
                    COUNT(p.id)                         AS positions_count,
                    COALESCE(SUM(p.annual_income), 0)   AS annual_income,
                    COALESCE(SUM(
                        COALESCE(p.total_cost_basis, p.avg_cost_basis * p.quantity, 0)
                    ), 0)                               AS cost_basis
                FROM platform_shared.portfolios po
                LEFT JOIN platform_shared.accounts a  ON a.id = po.account_id
                LEFT JOIN platform_shared.positions p
                       ON p.portfolio_id = po.id AND p.status = 'ACTIVE'
                WHERE po.status = 'ACTIVE'
                GROUP BY po.id, po.portfolio_name, a.account_type, a.broker, po.total_value
                ORDER BY po.total_value DESC NULLS LAST
            """)).fetchall()

            portfolios = []
            for r in p_rows:
                tv  = float(r.total_value)
                inc = float(r.annual_income)
                cb  = float(r.cost_basis)
                portfolios.append({
                    "id":              str(r.id),
                    "name":            r.name,
                    "account_type":    r.account_type,
                    "broker":          r.broker,
                    "positions_count": int(r.positions_count),
                    "total_value":     tv,
                    "cost_basis":      cb,
                    "annual_income":   inc,
                    "blended_yield":   round((inc / tv) * 100, 2) if tv > 0 else 0.0,
                    "gain_pct":        round(((tv - cb) / cb) * 100, 2) if cb > 0 else 0.0,
                })

            # ── 3. Asset allocation ───────────────────────────────────────────
            a_rows = conn.execute(text("""
                SELECT
                    COALESCE(s.asset_type, 'Unknown')   AS name,
                    COALESCE(SUM(p.current_value), 0)   AS value
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s ON s.symbol = p.symbol
                WHERE p.status = 'ACTIVE'
                GROUP BY s.asset_type
                ORDER BY value DESC
            """)).fetchall()

            alloc_total = sum(float(r.value) for r in a_rows)
            allocation = [
                {
                    "name":       r.name,
                    "value":      float(r.value),
                    "percentage": round((float(r.value) / alloc_total) * 100, 1) if alloc_total > 0 else 0.0,
                }
                for r in a_rows
            ]

            # ── 4. Income quality distribution ───────────────────────────────
            q_row = conn.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE COALESCE(sc.total_score, 0) >= 80)  AS high,
                    COUNT(*) FILTER (WHERE COALESCE(sc.total_score, 0) >= 50
                                      AND COALESCE(sc.total_score, 0) <  80)  AS medium,
                    COUNT(*) FILTER (WHERE COALESCE(sc.total_score, 0) < 50)  AS low
                FROM platform_shared.positions p
                LEFT JOIN LATERAL (
                    SELECT total_score
                    FROM platform_shared.income_scores
                    WHERE ticker = p.symbol
                    ORDER BY scored_at DESC
                    LIMIT 1
                ) sc ON TRUE
                WHERE p.status = 'ACTIVE'
            """)).fetchone()
            quality = {
                "high":   int(q_row.high   or 0) if q_row else 0,
                "medium": int(q_row.medium or 0) if q_row else 0,
                "low":    int(q_row.low    or 0) if q_row else 0,
            }

            # ── 5. Income by month ────────────────────────────────────────────
            proj_row = conn.execute(text("""
                SELECT metadata
                FROM platform_shared.income_projections
                ORDER BY computed_at DESC
                LIMIT 1
            """)).fetchone()
            income_by_month = _build_monthly_income(proj_row, annual_income)

        return JSONResponse(content={
            "metrics": {
                "total_value":       total_value,
                "annual_income":     annual_income,
                "blended_yield":     blended_yield,
                "active_alerts":     active_alerts,
                "positions_count":   positions_count,
                "pending_proposals": pending_proposals,
            },
            "portfolios":      portfolios,
            "allocation":      allocation,
            "quality":         quality,
            "income_by_month": income_by_month,
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_dashboard error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


def _build_monthly_income(proj_row, annual_income: float) -> list[dict]:
    """
    Build a 12-month income list with calendar labels starting from this month.
    Uses stored projection cashflow if available, otherwise flat monthly_avg.
    """
    monthly_avg = round(annual_income / 12.0, 2) if annual_income > 0 else 0.0

    cashflow: list[dict] = []
    if proj_row and proj_row[0]:
        meta = proj_row[0]
        if isinstance(meta, dict):
            cashflow = meta.get("monthly_cashflow", [])

    today = date.today()
    result = []
    for i in range(12):
        month_num = (today.month - 1 + i) % 12 + 1
        label = calendar.month_abbr[month_num]
        if cashflow and i < len(cashflow):
            projected = float(cashflow[i].get("projected_income", monthly_avg))
        else:
            projected = monthly_avg
        result.append({"month": label, "projected": projected})

    return result
