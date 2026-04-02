"""Tests for portfolio_aggregator.py"""
import os
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

import pytest
from unittest.mock import AsyncMock, patch
from app.services.portfolio_aggregator import compute_hhi, _is_stale


POSITIONS = [
    {"symbol": "MAIN", "current_value": 10000, "annual_income": 600, "asset_type": "BDC", "sector": "Financial"},
    {"symbol": "JEPI", "current_value": 5000, "annual_income": 300, "asset_type": "COVERED_CALL_ETF", "sector": "Financial"},
    {"symbol": "O",    "current_value": 5000, "annual_income": 200, "asset_type": "EQUITY_REIT",   "sector": "Real Estate"},
]

SCORES = {
    "MAIN": {"asset_class": "BDC", "hhs_score": 80.0, "unsafe_flag": False, "quality_gate_status": "PASS", "valid_until": "2099-01-01T00:00:00+00:00"},
    "JEPI": {"asset_class": "COVERED_CALL_ETF", "hhs_score": 60.0, "unsafe_flag": False, "quality_gate_status": "PASS", "valid_until": "2099-01-01T00:00:00+00:00"},
    "O":    {"asset_class": "EQUITY_REIT",  "hhs_score": 15.0, "unsafe_flag": True,  "quality_gate_status": "PASS", "valid_until": "2099-01-01T00:00:00+00:00"},
}


class TestComputeHhi:
    def test_equal_weights_three_positions(self):
        weights = [1/3, 1/3, 1/3]
        assert round(compute_hhi(weights), 4) == round(3 * (1/3)**2, 4)

    def test_single_position_is_one(self):
        assert compute_hhi([1.0]) == 1.0

    def test_empty_is_zero(self):
        assert compute_hhi([]) == 0.0


