"""
Integration tests for the stock history endpoints:

    GET  /api/market-data/stocks/{symbol}/history
    GET  /api/market-data/stocks/{symbol}/history/stats
    POST /api/market-data/stocks/{symbol}/history/refresh

Endpoint handler functions are called directly as async coroutines — no
ASGI server is spun up.  The global ``market_data_service`` in main.py is
replaced with an AsyncMock for the duration of each test via patch.object,
which is identical to the strategy used in test_price_persistence.py for
PriceService.

Run with:
    pytest tests/integration/market-data/test_history_endpoints.py -v
"""
import os
import statistics
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Set required env vars BEFORE importing main (config reads them at import time)
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("MARKET_DATA_API_KEY", "test-key")

# ---------------------------------------------------------------------------
# Make service modules importable
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "src" / "market-data-service"
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

import main as main_module  # noqa: E402  (env vars must be set first)

# RefreshRequest is registered in sys.modules["models"] by main's _load() call
RefreshRequest = main_module.RefreshRequest

# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

# Three OHLCV records, oldest-to-newest (the order get_historical_prices returns)
MOCK_PRICES = [
    {
        "date": "2024-01-02",
        "open": 185.20,
        "high": 187.00,
        "low": 184.50,
        "close": 186.86,
        "volume": 50_000_000,
        "adjusted_close": 186.86,
    },
    {
        "date": "2024-01-03",
        "open": 184.50,
        "high": 186.00,
        "low": 183.20,
        "close": 184.25,
        "volume": 48_000_000,
        "adjusted_close": 184.25,
    },
    {
        "date": "2024-01-04",
        "open": 183.00,
        "high": 185.50,
        "low": 182.50,
        "close": 185.59,
        "volume": 52_000_000,
        "adjusted_close": 185.59,
    },
]

_CLOSES = [p["close"] for p in MOCK_PRICES]


def _mock_mds(prices=None, refresh_count=0):
    """Build a mock MarketDataService with configurable return values."""
    mock = AsyncMock()
    mock.get_historical_prices = AsyncMock(return_value=prices if prices is not None else MOCK_PRICES)
    mock.refresh_historical_prices = AsyncMock(return_value=refresh_count)
    return mock


# ---------------------------------------------------------------------------
# GET /api/market-data/stocks/{symbol}/history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_stock_history_returns_symbol_count_and_prices():
    """Happy path: response carries symbol, correct count, and all prices."""
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_history(
            symbol="aapl",  # lowercase — endpoint should normalise
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            limit=90,
        )

    assert result.symbol == "AAPL"
    assert result.count == len(MOCK_PRICES)
    assert len(result.prices) == len(MOCK_PRICES)
    assert result.source == "alpha_vantage"
    assert str(result.start_date) == "2024-01-01"
    assert str(result.end_date) == "2024-01-31"

    mock.get_historical_prices.assert_awaited_once_with(
        "AAPL", date(2024, 1, 1), date(2024, 1, 31)
    )


@pytest.mark.asyncio
async def test_get_stock_history_limit_caps_returned_records():
    """When limit < total records only the first `limit` entries are returned."""
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_history(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            limit=2,
        )

    assert result.count == 2
    assert len(result.prices) == 2
    # First two records (oldest) should be returned
    assert str(result.prices[0].date) == "2024-01-02"
    assert str(result.prices[1].date) == "2024-01-03"


@pytest.mark.asyncio
async def test_get_stock_history_invalid_date_range_raises_400():
    """start_date after end_date must yield a 400 HTTPException."""
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        with pytest.raises(HTTPException) as exc_info:
            await main_module.get_stock_history(
                symbol="AAPL",
                start_date=date(2024, 2, 1),   # after end_date
                end_date=date(2024, 1, 1),
                limit=90,
            )

    assert exc_info.value.status_code == 400
    mock.get_historical_prices.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_stock_history_empty_prices_returns_zero_count():
    """When the service returns no data the response has count=0 and empty prices."""
    mock = _mock_mds(prices=[])

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_history(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            limit=90,
        )

    assert result.count == 0
    assert result.prices == []


# ---------------------------------------------------------------------------
# GET /api/market-data/stocks/{symbol}/history/stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_stock_history_stats_calculates_all_fields():
    """
    Stats endpoint computes min, max, avg, volatility, and price_change_pct
    from the closes returned by get_historical_prices.
    """
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_history_stats(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

    expected_min = round(min(_CLOSES), 4)
    expected_max = round(max(_CLOSES), 4)
    expected_avg = round(sum(_CLOSES) / len(_CLOSES), 4)
    expected_vol = round(statistics.stdev(_CLOSES), 4)
    expected_pct = round(((_CLOSES[-1] - _CLOSES[0]) / _CLOSES[0]) * 100, 4)

    assert result.symbol == "AAPL"
    assert result.period_days == (date(2024, 1, 31) - date(2024, 1, 1)).days
    assert result.min_price == expected_min
    assert result.max_price == expected_max
    assert result.avg_price == expected_avg
    assert result.volatility == expected_vol
    assert result.price_change_pct == expected_pct


@pytest.mark.asyncio
async def test_get_stock_history_stats_empty_data_returns_null_fields():
    """When no price data exists all numeric fields are None (not 0 or NaN)."""
    mock = _mock_mds(prices=[])

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_history_stats(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

    assert result.min_price is None
    assert result.max_price is None
    assert result.avg_price is None
    assert result.volatility is None
    assert result.price_change_pct is None
    assert result.period_days == 30


@pytest.mark.asyncio
async def test_get_stock_history_stats_invalid_date_range_raises_400():
    """start_date after end_date must yield a 400 HTTPException in stats too."""
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        with pytest.raises(HTTPException) as exc_info:
            await main_module.get_stock_history_stats(
                symbol="AAPL",
                start_date=date(2024, 3, 1),
                end_date=date(2024, 1, 1),
            )

    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/market-data/stocks/{symbol}/history/refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_stock_history_returns_records_saved():
    """Refresh response carries symbol, records_saved, source, and message."""
    mock = _mock_mds(refresh_count=87)

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.refresh_stock_history(
            symbol="msft",   # lowercase — endpoint should normalise
            body=RefreshRequest(full_history=False),
        )

    assert result.symbol == "MSFT"
    assert result.records_saved == 87
    assert result.source == "alpha_vantage"
    assert "87" in result.message

    mock.refresh_historical_prices.assert_awaited_once_with("MSFT", full_history=False)


@pytest.mark.asyncio
async def test_refresh_stock_history_full_history_flag_forwarded():
    """full_history=True in the request body is forwarded to the service."""
    mock = _mock_mds(refresh_count=5_000)

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.refresh_stock_history(
            symbol="AAPL",
            body=RefreshRequest(full_history=True),
        )

    assert result.records_saved == 5_000
    mock.refresh_historical_prices.assert_awaited_once_with("AAPL", full_history=True)
    assert "full" in result.message.lower()
