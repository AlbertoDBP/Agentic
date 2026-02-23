"""Repository for price_history table operations."""
import logging
from datetime import date
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from orm_models import PriceHistory

logger = logging.getLogger(__name__)

# Columns updated on conflict — everything except the natural key and created_at
_UPSERT_SET = (
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "adjusted_close",
    "volume",
    "data_source",
)


class PriceHistoryRepository:
    """Async repository for price_history table persistence."""

    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def save_price_record(
        self, symbol: str, record_date: date, ohlcv: dict
    ) -> None:
        """Upsert a single price record.

        Idempotent: re-fetching the same symbol + date overwrites the OHLCV
        columns but preserves the original row id and created_at.
        """
        row = _build_row(symbol, record_date, ohlcv)
        stmt = pg_insert(PriceHistory).values([row])
        stmt = stmt.on_conflict_do_update(
            constraint="uq_price_history_symbol_date",
            set_={col: getattr(stmt.excluded, col) for col in _UPSERT_SET},
        )

        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(stmt)

        logger.debug(f"Saved price record for {symbol.upper()} on {record_date}")

    async def bulk_save_prices(
        self, symbol: str, records: List[dict]
    ) -> int:
        """Batch upsert a list of OHLCV records for a single symbol.

        All rows are sent in a single INSERT ... ON CONFLICT statement,
        which is significantly faster than calling save_price_record() in a loop.

        Args:
            symbol:  Ticker symbol (e.g. "AAPL").
            records: List of dicts, each with keys:
                       date, open, high, low, close, volume,
                       adjusted_close (optional), data_source (optional).

        Returns:
            Number of rows affected (inserted + updated).
        """
        if not records:
            return 0

        rows = [_build_row(symbol, r["date"], r) for r in records]

        stmt = pg_insert(PriceHistory).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_price_history_symbol_date",
            set_={col: getattr(stmt.excluded, col) for col in _UPSERT_SET},
        )

        async with self.session_factory() as session:
            async with session.begin():
                result = await session.execute(stmt)

        count = result.rowcount
        logger.info(f"Bulk upserted {count} price records for {symbol.upper()}")
        return count

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_price_range(
        self, symbol: str, start_date: date, end_date: date
    ) -> List[PriceHistory]:
        """Return all price records for symbol in [start_date, end_date], asc."""
        async with self.session_factory() as session:
            stmt = (
                select(PriceHistory)
                .where(
                    PriceHistory.symbol == symbol.upper(),
                    PriceHistory.date >= start_date,
                    PriceHistory.date <= end_date,
                )
                .order_by(PriceHistory.date.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_price(self, symbol: str) -> Optional[PriceHistory]:
        """Return the most recent price record for symbol, or None."""
        async with self.session_factory() as session:
            stmt = (
                select(PriceHistory)
                .where(PriceHistory.symbol == symbol.upper())
                .order_by(PriceHistory.date.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_row(symbol: str, record_date: date, ohlcv: dict) -> dict:
    """Map an OHLCV dict to a price_history column dict."""
    return {
        "symbol": symbol.upper(),
        "date": record_date,
        "open_price": ohlcv.get("open"),
        "high_price": ohlcv.get("high"),
        "low_price": ohlcv.get("low"),
        "close_price": ohlcv.get("close"),
        "adjusted_close": ohlcv.get("adjusted_close"),
        "volume": ohlcv.get("volume"),
        "data_source": ohlcv.get("data_source", "alpha_vantage"),
    }
