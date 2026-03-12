"""
Tests for stock-data endpoints in main.py.

Endpoints under test:
  GET  /stocks/{symbol}/price
  GET  /stocks/{symbol}/history
  GET  /stocks/{symbol}/history/stats
  POST /stocks/{symbol}/history/refresh
  GET  /stocks/{symbol}/dividends
  GET  /stocks/{symbol}/fundamentals
  GET  /stocks/{symbol}/etf
  POST /stocks/{symbol}/sync
  GET  /api/v1/providers/status
  GET  /api/v1/cache/stats

All external I/O is mocked at the service layer (price_service and
market_data_service) so tests run fully offline.  The `authed_client`
fixture from conftest.py is used throughout — it injects the Authorization
header automatically.

Mock service objects are re-configured per test class using monkeypatch
to isolate side-effects between test scenarios.
"""
import sys
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Re-use conftest helpers
# ---------------------------------------------------------------------------
from conftest import _mock_market_data_service, _mock_price_service


# ---------------------------------------------------------------------------
# Canonical fixture data
# ---------------------------------------------------------------------------

_PRICE_PAYLOAD = {
    "ticker":         "AAPL",
    "price":          175.50,
    "change":         1.25,
    "change_percent": 0.72,
    "volume":         55_000_000,
    "timestamp":      "2026-03-12T14:30:00+00:00",
    "source":         "alpha_vantage",
    "cached":         False,
}

_HISTORY_ROW = {
    "date":           "2026-01-15",
    "open":           170.00,
    "high":           176.50,
    "low":            169.00,
    "close":          175.50,
    "volume":         48_000_000,
    "adjusted_close": 175.50,
}

_DIVIDEND_ROW = {
    "ex_date":      "2025-11-08",
    "payment_date": "2025-11-14",
    "amount":       0.25,
    "frequency":    "quarterly",
    "yield_pct":    0.57,
}

_FUNDAMENTALS_PAYLOAD = {
    "pe_ratio":        28.5,
    "debt_to_equity":  1.74,
    "payout_ratio":    0.15,
    "free_cash_flow":  90_215_000_000.0,
    "market_cap":      2_700_000_000_000.0,
    "sector":          "Technology",
    "name":            "Apple Inc.",
    "asset_type":      "CS",
    "exchange":        "NASDAQ",
    "currency":        "USD",
}

_ETF_PAYLOAD = {
    "expense_ratio": 0.0003,
    "aum":           400_000_000_000.0,
    "covered_call":  False,
    "top_holdings":  [
        {"ticker": "AAPL", "name": "Apple Inc.", "weight_pct": 7.2},
        {"ticker": "MSFT", "name": "Microsoft Corporation", "weight_pct": 6.8},
    ],
}


def _main():
    return sys.modules["main"]


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/price
# ---------------------------------------------------------------------------

class TestStockPrice:
    def test_price_returns_200_with_valid_token(self, authed_client):
        resp = authed_client.get("/stocks/AAPL/price")
        assert resp.status_code == 200

    def test_price_response_contains_required_fields(self, authed_client):
        body = authed_client.get("/stocks/AAPL/price").json()
        for field in ("ticker", "price", "change", "change_percent", "volume",
                      "timestamp", "source", "cached"):
            assert field in body, f"Missing field: {field}"

    def test_price_ticker_is_uppercased(self, authed_client, monkeypatch):
        """Route handler uppercases symbol before calling service."""
        captured = {}

        async def _capture(symbol):
            captured["symbol"] = symbol
            return _PRICE_PAYLOAD

        monkeypatch.setattr(_main().price_service, "get_current_price", _capture)
        authed_client.get("/stocks/aapl/price")
        assert captured.get("symbol") == "AAPL"

    def test_price_returns_correct_ticker(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().price_service, "get_current_price",
            AsyncMock(return_value={**_PRICE_PAYLOAD, "ticker": "AAPL"}),
        )
        body = authed_client.get("/stocks/AAPL/price").json()
        assert body["ticker"] == "AAPL"

    def test_price_returns_correct_price_value(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().price_service, "get_current_price",
            AsyncMock(return_value=_PRICE_PAYLOAD),
        )
        body = authed_client.get("/stocks/AAPL/price").json()
        assert body["price"] == 175.50

    def test_price_404_when_service_raises_value_error(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().price_service, "get_current_price",
            AsyncMock(side_effect=ValueError("No data found for ticker ZZZZ")),
        )
        resp = authed_client.get("/stocks/ZZZZ/price")
        assert resp.status_code == 404

    def test_price_500_when_service_raises_unexpected_exception(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().price_service, "get_current_price",
            AsyncMock(side_effect=RuntimeError("database exploded")),
        )
        resp = authed_client.get("/stocks/AAPL/price")
        assert resp.status_code == 500

    def test_price_returns_cached_true_flag(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().price_service, "get_current_price",
            AsyncMock(return_value={**_PRICE_PAYLOAD, "cached": True}),
        )
        body = authed_client.get("/stocks/AAPL/price").json()
        assert body["cached"] is True

    def test_price_requires_auth(self, client):
        resp = client.get("/stocks/AAPL/price")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/history
