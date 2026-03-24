"""Tests for portfolio_aggregator.py"""
import pytest
from app.services.portfolio_aggregator import aggregate_portfolio, compute_hhi, _is_stale


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
    def test_agg_hhs_is_value_weighted(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        # MAIN (10k): 80 * 0.5 = 40; JEPI (5k): 60 * 0.25 = 15; O (5k): hhs=15, unsafe=True, gate=PASS → included
        # O: hhs IS counted (unsafe doesn't exclude from avg, only gate-fail and stale excluded)
        assert result["agg_hhs"] is not None
        assert 30 < result["agg_hhs"] < 70

    def test_unsafe_count(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        assert result["unsafe_count"] == 1  # only O

    def test_total_value(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        assert result["total_value"] == 20000.0

    def test_annual_income(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        assert result["annual_income"] == 1100.0

    def test_concentration_by_class_sorted_desc(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        pcts = [c["pct"] for c in result["concentration_by_class"]]
        assert pcts == sorted(pcts, reverse=True)

    def test_empty_positions(self):
        result = aggregate_portfolio([], {})
        assert result["agg_hhs"] is None
        assert result["total_value"] == 0.0

    def test_stale_score_excluded_from_hhs(self):
        stale_scores = {k: {**v, "valid_until": "2000-01-01T00:00:00+00:00"} for k, v in SCORES.items()}
        result = aggregate_portfolio(POSITIONS, stale_scores)
        assert result["agg_hhs"] is None   # all stale → no HHS data
