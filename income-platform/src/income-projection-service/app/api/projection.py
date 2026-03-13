"""
Agent 09 — Projection API endpoints.

POST /projection/{portfolio_id}        — run fresh projection
GET  /projection/{portfolio_id}/latest — most recent stored projection
GET  /projection/{portfolio_id}/history — up to 30 historical projections
"""
from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.database import get_db
from app.models import IncomeProjection
from app.projector import portfolio_reader
from app.projector.engine import VALID_YIELD_SOURCES, run_projection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projection")


# ---------------------------------------------------------------------------
# POST /projection/{portfolio_id}
# ---------------------------------------------------------------------------

@router.post("/{portfolio_id}")
async def create_projection(
    portfolio_id: str,
    horizon_months: Annotated[int, Query(ge=1, le=60)] = 12,
    yield_source: Annotated[str, Query()] = "forward",
    _token: dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> dict:
    if yield_source not in VALID_YIELD_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"yield_source must be one of {VALID_YIELD_SOURCES}",
        )

    # Verify portfolio exists
    portfolio = await portfolio_reader.get_portfolio(portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Fetch positions early to give a useful 400 if none are active
    positions = await portfolio_reader.get_positions(portfolio_id)
    if not positions:
        raise HTTPException(
            status_code=400,
            detail="No active positions found for this portfolio",
        )

    result = await run_projection(
        portfolio_id=portfolio_id,
        horizon_months=horizon_months,
        yield_source=yield_source,
    )

    # Persist to income_projections
    try:
        record = IncomeProjection(
            portfolio_id=portfolio_id,
            computed_at=result.computed_at,
            horizon_months=result.horizon_months,
            total_projected_annual=result.total_projected_annual,
            total_projected_monthly_avg=result.total_projected_monthly_avg,
            yield_used=result.yield_source,
            positions_included=result.positions_included,
            positions_missing_data=result.positions_missing_data,
            position_detail=result.positions,
            metadata_={"monthly_cashflow": result.monthly_cashflow},
        )
        db.add(record)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to persist projection to DB: %s", exc)
        db.rollback()

    return {
        "portfolio_id": result.portfolio_id,
        "horizon_months": result.horizon_months,
        "yield_source": result.yield_source,
        "total_projected_annual": result.total_projected_annual,
        "total_projected_monthly_avg": result.total_projected_monthly_avg,
        "monthly_cashflow": result.monthly_cashflow,
        "positions": result.positions,
        "positions_included": result.positions_included,
        "positions_missing_data": result.positions_missing_data,
        "computed_at": result.computed_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /projection/{portfolio_id}/latest
# ---------------------------------------------------------------------------

@router.get("/{portfolio_id}/latest")
def get_latest_projection(
    portfolio_id: str,
    _token: dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> dict:
    record: Optional[IncomeProjection] = (
        db.query(IncomeProjection)
        .filter(IncomeProjection.portfolio_id == portfolio_id)
        .order_by(IncomeProjection.computed_at.desc())
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=404,
            detail="No projection history found for this portfolio",
        )
    return _serialise_record(record)


# ---------------------------------------------------------------------------
# GET /projection/{portfolio_id}/history
# ---------------------------------------------------------------------------

@router.get("/{portfolio_id}/history")
def get_projection_history(
    portfolio_id: str,
    _token: dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> list[dict]:
    records = (
        db.query(IncomeProjection)
        .filter(IncomeProjection.portfolio_id == portfolio_id)
        .order_by(IncomeProjection.computed_at.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id": r.id,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
            "total_projected_annual": float(r.total_projected_annual)
            if r.total_projected_annual is not None
            else None,
            "horizon_months": r.horizon_months,
        }
        for r in records
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialise_record(r: IncomeProjection) -> dict:
    meta = r.metadata_ or {}
    return {
        "id": r.id,
        "portfolio_id": str(r.portfolio_id),
        "computed_at": r.computed_at.isoformat() if r.computed_at else None,
        "horizon_months": r.horizon_months,
        "total_projected_annual": float(r.total_projected_annual)
        if r.total_projected_annual is not None
        else None,
        "total_projected_monthly_avg": float(r.total_projected_monthly_avg)
        if r.total_projected_monthly_avg is not None
        else None,
        "yield_used": r.yield_used,
        "positions_included": r.positions_included,
        "positions_missing_data": r.positions_missing_data,
        "position_detail": r.position_detail,
        "monthly_cashflow": meta.get("monthly_cashflow"),
    }
