"""
Unit tests for PolygonClient.

Covers:
  - get_daily_prices: "compact" outputsize requests exactly 140 calendar days.
  - get_daily_prices: "full" outputsize requests exactly 730 calendar days.
  - get_daily_prices: the end date is always today.
  - get_daily_prices: OHLCV field mapping from Polygon aggregate bar fields
    (o → open, h → high, l → low, c → close, v → volume, vw → adjusted_close).
  - get_daily_prices: empty results list → returns [].

All HTTP I/O is mocked at the _get level — no network calls are made.

Run with:
    pytest tests/unit/market-data/test_polygon_client.py -v
"""
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make service modules importable
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "src" / "market-data-service"
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from fetchers.polygon_client import PolygonClient  # noqa: E402

# ---------------------------------------------------------------------------
# Client factory helper
# ---------------------------------------------------------------------------


def _client() -> PolygonClient:
    """Return a PolygonClient with a dummy session — avoids context-manager check."""
    c = PolygonClient(api_key="test-key")
    c.session = MagicMock()
    return c


# ---------------------------------------------------------------------------
# Helper: fake Polygon aggregate response
# ---------------------------------------------------------------------------

def _agg_response(bars: list) -> dict:
    """Wrap bar list in the standard Polygon aggregate response envelope."""
    return {
        "status":       "OK",
        "resultsCount": len(bars),
        "results":      bars,
    }


_SAMPLE_BAR = {
    "t": 1704196800000,  # 2024-01-02 12:00:00 UTC — midday avoids local-timezone off-by-one
    "o": 185.20,
    "h": 187.00,
    "l": 184.50,
    "c": 186.86,
    "v": 50_000_000,
    "vw": 186.10,        # VWAP → mapped to adjusted_close
}


# ---------------------------------------------------------------------------
# Tests — date range calculation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_prices_compact_uses_140_day_window():
    """compact outputsize requests exactly 140 calendar days back from today."""
    client = _client()
    captured_paths = []

    async def _mock_get(path, **kwargs):
        captured_paths.append(path)
        return _agg_response([])

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        await client.get_daily_prices("AAPL", outputsize="compact")

    assert len(captured_paths) == 1
    # Path format: /v2/aggs/ticker/AAPL/range/1/day/{start}/{end}
    parts = captured_paths[0].split("/")
    start_str, end_str = parts[-2], parts[-1]

    start_date = date.fromisoformat(start_str)
    end_date   = date.fromisoformat(end_str)
    today      = date.today()

    assert end_date == today
    assert (today - start_date).days == 140


@pytest.mark.asyncio
async def test_get_daily_prices_full_uses_730_day_window():
    """full outputsize requests exactly 730 calendar days (2 years) back from today."""
    client = _client()
    captured_paths = []

    async def _mock_get(path, **kwargs):
        captured_paths.append(path)
        return _agg_response([])

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        await client.get_daily_prices("AAPL", outputsize="full")

    assert len(captured_paths) == 1
    parts = captured_paths[0].split("/")
    start_str, end_str = parts[-2], parts[-1]

    start_date = date.fromisoformat(start_str)
    end_date   = date.fromisoformat(end_str)
    today      = date.today()

    assert end_date == today
    assert (today - start_date).days == 730


@pytest.mark.asyncio
async def test_get_daily_prices_end_date_is_today():
    """The end date of the request window is always today, for both outputsizes."""
    client = _client()
    today  = date.today()

    for outputsize in ("compact", "full"):
        captured = []

        async def _mock_get(path, **kwargs):
            captured.append(path)
            return _agg_response([])

        with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
            await client.get_daily_prices("AAPL", outputsize=outputsize)

        end_str  = captured[0].split("/")[-1]
        assert date.fromisoformat(end_str) == today, (
            f"Expected end_date={today} for outputsize={outputsize!r}, "
            f"got {end_str}"
        )


# ---------------------------------------------------------------------------
# Tests — OHLCV field mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_prices_ohlcv_field_mapping():
    """Polygon bar fields are mapped correctly to the expected output keys."""
    client = _client()

    async def _mock_get(path, **kwargs):
        return _agg_response([_SAMPLE_BAR])

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_daily_prices("AAPL", outputsize="compact")

    assert len(result) == 1
    bar = result[0]

    assert bar["open"]           == 185.20
    assert bar["high"]           == 187.00
    assert bar["low"]            == 184.50
    assert bar["close"]          == 186.86
    assert bar["volume"]         == 50_000_000
    assert bar["adjusted_close"] == 186.10   # vw (VWAP) mapped to adjusted_close


@pytest.mark.asyncio
async def test_get_daily_prices_vwap_falls_back_to_close_when_absent():
    """When 'vw' is absent, adjusted_close falls back to 'c' (close price)."""
    client = _client()
    bar_no_vw = {k: v for k, v in _SAMPLE_BAR.items() if k != "vw"}

    async def _mock_get(path, **kwargs):
        return _agg_response([bar_no_vw])

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_daily_prices("AAPL")

    assert result[0]["adjusted_close"] == result[0]["close"]


@pytest.mark.asyncio
async def test_get_daily_prices_date_converted_from_milliseconds():
    """Bar timestamps (Unix ms) are converted to ISO-8601 date strings."""
    client = _client()

    async def _mock_get(path, **kwargs):
        return _agg_response([_SAMPLE_BAR])

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_daily_prices("AAPL")

    # t=1704153600000 ms → 2024-01-02 UTC
    assert result[0]["date"] == "2024-01-02"


@pytest.mark.asyncio
async def test_get_daily_prices_empty_results_returns_empty_list():
    """When Polygon returns no bars, get_daily_prices returns []."""
    client = _client()

    async def _mock_get(path, **kwargs):
        return _agg_response([])

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_daily_prices("AAPL")

    assert result == []
