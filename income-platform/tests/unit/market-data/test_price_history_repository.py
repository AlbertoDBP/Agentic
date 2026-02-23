"""
Unit tests for PriceHistoryRepository.

Covers upsert (INSERT … ON CONFLICT DO UPDATE) and read operations using a
fully mocked async SQLAlchemy session — no real database required.

Run with:
    pytest tests/unit/market-data/test_price_history_repository.py -v
"""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Make service modules importable without the src/market-data-service hyphen
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "src" / "market-data-service"
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from repositories.price_history_repository import PriceHistoryRepository  # noqa: E402

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

SYMBOL = "AAPL"
DATE_A = date(2024, 11, 14)
DATE_B = date(2024, 11, 15)

OHLCV_A = {
    "date": DATE_A,
    "open": 225.00,
    "high": 228.50,
    "low": 224.00,
    "close": 228.22,
    "adjusted_close": 228.22,
    "volume": 52_000_000,
}
OHLCV_B = {
    "date": DATE_B,
    "open": 228.00,
    "high": 230.50,
    "low": 227.00,
    "close": 229.87,
    "adjusted_close": 229.87,
    "volume": 55_000_000,
}


# ---------------------------------------------------------------------------
# Session factory helpers
# ---------------------------------------------------------------------------

def _write_factory(rowcount: int = 1):
    """Mock session_factory for write operations; execute() returns rowcount."""
    mock_result = MagicMock()
    mock_result.rowcount = rowcount

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    mock_cm.__aexit__.return_value = False

    return MagicMock(return_value=mock_cm), mock_session, mock_result


def _read_many_factory(rows: list):
    """Mock session_factory for queries returning scalars().all()."""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    mock_cm.__aexit__.return_value = False

    return MagicMock(return_value=mock_cm), mock_session


def _read_one_factory(row):
    """Mock session_factory for queries returning scalar_one_or_none()."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    mock_cm.__aexit__.return_value = False

    return MagicMock(return_value=mock_cm), mock_session


# ---------------------------------------------------------------------------
# Tests — writes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_price_record_executes_upsert():
    """save_price_record() fires exactly one execute() call for the upsert."""
    factory, session, _ = _write_factory(rowcount=1)
    repo = PriceHistoryRepository(factory)

    await repo.save_price_record(SYMBOL, DATE_B, OHLCV_B)

    session.execute.assert_awaited_once()
    factory.assert_called_once()


@pytest.mark.asyncio
async def test_bulk_save_prices_returns_rowcount():
    """bulk_save_prices() sends a single batch statement and returns rowcount."""
    records = [OHLCV_A, OHLCV_B]
    factory, session, mock_result = _write_factory(rowcount=len(records))

    repo = PriceHistoryRepository(factory)
    count = await repo.bulk_save_prices(SYMBOL, records)

    assert count == len(records)
    # All rows must be sent in a single execute, not one per row
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulk_save_prices_empty_list_returns_zero():
    """bulk_save_prices() short-circuits to 0 without hitting the DB for an empty list."""
    factory, session, _ = _write_factory()

    repo = PriceHistoryRepository(factory)
    count = await repo.bulk_save_prices(SYMBOL, [])

    assert count == 0
    session.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests — reads
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_price_range_returns_all_rows_in_range():
    """get_price_range() returns the list produced by scalars().all()."""
    mock_row_a = MagicMock(symbol=SYMBOL, date=DATE_A)
    mock_row_b = MagicMock(symbol=SYMBOL, date=DATE_B)

    factory, session = _read_many_factory([mock_row_a, mock_row_b])
    repo = PriceHistoryRepository(factory)

    rows = await repo.get_price_range(SYMBOL, date(2024, 11, 1), date(2024, 11, 30))

    assert len(rows) == 2
    assert rows[0] is mock_row_a
    assert rows[1] is mock_row_b
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_price_range_returns_empty_list_when_no_rows():
    """get_price_range() returns [] when the DB has no matching rows."""
    factory, _ = _read_many_factory([])
    repo = PriceHistoryRepository(factory)

    rows = await repo.get_price_range("ZZZ", date(2020, 1, 1), date(2020, 12, 31))

    assert rows == []


@pytest.mark.asyncio
async def test_get_latest_price_returns_most_recent_row():
    """get_latest_price() delegates to scalar_one_or_none() and returns the row."""
    mock_row = MagicMock(symbol=SYMBOL, date=DATE_B)

    factory, session = _read_one_factory(mock_row)
    repo = PriceHistoryRepository(factory)

    row = await repo.get_latest_price(SYMBOL)

    assert row is mock_row
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_latest_price_returns_none_for_unknown_symbol():
    """get_latest_price() returns None when the symbol has no rows."""
    factory, _ = _read_one_factory(None)
    repo = PriceHistoryRepository(factory)

    row = await repo.get_latest_price("UNKNOWN")

    assert row is None


# ---------------------------------------------------------------------------
# Test — duplicate prevention (upsert idempotency)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_upsert_does_not_raise():
    """
    Calling save_price_record() twice with the same symbol+date must not raise.

    The underlying INSERT … ON CONFLICT DO UPDATE guarantees idempotency.
    This test verifies that the code path is executed twice without error
    and that execute() is called for each invocation.
    """
    factory, session, _ = _write_factory(rowcount=1)
    repo = PriceHistoryRepository(factory)

    # First insert
    await repo.save_price_record(SYMBOL, DATE_B, OHLCV_B)
    # Second insert — same key, different close; ON CONFLICT should update silently
    await repo.save_price_record(SYMBOL, DATE_B, {**OHLCV_B, "close": 231.00})

    # Both round-trips must have reached the DB
    assert session.execute.await_count == 2
