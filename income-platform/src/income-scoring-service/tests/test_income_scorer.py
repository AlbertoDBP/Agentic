"""
Unit tests for IncomeScorer — 35+ test cases, no real API calls.

All tests use mocked market_data dicts and a lightweight FakeGateResult
to stand in for the quality gate result object.
"""
import pytest

from app.scoring.income_scorer import IncomeScorer, ScoreResult


# ── Helpers ────────────────────────────────────────────────────────────────────

class FakeGateResult:
    """Minimal stand-in for GateResult / QualityGateResult."""
    def __init__(self, dividend_history_years=None):
        self.dividend_history_years = dividend_history_years


def _make_divs(amount: float, count: int = 4, start_year: int = 2023) -> list:
    """Generate `count` quarterly dividend records with the given amount."""
    records = []
    months = [11, 8, 5, 2]
    for i in range(count):
        year  = start_year - (i // 4)
        month = months[i % 4]
        records.append({
            "ex_date": f"{year}-{month:02d}-01",
            "amount": amount,
        })
    return records


@pytest.fixture
def scorer():
    return IncomeScorer()


@pytest.fixture
def perfect_market_data():
    """Market data that should yield a near-perfect score (100)."""
    return {
        "fundamentals": {
            "payout_ratio":    0.35,        # < 0.40  → 16
            "free_cash_flow":  1_000_000_000,  # > 0   → 10
            "debt_to_equity":  0.3,         # < 0.50  → 16
        },
        "dividend_history": _make_divs(1.25),   # 4 × $1.25 = $5 annual
        "history_stats": {
            "avg_price":       100.0,        # yield = 5% > 4%  → 14
            "volatility":      1.5,          # < 2              → 10
            "price_change_pct": -16.0,       # < -15% oversold  → 12
            "min_price":       90.0,
            "max_price":       130.0,
        },
        "current_price": {"price": 91.0},    # ratio = (91-90)/(130-90) = 0.025 < 0.3 → 8
    }


@pytest.fixture
def null_market_data():
    """All scoreable fields absent — every dimension falls back to 50%."""
    return {
        "fundamentals":    {},
        "dividend_history": [],
        "history_stats":   {},
        "current_price":   {},
    }


@pytest.fixture
def gate26():
    return FakeGateResult(dividend_history_years=26)   # > 25 → 14 pts


@pytest.fixture
def gate_none():
    return FakeGateResult(dividend_history_years=None)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. End-to-end: perfect stock
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerfectScore:
    def test_perfect_stock_scores_at_least_85(self, scorer, perfect_market_data, gate26):
        result = scorer.score("JNJ", "DIVIDEND_STOCK", gate26, perfect_market_data)
        assert result.total_score >= 85

    def test_perfect_stock_grade_a_or_better(self, scorer, perfect_market_data, gate26):
        result = scorer.score("JNJ", "DIVIDEND_STOCK", gate26, perfect_market_data)
        assert result.grade in ("A", "A+")

    def test_perfect_stock_recommendation_aggressive_buy(
        self, scorer, perfect_market_data, gate26
    ):
        result = scorer.score("JNJ", "DIVIDEND_STOCK", gate26, perfect_market_data)
        assert result.recommendation == "AGGRESSIVE_BUY"

    def test_perfect_score_total_is_sum_of_components(
        self, scorer, perfect_market_data, gate26
    ):
        result = scorer.score("JNJ", "DIVIDEND_STOCK", gate26, perfect_market_data)
        expected = (
            result.valuation_yield_score
            + result.financial_durability_score
            + result.technical_entry_score
        )
        assert result.total_score_raw == pytest.approx(expected)

    def test_result_is_score_result_instance(self, scorer, perfect_market_data, gate26):
        result = scorer.score("JNJ", "DIVIDEND_STOCK", gate26, perfect_market_data)
        assert isinstance(result, ScoreResult)

    def test_ticker_uppercased(self, scorer, perfect_market_data, gate26):
        result = scorer.score("jnj", "DIVIDEND_STOCK", gate26, perfect_market_data)
        assert result.ticker == "JNJ"

    def test_nav_penalty_zero_by_default(self, scorer, perfect_market_data, gate26):
        result = scorer.score("JNJ", "DIVIDEND_STOCK", gate26, perfect_market_data)
        assert result.nav_erosion_penalty == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. All-None data → partial credit (50% per dimension, never zero, never error)
# ═══════════════════════════════════════════════════════════════════════════════

class TestNullData:
    def test_all_none_returns_scoreresult(self, scorer, null_market_data, gate_none):
        result = scorer.score("AAPL", "DIVIDEND_STOCK", gate_none, null_market_data)
        assert isinstance(result, ScoreResult)

    def test_all_none_score_not_zero(self, scorer, null_market_data, gate_none):
        result = scorer.score("AAPL", "DIVIDEND_STOCK", gate_none, null_market_data)
        assert result.total_score > 0

    def test_all_none_score_is_50(self, scorer, null_market_data, gate_none):
        # 50% of each: 8+7+5+8+7+5+6+4 = 50
        result = scorer.score("AAPL", "DIVIDEND_STOCK", gate_none, null_market_data)
        assert result.total_score_raw == pytest.approx(50.0)

    def test_all_none_completeness_zero(self, scorer, null_market_data, gate_none):
        result = scorer.score("AAPL", "DIVIDEND_STOCK", gate_none, null_market_data)
        assert result.data_completeness_pct == pytest.approx(0.0)

    def test_all_none_grade_d(self, scorer, null_market_data, gate_none):
        result = scorer.score("AAPL", "DIVIDEND_STOCK", gate_none, null_market_data)
        assert result.grade == "D"

    def test_all_none_recommendation_watch(self, scorer, null_market_data, gate_none):
        result = scorer.score("AAPL", "DIVIDEND_STOCK", gate_none, null_market_data)
        assert result.recommendation == "WATCH"

    def test_none_quality_gate_result_accepted(self, scorer, null_market_data):
        result = scorer.score("AAPL", "DIVIDEND_STOCK", None, null_market_data)
        assert isinstance(result, ScoreResult)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. payout_sustainability sub-component (max 16)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPayoutSustainability:
    def _score(self, scorer, payout_ratio):
        md = {"fundamentals": {"payout_ratio": payout_ratio}, "dividend_history": [], "history_stats": {}, "current_price": {}}
        r = scorer.score("X", "DIVIDEND_STOCK", FakeGateResult(), md)
        return r.factor_details["payout_sustainability"]["score"]

    def test_payout_below_040_gives_16(self, scorer):
        assert self._score(scorer, 0.39) == 16

    def test_payout_below_060_gives_12(self, scorer):
        assert self._score(scorer, 0.59) == 12

    def test_payout_below_075_gives_8(self, scorer):
        assert self._score(scorer, 0.74) == 8

    def test_payout_below_090_gives_4(self, scorer):
        assert self._score(scorer, 0.89) == 4

    def test_payout_above_090_gives_0(self, scorer):
        assert self._score(scorer, 0.95) == 0

    def test_payout_none_gives_8_partial(self, scorer):
        assert self._score(scorer, None) == 8


# ═══════════════════════════════════════════════════════════════════════════════
# 4. yield_vs_market sub-component (max 14)
# ═══════════════════════════════════════════════════════════════════════════════

class TestYieldVsMarket:
    def _score(self, scorer, annual_div, avg_price=100.0):
        divs = _make_divs(annual_div / 4) if annual_div else []
        md = {
            "fundamentals": {},
            "dividend_history": divs,
            "history_stats": {"avg_price": avg_price},
            "current_price": {},
        }
        r = scorer.score("X", "DIVIDEND_STOCK", FakeGateResult(), md)
        return r.factor_details["yield_vs_market"]["score"]

    def test_yield_above_4pct_gives_14(self, scorer):
        assert self._score(scorer, 5.0) == 14   # 5% yield

    def test_yield_above_3pct_gives_10(self, scorer):
        assert self._score(scorer, 3.5) == 10   # 3.5% yield

    def test_yield_above_2pct_gives_6(self, scorer):
        assert self._score(scorer, 2.5) == 6    # 2.5% yield

    def test_yield_above_1pct_gives_2(self, scorer):
        assert self._score(scorer, 1.5) == 2    # 1.5% yield

    def test_yield_below_1pct_gives_0(self, scorer):
        assert self._score(scorer, 0.5) == 0    # 0.5% yield

    def test_yield_none_no_history_gives_7_partial(self, scorer):
        assert self._score(scorer, None) == 7


# ═══════════════════════════════════════════════════════════════════════════════
# 5. fcf_coverage sub-component (max 10)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFCFCoverage:
    def _score(self, scorer, fcf):
        md = {"fundamentals": {"free_cash_flow": fcf}, "dividend_history": [], "history_stats": {}, "current_price": {}}
        r = scorer.score("X", "DIVIDEND_STOCK", FakeGateResult(), md)
        return r.factor_details["fcf_coverage"]["score"]

    def test_positive_fcf_gives_10(self, scorer):
        assert self._score(scorer, 1_000_000) == 10

    def test_zero_fcf_gives_5(self, scorer):
        assert self._score(scorer, 0) == 5

    def test_negative_fcf_gives_0(self, scorer):
        assert self._score(scorer, -500_000) == 0

    def test_none_fcf_gives_5_partial(self, scorer):
        assert self._score(scorer, None) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# 6. debt_safety sub-component (max 16)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDebtSafety:
    def _score(self, scorer, d2e):
        md = {"fundamentals": {"debt_to_equity": d2e}, "dividend_history": [], "history_stats": {}, "current_price": {}}
        r = scorer.score("X", "DIVIDEND_STOCK", FakeGateResult(), md)
        return r.factor_details["debt_safety"]["score"]

    def test_d2e_below_050_gives_16(self, scorer):
        assert self._score(scorer, 0.4) == 16

    def test_d2e_below_100_gives_12(self, scorer):
        assert self._score(scorer, 0.8) == 12

    def test_d2e_below_150_gives_8(self, scorer):
        assert self._score(scorer, 1.2) == 8

    def test_d2e_below_200_gives_4(self, scorer):
        assert self._score(scorer, 1.7) == 4

    def test_d2e_above_200_gives_0(self, scorer):
        assert self._score(scorer, 2.5) == 0

    def test_d2e_none_gives_8_partial(self, scorer):
        assert self._score(scorer, None) == 8


# ═══════════════════════════════════════════════════════════════════════════════
# 7. dividend_consistency sub-component (max 14)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDividendConsistency:
    def _score(self, scorer, years):
        md = {"fundamentals": {}, "dividend_history": [], "history_stats": {}, "current_price": {}}
        r = scorer.score("X", "DIVIDEND_STOCK", FakeGateResult(dividend_history_years=years), md)
        return r.factor_details["dividend_consistency"]["score"]

    def test_26_years_gives_14(self, scorer):
        assert self._score(scorer, 26) == 14

    def test_16_years_gives_10(self, scorer):
        assert self._score(scorer, 16) == 10

    def test_11_years_gives_7(self, scorer):
        assert self._score(scorer, 11) == 7

    def test_5_years_gives_4(self, scorer):
        assert self._score(scorer, 5) == 4

    def test_none_years_gives_7_partial(self, scorer):
        assert self._score(scorer, None) == 7


# ═══════════════════════════════════════════════════════════════════════════════
# 8. volatility_score sub-component (max 10)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVolatilityScore:
    def _score(self, scorer, vol):
        md = {"fundamentals": {}, "dividend_history": [], "history_stats": {"volatility": vol}, "current_price": {}}
        r = scorer.score("X", "DIVIDEND_STOCK", FakeGateResult(), md)
        return r.factor_details["volatility_score"]["score"]

    def test_vol_below_2_gives_10(self, scorer):
        assert self._score(scorer, 1.5) == 10

    def test_vol_below_5_gives_7(self, scorer):
        assert self._score(scorer, 3.0) == 7

    def test_vol_below_10_gives_4(self, scorer):
        assert self._score(scorer, 7.0) == 4

    def test_vol_below_20_gives_2(self, scorer):
        assert self._score(scorer, 15.0) == 2

    def test_vol_above_20_gives_0(self, scorer):
        assert self._score(scorer, 25.0) == 0

    def test_vol_none_gives_5_partial(self, scorer):
        assert self._score(scorer, None) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# 9. price_momentum sub-component (max 12)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPriceMomentum:
    def _score(self, scorer, pct):
        md = {"fundamentals": {}, "dividend_history": [], "history_stats": {"price_change_pct": pct}, "current_price": {}}
        r = scorer.score("X", "DIVIDEND_STOCK", FakeGateResult(), md)
        return r.factor_details["price_momentum"]["score"]

    def test_oversold_gives_12(self, scorer):
        assert self._score(scorer, -20.0) == 12

    def test_slight_down_gives_8(self, scorer):
        assert self._score(scorer, -10.0) == 8

    def test_flat_gives_6(self, scorer):
        assert self._score(scorer, 0.0) == 6

    def test_slightly_up_gives_3(self, scorer):
        assert self._score(scorer, 10.0) == 3

    def test_strong_up_gives_0(self, scorer):
        assert self._score(scorer, 20.0) == 0

    def test_none_gives_6_partial(self, scorer):
        assert self._score(scorer, None) == 6


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Grade thresholds
# ═══════════════════════════════════════════════════════════════════════════════

class TestGradeThresholds:
    def test_grade_a_plus_at_95(self, scorer):
        assert IncomeScorer._grade(95) == "A+"

    def test_grade_a_at_85(self, scorer):
        assert IncomeScorer._grade(85) == "A"

    def test_grade_b_plus_at_75(self, scorer):
        assert IncomeScorer._grade(75) == "B+"

    def test_grade_b_at_70(self, scorer):
        assert IncomeScorer._grade(70) == "B"

    def test_grade_c_at_60(self, scorer):
        assert IncomeScorer._grade(60) == "C"

    def test_grade_d_at_50(self, scorer):
        assert IncomeScorer._grade(50) == "D"

    def test_grade_f_at_49(self, scorer):
        assert IncomeScorer._grade(49) == "F"

    def test_grade_f_at_0(self, scorer):
        assert IncomeScorer._grade(0) == "F"


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Recommendation thresholds
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecommendation:
    def test_aggressive_buy_at_85(self):
        assert IncomeScorer._recommendation(85) == "AGGRESSIVE_BUY"

    def test_accumulate_at_70(self):
        assert IncomeScorer._recommendation(70) == "ACCUMULATE"

    def test_watch_at_69(self):
        assert IncomeScorer._recommendation(69) == "WATCH"

    def test_watch_at_0(self):
        assert IncomeScorer._recommendation(0) == "WATCH"


# ═══════════════════════════════════════════════════════════════════════════════
# 12. factor_details structure
# ═══════════════════════════════════════════════════════════════════════════════

class TestFactorDetails:
    def test_factor_details_has_all_eight_keys(self, scorer, null_market_data, gate_none):
        result = scorer.score("X", "DIVIDEND_STOCK", gate_none, null_market_data)
        expected_keys = {
            "payout_sustainability", "yield_vs_market", "fcf_coverage",
            "debt_safety", "dividend_consistency", "volatility_score",
            "price_momentum", "price_range_position",
        }
        assert set(result.factor_details.keys()) == expected_keys

    def test_each_factor_has_value_score_max(self, scorer, null_market_data, gate_none):
        result = scorer.score("X", "DIVIDEND_STOCK", gate_none, null_market_data)
        for key, detail in result.factor_details.items():
            assert "score" in detail, f"Missing 'score' in {key}"
            assert "max"   in detail, f"Missing 'max' in {key}"
