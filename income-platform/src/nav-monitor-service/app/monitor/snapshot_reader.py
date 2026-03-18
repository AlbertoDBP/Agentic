"""
Agent 10 — NAV Erosion Monitor
Snapshot reader: asyncpg reads from nav_snapshots and income_scores.

Both functions degrade gracefully when the pool is unavailable (return empty).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level pool reference — set by main.py lifespan
_pool = None


async def init_pool() -> None:
    """Initialise the asyncpg connection pool."""
    global _pool
    import re
    import asyncpg
    from app.config import settings

    raw_url = settings.database_url
    ssl_required = "sslmode=require" in raw_url
    db_url = re.sub(r"\?.+$", "", raw_url)

    try:
        _pool = await asyncpg.create_pool(
            db_url,
            min_size=1,
            max_size=5,
            ssl="require" if ssl_required else None,
        )
        logger.info("asyncpg pool initialised")
    except Exception as exc:
        logger.warning("asyncpg pool init failed (non-fatal): %s", exc)
        _pool = None


async def close_pool() -> None:
    """Close the asyncpg connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_recent_snapshots(lookback_days: int = 90) -> list[dict]:
    """Return the latest nav_snapshot per symbol within lookback_days.

    Returns an empty list when no pool is available (graceful degradation).
    """
    if _pool is None:
        logger.warning("asyncpg pool not available — returning empty snapshots")
        return []

    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (symbol)
                symbol,
                snapshot_date,
                nav,
                market_price,
                premium_discount,
                distribution_rate,
                erosion_rate_30d,
                erosion_rate_90d,
                erosion_rate_1y,
                erosion_flag,
                source
            FROM platform_shared.nav_snapshots
            WHERE snapshot_date >= CURRENT_DATE - $1::int * INTERVAL '1 day'
            ORDER BY symbol, snapshot_date DESC
            """,
            lookback_days,
        )
    return [dict(r) for r in rows]


async def get_income_scores(symbols: Optional[list[str]] = None) -> dict[str, dict]:
    """Return the latest income_score per ticker (optionally filtered to symbols list).

    Returns an empty dict when no pool is available (graceful degradation).
    """
    if _pool is None:
        logger.warning("asyncpg pool not available — returning empty income scores")
        return {}

    async with _pool.acquire() as conn:
        if symbols:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (ticker)
                    ticker,
                    total_score,
                    nav_erosion_penalty,
                    nav_erosion_details,
                    scored_at
                FROM platform_shared.income_scores
                WHERE ticker = ANY($1::text[])
                ORDER BY ticker, scored_at DESC
                """,
                symbols,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (ticker)
                    ticker,
                    total_score,
                    nav_erosion_penalty,
                    nav_erosion_details,
                    scored_at
                FROM platform_shared.income_scores
                ORDER BY ticker, scored_at DESC
                """
            )

    return {r["ticker"]: dict(r) for r in rows}