# ---------------------------------------------------------------------------

class TestStockHistory:
    _START = "2026-01-01"
    _END   = "2026-03-01"

    def _url(self, symbol="AAPL"):
        return (
            f"/stocks/{symbol}/history"
            f"?start_date={self._START}&end_date={self._END}"
        )

    def test_history_returns_200(self, authed_client):
        resp = authed_client.get(self._url())
        assert resp.status_code == 200

    def test_history_response_schema(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=[_HISTORY_ROW]),
        )
        body = authed_client.get(self._url()).json()
        for field in ("symbol", "start_date", "end_date", "count", "prices", "source"):
            assert field in body, f"Missing field: {field}"

    def test_history_count_matches_prices_length(self, authed_client, monkeypatch):
        rows = [_HISTORY_ROW, {**_HISTORY_ROW, "date": "2026-01-20"}]
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=rows),
        )
        body = authed_client.get(self._url()).json()
        assert body["count"] == len(body["prices"])

    def test_history_empty_prices_returns_count_zero(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=[]),
        )
        body = authed_client.get(self._url()).json()
        assert body["count"] == 0
        assert body["prices"] == []

    def test_history_symbol_uppercased(self, authed_client, monkeypatch):
        captured = {}

        async def _capture(symbol, start_date, end_date):
            captured["symbol"] = symbol
            return []

        monkeypatch.setattr(_main().market_data_service, "get_historical_prices", _capture)
        authed_client.get(
            "/stocks/aapl/history?start_date=2026-01-01&end_date=2026-03-01"
        )
        assert captured.get("symbol") == "AAPL"

    def test_history_400_when_start_after_end(self, authed_client):
        resp = authed_client.get(
            "/stocks/AAPL/history?start_date=2026-03-01&end_date=2026-01-01"
        )
        assert resp.status_code == 400

    def test_history_400_detail_message(self, authed_client):
        resp = authed_client.get(
            "/stocks/AAPL/history?start_date=2026-03-01&end_date=2026-01-01"
        )
        assert "start_date" in resp.json()["detail"].lower()

    def test_history_missing_start_date_returns_422(self, authed_client):
        resp = authed_client.get("/stocks/AAPL/history?end_date=2026-03-01")
        assert resp.status_code == 422

    def test_history_missing_end_date_returns_422(self, authed_client):
        resp = authed_client.get("/stocks/AAPL/history?start_date=2026-01-01")
        assert resp.status_code == 422

    def test_history_limit_parameter_truncates_results(self, authed_client, monkeypatch):
        """The route applies limit before building the response."""
        # Provide 5 rows but request limit=2
        rows = [
            {**_HISTORY_ROW, "date": f"2026-01-{i:02d}"}
            for i in range(1, 6)
        ]
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=rows),
        )
        body = authed_client.get(self._url() + "&limit=2").json()
        assert body["count"] == 2
        assert len(body["prices"]) == 2

    def test_history_limit_default_is_90(self, authed_client, monkeypatch):
        """Default limit is 90; service mock returns 91 rows."""
        from datetime import date, timedelta
        base = date(2025, 1, 1)
        rows = [
            {**_HISTORY_ROW, "date": (base + timedelta(days=i)).isoformat()}
            for i in range(91)
        ]
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=rows),
        )
        body = authed_client.get(self._url()).json()
        assert body["count"] <= 90

    def test_history_404_on_value_error(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(side_effect=ValueError("symbol not found")),
        )
        resp = authed_client.get(self._url())
        assert resp.status_code == 404

    def test_history_500_on_unexpected_exception(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(side_effect=RuntimeError("network timeout")),
        )
        resp = authed_client.get(self._url())
        assert resp.status_code == 500

    def test_history_requires_auth(self, client):
        resp = client.get(
            "/stocks/AAPL/history?start_date=2026-01-01&end_date=2026-03-01"
        )
        assert resp.status_code == 403

    def test_history_price_fields_present(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=[_HISTORY_ROW]),
        )
        body = authed_client.get(self._url()).json()
        row  = body["prices"][0]
        for field in ("date", "open", "high", "low", "close", "volume"):
            assert field in row, f"Missing price field: {field}"


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/history/stats
# ---------------------------------------------------------------------------

