"""
Agent 07 — Opportunity Scanner Service
API Routes: POST /scan, GET /scan/{scan_id}, GET /universe
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ScanResult
from app.scanner.engine import run_scan

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Request / Response models ───────────────────────────────────────────────

class ScanRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1, description="Ticker symbols to scan")
    min_score: float = Field(0.0, ge=0.0, le=100.0, description="Minimum total score (0–100)")
    min_yield: float = Field(0.0, ge=0.0, description="Minimum annual yield (informational filter)")
    asset_classes: Optional[List[str]] = Field(None, description="Restrict to these asset classes")
    quality_gate_only: bool = Field(False, description="If true, exclude tickers with score < 70")

    model_config = {"json_schema_extra": {
        "example": {
            "tickers": ["O", "JEPI", "MAIN", "ARCC", "PFF"],
            "min_score": 60.0,
            "quality_gate_only": True,
        }
    }}


class ScanItemResponse(BaseModel):
    ticker: str
    score: float
    grade: str
    recommendation: str
    asset_class: str
    chowder_signal: Optional[str]
    chowder_number: Optional[float]
    signal_penalty: float
    rank: int
    passed_quality_gate: bool
    veto_flag: bool
    score_details: dict[str, Any]


class ScanResponse(BaseModel):
    scan_id: str
    total_scanned: int
    total_passed: int
    total_vetoed: int
    items: List[ScanItemResponse]
    filters_applied: dict[str, Any]
    created_at: str


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/scan", response_model=ScanResponse)
async def post_scan(request: ScanRequest, db: Session = Depends(get_db)):
    """
    Score a list of tickers via Agent 03, apply filters, and return a ranked
    candidate list. Results are persisted and retrievable via GET /scan/{scan_id}.

    VETO gate: tickers with score < 70 are flagged (veto_flag=True) and excluded
    from results when quality_gate_only=True. When quality_gate_only=False they
    appear in results but are clearly flagged.
    """
    if len(request.tickers) > settings.max_tickers_per_scan:
        raise HTTPException(
            status_code=422,
            detail=f"Too many tickers. Max {settings.max_tickers_per_scan} per scan.",
        )

    result = await run_scan(
        tickers=request.tickers,
        min_score=request.min_score,
        min_yield=request.min_yield,
        asset_classes=request.asset_classes,
        quality_gate_only=request.quality_gate_only,
    )

    filters_applied = {
        "min_score": request.min_score,
        "min_yield": request.min_yield,
        "asset_classes": request.asset_classes,
        "quality_gate_only": request.quality_gate_only,
        "quality_gate_threshold": settings.quality_gate_threshold,
    }

    items_json = [
        {
            "ticker": it.ticker,
            "score": it.score,
            "grade": it.grade,
            "recommendation": it.recommendation,
            "asset_class": it.asset_class,
            "chowder_signal": it.chowder_signal,
            "chowder_number": it.chowder_number,
            "signal_penalty": it.signal_penalty,
            "rank": it.rank,
            "passed_quality_gate": it.passed_quality_gate,
            "veto_flag": it.veto_flag,
            "score_details": it.score_details,
        }
        for it in result.items
    ]

    orm_row = ScanResult(
        total_scanned=result.total_scanned,
        total_passed=result.total_passed,
        total_vetoed=result.total_vetoed,
        filters=filters_applied,
        items=items_json,
        status="COMPLETE",
    )
    db.add(orm_row)
    db.commit()
    db.refresh(orm_row)

    return ScanResponse(
        scan_id=str(orm_row.id),
        total_scanned=result.total_scanned,
        total_passed=result.total_passed,
        total_vetoed=result.total_vetoed,
        items=[ScanItemResponse(**it) for it in items_json],
        filters_applied=filters_applied,
        created_at=str(orm_row.created_at),
    )


@router.get("/scan/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: UUID, db: Session = Depends(get_db)):
    """Retrieve a previously run scan by its ID."""
    row = db.get(ScanResult, scan_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found.")
    return ScanResponse(
        scan_id=str(row.id),
        total_scanned=row.total_scanned,
        total_passed=row.total_passed,
        total_vetoed=row.total_vetoed,
        items=[ScanItemResponse(**it) for it in row.items],
        filters_applied=row.filters,
        created_at=str(row.created_at),
    )


@router.get("/universe")
def get_universe(
    asset_type: Optional[str] = Query(None, description="Filter by asset_type"),
    active_only: bool = Query(True, description="Only return active securities"),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """
    List the tracked securities universe from platform_shared.securities.
    Returns symbol, name, asset_type, sector, exchange, is_active.
    """
    filters = ["1=1"]
    params: dict = {"limit": limit}

    if active_only:
        filters.append("is_active = TRUE")
    if asset_type:
        filters.append("asset_type = :asset_type")
        params["asset_type"] = asset_type

    where = " AND ".join(filters)
    sql = text(
        f"SELECT symbol, name, asset_type, sector, exchange, is_active "
        f"FROM platform_shared.securities WHERE {where} "
        f"ORDER BY symbol LIMIT :limit"
    )
    rows = db.execute(sql, params).fetchall()
    return {
        "total": len(rows),
        "securities": [
            {
                "symbol": r[0],
                "name": r[1],
                "asset_type": r[2],
                "sector": r[3],
                "exchange": r[4],
                "is_active": r[5],
            }
            for r in rows
        ],
    }
