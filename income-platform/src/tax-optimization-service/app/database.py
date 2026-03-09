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

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Convert sync postgres URL to async
# asyncpg does not support ?sslmode=require — strip it and pass ssl via connect_args
_db_url = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace("?sslmode=require", "").replace("&sslmode=require", "")

_connect_args = {"ssl": "require"} if "sslmode=require" in settings.database_url else {}

engine = create_async_engine(
    _db_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    echo=settings.db_echo,
    future=True,
    connect_args=_connect_args,
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
