"""
Integration tests for the new market-data endpoints:

    GET  /stocks/{symbol}/dividends
    GET  /stocks/{symbol}/fundamentals
    GET  /stocks/{symbol}/etf          (SCHD → covered_call: false)
    GET  /stocks/{symbol}/etf          (JEPI → covered_call: true)

Endpoint handler functions are called directly as async coroutines — no
ASGI server is spun up.  The global ``market_data_service`` in main.py is
replaced with an AsyncMock for the duration of each test via patch.object,
which is identical to the strategy used in test_history_endpoints.py.

Run with:
    pytest tests/integration/market-data/test_new_endpoints.py -v
"""
import os
import sys
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

# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

MOCK_DIVIDENDS = [
    {
        "ex_date":      "2024-09-19",
        "payment_date": "2024-10-01",
        "amount":       0.52,
        "frequency":    "quarterly",
        "yield_pct":    1.0650,
    },
    {
        "ex_date":      "2024-06-20",
        "payment_date": "2024-07-01",
        "amount":       0.50,
        "frequency":    "quarterly",
        "yield_pct":    1.0200,
    },
]

MOCK_FUNDAMENTALS = {
    "pe_ratio":        28.5,
    "debt_to_equity":  1.47,
    "payout_ratio":    0.1542,
    "earnings_growth": None,
    "free_cash_flow":  95_000_000_000.0,
    "credit_rating":   None,
    "market_cap":      3_100_000_000_000.0,
    "sector":          "Technology",
}

MOCK_SCHD_ETF = {
    "expense_ratio": 0.06,
    "aum":           60_000_000_000.0,
    "covered_call":  False,
    "top_holdings": [
        {"ticker": "AVGO", "name": "Broadcom Inc",     "weight_pct": 4.41},
        {"ticker": "HD",   "name": "Home Depot Inc",   "weight_pct": 4.20},
        {"ticker": "ABBV", "name": "AbbVie Inc",       "weight_pct": 4.10},
    ],
}

MOCK_JEPI_ETF = {
    "expense_ratio": None,
    "aum":           35_000_000_000.0,
    "covered_call":  True,
    "top_holdings": [
        {"ticker": "MSFT", "name": "Microsoft Corp", "weight_pct": 1.80},
        {"ticker": "AMZN", "name": "Amazon.com Inc",  "weight_pct": 1.70},
    ],
}


def _mock_mds(**overrides):
    """Build a mock MarketDataService with configurable return values."""
    mock = AsyncMock()
    mock.get_dividend_history  = AsyncMock(return_value=MOCK_DIVIDENDS)
    mock.get_fundamentals      = AsyncMock(return_value=MOCK_FUNDAMENTALS)
    mock.get_etf_holdings      = AsyncMock(return_value=MOCK_SCHD_ETF)
    for attr, val in overrides.items():
        setattr(mock, attr, AsyncMock(return_value=val))
    return mock


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/dividends
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stock_dividends_returns_correct_shape():
    """Happy path: response carries symbol, count, source, and all dividend records."""
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_dividends(symbol="aapl")

    assert result.symbol == "AAPL"
    assert result.count  == len(MOCK_DIVIDENDS)
    assert len(result.dividends) == len(MOCK_DIVIDENDS)
    assert result.source == "fmp"

    mock.get_dividend_history.assert_awaited_once_with("AAPL")


@pytest.mark.asyncio
async def test_get_stock_dividends_field_values():
    """DividendRecord fields are populated from the service response."""
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_dividends(symbol="AAPL")

    first = result.dividends[0]
    assert first.ex_date      == "2024-09-19"
    assert first.payment_date == "2024-10-01"
    assert first.amount       == 0.52
    assert first.frequency    == "quarterly"
    assert first.yield_pct    == 1.0650


@pytest.mark.asyncio
async def test_get_stock_dividends_normalises_symbol_to_uppercase():
    """Lowercase symbol is uppercased before delegating to the service."""
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_dividends(symbol="schd")

    assert result.symbol == "SCHD"
    mock.get_dividend_history.assert_awaited_once_with("SCHD")


@pytest.mark.asyncio
async def test_get_stock_dividends_empty_returns_zero_count():
    """When the service returns no records, count is 0 and dividends list is empty."""
    mock = _mock_mds(get_dividend_history=[])

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_dividends(symbol="XYZ")

    assert result.count     == 0
    assert result.dividends == []


@pytest.mark.asyncio
async def test_get_stock_dividends_service_error_raises_500():
    """An unexpected error from the service propagates as a 500 HTTPException."""
    mock = AsyncMock()
    mock.get_dividend_history = AsyncMock(side_effect=RuntimeError("DB timeout"))

    with patch.object(main_module, "market_data_service", mock):
        with pytest.raises(HTTPException) as exc_info:
            await main_module.get_stock_dividends(symbol="AAPL")

    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/fundamentals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stock_fundamentals_returns_non_null_payout_ratio():
    """Fundamentals response includes a non-null payout_ratio."""
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_fundamentals(symbol="AAPL")

    assert result.symbol       == "AAPL"
    assert result.payout_ratio is not None
    assert result.payout_ratio == 0.1542