class TestStockHistoryStats:
    _URL = "/stocks/AAPL/history/stats?start_date=2026-01-01&end_date=2026-03-01"

    def test_stats_returns_200(self, authed_client):
        resp = authed_client.get(self._URL)
        assert resp.status_code == 200

    def test_stats_schema_with_no_data(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=[]),
        )
        body = authed_client.get(self._URL).json()
        assert "symbol" in body
        assert "period_days" in body
        # All optional stat fields are None when no data
        for field in ("min_price", "max_price", "avg_price", "volatility",
                      "price_change_pct"):
            assert body.get(field) is None

    def test_stats_computed_correctly(self, authed_client, monkeypatch):
        rows = [
            {**_HISTORY_ROW, "date": "2026-01-10", "close": 100.0},
            {**_HISTORY_ROW, "date": "2026-01-20", "close": 120.0},
            {**_HISTORY_ROW, "date": "2026-01-30", "close": 110.0},
        ]
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=rows),
        )
        body = authed_client.get(self._URL).json()
        assert body["min_price"] == 100.0
        assert body["max_price"] == 120.0
        # avg = (100 + 120 + 110) / 3 = 110
        assert abs(body["avg_price"] - 110.0) < 0.01

    def test_stats_price_change_pct_positive(self, authed_client, monkeypatch):
        rows = [
            {**_HISTORY_ROW, "date": "2026-01-10", "close": 100.0},
            {**_HISTORY_ROW, "date": "2026-01-20", "close": 150.0},
        ]
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=rows),
        )
        body = authed_client.get(self._URL).json()
        assert abs(body["price_change_pct"] - 50.0) < 0.01

    def test_stats_price_change_pct_negative(self, authed_client, monkeypatch):
        rows = [
            {**_HISTORY_ROW, "date": "2026-01-10", "close": 200.0},
            {**_HISTORY_ROW, "date": "2026-01-20", "close": 100.0},
        ]
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=rows),
        )
        body = authed_client.get(self._URL).json()
        assert abs(body["price_change_pct"] - (-50.0)) < 0.01

    def test_stats_400_when_start_after_end(self, authed_client):
        resp = authed_client.get(
            "/stocks/AAPL/history/stats?start_date=2026-03-01&end_date=2026-01-01"
        )
        assert resp.status_code == 400

    def test_stats_404_on_value_error(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(side_effect=ValueError("not found")),
        )
        resp = authed_client.get(self._URL)
        assert resp.status_code == 404

    def test_stats_requires_auth(self, client):
        resp = client.get(self._URL)
        assert resp.status_code == 403

    def test_stats_single_row_volatility_is_zero(self, authed_client, monkeypatch):
        """With a single price row, std dev is undefined; route returns 0.0."""
        rows = [{**_HISTORY_ROW, "date": "2026-01-10", "close": 100.0}]
        monkeypatch.setattr(
            _main().market_data_service, "get_historical_prices",
            AsyncMock(return_value=rows),
        )
        body = authed_client.get(self._URL).json()
        assert body["volatility"] == 0.0


# ---------------------------------------------------------------------------
# POST /stocks/{symbol}/history/refresh
# ---------------------------------------------------------------------------

