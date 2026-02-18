"""PostgreSQL Database Manager"""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async PostgreSQL connection manager"""

    def __init__(self, database_url: str):
        # Ensure asyncpg driver is used
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.database_url = database_url
        self.engine: Optional[AsyncEngine] = None

    async def connect(self):
        """Initialize database engine and verify connectivity"""
        try:
            self.engine = create_async_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            self.engine = None

    async def disconnect(self):
        """Dispose of the connection pool"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection pool closed")

    async def is_connected(self) -> bool:
        """Ping the database to verify the connection is alive"""
        if not self.engine:
            return False
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
