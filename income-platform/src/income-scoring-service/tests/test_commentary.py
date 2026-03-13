"""
Agent 03 — Income Scoring Service
Tests: score_commentary / _generate_commentary

20 tests covering:
  - Grade letters in commentary
  - Penalty language for poor safety grades
  - Chowder number mention
  - Non-empty string
  - Positive framing for high scores
  - Cautionary framing for low scores
  - Grade boundary conditions
  - Called directly from scorer context (no HTTP calls)
"""
import pytest

from app.api.scores import _generate_commentary
from app.scoring.income_scorer import IncomeScorer


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_factor_details(
    payout_score=12.0, payout_max=16.0,
    yield_score=10.0,  yield_max=14.0,
    fcf_score=8.0,     fcf_max=10.0,
    debt_score=12.0,   debt_max=16.0,
    consist_score=10.0, consist_max=14.0,
    vol_score=8.0,     vol_max=10.0,
    momentum_score=8.0, momentum_max=12.0,
    range_score=5.0,   range_max=8.0,
    chowder_number=None, chowder_signal=None,
) -> dict:
    """Build a minimal factor_details dict mirroring IncomeScorer output."""
    return {
        "payout_sustainability": {"value": 0.45, "score": payout_score, "max": payout_max},
        "yield_vs_market":       {"value": 4.2,  "score": yield_score,  "max": yield_max},
        "fcf_coverage":          {"value": 1e9,  "score": fcf_score,    "max": fcf_max},
        "debt_safety":           {"value": 0.4,  "score": debt_score,   "max": debt_max},
        "dividend_consistency":  {"value": 20,   "score": consist_score,"max": consist_max},
        "volatility_score":      {"value": 3.0,  "score": vol_score,    "max": vol_max},
        "price_momentum":        {"value": -8.0, "score": momentum_score,"max": momentum_max},
        "price_range_position":  {"value": 0.25, "score": range_score,  "max": range_max},
        "chowder_number": chowder_number,
        "chowder_signal": chowder_signal,
    }


def _commentary(
    total_score=75.0,
    grade="B+",
    recommendation="ACCUMULATE",
    signal_penalty=0.0,
    signal_penalty_details=None,
    nav_erosion_penalty=0.0,
    nav_erosion_details=None,
    chowder_signal=None,
    chowder_number=None,
    data_completeness_pct=100.0,
    factor_details=None,
) -> str:
    """Convenience wrapper around _generate_commentary."""
    fd = factor_details if factor_details is not None else _make_factor_details(
        chowder_number=chowder_number, chowder_signal=chowder_signal
    )
    return _generate_commentary(
        factor_details=fd,
        signal_penalty=signal_penalty,
        signal_penalty_details=signal_penalty_details,
        nav_erosion_penalty=nav_erosion_penalty,
        nav_erosion_details=nav_erosion_details,
        total_score=total_score,
        grade=grade,
        recommendation=recommendation,
        chowder_signal=chowder_signal,
        chowder_number=chowder_number,
        data_completeness_pct=data_completeness_pct,
    )


# ── 1. Commentary is always a non-empty string ─────────────────────────────────

class TestCommentaryIsNonEmpty:

    def test_returns_string(self):
        result = _commentary()
        assert isinstance(result, str)

    def test_non_empty_for_typical_score(self):
        result = _commentary(total_score=75.0, grade="B+")
        assert len(result) > 0

    def test_non_empty_for_perfect_score(self):
        result = _commentary(total_score=100.0, grade="A+", recommendation="AGGRESSIVE_BUY")
        assert len(result) > 0

    def test_non_empty_for_zero_score(self):
        result = _commentary(total_score=0.0, grade="F", recommendation="WATCH")
        assert len(result) > 0


# ── 2. Grade letter appears in commentary ─────────────────────────────────────

class TestGradeLetterInCommentary:

    def test_grade_A_plus_appears(self):
        result = _commentary(total_score=97.0, grade="A+", recommendation="AGGRESSIVE_BUY")
        assert "A+" in result

    def test_grade_A_appears(self):
        result = _commentary(total_score=87.0, grade="A", recommendation="AGGRESSIVE_BUY")
        assert "A" in result

    def test_grade_F_appears(self):
        result = _commentary(total_score=30.0, grade="F", recommendation="WATCH")
        assert "F" in result

    def test_grade_B_appears(self):
        result = _commentary(total_score=70.0, grade="B", recommendation="ACCUMULATE")
        assert "B" in result

    def test_grade_C_appears(self):
        result = _commentary(total_score=62.0, grade="C", recommendation="WATCH")
        assert "C" in result

    def test_grade_D_appears(self):
        result = _commentary(total_score=52.0, grade="D", recommendation="WATCH")
        assert "D" in result


# ── 3. Penalty language when signal_penalty > 0 ───────────────────────────────

