"""
Unit tests for AlphaVantageClient.fetch_daily_adjusted().

Verifies correct field mapping from the TIME_SERIES_DAILY_ADJUSTED response,
date ordering, cache hit/miss behaviour, and date serialisation for Redis.
All HTTP and Redis I/O is mocked — no network calls or live services required.

Run with:
    pytest tests/unit/market-data/test_alpha_vantage_parsing.py -v
"""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make service modules importable
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "src" / "market-data-service"
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from fetchers.alpha_vantage import AlphaVantageClient  # noqa: E402

# ---------------------------------------------------------------------------
# Fake API response fixture
# ---------------------------------------------------------------------------

# Three dates in deliberately non-sequential dict ordering to confirm sorting
_FAKE_AV_RESPONSE = {
    "Meta Data": {
        "1. Information": "Daily Time Series with Splits and Dividend Events",
        "2. Symbol": "AAPL",
        "3. Last Refreshed": "2024-11-15",
    },
    "Time Series (Daily Adjusted)": {
        "2024-11-13": {
            "1. open": "220.00",
            "2. high": "223.50",
            "3. low": "219.00",
            "4. close": "222.01",
            "5. adjusted close": "222.01",
            "6. volume": "48000000",
            "7. dividend amount": "0.0000",
            "8. split coefficient": "1.0",
        },
        "2024-11-15": {
            "1. open": "228.00",
            "2. high": "230.50",
            "3. low": "227.00",
            "4. close": "229.87",
            "5. adjusted close": "229.87",
            "6. volume": "55000000",
            "7. dividend amount": "0.0000",
            "8. split coefficient": "1.0",
        },
        "2024-11-14": {
            "1. open": "225.00",
            "2. high": "228.50",
            "3. low": "224.00",
            "4. close": "228.22",
            "5. adjusted close": "228.22",
            "6. volume": "52000000",
            "7. dividend amount": "0.0000",
            "8. split coefficient": "1.0",
        },
    },
}

_EMPTY_AV_RESPONSE = {
    "Meta Data": {"2. Symbol": "ZZZ"},
    "Time Series (Daily Adjusted)": {},
}


def _client(cache=None) -> AlphaVantageClient:
    """Return a client instance with a dummy session (avoids RuntimeError)."""
    c = AlphaVantageClient(api_key="test-key", cache=cache)
    c.session = MagicMock()  # prevents "Session not initialized" inside _make_request
    return c


# ---------------------------------------------------------------------------
# Tests — field parsing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_daily_adjusted_parses_all_ohlcv_fields():
    """All six OHLCV fields are correctly mapped from the numbered AV keys."""
    client = _client()

    with patch.object(client, "_make_request", new=AsyncMock(return_value=_FAKE_AV_RESPONSE)):
        result = await client.fetch_daily_adjusted("AAPL", "compact")

    assert len(result) == 3

    # The most recent entry (2024-11-15) should be first
    latest = result[0]
    assert latest["date"] == date(2024, 11, 15)
    assert latest["open"] == 228.00
    assert latest["high"] == 230.50
    assert latest["low"] == 227.00
    assert latest["close"] == 229.87
    assert latest["adjusted_close"] == 229.87
    assert latest["volume"] == 55_000_000


@pytest.mark.asyncio
async def test_fetch_daily_adjusted_uses_adjusted_close_not_plain_close():
    """
    The 'adjusted_close' field maps to key '5. adjusted close', which can
    differ from '4. close' when a split or dividend has occurred.
    """
    split_response = {
        "Time Series (Daily Adjusted)": {
            "2024-06-10": {
                "1. open": "200.00",
                "2. high": "205.00",
                "3. low": "198.00",
                "4. close": "202.00",
                "5. adjusted close": "50.50",   # post-split adjusted value
                "6. volume": "300000000",
            }
        }
    }
    client = _client()

    with patch.object(client, "_make_request", new=AsyncMock(return_value=split_response)):
        result = await client.fetch_daily_adjusted("AAPL", "compact")

    assert result[0]["close"] == 202.00
    assert result[0]["adjusted_close"] == 50.50


# ---------------------------------------------------------------------------
# Tests — date ordering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_daily_adjusted_sorted_descending():
    """Results are ordered most-recent-first regardless of dict insertion order."""
    client = _client()

    with patch.object(client, "_make_request", new=AsyncMock(return_value=_FAKE_AV_RESPONSE)):
        result = await client.fetch_daily_adjusted("AAPL", "compact")

    dates = [r["date"] for r in result]
    assert dates == sorted(dates, reverse=True), "Expected descending date order"
    assert dates[0] == date(2024, 11, 15)
    assert dates[-1] == date(2024, 11, 13)


# ---------------------------------------------------------------------------
# Tests — empty / error cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_daily_adjusted_empty_series_returns_empty_list():
    """An AV response with no entries in Time Series returns []."""
    client = _client()

    with patch.object(client, "_make_request", new=AsyncMock(return_value=_EMPTY_AV_RESPONSE)):
        result = await client.fetch_daily_adjusted("ZZZ", "compact")

    assert result == []


# ---------------------------------------------------------------------------
# Tests — caching behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_daily_adjusted_cache_hit_skips_api_call():
    """When the cache returns data the API must not be called."""
    cached_payload = [
        {
            "date": "2024-11-15",
            "open": 228.00,
            "high": 230.50,
            "low": 227.00,
            "close": 229.87,
            "adjusted_close": 229.87,
            "volume": 55_000_000,
        }
    ]

    mock_cache = AsyncMock()
    mock_cache.get.return_value = cached_payload

    client = _client(cache=mock_cache)
    mock_request = AsyncMock()

    with patch.object(client, "_make_request", new=mock_request):
        result = await client.fetch_daily_adjusted("AAPL", "compact")

    assert result == cached_payload
    mock_cache.get.assert_awaited_once()
    mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_daily_adjusted_writes_iso_dates_to_cache():
    """
    On a cache miss the results are persisted with date values as ISO strings,
    because date objects are not JSON-serialisable for Redis storage.
    """
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None  # cache miss

    client = _client(cache=mock_cache)

    with patch.object(client, "_make_request", new=AsyncMock(return_value=_FAKE_AV_RESPONSE)):
        await client.fetch_daily_adjusted("AAPL", "compact")

    mock_cache.set.assert_awaited_once()
    _, call_kwargs = mock_cache.set.call_args_list[0][0], mock_cache.set.call_args_list[0][1]

    # Retrieve the payload that was written to the cache
    cached_records = mock_cache.set.call_args.args[1]  # second positional arg
    for record in cached_records:
        assert isinstance(record["date"], str), (
            f"Expected ISO string in cache, got {type(record['date'])}: {record['date']}"
        )
        # Must be a valid ISO date string
        date.fromisoformat(record["date"])
