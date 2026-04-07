"""Unit tests for _compute_hhs(), _compute_ies_gate(), _generate_hhs_commentary()."""
import pytest
from dataclasses import dataclass, field
from typing import Optional

# Import the helpers directly
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.api.scores import _compute_hhs, _compute_ies_gate, _generate_hhs_commentary, _HHS_UNSAFE_THRESHOLD


@dataclass
class FakeResult:
    valuation_yield_score: float = 30.0
    financial_durability_score: float = 30.0
    technical_entry_score: float = 15.0
    factor_details: dict = field(default_factory=dict)


DEFAULT_PROFILE = {
    "weight_yield": 40,
    "weight_durability": 40,
    "weight_technical": 20,
    "yield_sub_weights": {"payout_sustainability": 40, "yield_vs_market": 35, "fcf_coverage": 25},
    "durability_sub_weights": {"debt_safety": 40, "dividend_consistency": 35, "volatility_score": 25},
    "technical_sub_weights": {"price_momentum": 60, "price_range_position": 40},
}


class TestComputeHhs:
    def test_pass_gate_returns_hhs_score(self):
        r = FakeResult(valuation_yield_score=30.0, financial_durability_score=30.0)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["hhs_score"] == 75.0          # (75 * 0.5) + (75 * 0.5) = 75
        assert out["income_pillar_score"] == 75.0  # 30/40 * 100
        assert out["durability_pillar_score"] == 75.0

    def test_insufficient_data_returns_provisional_hhs(self):
        # INSUFFICIENT_DATA: score is still computed but hhs_status is prefixed with "~"
        r = FakeResult()
        out = _compute_hhs(r, DEFAULT_PROFILE, "INSUFFICIENT_DATA")
        assert out["hhs_score"] is not None
        assert out["hhs_status"].startswith("~")

    def test_unsafe_flag_when_durability_at_threshold(self):
        dur_score = ((_HHS_UNSAFE_THRESHOLD / 100) * 40)  # 8.0 pts → 20/100 normalized
        r = FakeResult(financial_durability_score=dur_score)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["unsafe_flag"] is True
        assert out["hhs_status"] == "UNSAFE"

    def test_unsafe_flag_false_above_threshold(self):
        r = FakeResult(financial_durability_score=30.0)  # 75 normalized
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["unsafe_flag"] is False

    def test_status_strong_at_85(self):
        r = FakeResult(valuation_yield_score=34.0, financial_durability_score=34.0)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["hhs_score"] >= 85
        assert out["hhs_status"] == "STRONG"

    def test_status_watch_between_50_and_70(self):
        r = FakeResult(valuation_yield_score=22.0, financial_durability_score=22.0)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert 50 <= out["hhs_score"] < 70
        assert out["hhs_status"] in ("WATCH", "GOOD")

    def test_scores_clamped_at_100(self):
        r = FakeResult(valuation_yield_score=50.0, financial_durability_score=50.0)  # exceeds budget
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["income_pillar_score"] == 100.0
        assert out["durability_pillar_score"] == 100.0

    def test_scores_clamped_at_0(self):
        r = FakeResult(valuation_yield_score=-5.0, financial_durability_score=-5.0)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["income_pillar_score"] == 0.0
        assert out["durability_pillar_score"] == 0.0


class TestComputeIesGate:
    def test_ies_computed_when_hhs_above_50_and_not_unsafe(self):
        hhs_fields = {"hhs_score": 75.0, "unsafe_flag": False}
        r = FakeResult(valuation_yield_score=30.0, technical_entry_score=15.0)
        out = _compute_ies_gate(r, DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is True
        assert out["ies_score"] is not None
        assert 0.0 <= out["ies_score"] <= 100.0
        assert out["ies_blocked_reason"] is None

    def test_ies_blocked_when_unsafe(self):
        hhs_fields = {"hhs_score": 80.0, "unsafe_flag": True}
        out = _compute_ies_gate(FakeResult(), DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is False
        assert out["ies_blocked_reason"] == "UNSAFE_FLAG"

    def test_ies_blocked_when_hhs_below_50(self):
        hhs_fields = {"hhs_score": 45.0, "unsafe_flag": False}
        out = _compute_ies_gate(FakeResult(), DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is False
        assert out["ies_blocked_reason"] == "HHS_BELOW_THRESHOLD"

    def test_ies_blocked_when_hhs_none(self):
        hhs_fields = {"hhs_score": None, "unsafe_flag": None}
        out = _compute_ies_gate(FakeResult(), DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is False
        assert out["ies_blocked_reason"] == "INSUFFICIENT_DATA"

    def test_ies_blocked_when_unsafe_flag_is_none(self):
        # unsafe_flag=None means gate-failed — must NOT allow IES even if hhs > 50
        hhs_fields = {"hhs_score": 60.0, "unsafe_flag": None}
        out = _compute_ies_gate(FakeResult(), DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is False


class TestGenerateHhsCommentary:
    def test_returns_none_when_hhs_none(self):
        assert _generate_hhs_commentary({"hhs_score": None}, {}, "DIVIDEND_STOCK") is None

    def test_returns_string_with_hhs_score(self):
        hhs_fields = {
            "hhs_score": 75.0, "hhs_status": "GOOD",
            "income_pillar_score": 80.0, "durability_pillar_score": 70.0,
            "unsafe_flag": False,
        }
        result = _generate_hhs_commentary(hhs_fields, {}, "DIVIDEND_STOCK")
        assert result is not None
        assert "75" in result
        assert "GOOD" in result

    def test_unsafe_commentary_mentions_threshold(self):
        hhs_fields = {
            "hhs_score": 30.0, "hhs_status": "UNSAFE",
            "income_pillar_score": 60.0, "durability_pillar_score": 15.0,
            "unsafe_flag": True,
        }
        result = _generate_hhs_commentary(hhs_fields, {}, "DIVIDEND_STOCK")
        assert "UNSAFE" in result
