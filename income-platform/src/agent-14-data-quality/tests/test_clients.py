# src/agent-14-data-quality/tests/test_clients.py
from unittest.mock import MagicMock, patch
import pytest
from app.clients.fmp import FMPHealClient
from app.clients.massive import MASSIVEHealClient


class TestFMPHealClient:
    def test_fetch_price_returns_float(self):
        client = FMPHealClient(api_key="test", base_url="https://financialmodelingprep.com/stable")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"price": 42.5}]
        with patch("httpx.Client.get", return_value=mock_resp):
            result = client.fetch_field("AAPL", "price")
        assert result == 42.5

    def test_fetch_missing_field_returns_none(self):
        client = FMPHealClient(api_key="test", base_url="https://financialmodelingprep.com/stable")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{}]
        with patch("httpx.Client.get", return_value=mock_resp):
            result = client.fetch_field("AAPL", "nav_value")
        assert result is None

    def test_http_error_returns_none(self):
        client = FMPHealClient(api_key="test", base_url="https://financialmodelingprep.com/stable")
        import httpx
        with patch("httpx.Client.get", side_effect=httpx.TimeoutException("timeout")):
            result = client.fetch_field("AAPL", "price")
        assert result is None

    def test_fetch_nav_value_uses_etf_info_endpoint(self):
        client = FMPHealClient(api_key="test", base_url="https://financialmodelingprep.com/stable")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"navPrice": 25.10}]
        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            result = client.fetch_field("JEPI", "nav_value")
        call_url = mock_get.call_args[0][0]
        assert "etf-info" in call_url
        assert result == 25.10


class TestMASSIVEHealClient:
    def test_fetch_price_returns_float(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": {"day": {"c": 55.0}}}
        with patch("httpx.Client.get", return_value=mock_resp):
            result = client.fetch_field("AAPL", "price")
        assert result == 55.0

    def test_rate_limited_returns_none_with_diagnostic(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        with patch("httpx.Client.get", return_value=mock_resp):
            result, diag = client.fetch_field_with_diagnostic("AAPL", "price")
        assert result is None
        assert diag["code"] == "RATE_LIMITED"

    def test_sma_50_uses_indicators_sma_endpoint(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": {"values": [{"value": 185.0}]}}
        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            result = client.fetch_field("AAPL", "sma_50")
        call_url = mock_get.call_args[0][0]
        assert "/v1/indicators/sma/" in call_url
        assert result == 185.0

    def test_rsi_14d_uses_indicators_rsi_endpoint(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": {"values": [{"value": 62.5}]}}
        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            result = client.fetch_field("AAPL", "rsi_14d")
        call_url = mock_get.call_args[0][0]
        assert "/v1/indicators/rsi/" in call_url
        assert result == 62.5

    def test_week52_high_uses_aggs_endpoint(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"h": 210.0, "l": 180.0}, {"h": 220.0, "l": 175.0}]}
        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            result = client.fetch_field("AAPL", "week52_high")
        call_url = mock_get.call_args[0][0]
        assert "/v2/aggs/ticker/" in call_url
        assert result == 220.0

    def test_auth_error_returns_auth_error_diagnostic(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        with patch("httpx.Client.get", return_value=mock_resp):
            result, diag = client.fetch_field_with_diagnostic("AAPL", "price")
        assert result is None
        assert diag["code"] == "AUTH_ERROR"

    def test_not_found_returns_ticker_not_found_diagnostic(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("httpx.Client.get", return_value=mock_resp):
            result, diag = client.fetch_field_with_diagnostic("ZZZZZ", "price")
        assert result is None
        assert diag["code"] == "TICKER_NOT_FOUND"

    def test_malformed_sma_response_returns_none(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": {}}  # missing 'values' key
        with patch("httpx.Client.get", return_value=mock_resp):
            result, diag = client.fetch_field_with_diagnostic("AAPL", "sma_50")
        assert result is None
        assert diag["code"] == "FIELD_NOT_SUPPORTED"
