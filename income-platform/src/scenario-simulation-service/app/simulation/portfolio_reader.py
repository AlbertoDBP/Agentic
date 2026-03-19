"""
Agent 06 — Scenario Simulation Service
Portfolio Reader: reads positions and asset classifications via asyncpg.
Never raises — returns [] or {} on any error.
"""
import logging
from datetime import date
from typing import Optional

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


def _build_dsn() -> tuple[str, bool]:
    """Strip ?sslmode=* from URL for asyncpg; return (clean_url, ssl_required)."""
    url = settings.database_url
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    ssl_required = "sslmode=require" in url
    if "?" in url:
        url = url.split("?")[0]
    return url, ssl_required


async def init_pool() -> None:
    global _pool
    dsn, ssl_required = _build_dsn()
    _pool = await asyncpg.create_pool(
        dsn,
        ssl="require" if ssl_required else None,
        min_size=2,
        max_size=10,
        statement_cache_size=0,   # required: PgBouncer transaction pool mode
    )


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_positions(
    portfolio_id: str,
    as_of_date: Optional[date] = None,
) -> list:
    """Return open positions for portfolio_id. Returns [] on any error."""
    try:
        async with _pool.acquire() as conn:
            if as_of_date is not None:
                rows = await conn.fetch(
                    """
                    SELECT symbol, quantity, current_value, annual_income,
                           yield_on_value, portfolio_weight_pct, avg_cost_basis
                    FROM platform_shared.positions
                    WHERE portfolio_id = $1
                      AND status = 'ACTIVE'
                      AND acquired_date <= $2
                      AND (closed_date IS NULL OR closed_date > $2)
                    """,
                    portfolio_id,
                    as_of_date,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT symbol, quantity, current_value, annual_income,
                           yield_on_value, portfolio_weight_pct, avg_cost_basis
                    FROM platform_shared.positions
                    WHERE portfolio_id = $1
                      AND status = 'ACTIVE'
                    """,
                    portfolio_id,
                )
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("get_positions error for portfolio %s: %s", portfolio_id, exc)
        return []


async def get_asset_classes(symbols: list) -> dict:
    """Return {symbol: asset_class} for given symbols. Defaults unknown to DIVIDEND_STOCK."""
    if not symbols:
        return {}
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ticker, asset_class
                FROM platform_shared.asset_classifications
                WHERE ticker = ANY($1)
                """,
                symbols,
            )
            result = {r["ticker"]: r["asset_class"] for r in rows}
            # Default missing symbols
            for s in symbols:
                if s not in result:
                    result[s] = "DIVIDEND_STOCK"
            return result
    except Exception as exc:
        logger.error("get_asset_classes error for symbols %s: %s", symbols, exc)
        return {s: "DIVIDEND_STOCK" for s in symbols}