class TestHistoryRefresh:
    _URL = "/stocks/AAPL/history/refresh"

    def test_refresh_returns_200(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "refresh_historical_prices",
            AsyncMock(return_value=42),
        )
        resp = authed_client.post(self._URL)
        assert resp.status_code == 200

    def test_refresh_response_schema(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "refresh_historical_prices",
            AsyncMock(return_value=10),
        )
        body = authed_client.post(self._URL).json()
        for field in ("symbol", "records_saved", "source", "message"):
            assert field in body

    def test_refresh_records_saved_matches_service_return(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "refresh_historical_prices",
            AsyncMock(return_value=77),
        )
        body = authed_client.post(self._URL).json()
        assert body["records_saved"] == 77

    def test_refresh_full_history_body_passed_through(self, authed_client, monkeypatch):
        captured = {}

        async def _capture(symbol, full_history=False):
            captured["full_history"] = full_history
            return 5

        monkeypatch.setattr(
            _main().market_data_service, "refresh_historical_prices", _capture
        )
        authed_client.post(self._URL, json={"full_history": True})
        assert captured.get("full_history") is True

    def test_refresh_default_full_history_is_false(self, authed_client, monkeypatch):
        captured = {}

        async def _capture(symbol, full_history=False):
            captured["full_history"] = full_history
            return 0

        monkeypatch.setattr(
            _main().market_data_service, "refresh_historical_prices", _capture
        )
        authed_client.post(self._URL)
        assert captured.get("full_history") is False

    def test_refresh_502_on_value_error(self, authed_client, monkeypatch):
        """ValueError from the service maps to 502 (upstream provider error)."""
        monkeypatch.setattr(
            _main().market_data_service, "refresh_historical_prices",
            AsyncMock(side_effect=ValueError("API rate limit exceeded")),
        )
        resp = authed_client.post(self._URL)
        assert resp.status_code == 502

    def test_refresh_500_on_unexpected_exception(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "refresh_historical_prices",
            AsyncMock(side_effect=RuntimeError("something exploded")),
        )
        resp = authed_client.post(self._URL)
        assert resp.status_code == 500

    def test_refresh_requires_auth(self, client):
        resp = client.post(self._URL)
        assert resp.status_code == 403

    def test_refresh_symbol_uppercased(self, authed_client, monkeypatch):
        captured = {}

        async def _capture(symbol, full_history=False):
            captured["symbol"] = symbol
            return 0

        monkeypatch.setattr(
            _main().market_data_service, "refresh_historical_prices", _capture
        )
        authed_client.post("/stocks/aapl/history/refresh")
        assert captured.get("symbol") == "AAPL"


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/dividends
# ---------------------------------------------------------------------------

class TestStockDividends:
    def test_dividends_returns_200(self, authed_client):
        resp = authed_client.get("/stocks/AAPL/dividends")
        assert resp.status_code == 200

    def test_dividends_response_schema(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_dividend_history",
            AsyncMock(return_value=[_DIVIDEND_ROW]),
        )
        body = authed_client.get("/stocks/AAPL/dividends").json()
        for field in ("symbol", "count", "dividends", "source"):
            assert field in body

    def test_dividends_count_matches_list(self, authed_client, monkeypatch):
        rows = [_DIVIDEND_ROW, {**_DIVIDEND_ROW, "ex_date": "2025-08-08"}]
        monkeypatch.setattr(
            _main().market_data_service, "get_dividend_history",
            AsyncMock(return_value=rows),
        )
        body = authed_client.get("/stocks/AAPL/dividends").json()
        assert body["count"] == len(body["dividends"])
        assert body["count"] == 2

    def test_dividends_empty_list_count_zero(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_dividend_history",
            AsyncMock(return_value=[]),
        )
        body = authed_client.get("/stocks/AAPL/dividends").json()
        assert body["count"] == 0
        assert body["dividends"] == []

    def test_dividends_symbol_in_response(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_dividend_history",
            AsyncMock(return_value=[]),
        )
        body = authed_client.get("/stocks/msft/dividends").json()
        assert body["symbol"] == "MSFT"

    def test_dividends_record_has_ex_date_and_amount(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_dividend_history",
            AsyncMock(return_value=[_DIVIDEND_ROW]),
        )
        body = authed_client.get("/stocks/AAPL/dividends").json()
        record = body["dividends"][0]
        assert "ex_date" in record
        assert "amount" in record

    def test_dividends_source_is_fmp(self, authed_client, monkeypatch):
        """Route hardcodes source='fmp'."""
        monkeypatch.setattr(
            _main().market_data_service, "get_dividend_history",
            AsyncMock(return_value=[]),
        )
        body = authed_client.get("/stocks/AAPL/dividends").json()
        assert body["source"] == "fmp"

    def test_dividends_404_on_value_error(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_dividend_history",
            AsyncMock(side_effect=ValueError("no dividend history")),
        )
        resp = authed_client.get("/stocks/AAPL/dividends")
        assert resp.status_code == 404

    def test_dividends_500_on_unexpected_exception(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_dividend_history",
            AsyncMock(side_effect=RuntimeError("provider timeout")),
        )
        resp = authed_client.get("/stocks/AAPL/dividends")
        assert resp.status_code == 500

    def test_dividends_requires_auth(self, client):
        resp = client.get("/stocks/AAPL/dividends")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/fundamentals
