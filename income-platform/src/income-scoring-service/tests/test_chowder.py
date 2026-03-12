"""
Tests for Chowder Rule — Amendment A2.
Covers _compute_chowder() and chowder field propagation through ScoreResult / ScoreResponse.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.scoring.income_scorer import (
    _compute_chowder,
    _chowder_signal_from_number,
    IncomeScorer,
)
from app.api.scores import ScoreResponse
from app.scoring.data_client import MarketDataClient


# ── _compute_chowder unit tests ────────────────────────────────────────────────

def test_dividend_stock_attractive():
    num, sig = _compute_chowder(7.0, 6.0, "DIVIDEND_STOCK")
    assert sig == "ATTRACTIVE"
    assert num == 13.0


def test_dividend_stock_borderline():
    num, sig = _compute_chowder(5.0, 5.0, "DIVIDEND_STOCK")
    assert sig == "BORDERLINE"
    assert num == 10.0


def test_dividend_stock_unattractive():
    num, sig = _compute_chowder(3.0, 2.0, "DIVIDEND_STOCK")
    assert sig == "UNATTRACTIVE"
    assert num == 5.0


def test_covered_call_etf_attractive():
    num, sig = _compute_chowder(5.0, 4.0, "COVERED_CALL_ETF")
    assert sig == "ATTRACTIVE"
    assert num == 9.0


def test_covered_call_etf_borderline():
    num, sig = _compute_chowder(3.0, 3.0, "COVERED_CALL_ETF")
    assert sig == "BORDERLINE"
    assert num == 6.0


def test_yield_ttm_none():
    num, sig = _compute_chowder(None, 5.0, "DIVIDEND_STOCK")
    assert num is None
    assert sig == "INSUFFICIENT_DATA"


def test_div_cagr_5y_none():
    num, sig = _compute_chowder(5.0, None, "DIVIDEND_STOCK")
    assert num is None
    assert sig == "INSUFFICIENT_DATA"


def test_both_none():
    num, sig = _compute_chowder(None, None, "DIVIDEND_STOCK")
    assert num is None
    assert sig == "INSUFFICIENT_DATA"


def test_exact_boundary_12_attractive():
    num, sig = _compute_chowder(6.0, 6.0, "DIVIDEND_STOCK")
    assert sig == "ATTRACTIVE"
    assert num == 12.0


def test_exact_boundary_8_borderline_dividend_stock():
    num, sig = _compute_chowder(4.0, 4.0, "DIVIDEND_STOCK")
    assert sig == "BORDERLINE"
    assert num == 8.0


# ── ScoreResponse optional field tests ────────────────────────────────────────

def _minimal_score_response(**overrides) -> ScoreResponse:
    defaults = dict(
        ticker="TEST",
        asset_class="DIVIDEND_STOCK",
        valuation_yield_score=20.0,
        financial_durability_score=20.0,
        technical_entry_score=10.0,
        total_score_raw=50.0,
        nav_erosion_penalty=0.0,
        total_score=50.0,
        grade="D",
        recommendation="WATCH",
        factor_details={},
        data_quality_score=100.0,
        data_completeness_pct=100.0,
        scored_at=datetime.utcnow(),
    )
    defaults.update(overrides)
    return ScoreResponse(**defaults)


def test_score_response_chowder_fields_default_none():
    resp = _minimal_score_response()
    assert resp.chowder_number is None
    assert resp.chowder_signal is None


def test_score_response_accepts_chowder_fields():
    resp = _minimal_score_response(chowder_number=13.5, chowder_signal="ATTRACTIVE")
    assert resp.chowder_number == 13.5
    assert resp.chowder_signal == "ATTRACTIVE"


# ── factor_details propagation via IncomeScorer ───────────────────────────────

class _FakeGate:
    dividend_history_years = 10


def test_factor_details_contains_chowder_after_scoring():
    scorer = IncomeScorer()
    market_data = {
        "features": {
            "yield_trailing_12m": 4.0,
            "div_cagr_5y": 9.0,
        },
        "fundamentals": {
            "payout_ratio": 0.5,
            "free_cash_flow": 1_000_000,
            "debt_to_equity": 0.8,
        },
        "dividend_history": [
            {"amount": "1.00"},
            {"amount": "1.00"},
            {"amount": "1.00"},
            {"amount": "1.00"},
        ],
        "history_stats": {
            "avg_price": 50.0,
            "volatility": 3.0,
            "price_change_pct": -2.0,
            "min_price": 45.0,
            "max_price": 55.0,
        },
        "current_price": {"price": 48.0},
    }
    result = scorer.score("TEST", "DIVIDEND_STOCK", _FakeGate(), market_data)
    assert "chowder_number" in result.factor_details
    assert "chowder_signal" in result.factor_details
    assert result.factor_details["chowder_number"] == 13.0
    assert result.factor_details["chowder_signal"] == "ATTRACTIVE"
    assert result.chowder_number == 13.0
    assert result.chowder_signal == "ATTRACTIVE"


def test_factor_details_chowder_insufficient_when_yield_missing():
    scorer = IncomeScorer()
    market_data = {
        "fundamentals": {
            "five_year_div_growth": 5.0,
            # dividend_yield omitted
        },
        "dividend_history": [],
        "history_stats": {},
        "current_price": {},
    }
    result = scorer.score("TEST", "DIVIDEND_STOCK", _FakeGate(), market_data)
    assert result.factor_details["chowder_number"] is None
    assert result.factor_details["chowder_signal"] == "INSUFFICIENT_DATA"


# ── get_features tests ─────────────────────────────────────────────────────────

import asyncio  # noqa: E402
import pytest   # noqa: E402


def _run(coro):
    """Run a coroutine synchronously in the test process."""
    return asyncio.run(coro)


def test_get_features_returns_empty_dict_on_db_error():
    """Pool raises → get_features swallows and returns {}."""
    mock_pool = MagicMock()
    mock_pool.acquire.side_effect = Exception("conn refused")
    with patch("app.scoring.data_client._pool", mock_pool):
        client = MarketDataClient(base_url="http://localhost:8001", timeout=5)
        result = _run(client.get_features("AAPL"))
    assert result == {}


def test_get_features_returns_correct_keys_on_success():
    """Pool returns a row → get_features returns a dict with the expected keys."""
    fake_row = {
        "yield_trailing_12m": 3.5,
        "div_cagr_5y": 8.2,
        "chowder_number": 11.7,
        "yield_5yr_avg": 3.1,
        "credit_rating": "A",
        "credit_quality_proxy": "IG",
    }
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.scoring.data_client._pool", mock_pool):
        client = MarketDataClient(base_url="http://localhost:8001", timeout=5)
        result = _run(client.get_features("AAPL"))

    assert result["yield_trailing_12m"] == 3.5
    assert result["div_cagr_5y"] == 8.2
    assert result["chowder_number"] == 11.7
    assert result["credit_rating"] == "A"


def test_score_uses_features_chowder_number_when_yield_ttm_missing():
    """When features_historical has chowder_number but yield_trailing_12m is None,
    score() adopts the pre-computed chowder_number instead of computing from scratch."""
    scorer = IncomeScorer()
    market_data = {
        "features": {
            "chowder_number": 14.5,
            # yield_trailing_12m intentionally absent → fallback path
        },
        "fundamentals": {},
        "dividend_history": [],
        "history_stats": {},
        "current_price": {},
    }
    result = scorer.score("TEST", "DIVIDEND_STOCK", _FakeGate(), market_data)
    assert result.chowder_number == 14.5
    assert result.chowder_signal == "ATTRACTIVE"
    assert result.factor_details["chowder_number"] == 14.5
    assert result.factor_details["chowder_signal"] == "ATTRACTIVE"