@pytest.mark.asyncio
async def test_get_stock_fundamentals_all_fields_present():
    """All fundamental fields are populated from the service response."""
    mock = _mock_mds()

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_fundamentals(symbol="AAPL")

    assert result.pe_ratio        == 28.5
    assert result.debt_to_equity  == 1.47
    assert result.payout_ratio    == 0.1542
    assert result.free_cash_flow  == 95_000_000_000.0
    assert result.market_cap      == 3_100_000_000_000.0
    assert result.sector          == "Technology"
    assert result.source          == "fmp"


@pytest.mark.asyncio
async def test_get_stock_fundamentals_null_fields_are_accepted():
    """Fields absent from the service response are returned as null (not errors)."""
    sparse = {
        "pe_ratio":        None,
        "debt_to_equity":  None,
        "payout_ratio":    0.25,
        "earnings_growth": None,
        "free_cash_flow":  None,
        "credit_rating":   None,
        "market_cap":      None,
        "sector":          None,
    }
    mock = _mock_mds(get_fundamentals=sparse)

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_stock_fundamentals(symbol="AAPL")

    assert result.pe_ratio       is None
    assert result.payout_ratio   == 0.25
    assert result.market_cap     is None


@pytest.mark.asyncio
async def test_get_stock_fundamentals_service_error_raises_500():
    """An unexpected error from the service propagates as a 500 HTTPException."""
    mock = AsyncMock()
    mock.get_fundamentals = AsyncMock(side_effect=RuntimeError("timeout"))

    with patch.object(main_module, "market_data_service", mock):
        with pytest.raises(HTTPException) as exc_info:
            await main_module.get_stock_fundamentals(symbol="AAPL")

    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/etf — SCHD (covered_call: false)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_etf_data_schd_covered_call_is_false():
    """SCHD: a plain dividend ETF must return covered_call=False."""
    mock = _mock_mds(get_etf_holdings=MOCK_SCHD_ETF)

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_etf_data(symbol="SCHD")

    assert result.symbol       == "SCHD"
    assert result.covered_call is False
    assert result.source       == "fmp"
    mock.get_etf_holdings.assert_awaited_once_with("SCHD")


@pytest.mark.asyncio
async def test_get_etf_data_schd_holdings_and_aum():
    """SCHD response carries top_holdings and aum from the service data."""
    mock = _mock_mds(get_etf_holdings=MOCK_SCHD_ETF)

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_etf_data(symbol="SCHD")

    assert result.aum              == 60_000_000_000.0
    assert len(result.top_holdings) == 3
    assert result.top_holdings[0].ticker     == "AVGO"
    assert result.top_holdings[0].weight_pct == 4.41


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/etf — JEPI (covered_call: true)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_etf_data_jepi_covered_call_is_true():
    """JEPI: a covered-call ETF must return covered_call=True."""
    mock = _mock_mds(get_etf_holdings=MOCK_JEPI_ETF)

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_etf_data(symbol="JEPI")

    assert result.symbol       == "JEPI"
    assert result.covered_call is True
    assert result.source       == "fmp"
    mock.get_etf_holdings.assert_awaited_once_with("JEPI")


@pytest.mark.asyncio
async def test_get_etf_data_jepi_holdings_shape():
    """JEPI ETFHolding objects are correctly constructed from the service data."""
    mock = _mock_mds(get_etf_holdings=MOCK_JEPI_ETF)

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_etf_data(symbol="JEPI")

    assert len(result.top_holdings) == 2
    first = result.top_holdings[0]
    assert first.ticker     == "MSFT"
    assert first.name       == "Microsoft Corp"
    assert first.weight_pct == 1.80


@pytest.mark.asyncio
async def test_get_etf_data_service_error_raises_500():
    """An unexpected error from the service propagates as a 500 HTTPException."""
    mock = AsyncMock()
    mock.get_etf_holdings = AsyncMock(side_effect=RuntimeError("provider failure"))

    with patch.object(main_module, "market_data_service", mock):
        with pytest.raises(HTTPException) as exc_info:
            await main_module.get_etf_data(symbol="JEPI")

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_etf_data_symbol_uppercased():
    """Lowercase ETF symbol is uppercased before delegating to the service."""
    mock = _mock_mds(get_etf_holdings=MOCK_JEPI_ETF)

    with patch.object(main_module, "market_data_service", mock):
        result = await main_module.get_etf_data(symbol="jepi")

    assert result.symbol == "JEPI"
    mock.get_etf_holdings.assert_awaited_once_with("JEPI")
