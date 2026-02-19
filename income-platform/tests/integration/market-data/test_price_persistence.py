"""
Integration tests for price persistence (cache → DB → Alpha Vantage).

These tests verify the three-layer retrieval strategy:
  1. Cache hit  → served from Redis, no DB or API call
  2. Cache miss + DB hit → served from DB, no API call
  3. Cache miss + DB miss → fetched from Alpha Vantage, persisted to DB + cache

Run with:
    pytest tests/integration/market-data/test_price_persistence.py -v

Requires:
    TEST_DATABASE_URL and TEST_REDIS_URL env vars pointing at a test instance,
    OR the service running with the production database (read-only tests).
"""
import json
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_AV_PRICES = [
    {
        "date": date(2024, 11, 15),
        "open": 228.0,
        "high": 230.5,
        "low": 227.0,
        "close": 229.0,
        "volume": 55_000_000,
        "adjusted_close": 229.0,
    },
    {
        "date": date(2024, 11, 14),
        "open": 225.0,
        "high": 228.5,
        "low": 224.0,
        "close": 228.0,
        "volume": 52_000_000,
        "adjusted_close": 228.0,
    },
]


def _make_price_service(price_repo=None, cache_manager=None, av_api_key="test-key"):
    """Helper to construct a PriceService with optional mock dependencies."""
    from src.market_data_service.services.price_service import PriceService

    return PriceService(
        price_repo=price_repo,
        cache_manager=cache_manager,
        av_api_key=av_api_key,
        cache_ttl=300,
    )


# ---------------------------------------------------------------------------
# Test 1: API fetch → stored in DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_fetch_stores_in_db():
    """
    When cache and DB both miss, the service fetches from Alpha Vantage
    and persists the result to the database.
    """
    # Mock cache — always miss
    mock_cache = AsyncMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()

    # Mock repository — no existing row, capture save call
    mock_repo = AsyncMock()
    mock_repo.get_latest_price = AsyncMock(return_value=None)
    mock_repo.save_price = AsyncMock()

    # Mock Alpha Vantage client
    mock_av = AsyncMock()
    mock_av.__aenter__ = AsyncMock(return_value=mock_av)
    mock_av.__aexit__ = AsyncMock(return_value=False)
    mock_av.get_daily_prices = AsyncMock(return_value=MOCK_AV_PRICES)

    svc = _make_price_service(price_repo=mock_repo, cache_manager=mock_cache)

    with patch(
        "src.market_data_service.services.price_service.AlphaVantageClient",
        return_value=mock_av,
    ):
        result = await svc.get_current_price("AAPL")

    # Response is correct
    assert result["ticker"] == "AAPL"
    assert result["price"] == 229.0
    assert result["source"] == "alpha_vantage"
    assert result["cached"] is False

    # DB save was called with the latest day's data
    mock_repo.save_price.assert_called_once_with(
        "AAPL", MOCK_AV_PRICES[0]["date"], MOCK_AV_PRICES[0]
    )

    # Cache was warmed
    mock_cache.set.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: Cache hit → no DB or API call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_skips_db_and_api():
    """
    When a valid cache entry exists, the service returns it immediately
    without touching the database or Alpha Vantage.
    """
    cached_data = {
        "ticker": "MSFT",
        "price": 420.0,
        "change": 2.5,
        "change_percent": 0.6,
        "volume": 30_000_000,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "source": "alpha_vantage",
        "cached": False,
    }

    mock_cache = AsyncMock()
    mock_cache.get = AsyncMock(return_value=cached_data)

    mock_repo = AsyncMock()
    mock_av_class = MagicMock()

    svc = _make_price_service(price_repo=mock_repo, cache_manager=mock_cache)

    with patch(
        "src.market_data_service.services.price_service.AlphaVantageClient",
        mock_av_class,
    ):
        result = await svc.get_current_price("MSFT")

    assert result["ticker"] == "MSFT"
    assert result["price"] == 420.0
    assert result["cached"] is True

    # DB and API must NOT have been called
    mock_repo.get_latest_price.assert_not_called()
    mock_av_class.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Cache miss + DB hit → no API call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_miss_db_hit_skips_api():
    """
    When cache misses but the DB has a row, the service returns from the DB
    and warms the cache — without calling Alpha Vantage.
    """
    from unittest.mock import MagicMock
    from decimal import Decimal

    # Build a mock ORM row
    mock_row = MagicMock()
    mock_row.ticker_symbol = "JNJ"
    mock_row.trade_date = date(2024, 11, 14)
    mock_row.close_price = Decimal("155.50")
    mock_row.volume = 8_000_000
    mock_row.created_at = datetime(2024, 11, 14, 20, 0, 0, tzinfo=timezone.utc)

    mock_cache = AsyncMock()
    mock_cache.get = AsyncMock(return_value=None)   # cache miss
    mock_cache.set = AsyncMock()

    mock_repo = AsyncMock()
    mock_repo.get_latest_price = AsyncMock(return_value=mock_row)

    mock_av_class = MagicMock()

    svc = _make_price_service(price_repo=mock_repo, cache_manager=mock_cache)

    with patch(
        "src.market_data_service.services.price_service.AlphaVantageClient",
        mock_av_class,
    ):
        result = await svc.get_current_price("JNJ")

    assert result["ticker"] == "JNJ"
    assert result["price"] == 155.5
    assert result["source"] == "database"
    assert result["cached"] is False

    # API must NOT have been called
    mock_av_class.assert_not_called()

    # Cache should have been warmed with the DB data
    mock_cache.set.assert_called_once()