class TestPenaltyMention:

    def test_bearish_signal_penalty_mentions_penalty(self):
        result = _commentary(
            total_score=60.0,
            grade="C",
            signal_penalty=10.0,
            signal_penalty_details={"signal_strength": "STRONG"},
        )
        assert "penalty" in result.lower()

    def test_bearish_signal_penalty_mentions_signal_strength(self):
        result = _commentary(
            total_score=65.0,
            grade="C",
            signal_penalty=8.0,
            signal_penalty_details={"signal_strength": "MODERATE"},
        )
        # "moderate" should appear in the penalty description
        assert "moderate" in result.lower()

    def test_nav_erosion_penalty_mentioned(self):
        result = _commentary(
            total_score=58.0,
            grade="D",
            nav_erosion_penalty=12.0,
            nav_erosion_details={"risk_classification": "HIGH"},
        )
        assert "penalty" in result.lower() or "nav" in result.lower() or "erosion" in result.lower()

    def test_no_penalty_language_when_no_penalty(self):
        result = _commentary(
            total_score=80.0,
            grade="A",
            signal_penalty=0.0,
            nav_erosion_penalty=0.0,
        )
        # When no penalty, "penalty" word should not appear
        assert "penalty" not in result.lower()


# ── 4. Chowder number mention ──────────────────────────────────────────────────

class TestChowderMention:

    def test_chowder_signal_appears_when_available(self):
        result = _commentary(
            total_score=80.0,
            grade="A",
            chowder_signal="ATTRACTIVE",
            chowder_number=13.5,
        )
        assert "attractive" in result.lower() or "13.5" in result

    def test_chowder_number_value_in_commentary(self):
        result = _commentary(
            total_score=75.0,
            grade="B+",
            chowder_signal="BORDERLINE",
            chowder_number=9.0,
        )
        assert "9.0" in result or "borderline" in result.lower()

    def test_no_chowder_mention_when_none(self):
        result = _commentary(
            total_score=70.0,
            grade="B",
            chowder_signal=None,
            chowder_number=None,
        )
        # Chowder keyword should not appear when data is missing
        assert "chowder" not in result.lower()

    def test_chowder_unattractive_signal_present(self):
        result = _commentary(
            total_score=55.0,
            grade="D",
            chowder_signal="UNATTRACTIVE",
            chowder_number=4.5,
        )
        assert "unattractive" in result.lower() or "4.5" in result


# ── 5. High-score positive framing (score ≥ 80) ───────────────────────────────

class TestHighScorePositiveFraming:

    def test_high_score_contains_accumulate_or_buy(self):
        result = _commentary(
            total_score=85.0,
            grade="A",
            recommendation="AGGRESSIVE_BUY",
        )
        # "Aggressive Buy" or "Accumulate" should appear (from rec_label)
        assert "aggressive buy" in result.lower() or "buy" in result.lower()

    def test_high_score_score_number_present(self):
        result = _commentary(total_score=90.0, grade="A+", recommendation="AGGRESSIVE_BUY")
        assert "90" in result


# ── 6. Low-score cautionary framing (score < 40) ─────────────────────────────

class TestLowScoreCautiousFraming:

    def test_low_score_contains_watch(self):
        result = _commentary(
            total_score=30.0,
            grade="F",
            recommendation="WATCH",
        )
        assert "watch" in result.lower()

    def test_low_score_grade_F_in_commentary(self):
        result = _commentary(total_score=25.0, grade="F", recommendation="WATCH")
        assert "F" in result


# ── 7. Grade boundary conditions ──────────────────────────────────────────────

class TestGradeBoundaries:

    def test_score_95_gives_A_plus(self):
        grade = IncomeScorer._grade(95.0)
        assert grade == "A+"

    def test_score_94_gives_A(self):
        grade = IncomeScorer._grade(94.9)
        assert grade == "A"

    def test_score_85_gives_A(self):
        grade = IncomeScorer._grade(85.0)
        assert grade == "A"

    def test_score_75_gives_B_plus(self):
        grade = IncomeScorer._grade(75.0)
        assert grade == "B+"

    def test_score_70_gives_B(self):
        grade = IncomeScorer._grade(70.0)
        assert grade == "B"

    def test_score_60_gives_C(self):
        grade = IncomeScorer._grade(60.0)
        assert grade == "C"

    def test_score_50_gives_D(self):
        grade = IncomeScorer._grade(50.0)
        assert grade == "D"

    def test_score_49_gives_F(self):
        grade = IncomeScorer._grade(49.9)
        assert grade == "F"

    def test_commentary_grade_matches_threshold_A_at_85(self):
        result = _commentary(total_score=85.0, grade="A", recommendation="AGGRESSIVE_BUY")
        assert "A" in result
        assert "85" in result

    def test_commentary_grade_F_at_boundary(self):
        result = _commentary(total_score=44.0, grade="F", recommendation="WATCH")
        assert "F" in result
        assert "44" in result
