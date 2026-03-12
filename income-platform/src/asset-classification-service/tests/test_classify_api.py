"""
Tests for API: POST /classify, POST /classify/batch, GET /classify/{ticker}
Target: 30 tests — auth, validation, success paths, engine errors.
"""
import sys
import os

# Env vars before any app import (also done in conftest but be safe for isolation)
os.environ.setdefault("JWT_SECRET",              "test-secret")
os.environ.setdefault("DATABASE_URL",            "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("MARKET_DATA_SERVICE_URL", "http://localhost:8001")
os.environ.setdefault("REDIS_URL",               "redis://localhost:6379")

from unittest.mock import AsyncMock, patch

import pytest

# conftest provides: client, auth_headers, expired_headers, mock_db

_CLASSIFICATION_RESPONSE = {
    "ticker": "JEPI",
    "asset_class": "COVERED_CALL_ETF",
    "parent_class": "ETF",
    "confidence": 0.95,
    "is_hybrid": False,
    "characteristics": {"income_type": "option_premium"},
    "benchmarks": None,
    "sub_scores": None,
    "tax_efficiency": {
        "income_type": "option_premium",
        "tax_treatment": "ordinary",
        "estimated_tax_drag_pct": 37.0,
        "preferred_account": "IRA",
        "notes": "Hold in IRA.",
    },
    "source": "rule_engine_v1",
    "is_override": False,
    "classified_at": "2026-03-01T00:00:00+00:00",
    "valid_until": "2026-03-02T00:00:00+00:00",
}


# ── POST /classify ──────────────────────────────────────────────────────────

class TestClassifySingle:
    def test_valid_request_returns_200(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post("/classify", json={"ticker": "JEPI"}, headers=auth_headers)
        assert r.status_code == 200

    def test_response_has_ticker(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post("/classify", json={"ticker": "JEPI"}, headers=auth_headers)
        assert r.json()["ticker"] == "JEPI"

    def test_response_has_asset_class(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post("/classify", json={"ticker": "JEPI"}, headers=auth_headers)
        assert r.json()["asset_class"] == "COVERED_CALL_ETF"

    def test_response_has_tax_efficiency(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post("/classify", json={"ticker": "JEPI"}, headers=auth_headers)
        assert "tax_efficiency" in r.json()

    def test_no_auth_returns_403(self, client):
        r = client.post("/classify", json={"ticker": "JEPI"})
        assert r.status_code in (401, 403)

    def test_expired_token_returns_401(self, client, expired_headers):
        r = client.post("/classify", json={"ticker": "JEPI"}, headers=expired_headers)
        assert r.status_code == 401

    def test_empty_ticker_returns_422(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post("/classify", json={"ticker": ""}, headers=auth_headers)
        assert r.status_code == 422

    def test_missing_body_returns_422(self, client, auth_headers):
        r = client.post("/classify", json={}, headers=auth_headers)
        assert r.status_code == 422

    def test_optional_security_data_accepted(self, client, auth_headers):
        payload = {"ticker": "AAPL", "security_data": {"sector": "Technology"}}
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value={**_CLASSIFICATION_RESPONSE, "ticker": "AAPL"}),
        ):
            r = client.post("/classify", json=payload, headers=auth_headers)
        assert r.status_code == 200

    def test_ticker_lowercased_still_accepted(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post("/classify", json={"ticker": "jepi"}, headers=auth_headers)
        assert r.status_code == 200


# ── POST /classify/batch ─────────────────────────────────────────────────────

class TestClassifyBatch:
    def test_valid_batch_returns_200(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post(
                "/classify/batch",
                json={"tickers": ["JEPI", "JEPQ", "QYLD"]},
                headers=auth_headers,
            )
        assert r.status_code == 200

    def test_batch_returns_total_count(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post(
                "/classify/batch",
                json={"tickers": ["JEPI", "JEPQ"]},
                headers=auth_headers,
            )
        assert r.json()["total"] == 2

    def test_batch_returns_results_list(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post(
                "/classify/batch",
                json={"tickers": ["JEPI"]},
                headers=auth_headers,
            )
        assert isinstance(r.json()["results"], list)
        assert len(r.json()["results"]) == 1

    def test_batch_over_100_returns_422(self, client, auth_headers):
        tickers = [f"T{i:03d}" for i in range(101)]
        r = client.post(
            "/classify/batch",
            json={"tickers": tickers},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_batch_exactly_100_accepted(self, client, auth_headers):
        tickers = [f"T{i:03d}" for i in range(100)]
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.post(
                "/classify/batch",
                json={"tickers": tickers},
                headers=auth_headers,
            )
        assert r.status_code == 200

    def test_batch_no_auth_returns_403(self, client):
        r = client.post("/classify/batch", json={"tickers": ["JEPI"]})
        assert r.status_code in (401, 403)

    def test_batch_engine_error_goes_to_errors_list(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(side_effect=Exception("engine failure")),
        ):
            r = client.post(
                "/classify/batch",
                json={"tickers": ["BROKEN"]},
                headers=auth_headers,
            )
        assert r.status_code == 200
        body = r.json()
        assert body["errors"] == 1
        assert body["classified"] == 0

    def test_batch_partial_failure_reported(self, client, auth_headers):
        async def _side_effect(self_engine, ticker, *a, **kw):
            if ticker == "BAD":
                raise Exception("bad ticker")
            return _CLASSIFICATION_RESPONSE

        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=_side_effect,
        ):
            r = client.post(
                "/classify/batch",
                json={"tickers": ["JEPI", "BAD"]},
                headers=auth_headers,
            )
        body = r.json()
        assert body["classified"] == 1
        assert body["errors"] == 1


# ── GET /classify/{ticker} ───────────────────────────────────────────────────

class TestGetClassification:
    def test_valid_ticker_returns_200(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.get("/classify/JEPI", headers=auth_headers)
        assert r.status_code == 200

    def test_ticker_in_response(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.get("/classify/JEPI", headers=auth_headers)
        assert r.json()["ticker"] == "JEPI"

    def test_no_auth_returns_403(self, client):
        r = client.get("/classify/JEPI")
        assert r.status_code in (401, 403)

    def test_lowercase_ticker_accepted(self, client, auth_headers):
        with patch(
            "app.classification.engine.ClassificationEngine.classify",
            new=AsyncMock(return_value=_CLASSIFICATION_RESPONSE),
        ):
            r = client.get("/classify/jepi", headers=auth_headers)
        assert r.status_code == 200
