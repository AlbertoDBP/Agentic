"""PostgreSQL Database Manager"""
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async PostgreSQL connection manager with ORM session factory."""

    def __init__(self, database_url: str):
        # Ensure asyncpg driver is used
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        # asyncpg doesn't understand ?sslmode=require — strip it and pass ssl
        # via connect_args instead (handled in connect())
        self._ssl_required = "sslmode=require" in database_url
        database_url = database_url.replace("?sslmode=require", "").replace(
            "&sslmode=require", ""
        )
        self.database_url = database_url
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None

    async def connect(self):
        """Initialize engine, verify connectivity and table existence, build session factory."""
        try:
            connect_args = {"timeout": 10}
            if self._ssl_required:
                connect_args["ssl"] = "require"
            self.engine = create_async_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                connect_args=connect_args,
            )

            # Verify basic connectivity
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

            # Verify the market_data_daily table exists (created by V3.0 migration)
            async with self.engine.connect() as conn:
                await conn.execute(
                    text("SELECT 1 FROM market_data_daily LIMIT 1")
                )

            # Build session factory for repository use
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            logger.info("✅ Connected to PostgreSQL database")

        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            self.engine = None
            self.session_factory = None

    async def disconnect(self):
        """Dispose of the connection pool."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection pool closed")

    async def is_connected(self) -> bool:
        """Ping the database to verify the connection is alive."""
        if not self.engine:
            return False
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