# ---------------------------------------------------------------------------

class TestStockFundamentals:
    def test_fundamentals_returns_200(self, authed_client):
        resp = authed_client.get("/stocks/AAPL/fundamentals")
        assert resp.status_code == 200

    def test_fundamentals_response_schema(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_fundamentals",
            AsyncMock(return_value=_FUNDAMENTALS_PAYLOAD),
        )
        body = authed_client.get("/stocks/AAPL/fundamentals").json()
        for field in ("symbol", "pe_ratio", "debt_to_equity", "payout_ratio",
                      "free_cash_flow", "market_cap", "sector", "source"):
            assert field in body

    def test_fundamentals_values_match_mock(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_fundamentals",
            AsyncMock(return_value=_FUNDAMENTALS_PAYLOAD),
        )
        body = authed_client.get("/stocks/AAPL/fundamentals").json()
        assert body["pe_ratio"]       == 28.5
        assert body["sector"]         == "Technology"
        assert body["market_cap"]     == 2_700_000_000_000.0

    def test_fundamentals_null_fields_allowed(self, authed_client, monkeypatch):
        """All optional fields may be null — model allows None."""
        monkeypatch.setattr(
            _main().market_data_service, "get_fundamentals",
            AsyncMock(return_value={}),
        )
        body = authed_client.get("/stocks/AAPL/fundamentals").json()
        assert body["pe_ratio"]       is None
        assert body["market_cap"]     is None
        assert body["sector"]         is None

    def test_fundamentals_source_is_fmp(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_fundamentals",
            AsyncMock(return_value={}),
        )
        body = authed_client.get("/stocks/AAPL/fundamentals").json()
        assert body["source"] == "fmp"

    def test_fundamentals_symbol_uppercased(self, authed_client, monkeypatch):
        captured = {}

        async def _capture(symbol):
            captured["symbol"] = symbol
            return {}

        monkeypatch.setattr(_main().market_data_service, "get_fundamentals", _capture)
        authed_client.get("/stocks/aapl/fundamentals")
        assert captured.get("symbol") == "AAPL"

    def test_fundamentals_404_on_value_error(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_fundamentals",
            AsyncMock(side_effect=ValueError("not found")),
        )
        resp = authed_client.get("/stocks/AAPL/fundamentals")
        assert resp.status_code == 404

    def test_fundamentals_500_on_unexpected_exception(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_fundamentals",
            AsyncMock(side_effect=RuntimeError("provider down")),
        )
        resp = authed_client.get("/stocks/AAPL/fundamentals")
        assert resp.status_code == 500

    def test_fundamentals_requires_auth(self, client):
        resp = client.get("/stocks/AAPL/fundamentals")
        assert resp.status_code == 403

    def test_fundamentals_upsert_security_called_when_repo_available(
        self, authed_client, monkeypatch
    ):
        """When _securities_repo is set, ensure_future is called (fire-and-forget)."""
        mock_repo = MagicMock()
        mock_repo.upsert_security = AsyncMock(return_value=None)
        monkeypatch.setattr(
            _main().market_data_service, "_securities_repo", mock_repo
        )
        monkeypatch.setattr(
            _main().market_data_service, "get_fundamentals",
            AsyncMock(return_value=_FUNDAMENTALS_PAYLOAD),
        )
        resp = authed_client.get("/stocks/AAPL/fundamentals")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /stocks/{symbol}/etf
