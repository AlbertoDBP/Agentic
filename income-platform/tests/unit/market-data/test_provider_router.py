"""
Unit tests for ProviderRouter fallback chain behaviour.

Verifies that:
  - A ProviderError from Polygon causes the router to fall back to FMP.
  - A DataUnavailableError also triggers fallback.
  - get_daily_prices skips FMP and falls back directly to yfinance.
  - When every configured provider fails, ProviderError is raised with a
    combined summary of all failures.
  - Skipping None providers does not cause errors.

No network calls or live services are used — all providers are mocked.

Run with:
    pytest tests/unit/market-data/test_provider_router.py -v
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Make service modules importable
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "src" / "market-data-service"
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from fetchers.base_provider import DataUnavailableError, ProviderError  # noqa: E402
from fetchers.provider_router import ProviderRouter                     # noqa: E402

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

_PRICE_RESULT = {
    "symbol": "AAPL", "price": 195.50, "volume": 50_000_000,
    "timestamp": "2024-01-02T10:00:00+00:00", "source": "fmp",
}

_DAILY_RESULT = [
    {
        "date": "2024-01-02", "open": 185.20, "high": 187.00, "low": 184.50,
        "close": 186.86, "adjusted_close": 186.86, "volume": 50_000_000,
    }
]


def _polygon(method="get_current_price", *, raise_error=None, return_value=None):
    """Build a minimal Polygon mock."""
    mock = MagicMock()
    m = AsyncMock(
        side_effect=raise_error,
        return_value=return_value if raise_error is None else None,
    )
    setattr(mock, method, m)
    return mock


def _fmp(method="get_current_price", *, raise_error=None, return_value=None):
    """Build a minimal FMP mock."""
    mock = MagicMock()
    m = AsyncMock(
        side_effect=raise_error,
        return_value=return_value if raise_error is None else None,
    )
    setattr(mock, method, m)
    return mock


def _yfinance(method="get_current_price", *, raise_error=None, return_value=None):
    """Build a minimal yfinance mock."""
    mock = MagicMock()
    m = AsyncMock(
        side_effect=raise_error,
        return_value=return_value if raise_error is None else None,
    )
    setattr(mock, method, m)
    return mock


# ---------------------------------------------------------------------------
# Tests — get_current_price chain: Polygon → FMP → yfinance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_polygon_provider_error_falls_back_to_fmp():
    """ProviderError from Polygon causes the router to try FMP next."""
    polygon = _polygon(raise_error=ProviderError("polygon down"))
    fmp     = _fmp(return_value=_PRICE_RESULT)

    router = ProviderRouter(polygon=polygon, fmp=fmp, yfinance=None)
    result = await router.get_current_price("AAPL")

    assert result["source"] == "fmp"
    assert result["price"] == 195.50
    polygon.get_current_price.assert_awaited_once_with("AAPL")
    fmp.get_current_price.assert_awaited_once_with("AAPL")


@pytest.mark.asyncio
async def test_data_unavailable_error_also_triggers_fmp_fallback():
    """DataUnavailableError is treated the same as ProviderError — triggers fallback."""
    polygon = _polygon(raise_error=DataUnavailableError("no data for AAPL"))
    fmp     = _fmp(return_value=_PRICE_RESULT)

    router = ProviderRouter(polygon=polygon, fmp=fmp, yfinance=None)
    result = await router.get_current_price("AAPL")

    assert result["source"] == "fmp"
    polygon.get_current_price.assert_awaited_once()
    fmp.get_current_price.assert_awaited_once()


@pytest.mark.asyncio
async def test_polygon_success_skips_fmp():
    """When Polygon succeeds, FMP must not be called."""
    poly_result = {**_PRICE_RESULT, "source": "polygon"}
    polygon = _polygon(return_value=poly_result)
    fmp     = _fmp(return_value=_PRICE_RESULT)

    router = ProviderRouter(polygon=polygon, fmp=fmp, yfinance=None)
    result = await router.get_current_price("AAPL")

    assert result["source"] == "polygon"
    polygon.get_current_price.assert_awaited_once()
    fmp.get_current_price.assert_not_awaited()


@pytest.mark.asyncio
async def test_all_providers_fail_raises_provider_error_with_summary():
    """When every configured provider fails, ProviderError is raised with a summary."""
    polygon = _polygon(raise_error=ProviderError("polygon down"))
    fmp     = _fmp(raise_error=ProviderError("fmp down"))

    router = ProviderRouter(polygon=polygon, fmp=fmp, yfinance=None)

    with pytest.raises(ProviderError) as exc_info:
        await router.get_current_price("AAPL")

    error_msg = str(exc_info.value)
    assert "polygon" in error_msg.lower()
    assert "fmp" in error_msg.lower()


@pytest.mark.asyncio
async def test_no_providers_configured_raises_provider_error():
    """When no providers are configured, ProviderError is raised immediately."""
    router = ProviderRouter(polygon=None, fmp=None, yfinance=None)

    with pytest.raises(ProviderError):
        await router.get_current_price("AAPL")


# ---------------------------------------------------------------------------
# Tests — get_daily_prices chain: Polygon → yfinance (FMP intentionally absent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_prices_polygon_failure_goes_to_yfinance_not_fmp():
    """get_daily_prices falls back to yfinance, not FMP, when Polygon fails."""
    polygon  = MagicMock()
    polygon.get_daily_prices = AsyncMock(side_effect=ProviderError("polygon down"))

    fmp = MagicMock()
    fmp.get_daily_prices = AsyncMock(return_value=_DAILY_RESULT)  # should NOT be called

    yfinance = MagicMock()
    yfinance.get_daily_prices = AsyncMock(return_value=_DAILY_RESULT)

    router = ProviderRouter(polygon=polygon, fmp=fmp, yfinance=yfinance)
    result = await router.get_daily_prices("AAPL")

    assert result == _DAILY_RESULT
    polygon.get_daily_prices.assert_awaited_once()
    fmp.get_daily_prices.assert_not_awaited()   # FMP is absent from this chain
    yfinance.get_daily_prices.assert_awaited_once()


@pytest.mark.asyncio
async def test_daily_prices_polygon_success_skips_yfinance():
    """When Polygon's get_daily_prices succeeds, yfinance must not be called."""
    polygon  = MagicMock()
    polygon.get_daily_prices = AsyncMock(return_value=_DAILY_RESULT)

    yfinance = MagicMock()
    yfinance.get_daily_prices = AsyncMock(return_value=[])

    router = ProviderRouter(polygon=polygon, fmp=None, yfinance=yfinance)
    await router.get_daily_prices("AAPL", outputsize="compact")

    polygon.get_daily_prices.assert_awaited_once_with("AAPL", outputsize="compact")
    yfinance.get_daily_prices.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests — dividend / fundamentals / etf: FMP → yfinance (Polygon absent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dividend_history_fmp_failure_falls_back_to_yfinance():
    """get_dividend_history falls back to yfinance when FMP fails."""
    _div_result = [{"ex_date": "2024-09-19", "payment_date": "2024-10-01",
                    "amount": 0.52, "frequency": "quarterly", "yield_pct": None}]

    fmp      = MagicMock()
    fmp.get_dividend_history = AsyncMock(side_effect=ProviderError("fmp down"))

    yfinance = MagicMock()
    yfinance.get_dividend_history = AsyncMock(return_value=_div_result)

    router = ProviderRouter(polygon=None, fmp=fmp, yfinance=yfinance)
    result = await router.get_dividend_history("AAPL")

    assert result == _div_result
    fmp.get_dividend_history.assert_awaited_once()
    yfinance.get_dividend_history.assert_awaited_once()