class TestAggregatePortfolio:
    @pytest.mark.anyio
    async def test_agg_hhs_is_value_weighted(self):
        from app.services.portfolio_aggregator import aggregate_portfolio
        with patch("app.services.portfolio_aggregator._fetch_tax_nay",
                   new_callable=AsyncMock, return_value=None):
            result = await aggregate_portfolio("test-id", POSITIONS, SCORES)
        # MAIN (10k): 80 * 0.5 = 40; JEPI (5k): 60 * 0.25 = 15; O (5k): hhs=15, unsafe=True, gate=PASS → included
        # O: hhs IS counted (unsafe doesn't exclude from avg, only gate-fail and stale excluded)
        assert result["agg_hhs"] is not None
        assert 30 < result["agg_hhs"] < 70

    @pytest.mark.anyio
    async def test_unsafe_count(self):
        from app.services.portfolio_aggregator import aggregate_portfolio
        with patch("app.services.portfolio_aggregator._fetch_tax_nay",
                   new_callable=AsyncMock, return_value=None):
            result = await aggregate_portfolio("test-id", POSITIONS, SCORES)
        assert result["unsafe_count"] == 1  # only O

    @pytest.mark.anyio
    async def test_total_value(self):
        from app.services.portfolio_aggregator import aggregate_portfolio
        with patch("app.services.portfolio_aggregator._fetch_tax_nay",
                   new_callable=AsyncMock, return_value=None):
            result = await aggregate_portfolio("test-id", POSITIONS, SCORES)
        assert result["total_value"] == 20000.0

    @pytest.mark.anyio
    async def test_annual_income(self):
        from app.services.portfolio_aggregator import aggregate_portfolio
        with patch("app.services.portfolio_aggregator._fetch_tax_nay",
                   new_callable=AsyncMock, return_value=None):
            result = await aggregate_portfolio("test-id", POSITIONS, SCORES)
        assert result["annual_income"] == 1100.0

    @pytest.mark.anyio
    async def test_concentration_by_class_sorted_desc(self):
        from app.services.portfolio_aggregator import aggregate_portfolio
        with patch("app.services.portfolio_aggregator._fetch_tax_nay",
                   new_callable=AsyncMock, return_value=None):
            result = await aggregate_portfolio("test-id", POSITIONS, SCORES)
        pcts = [c["pct"] for c in result["concentration_by_class"]]
        assert pcts == sorted(pcts, reverse=True)

    @pytest.mark.anyio
    async def test_empty_positions(self):
        from app.services.portfolio_aggregator import aggregate_portfolio
        with patch("app.services.portfolio_aggregator._fetch_tax_nay",
                   new_callable=AsyncMock, return_value=None):
            result = await aggregate_portfolio("test-id", [], {})
        assert result["agg_hhs"] is None
        assert result["total_value"] == 0.0

    @pytest.mark.anyio
    async def test_stale_score_excluded_from_hhs(self):
        from app.services.portfolio_aggregator import aggregate_portfolio
        stale_scores = {k: {**v, "valid_until": "2000-01-01T00:00:00+00:00"} for k, v in SCORES.items()}
        with patch("app.services.portfolio_aggregator._fetch_tax_nay",
                   new_callable=AsyncMock, return_value=None):
            result = await aggregate_portfolio("test-id", POSITIONS, stale_scores)
        assert result["agg_hhs"] is None   # all stale → no HHS data

    @pytest.mark.anyio
    async def test_gate_fail_excluded_from_hhs_and_counted(self):
        from app.services.portfolio_aggregator import aggregate_portfolio
        scores_with_gate_fail = {
            "MAIN": {"asset_class": "BDC", "hhs_score": 80.0, "unsafe_flag": False, "quality_gate_status": "PASS", "valid_until": "2099-01-01T00:00:00+00:00"},
            "JEPI": {"asset_class": "COVERED_CALL_ETF", "hhs_score": None, "unsafe_flag": None, "quality_gate_status": "INSUFFICIENT_DATA", "valid_until": "2099-01-01T00:00:00+00:00"},
            "O":    {"asset_class": "EQUITY_REIT", "hhs_score": None, "unsafe_flag": None, "quality_gate_status": "FAIL", "valid_until": "2099-01-01T00:00:00+00:00"},
        }
        with patch("app.services.portfolio_aggregator._fetch_tax_nay",
                   new_callable=AsyncMock, return_value=None):
            result = await aggregate_portfolio("test-id", POSITIONS, scores_with_gate_fail)
        assert result["gate_fail_count"] == 2   # JEPI (INSUFFICIENT_DATA) + O (FAIL)
        # Only MAIN contributes to agg_hhs (JEPI and O have gate status != PASS)
        assert result["agg_hhs"] is not None


@pytest.mark.anyio
async def test_aggregator_uses_tax_service_naa_when_available():
    """When tax service returns portfolio_nay, aggregator should use it."""
    from app.services.portfolio_aggregator import aggregate_portfolio

    mock_positions = [
        {"symbol": "ECC", "current_value": 10000.0, "annual_income": 4230.0,
         "asset_type": "CEF", "cost_basis": 9500.0},
    ]

    with patch("app.services.portfolio_aggregator._fetch_tax_nay",
               new_callable=AsyncMock, return_value=0.18):
        result = await aggregate_portfolio("test-portfolio-id", mock_positions, {}, {
            "annual_income": 150000, "filing_status": "SINGLE", "state_code": "CA"
        })

    assert result["naa_yield"] == pytest.approx(0.18)
    assert result["naa_yield_pre_tax"] is False


@pytest.mark.anyio
async def test_aggregator_falls_back_to_gross_when_tax_unavailable():
    """When tax service fails, aggregator falls back to gross yield."""
    from app.services.portfolio_aggregator import aggregate_portfolio

    mock_positions = [
        {"symbol": "ECC", "current_value": 10000.0, "annual_income": 4230.0,
         "asset_type": "CEF", "cost_basis": 9500.0},
    ]

    with patch("app.services.portfolio_aggregator._fetch_tax_nay",
               new_callable=AsyncMock, return_value=None):
        result = await aggregate_portfolio("test-portfolio-id", mock_positions, {}, None)

    # Falls back to gross: 4230 / 10000 = 0.423
    assert result["naa_yield"] == pytest.approx(0.423, abs=0.001)
    assert result["naa_yield_pre_tax"] is True