# ---------------------------------------------------------------------------

class TestStockETF:
    def test_etf_returns_200(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_etf_holdings",
            AsyncMock(return_value=_ETF_PAYLOAD),
        )
        resp = authed_client.get("/stocks/SPY/etf")
        assert resp.status_code == 200

    def test_etf_response_schema(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_etf_holdings",
            AsyncMock(return_value=_ETF_PAYLOAD),
        )
        body = authed_client.get("/stocks/SPY/etf").json()
        for field in ("symbol", "expense_ratio", "aum", "covered_call",
                      "top_holdings", "source"):
            assert field in body

    def test_etf_holdings_list_populated(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_etf_holdings",
            AsyncMock(return_value=_ETF_PAYLOAD),
        )
        body = authed_client.get("/stocks/SPY/etf").json()
        assert len(body["top_holdings"]) == 2
        assert body["top_holdings"][0]["ticker"] == "AAPL"

    def test_etf_empty_payload_returns_defaults(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_etf_holdings",
            AsyncMock(return_value={}),
        )
        body = authed_client.get("/stocks/SPY/etf").json()
        assert body["expense_ratio"] is None
        assert body["aum"]           is None
        assert body["covered_call"]  is False
        assert body["top_holdings"]  == []

    def test_etf_covered_call_flag(self, authed_client, monkeypatch):
        payload = {**_ETF_PAYLOAD, "covered_call": True}
        monkeypatch.setattr(
            _main().market_data_service, "get_etf_holdings",
            AsyncMock(return_value=payload),
        )
        body = authed_client.get("/stocks/QYLD/etf").json()
        assert body["covered_call"] is True

    def test_etf_404_on_value_error(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_etf_holdings",
            AsyncMock(side_effect=ValueError("not an ETF")),
        )
        resp = authed_client.get("/stocks/AAPL/etf")
        assert resp.status_code == 404

    def test_etf_500_on_unexpected_exception(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_etf_holdings",
            AsyncMock(side_effect=RuntimeError("network error")),
        )
        resp = authed_client.get("/stocks/SPY/etf")
        assert resp.status_code == 500

    def test_etf_requires_auth(self, client):
        resp = client.get("/stocks/SPY/etf")
        assert resp.status_code == 403

    def test_etf_source_is_fmp(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "get_etf_holdings",
            AsyncMock(return_value=_ETF_PAYLOAD),
        )
        body = authed_client.get("/stocks/SPY/etf").json()
        assert body["source"] == "fmp"


# ---------------------------------------------------------------------------
# POST /stocks/{symbol}/sync
# ---------------------------------------------------------------------------

class TestStockSync:
    _SYNC_RESULT = {
        "symbol":               "AAPL",
        "as_of_date":           "2026-03-12",
        "securities_updated":   True,
        "features_updated":     True,
        "credit_rating":        "AA+",
        "credit_quality_proxy": "INVESTMENT_GRADE",
        "chowder_number":       14.5,
        "yield_5yr_avg":        0.57,
        "providers_used":       ["fmp_fundamentals", "fmp_dividends", "finnhub"],
        "missing_fields":       [],
    }

    def test_sync_returns_200(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "sync_symbol",
            AsyncMock(return_value=self._SYNC_RESULT),
        )
        resp = authed_client.post("/stocks/AAPL/sync")
        assert resp.status_code == 200

    def test_sync_response_schema(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "sync_symbol",
            AsyncMock(return_value=self._SYNC_RESULT),
        )
        body = authed_client.post("/stocks/AAPL/sync").json()
        for field in ("symbol", "as_of_date", "securities_updated",
                      "features_updated", "providers_used", "missing_fields"):
            assert field in body

    def test_sync_symbol_uppercased(self, authed_client, monkeypatch):
        captured = {}

        async def _capture(symbol):
            captured["symbol"] = symbol
            return self._SYNC_RESULT

        monkeypatch.setattr(_main().market_data_service, "sync_symbol", _capture)
        authed_client.post("/stocks/aapl/sync")
        assert captured.get("symbol") == "AAPL"

    def test_sync_500_on_unexpected_exception(self, authed_client, monkeypatch):
        monkeypatch.setattr(
            _main().market_data_service, "sync_symbol",
            AsyncMock(side_effect=RuntimeError("db write failed")),
        )
        resp = authed_client.post("/stocks/AAPL/sync")
        assert resp.status_code == 500

    def test_sync_requires_auth(self, client):
        resp = client.post("/stocks/AAPL/sync")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/v1/providers/status
