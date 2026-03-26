"""
Agent 07 — Opportunity Scanner Service
API Routes: POST /scan, GET /scan/{scan_id}, GET /universe
"""
from __future__ import annotations

import asyncio
import logging
import uuid as uuid_mod
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import ProposalDraft, ScanResult
from app.scanner.engine import run_scan
from app.scanner.market_cache import apply_market_filters, fetch_and_upsert, get_stale_tickers
from app.scanner.portfolio_context import (
    PortfolioPosition,
    annotate_with_portfolio,
    apply_lens,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Request / Response models ───────────────────────────────────────────────

class ScanRequest(BaseModel):
    tickers: List[str] = Field(default=[], description="Ticker symbols to scan")
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
    portfolio_id: Optional[str] = Field(None, description="Portfolio UUID to scan against")
    portfolio_lens: Optional[str] = Field(None, description="gap | replacement | concentration | null")

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
    entry_exit: Optional[dict] = None
    portfolio_context: Optional[dict] = None


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
    elif request.portfolio_id and not tickers:
        rows = db.execute(
            text(
                "SELECT DISTINCT symbol FROM platform_shared.positions "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": request.portfolio_id},
        ).fetchall()
        tickers = [r[0].upper() for r in rows]

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

    # Batch-fetch market data and scores from DB — single query each, no HTTP per ticker
    market_cache: dict[str, dict] = {}
    score_cache: dict[str, dict] = {}
    if tickers:
        cache_rows = db.execute(
            text("""
                SELECT symbol, price, support_level, sma_200,
                       resistance_level, week52_high, dividend_yield, nav_value
                FROM platform_shared.market_data_cache
                WHERE symbol = ANY(:syms)
            """),
            {"syms": tickers},
        ).fetchall()
        for row in cache_rows:
            market_cache[row[0]] = {
                "price": row[1],
                "support_level": row[2],
                "sma_200": row[3],
                "resistance_level": row[4],
                "week_52_high": row[5],
                "dividend_yield": row[6],
                "nav_value": row[7],
            }

        # Fetch latest score per ticker directly from income_scores — avoids N HTTP calls
        score_rows = db.execute(
            text("""
                SELECT DISTINCT ON (ticker)
                    ticker, asset_class, total_score, grade, recommendation,
                    valuation_yield_score, financial_durability_score,
                    technical_entry_score, nav_erosion_penalty, signal_penalty,
                    factor_details, scored_at
                FROM platform_shared.income_scores
                WHERE ticker = ANY(:syms)
                ORDER BY ticker, scored_at DESC
            """),
            {"syms": tickers},
        ).fetchall()
        for row in score_rows:
            fd = row[10] or {}
            score_cache[row[0]] = {
                "ticker": row[0],
                "asset_class": row[1],
                "total_score": row[2],
                "grade": row[3],
                "recommendation": row[4],
                "valuation_yield_score": row[5],
                "financial_durability_score": row[6],
                "technical_entry_score": row[7],
                "nav_erosion_penalty": row[8],
                "signal_penalty": row[9],
                "chowder_number": fd.get("chowder_number"),
                "chowder_signal": fd.get("chowder_signal"),
                "scored_at": str(row[11]),
            }
        logger.info(
            "Batch DB fetch: %d market rows, %d score rows for %d tickers",
            len(market_cache), len(score_cache), len(tickers),
        )

    result = await run_scan(
        tickers=tickers,
        min_score=request.min_score,
        min_yield=request.min_yield,
        asset_classes=request.asset_classes,
        quality_gate_only=request.quality_gate_only,
        market_cache=market_cache,
        score_cache=score_cache,
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
            "entry_exit": it.entry_exit,
            "portfolio_context": it.portfolio_context,
        }
        for it in result.items
    ]

    if request.portfolio_id:
        # Fetch positions for portfolio
        pos_rows = db.execute(
            text("""
                SELECT p.symbol, p.shares, p.asset_type,
                       s.sector, m.price,
                       sc.valuation_yield_score, sc.financial_durability_score
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s ON s.symbol = p.symbol
                LEFT JOIN platform_shared.market_data_cache m ON m.symbol = p.symbol
                LEFT JOIN LATERAL (
                    SELECT valuation_yield_score, financial_durability_score
                    FROM platform_shared.income_scores
                    WHERE ticker = p.symbol
                    ORDER BY created_at DESC LIMIT 1
                ) sc ON true
                WHERE p.portfolio_id = :pid
            """),
            {"pid": request.portfolio_id},
        ).fetchall()

        positions = [
            PortfolioPosition(
                symbol=r[0], shares=float(r[1] or 0), asset_class=r[2] or "",
                sector=r[3] or "", price=float(r[4]) if r[4] else None,
                valuation_yield_score=float(r[5]) if r[5] else None,
                financial_durability_score=float(r[6]) if r[6] else None,
            )
            for r in pos_rows
        ]

        items_json = annotate_with_portfolio(
            items_json, positions,
            class_overweight_pct=settings.class_overweight_pct,
            sector_overweight_pct=settings.sector_overweight_pct,
        )
        if request.portfolio_lens:
            items_json = apply_lens(items_json, lens=request.portfolio_lens)
            for rank, item in enumerate(items_json, start=1):
                item["rank"] = rank

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


class ProposeRequest(BaseModel):
    selected_tickers: list[str] = Field(..., min_length=1)
    target_portfolio_id: str = Field(..., description="UUID of target portfolio")


class ProposeDraftResponse(BaseModel):
    proposal_id: str
    status: str
    tickers: list[dict]
    entry_limits: dict
    target_portfolio_id: str
    created_at: str


@router.post("/scan/{scan_id}/propose", response_model=ProposeDraftResponse)
def post_propose(scan_id: UUID, request: ProposeRequest, db: Session = Depends(get_db)):
    """
    Synchronous endpoint — DB write only, no async scan needed.
    Create a proposal draft from selected scan results.
    Writes to proposal_drafts; Agent 12 will pick it up when available.
    """
    scan_row = db.get(ScanResult, scan_id)
    if scan_row is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found.")

    # Validate portfolio exists
    port_check = db.execute(
        text("SELECT id FROM platform_shared.portfolios WHERE id = :pid"),
        {"pid": request.target_portfolio_id},
    ).fetchone()
    if port_check is None:
        raise HTTPException(status_code=422, detail=f"Portfolio {request.target_portfolio_id} not found.")

    # Build tickers payload from scan items
    selected = {t.upper() for t in request.selected_tickers}
    tickers_payload = []
    entry_limits = {}
    for item in scan_row.items:
        if item["ticker"].upper() not in selected:
            continue
        ee = item.get("entry_exit") or {}
        tickers_payload.append({
            "ticker": item["ticker"],
            "entry_limit": ee.get("entry_limit"),
            "exit_limit": ee.get("exit_limit"),
            "zone_status": ee.get("zone_status"),
            "score": item.get("score"),
            "asset_class": item.get("asset_class"),
        })
        entry_limits[item["ticker"]] = ee.get("entry_limit")

    draft = ProposalDraft(
        scan_id=scan_id,
        target_portfolio_id=uuid_mod.UUID(request.target_portfolio_id),
        tickers=tickers_payload,
        entry_limits=entry_limits,
        status="DRAFT",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    return ProposeDraftResponse(
        proposal_id=str(draft.id),
        status=draft.status,
        tickers=draft.tickers,
        entry_limits=draft.entry_limits,
        target_portfolio_id=str(draft.target_portfolio_id),
        created_at=str(draft.created_at),
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
