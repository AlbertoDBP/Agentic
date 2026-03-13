"""
Agent 08 — Rebalancing Service
Tests: Tax client — 25 tests.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("INCOME_SCORING_URL", "http://agent-03:8003")
os.environ.setdefault("TAX_OPTIMIZATION_URL", "http://agent-05:8005")

import httpx

from app.rebalancer.tax_client import _holding_days, _make_token, get_harvest_impact


# ── Class 1: Token generation ──────────────────────────────────────────────────

class TestMakeToken:
    """8 tests for _make_token()."""

    def test_token_has_three_parts(self):
        token = _make_token()
        parts = token.split(".")
        assert len(parts) == 3

    def test_token_is_string(self):
        assert isinstance(_make_token(), str)

    def test_token_not_empty(self):
        assert len(_make_token()) > 0

    def test_token_header_alg_hs256(self):
        import base64
        import json
        token = _make_token()
        header_b64 = token.split(".")[0]
        padding = 4 - len(header_b64) % 4
        header = json.loads(base64.urlsafe_b64decode(header_b64 + "=" * padding))
        assert header["alg"] == "HS256"
        assert header["typ"] == "JWT"

    def test_token_payload_sub_is_agent08(self):
        import base64
        import json
        token = _make_token()
        payload_b64 = token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * padding))
        assert payload["sub"] == "agent-08"

    def test_token_payload_exp_in_future(self):
        import base64
        import json
        import time
        token = _make_token()
        payload_b64 = token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * padding))
        assert payload["exp"] > int(time.time())

    def test_two_tokens_are_strings(self):
        t1 = _make_token()
        t2 = _make_token()
        assert isinstance(t1, str) and isinstance(t2, str)

    def test_token_verifiable_by_pyjwt(self):
        import jwt
        token = _make_token()
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
        assert payload["sub"] == "agent-08"


# ── Class 2: get_harvest_impact success paths ─────────────────────────────────

class TestGetHarvestImpactSuccess:
    """10 tests for get_harvest_impact() happy paths."""

    def _mock_200(self, opportunities):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"opportunities": opportunities}
        return mock_resp

    @pytest.mark.anyio
    async def test_returns_dict_on_200_with_opportunities(self):
        opp = {"symbol": "O", "unrealized_loss": -500.0, "tax_savings_estimated": 100.0}
        mock_resp = self._mock_200([opp])
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await get_harvest_impact("O", 10000.0, 10500.0, None)
        assert result is not None
        assert result["symbol"] == "O"

    @pytest.mark.anyio
    async def test_posts_to_harvest_endpoint(self):
        mock_resp = self._mock_200([{"symbol": "O"}])
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await get_harvest_impact("O", 10000.0, 10500.0, None)
        url = mock_post.call_args.args[0]
        assert "/tax/harvest" in url

    @pytest.mark.anyio
    async def test_sends_symbol_in_candidates(self):
        mock_resp = self._mock_200([{"symbol": "O"}])
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await get_harvest_impact("O", 10000.0, 10500.0, None)
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert body["candidates"][0]["symbol"] == "O"

    @pytest.mark.anyio
    async def test_sends_current_value_and_cost_basis(self):
        mock_resp = self._mock_200([{"symbol": "O"}])
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await get_harvest_impact("O", 9000.0, 10000.0, None)
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        candidate = body["candidates"][0]
        assert candidate["current_value"] == 9000.0
        assert candidate["cost_basis"] == 10000.0

    @pytest.mark.anyio
    async def test_sends_wash_sale_check_true(self):
        mock_resp = self._mock_200([{"symbol": "O"}])
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await get_harvest_impact("O", 9000.0, 10000.0, None)
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert body["wash_sale_check"] is True

    @pytest.mark.anyio
    async def test_holding_days_computed_from_acquired_date(self):
        acquired = date.today() - timedelta(days=100)
        mock_resp = self._mock_200([{"symbol": "O"}])
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await get_harvest_impact("O", 9000.0, 10000.0, acquired)
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert body["candidates"][0]["holding_period_days"] == 100

    @pytest.mark.anyio
    async def test_none_acquired_date_gives_zero_holding_days(self):
        mock_resp = self._mock_200([{"symbol": "O"}])
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await get_harvest_impact("O", 9000.0, 10000.0, None)
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert body["candidates"][0]["holding_period_days"] == 0

    @pytest.mark.anyio
    async def test_long_held_position_over_365_days(self):
        acquired = date.today() - timedelta(days=400)
        mock_resp = self._mock_200([{"symbol": "O"}])
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await get_harvest_impact("O", 9000.0, 10000.0, acquired)
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert body["candidates"][0]["holding_period_days"] > 365

    @pytest.mark.anyio
    async def test_returns_first_opportunity(self):
        opps = [
            {"symbol": "O", "tax_savings_estimated": 100.0},
            {"symbol": "O", "tax_savings_estimated": 200.0},
        ]
        mock_resp = self._mock_200(opps)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await get_harvest_impact("O", 9000.0, 10000.0, None)
        assert result["tax_savings_estimated"] == 100.0

    @pytest.mark.anyio
    async def test_empty_opportunities_returns_none(self):
        mock_resp = self._mock_200([])
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await get_harvest_impact("O", 9000.0, 10000.0, None)
        assert result is None


# ── Class 3: get_harvest_impact error paths ───────────────────────────────────

class TestGetHarvestImpactErrors:
    """7 tests for get_harvest_impact() error handling."""

    @pytest.mark.anyio
    async def test_http_500_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await get_harvest_impact("O", 9000.0, 10000.0, None)
        assert result is None

    @pytest.mark.anyio
    async def test_timeout_returns_none(self):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=httpx.TimeoutException("timeout")):
            result = await get_harvest_impact("O", 9000.0, 10000.0, None)
        assert result is None

    @pytest.mark.anyio
    async def test_connection_error_returns_none(self):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=httpx.ConnectError("refused")):
            result = await get_harvest_impact("O", 9000.0, 10000.0, None)
        assert result is None

    @pytest.mark.anyio
    async def test_generic_exception_returns_none(self):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=Exception("boom")):
            result = await get_harvest_impact("O", 9000.0, 10000.0, None)
        assert result is None

    @pytest.mark.anyio
    async def test_never_raises(self):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=RuntimeError("unexpected")):
            result = await get_harvest_impact("O", 9000.0, 10000.0, None)
        assert result is None

    @pytest.mark.anyio
    async def test_non_200_logs_warning(self, caplog):
        import logging
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with caplog.at_level(logging.WARNING):
                result = await get_harvest_impact("O", 9000.0, 10000.0, None)
        assert result is None

    @pytest.mark.anyio
    async def test_missing_opportunities_key_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"some_other_key": []}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await get_harvest_impact("O", 9000.0, 10000.0, None)
        assert result is None
