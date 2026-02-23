"""
Unit tests for FMPClient.

Covers:
  - get_dividend_history: correct field mapping from FMP response shapes
    (date → ex_date, paymentDate → payment_date, dividend → amount).
  - get_dividend_history: yield_pct calculation when current price is available.
  - get_dividend_history: frequency is always None (FMP endpoint omits it).
  - get_etf_holdings: covered_call detection from description text (positive case).
  - get_etf_holdings: covered_call is False for a plain equity ETF (negative case).
  - get_etf_holdings: weight decimal-to-percent conversion (0.0741 → 7.41).

All HTTP I/O is mocked at the _get level — no network calls are made.

Run with:
    pytest tests/unit/market-data/test_fmp_client.py -v
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make service modules importable
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "src" / "market-data-service"
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from fetchers.fmp_client import FMPClient  # noqa: E402

# ---------------------------------------------------------------------------
# Client factory helper
# ---------------------------------------------------------------------------


def _client() -> FMPClient:
    """Return an FMPClient with a dummy session — avoids context-manager check."""
    c = FMPClient(api_key="test-key")
    c.session = MagicMock()
    return c


# ---------------------------------------------------------------------------
# Fixtures: fake FMP API responses
# ---------------------------------------------------------------------------

_DIV_HISTORY_RESPONSE = {
    "historical": [
        {
            "date":        "2024-09-19",
            "paymentDate": "2024-10-01",
            "dividend":    0.52,
            "adjDividend": 0.52,
        },
        {
            "date":        "2024-06-20",
            "paymentDate": "2024-07-01",
            "dividend":    0.50,
            "adjDividend": 0.50,
        },
    ]
}

_QUOTE_RESPONSE = [{"symbol": "AAPL", "price": 200.0, "volume": 60_000_000}]

# ETF holdings list returned by /etf-holder/{symbol}
_ETF_HOLDINGS = [
    {"asset": "MSFT", "name": "Microsoft Corp",  "weight": 0.0741},
    {"asset": "AAPL", "name": "Apple Inc",       "weight": 0.0500},
    {"asset": "NVDA", "name": "NVIDIA Corp",     "weight": 0.0410},
]

# Profile for a covered-call ETF (JEPI-like)
_JEPI_PROFILE = [
    {
        "symbol":      "JEPI",
        "longName":    "JPMorgan Equity Premium Income ETF",
        "description": (
            "The fund invests in equities and employs an options overlay "
            "strategy consisting of out-of-the-money S&P 500 Index "
            "covered call options to generate income."
        ),
        "mktCap": 35_000_000_000.0,
        "sector": None,
    }
]

# Profile for a plain dividend ETF (SCHD-like) — no covered-call language
_SCHD_PROFILE = [
    {
        "symbol":      "SCHD",
        "longName":    "Schwab US Dividend Equity ETF",
        "description": (
            "The fund seeks to track as closely as possible, before fees and "
            "expenses, the total return of the Dow Jones U.S. Dividend 100 Index."
        ),
        "mktCap": 60_000_000_000.0,
        "sector": None,
    }
]


# ---------------------------------------------------------------------------
# Tests — get_dividend_history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dividend_history_field_mapping():
    """FMP 'date' → 'ex_date', 'paymentDate' → 'payment_date', 'dividend' → 'amount'."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "stock_dividend" in path:
            return _DIV_HISTORY_RESPONSE
        return _QUOTE_RESPONSE

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_dividend_history("AAPL")

    assert len(result) == 2

    first = result[0]
    assert first["ex_date"]      == "2024-09-19"
    assert first["payment_date"] == "2024-10-01"
    assert first["amount"]       == 0.52


