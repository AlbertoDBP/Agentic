"""
Agent 05 — Tax Optimization Service
Database layer — READ-ONLY access to shared platform DB.
No new tables are created; existing user_preferences table is queried.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def _build_url(raw_url: str) -> str:
    url = raw_url
    # Normalise to a plain postgresql:// base, then force asyncpg driver
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "?" in url:
        url = url.split("?")[0]
    return url


# NullPool: create a fresh connection per session — avoids pgbouncer
# transaction-mode incompatibility with asyncpg named prepared statements.
# (statement_cache_size=0 disables the cache but asyncpg still uses named
# prepared statements, which pgbouncer can route to a different backend
# between Parse and Bind, causing "prepared statement does not exist".)
engine = create_async_engine(
    _build_url(settings.database_url),
    echo=settings.db_echo,
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a read-only async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for DB sessions."""
    async with get_db_session() as session:
        yield session


async def check_db_health() -> bool:
    """Return True if the DB is reachable."""
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)
        return False


async def get_portfolio_holdings(portfolio_id: str) -> list:
    """
    Fetch all active positions from a portfolio and return as a list of dicts
    suitable for constructing HoldingInput objects.
    Returns [] on error or no positions found.
    """
    try:
        async with get_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT
                        p.symbol,
                        COALESCE(s.asset_type, 'UNKNOWN')                                AS asset_type,
                        LOWER(COALESCE(s.name, ''))                                       AS security_name,
                        COALESCE(p.current_value, 0)                                      AS current_value,
                        CASE
                            WHEN COALESCE(p.current_value, 0) > 0
                             AND COALESCE(p.annual_income,  0) > 0
                            THEN p.annual_income / p.current_value
                            ELSE 0
                        END                                                               AS annual_yield,
                        COALESCE(a.account_type, 'TAXABLE')                               AS account_type,
                        mdc.expense_ratio
                    FROM platform_shared.positions p
                    LEFT JOIN platform_shared.securities           s   ON s.symbol  = p.symbol
                    LEFT JOIN platform_shared.portfolios           po  ON po.id     = p.portfolio_id
                    LEFT JOIN platform_shared.accounts             a   ON a.id      = po.account_id
                    LEFT JOIN platform_shared.market_data_cache    mdc ON mdc.symbol = p.symbol
                    WHERE p.portfolio_id = :pid
                      AND p.status       = 'ACTIVE'
                      AND COALESCE(p.current_value, 0) > 0
                    ORDER BY p.current_value DESC
                """),
                {"pid": portfolio_id},
            )
            rows = result.fetchall()
            holdings = []
            for r in rows:
                row = dict(r._mapping)
                row["expense_ratio"] = (
                    float(row["expense_ratio"]) if row.get("expense_ratio") is not None else None
                )
                holdings.append(row)
            return holdings
    except Exception as exc:
        logger.warning("get_portfolio_holdings error for %s: %s", portfolio_id, exc)
        return []


async def get_user_tax_preferences(
    session: AsyncSession,
    user_id: str | None = None,
) -> dict:
    """
    Read tax-relevant preferences from the shared user_preferences table.
    Returns empty dict when user_id is None or row not found.
    """
    if not user_id:
        return {}
    try:
        result = await session.execute(
            text(
                "SELECT preferences FROM user_preferences "
                "WHERE user_id = :uid LIMIT 1"
            ),
            {"uid": user_id},
        )
        row = result.fetchone()
        if row and row[0]:
            prefs: dict = row[0]
            # Extract only tax-relevant keys
            return {
                k: prefs[k]
                for k in (
                    "filing_status",
                    "state_code",
                    "annual_income",
                    "account_types",
                )
                if k in prefs
            }
    except Exception as exc:
        logger.warning("Could not fetch user_preferences: %s", exc)
    return {}
