"""
Agent 09 — Portfolio Reader
Reads positions and features_historical from platform_shared via asyncpg.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


def _strip_query_params(url: str) -> tuple[str, bool]:
    """Strip sslmode from URL for asyncpg; return (clean_url, ssl_required)."""
    ssl_required = "sslmode=require" in url
    clean = re.sub(r"\?.+$", "", url)
    return clean, ssl_required


async def init_pool() -> None:
    global _pool
    dsn, ssl_required = _strip_query_params(settings.database_url)
    try:
        _pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=5,
            ssl="require" if ssl_required else None,
        )
        logger.info("asyncpg pool initialised")
    except Exception as exc:
        logger.warning("asyncpg pool init failed (non-fatal): %s", exc)
        _pool = None


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_portfolio(portfolio_id: str) -> Optional[dict]:
    """Return portfolio row if it exists and is active."""
    if _pool is None:
        logger.warning("asyncpg pool not available — returning None for portfolio")
        return None
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text, status
            FROM platform_shared.portfolios
            WHERE id = $1
            """,
            portfolio_id,
        )
    return dict(row) if row else None


async def get_positions(portfolio_id: str) -> list[dict]:
    """Return all active positions for portfolio_id."""
    if _pool is None:
        logger.warning("asyncpg pool not available — returning empty positions")
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id::text AS position_id,
                symbol,
                quantity,
                current_value,
                annual_income,
                yield_on_value,
                portfolio_weight_pct,
                acquired_date
            FROM platform_shared.positions
            WHERE portfolio_id = $1 AND UPPER(status) = 'ACTIVE'
            """,
            portfolio_id,
        )
    return [dict(r) for r in rows]


async def get_features(symbols: list[str]) -> dict[str, dict]:
    """
    Return the latest features_historical row per symbol.
    Result is keyed by symbol for O(1) lookup.
    """
    if _pool is None or not symbols:
        return {}
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (symbol)
                symbol,
                yield_trailing_12m,
                yield_forward,
                yield_5yr_avg,
                div_cagr_1y,
                div_cagr_3y,
                div_cagr_5y,
                chowder_number,
                payout_ratio,
                as_of_date
            FROM platform_shared.features_historical
            WHERE symbol = ANY($1::text[])
            ORDER BY symbol, as_of_date DESC
            """,
            symbols,
        )
    return {dict(r)["symbol"]: dict(r) for r in rows}