@pytest.mark.asyncio
async def test_get_dividend_history_frequency_is_none():
    """FMP historical dividends endpoint omits frequency — it must always be None."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "stock_dividend" in path:
            return _DIV_HISTORY_RESPONSE
        return _QUOTE_RESPONSE

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_dividend_history("AAPL")

    for record in result:
        assert record["frequency"] is None, (
            f"Expected frequency=None, got {record['frequency']!r}"
        )


@pytest.mark.asyncio
async def test_get_dividend_history_yield_pct_computed_from_current_price():
    """yield_pct = (amount / current_price) * 100, rounded to 4 decimal places."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "stock_dividend" in path:
            return _DIV_HISTORY_RESPONSE
        return _QUOTE_RESPONSE  # price = 200.0

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_dividend_history("AAPL")

    first = result[0]
    expected_yield = round((0.52 / 200.0) * 100, 4)
    assert first["yield_pct"] is not None
    assert abs(first["yield_pct"] - expected_yield) < 1e-6


@pytest.mark.asyncio
async def test_get_dividend_history_yield_pct_none_when_price_unavailable():
    """yield_pct is None when the quote fetch fails."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "stock_dividend" in path:
            return _DIV_HISTORY_RESPONSE
        return []  # empty quote → no current price

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_dividend_history("AAPL")

    for record in result:
        assert record["yield_pct"] is None


@pytest.mark.asyncio
async def test_get_dividend_history_empty_returns_empty_list():
    """When the FMP response has no historical records, an empty list is returned."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "stock_dividend" in path:
            return {"historical": []}
        return _QUOTE_RESPONSE

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_dividend_history("AAPL")

    assert result == []


# ---------------------------------------------------------------------------
# Tests — get_etf_holdings (covered_call detection)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_etf_holdings_covered_call_true_for_jepi():
    """A profile description containing 'covered call' sets covered_call=True."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "etf-holder" in path:
            return _ETF_HOLDINGS
        return _JEPI_PROFILE  # description contains "covered call"

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_etf_holdings("JEPI")

    assert result["covered_call"] is True


@pytest.mark.asyncio
async def test_get_etf_holdings_covered_call_false_for_schd():
    """A profile description with no covered-call language sets covered_call=False."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "etf-holder" in path:
            return _ETF_HOLDINGS
        return _SCHD_PROFILE  # plain dividend ETF, no covered-call language

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_etf_holdings("SCHD")

    assert result["covered_call"] is False


@pytest.mark.asyncio
async def test_get_etf_holdings_weight_decimal_to_percent():
    """Holdings weight is a decimal (0.0741) that must be converted to percent (7.41)."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "etf-holder" in path:
            return _ETF_HOLDINGS
        return _SCHD_PROFILE

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_etf_holdings("SCHD")

    holdings = result["top_holdings"]
    assert len(holdings) == 3

    first = holdings[0]
    assert first["ticker"]     == "MSFT"
    assert first["name"]       == "Microsoft Corp"
    # 0.0741 * 100 = 7.41
    assert abs(first["weight_pct"] - 7.41) < 1e-4


@pytest.mark.asyncio
async def test_get_etf_holdings_aum_from_profile_mkt_cap():
    """'aum' is populated from the profile's 'mktCap' field."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "etf-holder" in path:
            return _ETF_HOLDINGS
        return _SCHD_PROFILE  # mktCap = 60_000_000_000

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_etf_holdings("SCHD")

    assert result["aum"] == 60_000_000_000.0


@pytest.mark.asyncio
async def test_get_etf_holdings_expense_ratio_is_none():
    """FMP profile does not expose expense_ratio — it must always be None."""
    client = _client()

    async def _mock_get(path, **kwargs):
        if "etf-holder" in path:
            return _ETF_HOLDINGS
        return _JEPI_PROFILE

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_etf_holdings("JEPI")

    assert result["expense_ratio"] is None


@pytest.mark.asyncio
async def test_get_etf_holdings_buy_write_description_also_sets_covered_call():
    """A profile description containing 'buy-write' also sets covered_call=True."""
    client = _client()

    buy_write_profile = [
        {
            "symbol":      "XYLD",
            "description": "Employs a buy-write strategy to generate high current income.",
            "mktCap": 1_000_000_000.0,
        }
    ]

    async def _mock_get(path, **kwargs):
        if "etf-holder" in path:
            return _ETF_HOLDINGS
        return buy_write_profile

    with patch.object(client, "_get", new=AsyncMock(side_effect=_mock_get)):
        result = await client.get_etf_holdings("XYLD")

    assert result["covered_call"] is True
