"""
Agent 07 — Opportunity Scanner Service
Cache API: POST /cache/refresh — batch-update market_data_cache for tracked tickers.
Called by scheduler daily, or on-demand.
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.scanner.market_cache import fetch_and_upsert, get_stale_tickers, get_tracked_tickers

logger = logging.getLogger(__name__)
router = APIRouter()


class CacheRefreshResponse(BaseModel):
    upserted: int
    already_fresh: int
    total_tracked: int
    snapshot_date: str


@router.post("/cache/refresh", response_model=CacheRefreshResponse)
async def refresh_cache(
    force: bool = Query(False, description="Force refresh even if data is fresh today"),
    db: Session = Depends(get_db),
):
    """
    Batch-refresh market_data_cache for all tracked tickers.
    Fetches only stale/missing entries unless force=true.
    Scheduler calls this daily at 06:30 ET.
    """
    # Also include all portfolio symbols
    portfolio_rows = db.execute(
        text(
            "SELECT DISTINCT symbol FROM platform_shared.positions "
            "WHERE status = 'ACTIVE'"
        )
    ).fetchall()
    portfolio_symbols = [r[0] for r in portfolio_rows]

    tracked = get_tracked_tickers(db)
    all_symbols = list({*tracked, *portfolio_symbols})

    if force:
        stale = all_symbols
        fresh_count = 0
    else:
        fresh, stale = get_stale_tickers(all_symbols, db)
        fresh_count = len(fresh)

    upserted = await fetch_and_upsert(stale, db, track_reason="daily_refresh")

    return CacheRefreshResponse(
        upserted=upserted,
        already_fresh=fresh_count,
        total_tracked=len(all_symbols),
        snapshot_date=date.today().isoformat(),
    )
