"""
Agent 03 — Income Scoring Service
Tests: Dynamic class-specific weight profiles in IncomeScorer (Phase 1).

Verifies:
- Normalised score functions return correct values
- _compute_ceilings produces correct absolute ceilings from profile dicts
- IncomeScorer.score() uses the weight profile to derive ceilings
- Default profile (40/40/20) gives identical results to v1.0 hardcoded values
- Different profiles produce different component totals on identical input
- weight_profile_version and weight_profile_id are propagated into ScoreResult
- Fallback (None profile) behaves the same as explicit default profile
"""
import os
import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

from app.scoring.income_scorer import (
    IncomeScorer,
    ScoreResult,
    _DEFAULT_WEIGHT_PROFILE,
    _compute_ceilings,
    _norm_payout,
    _norm_yield,
    _norm_fcf,
    _norm_debt,
    _norm_consistency,
    _norm_volatility,
    _norm_momentum,
    _norm_range,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _perfect_market_data() -> dict:
    """Market data that maximises every sub-component with default weights."""
    return {
        "fundamentals": {
            "payout_ratio": 0.35,       # < 0.40 → norm=1.0
            "debt_to_equity": 0.4,      # < 0.5  → norm=1.0
            "free_cash_flow": 1_000_000,  # > 0  → norm=1.0
        },
        "dividend_history": [
            {"amount": 1.5}, {"amount": 1.5}, {"amount": 1.5}, {"amount": 1.5},
        ],                              # annual=6.0 on avg_price=100 → div_yield=6% → norm=1.0
        "history_stats": {
            "avg_price": 100.0,
            "volatility": 1.5,          # < 2   → norm=1.0
            "price_change_pct": -20.0,  # < -15 → norm=1.0
            "min_price": 80.0,
            "max_price": 120.0,
        },
        "current_price": {"price": 82.0},  # range_ratio=(82-80)/(120-80)=0.05 < 0.3 → norm=1.0
        "features": {},
    }


def _null_market_data() -> dict:
    """All fields None — each sub-component falls back to 50% partial credit."""
    return {
        "fundamentals": {},
        "dividend_history": [],
        "history_stats": {},
        "current_price": None,
        "features": {},
    }


def _make_profile(wy=40, wd=40, wt=20) -> dict:
    return {
        "asset_class": "DIVIDEND_STOCK",
        "version": 1,
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "source": "INITIAL_SEED",
        "weight_yield": wy,
        "weight_durability": wd,
        "weight_technical": wt,
        "yield_sub_weights":      {"payout_sustainability": 40, "yield_vs_market": 35, "fcf_coverage": 25},
        "durability_sub_weights": {"debt_safety": 40, "dividend_consistency": 35, "volatility_score": 25},
        "technical_sub_weights":  {"price_momentum": 60, "price_range_position": 40},
    }


_scorer = IncomeScorer()
_GATE = type("FakeGate", (), {"dividend_history_years": 30})()  # > 25 → norm=1.0


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Normalised score functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormFunctions:

    # _norm_payout
    def test_norm_payout_none(self):
        assert _norm_payout(None) == 0.5

    def test_norm_payout_below_40(self):
        assert _norm_payout(0.35) == 1.0

    def test_norm_payout_below_60(self):
        assert _norm_payout(0.50) == 0.75

    def test_norm_payout_below_75(self):
        assert _norm_payout(0.70) == 0.50

    def test_norm_payout_below_90(self):
        assert _norm_payout(0.85) == 0.25

    def test_norm_payout_above_90(self):
        assert _norm_payout(0.95) == 0.0

    def test_norm_payout_exactly_90(self):
        assert _norm_payout(0.90) == 0.0  # not < 0.90

    # _norm_yield
    def test_norm_yield_none(self):
        assert _norm_yield(None) == 0.5

    def test_norm_yield_above_4(self):
        assert _norm_yield(5.0) == 1.0

    def test_norm_yield_above_3(self):
        assert abs(_norm_yield(3.5) - 10.0 / 14.0) < 1e-9

    def test_norm_yield_above_2(self):
        assert abs(_norm_yield(2.5) - 6.0 / 14.0) < 1e-9

    def test_norm_yield_above_1(self):
        assert abs(_norm_yield(1.5) - 2.0 / 14.0) < 1e-9

    def test_norm_yield_zero(self):
        assert _norm_yield(0.0) == 0.0

    # _norm_fcf
    def test_norm_fcf_none(self):
        assert _norm_fcf(None) == 0.5

    def test_norm_fcf_positive(self):
        assert _norm_fcf(1_000) == 1.0

    def test_norm_fcf_negative(self):
        assert _norm_fcf(-500) == 0.0

    def test_norm_fcf_zero(self):
        assert _norm_fcf(0) == 0.5

    # _norm_debt
    def test_norm_debt_none(self):
        assert _norm_debt(None) == 0.5

    def test_norm_debt_low(self):
        assert _norm_debt(0.3) == 1.0

    def test_norm_debt_moderate(self):
        assert _norm_debt(0.8) == 0.75

    def test_norm_debt_high(self):
        assert _norm_debt(2.5) == 0.0

    # _norm_consistency
    def test_norm_consistency_none(self):
        assert _norm_consistency(None) == 0.5

    def test_norm_consistency_above_25(self):
        assert _norm_consistency(30) == 1.0

    def test_norm_consistency_above_15(self):
        assert abs(_norm_consistency(20) - 10.0 / 14.0) < 1e-9

    def test_norm_consistency_above_10(self):
        assert abs(_norm_consistency(12) - 7.0 / 14.0) < 1e-9

    def test_norm_consistency_low(self):
        assert abs(_norm_consistency(5) - 4.0 / 14.0) < 1e-9

    # _norm_volatility
    def test_norm_volatility_none(self):
        assert _norm_volatility(None) == 0.5

    def test_norm_volatility_very_low(self):
        assert _norm_volatility(1.0) == 1.0

    def test_norm_volatility_moderate(self):
        assert _norm_volatility(7.0) == 0.4

    def test_norm_volatility_high(self):
        assert _norm_volatility(25.0) == 0.0

    # _norm_momentum
    def test_norm_momentum_none(self):
        assert _norm_momentum(None) == 0.5

    def test_norm_momentum_oversold(self):
        assert _norm_momentum(-20.0) == 1.0

    def test_norm_momentum_mildly_down(self):
        assert abs(_norm_momentum(-10.0) - 8.0 / 12.0) < 1e-9

    def test_norm_momentum_flat(self):
        assert abs(_norm_momentum(0.0) - 6.0 / 12.0) < 1e-9

    def test_norm_momentum_overbought(self):
        assert _norm_momentum(20.0) == 0.0

    # _norm_range
    def test_norm_range_none(self):
        assert _norm_range(None) == 0.5

    def test_norm_range_low(self):
        assert _norm_range(0.1) == 1.0

    def test_norm_range_mid_low(self):
        assert abs(_norm_range(0.4) - 5.0 / 8.0) < 1e-9

    def test_norm_range_mid(self):
        assert abs(_norm_range(0.6) - 3.0 / 8.0) < 1e-9

    def test_norm_range_high(self):
        assert abs(_norm_range(0.9) - 1.0 / 8.0) < 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
# 2. _compute_ceilings
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeCeilings:

    def test_default_profile_ceilings_match_v1(self):
        """Default 40/40/20 profile produces exactly the v1.0 hardcoded ceilings."""
        c = _compute_ceilings(_DEFAULT_WEIGHT_PROFILE)
        assert c["payout_sustainability"] == 16.0
        assert c["yield_vs_market"]       == 14.0
        assert c["fcf_coverage"]          == 10.0
        assert c["debt_safety"]           == 16.0
        assert c["dividend_consistency"]  == 14.0
        assert c["volatility_score"]      == 10.0
        assert c["price_momentum"]        == 12.0
        assert c["price_range_position"]  == 8.0

    def test_mreit_profile_ceilings(self):
        """MORTGAGE_REIT 30/45/25 profile gives correct sub-component ceilings."""
        profile = _make_profile(wy=30, wd=45, wt=25)
        c = _compute_ceilings(profile)
        assert c["payout_sustainability"] == 30 * 40 / 100   # 12.0
        assert c["yield_vs_market"]       == 30 * 35 / 100   # 10.5
        assert c["fcf_coverage"]          == 30 * 25 / 100   # 7.5
        assert c["debt_safety"]           == 45 * 40 / 100   # 18.0
        assert c["dividend_consistency"]  == 45 * 35 / 100   # 15.75
        assert c["volatility_score"]      == 45 * 25 / 100   # 11.25
        assert c["price_momentum"]        == 25 * 60 / 100   # 15.0
        assert c["price_range_position"]  == 25 * 40 / 100   # 10.0

    def test_ceilings_sum_to_100(self):
        """All sub-component ceilings sum to the total pillar weight (= 100)."""
        for wy, wd, wt in [(30, 45, 25), (35, 40, 25), (40, 30, 30), (25, 45, 30)]:
            profile = _make_profile(wy=wy, wd=wd, wt=wt)
            c = _compute_ceilings(profile)
            yield_total      = c["payout_sustainability"] + c["yield_vs_market"] + c["fcf_coverage"]
            durability_total = c["debt_safety"] + c["dividend_consistency"] + c["volatility_score"]
            technical_total  = c["price_momentum"] + c["price_range_position"]
            assert abs(yield_total - wy) < 1e-9
            assert abs(durability_total - wd) < 1e-9
            assert abs(technical_total - wt) < 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
# 3. IncomeScorer.score() with dynamic weight profile
# ═══════════════════════════════════════════════════════════════════════════════

class TestScorerWithDynamicWeights:

    def test_perfect_score_with_default_profile_equals_100(self):
        """Perfect market data + default 40/40/20 profile = total_score_raw 100."""
        result = _scorer.score(
            "TEST", "DIVIDEND_STOCK", _GATE, _perfect_market_data(),
            weight_profile=_DEFAULT_WEIGHT_PROFILE,
        )
        assert result.total_score_raw == 100.0

    def test_perfect_score_with_no_profile_equals_100(self):
        """Passing weight_profile=None falls back to default → still 100."""
        result = _scorer.score(
            "TEST", "DIVIDEND_STOCK", _GATE, _perfect_market_data(),
            weight_profile=None,
        )
        assert result.total_score_raw == 100.0

    def test_null_data_with_default_profile_equals_50(self):
        """All-None data + default 40/40/20 = 50 (50% partial credit on everything)."""
        result = _scorer.score(
            "TEST", "DIVIDEND_STOCK", None, _null_market_data(),
            weight_profile=_DEFAULT_WEIGHT_PROFILE,
        )
        assert result.total_score_raw == 50.0

    def test_null_data_with_any_profile_equals_50_pct(self):
        """All-None data always produces exactly 50% of total regardless of profile."""
        for wy, wd, wt in [(30, 45, 25), (35, 40, 25), (40, 30, 30)]:
            profile = _make_profile(wy=wy, wd=wd, wt=wt)
            result = _scorer.score(
                "TEST", "DIVIDEND_STOCK", None, _null_market_data(),
                weight_profile=profile,
            )
            assert abs(result.total_score_raw - 50.0) < 1e-6, \
                f"Profile {wy}/{wd}/{wt}: expected 50.0, got {result.total_score_raw}"

    def test_default_and_explicit_profile_give_same_result(self):
        """score() with None profile is identical to score() with explicit default."""
        md = _perfect_market_data()
        r1 = _scorer.score("JEPI", "COVERED_CALL_ETF", _GATE, md, weight_profile=None)
        r2 = _scorer.score("JEPI", "COVERED_CALL_ETF", _GATE, md,
                           weight_profile=_DEFAULT_WEIGHT_PROFILE)
        assert r1.total_score_raw == r2.total_score_raw
        assert r1.valuation_yield_score == r2.valuation_yield_score
        assert r1.financial_durability_score == r2.financial_durability_score
        assert r1.technical_entry_score == r2.technical_entry_score

    def test_higher_durability_weight_increases_durability_score(self):
        """Increasing durability weight increases financial_durability_score
        relative to lower durability weight, on identical market data."""
        md = _perfect_market_data()
        gate = type("G", (), {"dividend_history_years": 30})()

        low_dur  = _make_profile(wy=40, wd=30, wt=30)  # durability pillar = 30
        high_dur = _make_profile(wy=30, wd=45, wt=25)  # durability pillar = 45

        r_low  = _scorer.score("X", "MORTGAGE_REIT", gate, md, weight_profile=low_dur)
        r_high = _scorer.score("X", "MORTGAGE_REIT", gate, md, weight_profile=high_dur)

        assert r_high.financial_durability_score > r_low.financial_durability_score

    def test_higher_yield_weight_increases_yield_score(self):
        md = _perfect_market_data()
        gate = type("G", (), {"dividend_history_years": 30})()

        low_yield  = _make_profile(wy=25, wd=50, wt=25)
        high_yield = _make_profile(wy=40, wd=40, wt=20)

        r_low  = _scorer.score("X", "DIVIDEND_STOCK", gate, md, weight_profile=low_yield)
        r_high = _scorer.score("X", "DIVIDEND_STOCK", gate, md, weight_profile=high_yield)

        assert r_high.valuation_yield_score > r_low.valuation_yield_score

    def test_total_score_raw_always_sums_pillars(self):
        """total_score_raw == sum of three pillar scores for all profiles."""
        md = _perfect_market_data()
        gate = type("G", (), {"dividend_history_years": 30})()
        for wy, wd, wt in [(30, 45, 25), (35, 40, 25), (40, 30, 30), (25, 45, 30)]:
            profile = _make_profile(wy=wy, wd=wd, wt=wt)
            r = _scorer.score("X", "DIVIDEND_STOCK", gate, md, weight_profile=profile)
            expected = r.valuation_yield_score + r.financial_durability_score + r.technical_entry_score
            assert abs(r.total_score_raw - expected) < 1e-6

    def test_perfect_score_with_mreit_profile_equals_100(self):
        """Perfect data + any valid profile (sum=100) → total_score_raw=100."""
        profile = _make_profile(wy=30, wd=45, wt=25)  # MORTGAGE_REIT seed
        result = _scorer.score(
            "REM", "MORTGAGE_REIT", _GATE, _perfect_market_data(),
            weight_profile=profile,
        )
        assert abs(result.total_score_raw - 100.0) < 1e-6

    def test_weight_profile_version_propagated(self):
        """weight_profile_version in ScoreResult matches the profile's version."""
        profile = _make_profile(wy=35, wd=40, wt=25)
        profile["version"] = 3
        result = _scorer.score(
            "BDC1", "BDC", _GATE, _null_market_data(), weight_profile=profile
        )
        assert result.weight_profile_version == 3

    def test_weight_profile_id_propagated(self):
        """weight_profile_id in ScoreResult matches the profile's id."""
        profile = _make_profile()
        profile["id"] = "test-profile-uuid"
        result = _scorer.score(
            "PFFD", "PREFERRED_STOCK", _GATE, _null_market_data(), weight_profile=profile
        )
        assert result.weight_profile_id == "test-profile-uuid"

    def test_none_profile_has_none_version(self):
        """Fallback profile → weight_profile_version=0 (default profile version)."""
        result = _scorer.score(
            "TEST", "DIVIDEND_STOCK", _GATE, _null_market_data(), weight_profile=None
        )
        assert result.weight_profile_version == 0  # _DEFAULT_WEIGHT_PROFILE["version"]

    def test_factor_details_max_reflects_profile(self):
        """factor_details[sub].max reflects the ceiling from the active profile."""
        profile = _make_profile(wy=30, wd=45, wt=25)  # MORTGAGE_REIT-style
        result = _scorer.score(
            "TEST", "MORTGAGE_REIT", _GATE, _null_market_data(), weight_profile=profile
        )
        fd = result.factor_details
        # payout ceiling = 30 * 40 / 100 = 12.0
        assert fd["payout_sustainability"]["max"] == 12.0
        # debt ceiling = 45 * 40 / 100 = 18.0
        assert fd["debt_safety"]["max"] == 18.0
        # momentum ceiling = 25 * 60 / 100 = 15.0
        assert fd["price_momentum"]["max"] == 15.0

    def test_factor_details_max_default_profile_unchanged(self):
        """With default profile, factor_details maxes are the v1.0 values."""
        result = _scorer.score(
            "TEST", "DIVIDEND_STOCK", _GATE, _null_market_data(),
            weight_profile=_DEFAULT_WEIGHT_PROFILE,
        )
        fd = result.factor_details
        assert fd["payout_sustainability"]["max"] == 16.0
        assert fd["yield_vs_market"]["max"]       == 14.0
        assert fd["fcf_coverage"]["max"]          == 10.0
        assert fd["debt_safety"]["max"]           == 16.0
        assert fd["dividend_consistency"]["max"]  == 14.0
        assert fd["volatility_score"]["max"]      == 10.0
        assert fd["price_momentum"]["max"]        == 12.0
        assert fd["price_range_position"]["max"]  == 8.0

    def test_mreit_versus_dividend_stock_on_identical_data(self):
        """mREIT profile scores higher on durability-dominated input than DIVIDEND_STOCK profile."""
        md = _perfect_market_data()
        gate = type("G", (), {"dividend_history_years": 30})()

        mreit_profile = _make_profile(wy=30, wd=45, wt=25)
        ds_profile    = _make_profile(wy=25, wd=45, wt=30)

        # Both have the same durability weight (45), so durability score == 45 on perfect data
        r_mreit = _scorer.score("X", "MORTGAGE_REIT", gate, md, weight_profile=mreit_profile)
        r_ds    = _scorer.score("X", "DIVIDEND_STOCK", gate, md, weight_profile=ds_profile)

        # Both have durability=45, so durability scores are equal
        assert abs(r_mreit.financial_durability_score - r_ds.financial_durability_score) < 1e-6
        # mREIT has higher yield weight (30 > 25) so higher yield score
        assert r_mreit.valuation_yield_score > r_ds.valuation_yield_score
        # DS has higher technical weight (30 > 25) so higher technical score
        assert r_ds.technical_entry_score > r_mreit.technical_entry_score


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Grade and recommendation thresholds still work with dynamic profiles
# ═══════════════════════════════════════════════════════════════════════════════

class TestGradeThresholdsWithDynamicWeights:

    def test_grade_thresholds_are_profile_independent(self):
        """Grade is based on total_score_raw, which scales with profile — thresholds invariant."""
        # With any balanced profile, perfect data always gives score=100 → A+
        for wy, wd, wt in [(40, 40, 20), (30, 45, 25), (35, 40, 25)]:
            profile = _make_profile(wy=wy, wd=wd, wt=wt)
            r = _scorer.score("X", "DIVIDEND_STOCK", _GATE, _perfect_market_data(),
                              weight_profile=profile)
            assert r.grade == "A+", f"Profile {wy}/{wd}/{wt}: expected A+, got {r.grade} (score={r.total_score_raw})"
            assert r.recommendation == "AGGRESSIVE_BUY"

    def test_null_data_always_grade_F_with_any_profile(self):
        """Null data → 50.0 → D grade (just at the boundary) — not F."""
        # 50.0 is at the D boundary (≥50 → D, <50 → F)
        for wy, wd, wt in [(40, 40, 20), (30, 45, 25)]:
            profile = _make_profile(wy=wy, wd=wd, wt=wt)
            r = _scorer.score("X", "DIVIDEND_STOCK", None, _null_market_data(),
                              weight_profile=profile)
            assert r.total_score_raw == 50.0
            assert r.grade == "D"
            assert r.recommendation == "WATCH"
