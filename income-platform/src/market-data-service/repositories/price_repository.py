"""Repository for market_data_daily table operations."""
import logging
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from orm_models import MarketDataDaily

logger = logging.getLogger(__name__)


class PriceRepository:
    """Async repository for historical price persistence."""

    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def save_price(self, ticker: str, trade_date: date, ohlcv: dict) -> None:
        """Upsert a single price row.

        Uses ON CONFLICT (ticker_symbol, trade_date) DO UPDATE so re-fetching
        the same ticker on the same day is idempotent.
        """
        row = {
            "ticker_symbol": ticker.upper(),
            "trade_date": trade_date,
            "open_price": ohlcv.get("open"),
            "high_price": ohlcv.get("high"),
            "low_price": ohlcv.get("low"),
            "close_price": ohlcv["close"],
            "volume": ohlcv.get("volume"),
            "adjusted_close": ohlcv.get("adjusted_close"),
        }

        stmt = pg_insert(MarketDataDaily).values([row])
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker_symbol", "trade_date"],
            set_={
                "open_price": stmt.excluded.open_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "close_price": stmt.excluded.close_price,
                "volume": stmt.excluded.volume,
                "adjusted_close": stmt.excluded.adjusted_close,
            },
        )

        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(stmt)

        logger.debug(f"Saved price for {ticker} on {trade_date}")

    async def get_latest_price(self, ticker: str) -> Optional[MarketDataDaily]:
        """Return the most recent row for ticker, or None if not in DB."""
        async with self.session_factory() as session:
            stmt = (
                select(MarketDataDaily)
                .where(MarketDataDaily.ticker_symbol == ticker.upper())
                .order_by(MarketDataDaily.trade_date.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_price_by_date(
        self, ticker: str, trade_date: date
    ) -> Optional[MarketDataDaily]:
        """Return the row for a specific ticker + date, or None."""
        async with self.session_factory() as session:
            stmt = select(MarketDataDaily).where(
                MarketDataDaily.ticker_symbol == ticker.upper(),
                MarketDataDaily.trade_date == trade_date,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
