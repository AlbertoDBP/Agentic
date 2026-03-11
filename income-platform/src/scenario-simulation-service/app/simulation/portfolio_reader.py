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


def _build_dsn() -> str:
    """Strip ?sslmode=require from URL; ssl= is passed via connect kwarg."""
    url = settings.database_url
    # Replace postgresql+psycopg2:// with postgresql:// for asyncpg
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in url:
        url = url.split("?")[0]
    return url


async def get_positions(
    portfolio_id: str,
    as_of_date: Optional[date] = None,
) -> list:
    """Return open positions for portfolio_id. Returns [] on any error."""
    try:
        conn = await asyncpg.connect(_build_dsn(), ssl="require")
        try:
            if as_of_date is not None:
                rows = await conn.fetch(
                    """
                    SELECT symbol, quantity, current_value, annual_income,
                           yield_on_value, portfolio_weight_pct, avg_cost_basis
                    FROM platform_shared.positions
                    WHERE portfolio_id = $1
                      AND status = 'OPEN'
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
                      AND status = 'OPEN'
                    """,
                    portfolio_id,
                )
            return [dict(r) for r in rows]
        finally:
            await conn.close()
    except Exception as exc:
        logger.error("get_positions error for portfolio %s: %s", portfolio_id, exc)
        return []


async def get_asset_classes(symbols: list) -> dict:
    """Return {symbol: asset_class} for given symbols. Defaults unknown to DIVIDEND_STOCK."""
    if not symbols:
        return {}
    try:
        conn = await asyncpg.connect(_build_dsn(), ssl="require")
        try:
            rows = await conn.fetch(
                """
                SELECT symbol, asset_class
                FROM platform_shared.asset_classifications
                WHERE symbol = ANY($1)
                """,
                symbols,
            )
            result = {r["symbol"]: r["asset_class"] for r in rows}
            # Default missing symbols
            for s in symbols:
                if s not in result:
                    result[s] = "DIVIDEND_STOCK"
            return result
        finally:
            await conn.close()
    except Exception as exc:
        logger.error("get_asset_classes error for symbols %s: %s", symbols, exc)
        return {s: "DIVIDEND_STOCK" for s in symbols}
