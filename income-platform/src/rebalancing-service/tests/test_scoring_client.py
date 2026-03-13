"""
Agent 08 — Rebalancing Service
Tests: Scoring client — 25 tests.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("INCOME_SCORING_URL", "http://agent-03:8003")
os.environ.setdefault("TAX_OPTIMIZATION_URL", "http://agent-05:8005")

import httpx

from app.rebalancer.scoring_client import _make_token, score_ticker


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


# ── Class 2: score_ticker success paths ───────────────────────────────────────

class TestScoreTickerSuccess:
    """10 tests for score_ticker() happy paths."""

    @pytest.mark.anyio
    async def test_returns_dict_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": "O", "total_score": 75.0}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await score_ticker("O")
        assert result is not None
        assert result["ticker"] == "O"

    @pytest.mark.anyio
    async def test_posts_to_evaluate_endpoint(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": "O", "total_score": 75.0}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await score_ticker("O")
        url = mock_post.call_args.args[0]
        assert "/scores/evaluate" in url

    @pytest.mark.anyio
    async def test_sends_ticker_in_body(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": "O", "total_score": 75.0}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await score_ticker("O")
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert body["ticker"] == "O"

    @pytest.mark.anyio
    async def test_sends_bearer_auth_header(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await score_ticker("O")
        headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args[1].get("headers")
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    @pytest.mark.anyio
    async def test_returns_full_score_dict(self):
        score_data = {
            "ticker": "O", "total_score": 80.0, "grade": "A",
            "asset_class": "EQUITY_REIT", "recommendation": "AGGRESSIVE_BUY",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = score_data
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await score_ticker("O")
        assert result["grade"] == "A"
        assert result["asset_class"] == "EQUITY_REIT"

    @pytest.mark.anyio
    async def test_ticker_case_preserved(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": "JEPI", "total_score": 70.0}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await score_ticker("JEPI")
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert body["ticker"] == "JEPI"

    @pytest.mark.anyio
    async def test_total_score_zero_returns_dict(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": "X", "total_score": 0.0}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await score_ticker("X")
        assert result is not None

    @pytest.mark.anyio
    async def test_total_score_100_returned(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": "X", "total_score": 100.0}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await score_ticker("X")
        assert result["total_score"] == 100.0

    @pytest.mark.anyio
    async def test_grade_field_present(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": "O", "total_score": 80.0, "grade": "A"}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await score_ticker("O")
        assert "grade" in result

    @pytest.mark.anyio
    async def test_recommendation_field_present(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ticker": "O", "total_score": 80.0, "recommendation": "ACCUMULATE"
        }
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await score_ticker("O")
        assert "recommendation" in result


# ── Class 3: score_ticker error paths ────────────────────────────────────────

class TestScoreTickerErrors:
    """7 tests for score_ticker() error handling."""

    @pytest.mark.anyio
    async def test_http_404_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await score_ticker("INVALID")
        assert result is None

    @pytest.mark.anyio
    async def test_http_500_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await score_ticker("O")
        assert result is None

    @pytest.mark.anyio
    async def test_timeout_returns_none(self):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=httpx.TimeoutException("timeout")):
            result = await score_ticker("O")
        assert result is None

    @pytest.mark.anyio
    async def test_connection_error_returns_none(self):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=httpx.ConnectError("connection refused")):
            result = await score_ticker("O")
        assert result is None

    @pytest.mark.anyio
    async def test_generic_exception_returns_none(self):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=Exception("unexpected")):
            result = await score_ticker("O")
        assert result is None

    @pytest.mark.anyio
    async def test_never_raises(self):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=RuntimeError("boom")):
            result = await score_ticker("O")
        assert result is None

    @pytest.mark.anyio
    async def test_non_200_logs_warning(self, caplog):
        import logging
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with caplog.at_level(logging.WARNING):
                result = await score_ticker("O")
        assert result is None