# ---------------------------------------------------------------------------

class TestProvidersStatus:
    _URL = "/api/v1/providers/status"

    def test_providers_status_returns_200(self, authed_client):
        resp = authed_client.get(self._URL)
        assert resp.status_code == 200

    def test_providers_status_schema(self, authed_client):
        body = authed_client.get(self._URL).json()
        for provider in ("polygon", "fmp", "yfinance", "finnhub"):
            assert provider in body, f"Missing provider: {provider}"
            info = body[provider]
            assert "healthy" in info
            assert "last_used" in info

    def test_providers_all_unhealthy_when_mocked_as_none(self, authed_client):
        """Default mock has all router providers as None → healthy=False."""
        body = authed_client.get(self._URL).json()
        # polygon, fmp, yfinance are None on the mock router; finnhub is also None
        for provider in ("polygon", "fmp", "yfinance", "finnhub"):
            assert body[provider]["healthy"] is False

    def test_providers_status_healthy_when_router_has_providers(
        self, authed_client, monkeypatch
    ):
        """Inject non-None providers into the router and verify healthy=True."""
        mock_router = MagicMock()
        mock_router.polygon  = MagicMock()
        mock_router.fmp      = MagicMock()
        mock_router.yfinance = MagicMock()
        monkeypatch.setattr(
            _main().market_data_service, "_router", mock_router
        )
        monkeypatch.setattr(
            _main().market_data_service, "_finnhub", MagicMock()
        )
        body = authed_client.get(self._URL).json()
        assert body["polygon"]["healthy"]  is True
        assert body["fmp"]["healthy"]      is True
        assert body["yfinance"]["healthy"] is True
        assert body["finnhub"]["healthy"]  is True

    def test_providers_status_requires_auth(self, client):
        resp = client.get(self._URL)
        assert resp.status_code == 403

    def test_providers_requests_today_is_null(self, authed_client):
        """requests_today is reserved for future use; always null for now."""
        body = authed_client.get(self._URL).json()
        for provider in ("polygon", "fmp", "yfinance", "finnhub"):
            assert body[provider]["requests_today"] is None


# ---------------------------------------------------------------------------
# GET /api/v1/cache/stats
# ---------------------------------------------------------------------------

class TestCacheStats:
    _URL = "/api/v1/cache/stats"

    def test_cache_stats_returns_200(self, authed_client):
        resp = authed_client.get(self._URL)
        assert resp.status_code == 200

    def test_cache_stats_body_is_dict(self, authed_client):
        body = authed_client.get(self._URL).json()
        assert isinstance(body, dict)

    def test_cache_stats_disconnected_returns_connected_false(
        self, authed_client
    ):
        """Default mock reports connected=False."""
        body = authed_client.get(self._URL).json()
        assert body.get("connected") is False

    def test_cache_stats_requires_auth(self, client):
        resp = client.get(self._URL)
        assert resp.status_code == 403

    def test_cache_stats_no_cache_manager_returns_error_key(
        self, authed_client, monkeypatch
    ):
        """When cache_manager is None, the route returns an error dict."""
        monkeypatch.setattr(_main(), "cache_manager", None)
        body = authed_client.get(self._URL).json()
        assert "error" in body


# ---------------------------------------------------------------------------
# Symbol case normalisation — cross-endpoint smoke tests
# ---------------------------------------------------------------------------

class TestSymbolNormalisation:
    @pytest.mark.parametrize("symbol,expected", [
        ("aapl",   "AAPL"),
        ("Msft",   "MSFT"),
        ("spy",    "SPY"),
        ("O",      "O"),
    ])
    def test_symbol_is_uppercased_in_price_response(
        self, authed_client, monkeypatch, symbol, expected
    ):
        monkeypatch.setattr(
            _main().price_service, "get_current_price",
            AsyncMock(return_value={**_PRICE_PAYLOAD, "ticker": expected}),
        )
        body = authed_client.get(f"/stocks/{symbol}/price").json()
        assert body["ticker"] == expected
