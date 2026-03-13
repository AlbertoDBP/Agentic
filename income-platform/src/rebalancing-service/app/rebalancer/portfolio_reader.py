"""
Agent 08 — Portfolio Reader
Reads positions, constraints, and income metrics from platform_shared via asyncpg.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


def _strip_query_params(url: str) -> str:
    """Remove ?sslmode=require from DB URL for asyncpg."""
    return re.sub(r"\?.+$", "", url)


async def init_pool() -> None:
    global _pool
    try:
        _pool = await asyncpg.create_pool(
            _strip_query_params(settings.database_url),
            min_size=1,
            max_size=5,
            ssl="require",
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


async def get_positions(portfolio_id: str) -> list[dict]:
    """Return active positions for portfolio_id."""
    if _pool is None:
        logger.warning("asyncpg pool not available — returning empty positions")
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT symbol, quantity, current_value, annual_income,
                   yield_on_value, portfolio_weight_pct, avg_cost_basis,
                   acquired_date, id::text as position_id
            FROM platform_shared.positions
            WHERE portfolio_id = $1 AND status = 'ACTIVE'
            """,
            portfolio_id,
        )
    return [dict(r) for r in rows]


async def get_portfolio(portfolio_id: str) -> Optional[dict]:
    """Return portfolio-level metadata."""
    if _pool is None:
        return None
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text, portfolio_name, total_value, cash_balance,
                   capital_to_deploy, last_rebalanced_at
            FROM platform_shared.portfolios
            WHERE id = $1 AND status = 'ACTIVE'
            """,
            portfolio_id,
        )
    return dict(row) if row else None


async def get_constraints(portfolio_id: str) -> Optional[dict]:
    """Return portfolio constraints for rebalancing rules."""
    if _pool is None:
        return None
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT max_position_pct, min_position_pct, max_sector_pct,
                   max_asset_class_pct, min_income_score_grade, min_chowder_signal,
                   target_income_annual, target_yield_pct,
                   exclude_junk_bond_risk, exclude_nav_erosion_risk,
                   sector_limits, asset_class_limits
            FROM platform_shared.portfolio_constraints
            WHERE portfolio_id = $1
            """,
            portfolio_id,
        )
    return dict(row) if row else None


async def get_latest_income_metrics(portfolio_id: str) -> Optional[dict]:
    """Return most recent portfolio income metrics row."""
    if _pool is None:
        return None
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT actual_income_annual, target_income_annual, income_gap_annual,
                   actual_yield_pct, as_of_date
            FROM platform_shared.portfolio_income_metrics
            WHERE portfolio_id = $1
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            portfolio_id,
        )
    return dict(row) if row else None
