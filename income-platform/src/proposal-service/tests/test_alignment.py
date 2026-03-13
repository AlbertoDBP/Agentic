"""25 tests for compute_alignment() logic."""
import pytest
from app.proposal_engine.alignment import compute_alignment


# ---------------------------------------------------------------------------
# Group 1: veto_flags truthy → always "Vetoed" (5 tests)
# ---------------------------------------------------------------------------

class TestVetoAlwaysWins:
    def test_veto_single_flag(self):
        result = compute_alignment(0.8, 80.0, {"nav_erosion_penalty": 20.0})
        assert result == "Vetoed"

    def test_veto_grade_f(self):
        result = compute_alignment(0.9, 90.0, {"grade": "F"})
        assert result == "Vetoed"

    def test_veto_overrides_aligned_numbers(self):
        # Even when analyst and platform would align, veto wins
        result = compute_alignment(0.0, 50.0, {"nav_erosion_penalty": 16.0})
        assert result == "Vetoed"

    def test_veto_multiple_flags(self):
        result = compute_alignment(-0.5, 20.0, {"nav_erosion_penalty": 25.0, "grade": "F"})
        assert result == "Vetoed"

    def test_veto_with_none_sentiment(self):
        result = compute_alignment(None, None, {"nav_erosion_penalty": 20.0})
        assert result == "Vetoed"


# ---------------------------------------------------------------------------
# Group 2: divergence <= 0.25 → "Aligned" (5 tests)
# ---------------------------------------------------------------------------

class TestAligned:
    def test_zero_divergence(self):
        # sentiment=0.0, platform_score=50 → platform_sentiment=0.0, divergence=0
        result = compute_alignment(0.0, 50.0, None)
        assert result == "Aligned"

    def test_small_positive_divergence(self):
        # sentiment=0.5, platform_score=75 → platform_sentiment=0.5, divergence=0
        result = compute_alignment(0.5, 75.0, None)
        assert result == "Aligned"

    def test_small_negative_alignment(self):
        # sentiment=-0.5, platform_score=25 → platform_sentiment=-0.5, divergence=0
        result = compute_alignment(-0.5, 25.0, None)
        assert result == "Aligned"

    def test_divergence_within_threshold(self):
        # sentiment=0.3, platform_score=50 → platform_sentiment=0.0, divergence=0.3 > 0.25 — but let's pick 0.2
        # sentiment=0.2, platform_score=50 → divergence=0.2 → Aligned
        result = compute_alignment(0.2, 50.0, None)
        assert result == "Aligned"

    def test_near_perfect_alignment(self):
        # sentiment=0.8, platform_score=90 → platform_sentiment=0.8, divergence=0
        result = compute_alignment(0.8, 90.0, None)
        assert result == "Aligned"


# ---------------------------------------------------------------------------
# Group 3: divergence 0.25–0.50 → "Partial" (5 tests)
# ---------------------------------------------------------------------------

class TestPartial:
    def test_moderate_divergence(self):
        # sentiment=0.5, platform_score=50 → platform_sentiment=0.0, divergence=0.5 → boundary (Partial at <=0.50)
        # Pick divergence=0.35: sentiment=0.35, platform_score=50
        result = compute_alignment(0.35, 50.0, None)
        assert result == "Partial"

    def test_partial_negative_spread(self):
        # sentiment=-0.3, platform_score=50 → platform_sentiment=0.0, divergence=0.3 → Partial
        result = compute_alignment(-0.3, 50.0, None)
        assert result == "Partial"

    def test_partial_high_score_low_sentiment(self):
        # platform_score=85 → platform_sentiment=0.7
        # sentiment=0.3 → divergence=0.4 → Partial
        result = compute_alignment(0.3, 85.0, None)
        assert result == "Partial"

    def test_partial_both_negative(self):
        # sentiment=-0.7, platform_score=25 → platform_sentiment=-0.5, divergence=0.2 → Aligned? No…
        # Let's use divergence=0.4: sentiment=0.0, platform_score=70 → platform_sentiment=0.4 → divergence=0.4
        result = compute_alignment(0.0, 70.0, None)
        assert result == "Partial"

    def test_partial_mixed_direction(self):
        # sentiment=0.2, platform_score=30 → platform_sentiment=-0.4, divergence=0.6 → Divergent
        # Use: sentiment=0.1, platform_score=40 → platform_sentiment=-0.2, divergence=0.3 → Partial
        result = compute_alignment(0.1, 40.0, None)
        assert result == "Partial"


# ---------------------------------------------------------------------------
# Group 4: divergence > 0.50 → "Divergent" (5 tests)
# ---------------------------------------------------------------------------

class TestDivergent:
    def test_strong_divergence(self):
        # sentiment=0.8, platform_score=20 → platform_sentiment=-0.6, divergence=1.4
        result = compute_alignment(0.8, 20.0, None)
        assert result == "Divergent"

    def test_opposite_directions(self):
        # sentiment=-0.9, platform_score=90 → platform_sentiment=0.8, divergence=1.7
        result = compute_alignment(-0.9, 90.0, None)
        assert result == "Divergent"

    def test_large_spread(self):
        # sentiment=0.6, platform_score=0 → platform_sentiment=-1.0, divergence=1.6
        result = compute_alignment(0.6, 0.0, None)
        assert result == "Divergent"

    def test_analyst_bearish_platform_bullish(self):
        # sentiment=-0.7, platform_score=80 → platform_sentiment=0.6, divergence=1.3
        result = compute_alignment(-0.7, 80.0, None)
        assert result == "Divergent"

    def test_just_above_divergent_threshold(self):
        # sentiment=0.51, platform_score=50 → platform_sentiment=0.0, divergence=0.51
        result = compute_alignment(0.51, 50.0, None)
        assert result == "Divergent"


# ---------------------------------------------------------------------------
# Group 5: boundary conditions at exactly 0.25 and 0.50 (5 tests)
# ---------------------------------------------------------------------------

class TestBoundaryConditions:
    def test_exactly_0_25_is_aligned(self):
        # divergence exactly 0.25 → Aligned (<=0.25)
        # sentiment=0.25, platform_score=50 → platform_sentiment=0.0, divergence=0.25
        result = compute_alignment(0.25, 50.0, None)
        assert result == "Aligned"

    def test_exactly_0_50_is_partial(self):
        # divergence exactly 0.50 → Partial (<=0.50)
        # sentiment=0.5, platform_score=50 → platform_sentiment=0.0, divergence=0.50
        result = compute_alignment(0.5, 50.0, None)
        assert result == "Partial"

    def test_just_above_0_25_is_partial(self):
        # sentiment=0.26, platform_score=50 → divergence=0.26 → Partial
        result = compute_alignment(0.26, 50.0, None)
        assert result == "Partial"

    def test_just_below_0_25_is_aligned(self):
        # sentiment=0.24, platform_score=50 → divergence=0.24 → Aligned
        result = compute_alignment(0.24, 50.0, None)
        assert result == "Aligned"

    def test_just_above_0_50_is_divergent(self):
        # sentiment=0.51, platform_score=50 → divergence=0.51 → Divergent
        result = compute_alignment(0.51, 50.0, None)
        assert result == "Divergent"
