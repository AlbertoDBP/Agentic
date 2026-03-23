"""
Agent 07 — Opportunity Scanner Service
API Routes: POST /scan, GET /scan/{scan_id}, GET /universe
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import ScanResult
from app.scanner.engine import run_scan
from app.scanner.market_cache import apply_market_filters, fetch_and_upsert, get_stale_tickers

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Request / Response models ───────────────────────────────────────────────

class ScanRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1, description="Ticker symbols to scan")
    min_score: float = Field(0.0, ge=0.0, le=100.0, description="Minimum total score (0–100)")
    asset_classes: Optional[List[str]] = Field(None, description="Restrict to these asset classes")
    quality_gate_only: bool = Field(False, description="If true, exclude tickers with score < 70")

    # Group 2 — market data filters (applied against market_data_cache)
    min_yield: float = Field(0.0, ge=0.0, description="Minimum annual dividend yield (%)")
    max_payout_ratio: Optional[float] = Field(None, ge=0.0, le=200.0, description="Max payout ratio (%)")
    min_volume: Optional[int] = Field(None, ge=0, description="Min average daily volume (shares)")
    min_market_cap_m: Optional[float] = Field(None, ge=0.0, description="Min market cap ($M)")
    max_market_cap_m: Optional[float] = Field(None, ge=0.0, description="Max market cap ($M)")
    min_price: Optional[float] = Field(None, ge=0.0, description="Min price ($)")
    max_price: Optional[float] = Field(None, ge=0.0, description="Max price ($)")
    max_pe: Optional[float] = Field(None, ge=0.0, description="Max P/E ratio")
    min_nav_discount_pct: Optional[float] = Field(None, description="Min NAV discount (negative = discount, e.g. -5 means ≥5% discount)")
    use_universe: bool = Field(False, description="If true, scan full active universe instead of supplied tickers")

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
    # ── Resolve ticker universe ──────────────────────────────────────────
    tickers = [t.upper() for t in request.tickers]

    if request.use_universe:
        rows = db.execute(
            text(
                "SELECT symbol FROM platform_shared.securities "
                "WHERE is_active = TRUE ORDER BY symbol"
            )
        ).fetchall()
        tickers = [r[0] for r in rows]

    if not tickers:
        raise HTTPException(status_code=422, detail="No tickers to scan.")

    if len(tickers) > settings.max_tickers_per_scan:
        raise HTTPException(
            status_code=422,
            detail=f"Too many tickers. Max {settings.max_tickers_per_scan} per scan.",
        )

    # ── Ensure market cache is fresh (non-blocking background refresh) ───
    # We fire the refresh as a background task so the scan is never gated on
    # the ~38 s cold-start cost of fetching 9 FMP endpoints × N tickers.
    # The scan proceeds immediately with whatever is already in cache; the
    # updated rows will be available for the next scan or filter re-run.
    _fresh, stale = get_stale_tickers(tickers, db)
    if stale:
        logger.info("Market cache stale for %d tickers — refreshing in background", len(stale))

        async def _bg_refresh(syms: list[str]) -> None:
            bg_db = SessionLocal()
            try:
                await fetch_and_upsert(syms, bg_db, track_reason="scan-bg")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Background market cache refresh failed: %s", exc)
            finally:
                bg_db.close()

        asyncio.create_task(_bg_refresh(list(stale)))

    # ── SQL pre-filter (Group 2) ─────────────────────────────────────────
    any_market_filter = any([
        request.min_yield > 0,
        request.max_payout_ratio is not None,
        request.min_volume is not None,
        request.min_market_cap_m is not None,
        request.max_market_cap_m is not None,
        request.min_price is not None,
        request.max_price is not None,
        request.max_pe is not None,
        request.min_nav_discount_pct is not None,
    ])
    if any_market_filter:
        tickers = apply_market_filters(
            tickers=tickers,
            db=db,
            min_yield=request.min_yield,
            max_payout_ratio=request.max_payout_ratio,
            min_volume=request.min_volume,
            min_market_cap_m=request.min_market_cap_m,
            max_market_cap_m=request.max_market_cap_m,
            min_price=request.min_price,
            max_price=request.max_price,
            max_pe=request.max_pe,
            min_nav_discount_pct=request.min_nav_discount_pct,
        )
    if not tickers:
        # Return empty result immediately — no tickers passed market filters
        return ScanResponse(
            scan_id="00000000-0000-0000-0000-000000000000",
            total_scanned=0,
            total_passed=0,
            total_vetoed=0,
            items=[],
            filters_applied={},
            created_at=str(__import__("datetime").datetime.utcnow()),
        )

    result = await run_scan(
        tickers=tickers,
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
        "max_payout_ratio": request.max_payout_ratio,
        "min_volume": request.min_volume,
        "min_market_cap_m": request.min_market_cap_m,
        "max_market_cap_m": request.max_market_cap_m,
        "min_price": request.min_price,
        "max_price": request.max_price,
        "max_pe": request.max_pe,
        "min_nav_discount_pct": request.min_nav_discount_pct,
        "use_universe": request.use_universe,
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


@router.get("/quote/{symbol}")
def get_quote(symbol: str, db: Session = Depends(get_db)):
    """
    Return name, price, and dividend_yield for a single symbol from DB cache.
    Joins market_data_cache (price, yield) with securities (name). No external API call.
    """
    sym = symbol.upper()
    row = db.execute(
        text("""
            SELECT
                COALESCE(s.name, m.symbol)  AS name,
                m.price,
                m.dividend_yield
            FROM platform_shared.market_data_cache m
            LEFT JOIN platform_shared.securities s ON s.symbol = m.symbol
            WHERE m.symbol = :sym
            LIMIT 1
        """),
        {"sym": sym},
    ).fetchone()
    if row is None:
        # Symbol not in cache — return nulls so caller can fall back gracefully
        return {"symbol": sym, "name": sym, "price": None, "dividend_yield": None}
    return {
        "symbol": sym,
        "name": row[0] or sym,
        "price": row[1],
        "dividend_yield": row[2],
    }


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
