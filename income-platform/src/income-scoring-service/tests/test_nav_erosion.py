"""
Unit tests for NAVErosionAnalyzer.

Fixed numpy random seed (42) is used where determinism matters.
For risk-classification tests that require specific probability values,
we monkeypatch numpy.random.normal to return controlled arrays.
"""
import numpy as np
import pytest

from app.scoring.nav_erosion import NAVErosionAnalyzer, NAVErosionResult


@pytest.fixture
def analyzer():
    return NAVErosionAnalyzer()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Missing / zero volatility → UNKNOWN, penalty 0
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingVolatility:
    def test_none_volatility_returns_unknown(self, analyzer):
        result = analyzer.analyze("JEPI", {}, n_simulations=1000)
        assert result.risk_classification == "UNKNOWN"

    def test_none_volatility_penalty_zero(self, analyzer):
        result = analyzer.analyze("JEPI", {}, n_simulations=1000)
        assert result.penalty == 0

    def test_zero_volatility_returns_unknown(self, analyzer):
        result = analyzer.analyze("JEPI", {"volatility": 0}, n_simulations=1000)
        assert result.risk_classification == "UNKNOWN"

    def test_zero_volatility_penalty_zero(self, analyzer):
        result = analyzer.analyze("JEPI", {"volatility": 0}, n_simulations=1000)
        assert result.penalty == 0

    def test_none_stats_dict_returns_unknown(self, analyzer):
        result = analyzer.analyze("JEPI", None, n_simulations=1000)
        assert result.risk_classification == "UNKNOWN"
        assert result.penalty == 0

    def test_empty_stats_dict_returns_unknown(self, analyzer):
        result = analyzer.analyze("JEPI", {}, n_simulations=1000)
        assert result.risk_classification == "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Low volatility → LOW risk, penalty 0
# ═══════════════════════════════════════════════════════════════════════════════

class TestLowRisk:
    def test_very_low_volatility_gives_low_risk(self, analyzer):
        # sigma = 0.005 → P(N(-0.03, 0.005) < -0.05) = P(Z < -4) ≈ 0.00003 → LOW
        np.random.seed(42)
        result = analyzer.analyze("JEPI", {"volatility": 0.5}, n_simulations=10_000)
        assert result.risk_classification == "LOW"
        assert result.penalty == 0

    def test_low_volatility_penalty_zero(self, analyzer):
        np.random.seed(42)
        result = analyzer.analyze("JEPI", {"volatility": 0.5}, n_simulations=10_000)
        assert result.penalty == 0

    def test_low_risk_prob_below_030(self, analyzer):
        np.random.seed(42)
        result = analyzer.analyze("JEPI", {"volatility": 0.5}, n_simulations=10_000)
        assert result.prob_erosion_gt_5pct < 0.30


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Mocked probabilities → each risk tier
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskClassificationMocked:
    """Use monkeypatch to inject controlled simulation outcomes."""

    def _mock_normal(self, monkeypatch, fraction_below_minus5: float, n: int = 10_000):
        """Returns an array where exactly `fraction` of values are < -0.05."""
        def _fn(mu, sigma, size):
            arr = np.full(size, 0.0)           # all values above -0.05
            n_bad = int(fraction_below_minus5 * size)
            arr[:n_bad] = -0.10                # force them below -0.05
            return arr
        monkeypatch.setattr("app.scoring.nav_erosion.np.random.normal", _fn)

    def test_moderate_risk_penalty_10(self, analyzer, monkeypatch):
        self._mock_normal(monkeypatch, 0.40)   # prob = 0.40 → MODERATE
        result = analyzer.analyze("JEPI", {"volatility": 15}, n_simulations=10_000)
        assert result.risk_classification == "MODERATE"
        assert result.penalty == 10

    def test_high_risk_penalty_20(self, analyzer, monkeypatch):
        self._mock_normal(monkeypatch, 0.60)   # prob = 0.60 → HIGH
        result = analyzer.analyze("JEPI", {"volatility": 15}, n_simulations=10_000)
        assert result.risk_classification == "HIGH"
        assert result.penalty == 20

    def test_severe_risk_penalty_30(self, analyzer, monkeypatch):
        self._mock_normal(monkeypatch, 0.75)   # prob = 0.75 → SEVERE
        result = analyzer.analyze("JEPI", {"volatility": 15}, n_simulations=10_000)
        assert result.risk_classification == "SEVERE"
        assert result.penalty == 30

    def test_low_boundary_exactly_030_is_moderate(self, analyzer, monkeypatch):
        # prob = 0.30 is NOT < 0.30, so should be MODERATE
        self._mock_normal(monkeypatch, 0.30)
        result = analyzer.analyze("JEPI", {"volatility": 15}, n_simulations=10_000)
        assert result.risk_classification == "MODERATE"

    def test_prob_exactly_050_is_high(self, analyzer, monkeypatch):
        self._mock_normal(monkeypatch, 0.50)
        result = analyzer.analyze("JEPI", {"volatility": 15}, n_simulations=10_000)
        assert result.risk_classification == "HIGH"

    def test_prob_exactly_070_is_severe(self, analyzer, monkeypatch):
        self._mock_normal(monkeypatch, 0.70)
        result = analyzer.analyze("JEPI", {"volatility": 15}, n_simulations=10_000)
        assert result.risk_classification == "SEVERE"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. n_simulations is configurable
# ═══════════════════════════════════════════════════════════════════════════════

class TestNSimulations:
    def test_n_simulations_reflected_in_result(self, analyzer):
        np.random.seed(42)
        result = analyzer.analyze("JEPI", {"volatility": 5}, n_simulations=500)
        assert result.n_simulations == 500

    def test_n_simulations_1000(self, analyzer):
        np.random.seed(42)
        result = analyzer.analyze("JEPI", {"volatility": 5}, n_simulations=1000)
        assert result.n_simulations == 1000

    def test_n_simulations_unknown_path_uses_value(self, analyzer):
        result = analyzer.analyze("JEPI", {}, n_simulations=9999)
        assert result.n_simulations == 9999


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Result structure
# ═══════════════════════════════════════════════════════════════════════════════

class TestResultFields:
    def test_result_is_nav_erosion_result(self, analyzer):
        np.random.seed(42)
        result = analyzer.analyze("JEPI", {"volatility": 5}, n_simulations=1000)
        assert isinstance(result, NAVErosionResult)

    def test_all_fields_present(self, analyzer):
        np.random.seed(42)
        result = analyzer.analyze("JEPI", {"volatility": 5}, n_simulations=1000)
        assert hasattr(result, "prob_erosion_gt_5pct")
        assert hasattr(result, "median_annual_nav_change_pct")
        assert hasattr(result, "risk_classification")
        assert hasattr(result, "penalty")
        assert hasattr(result, "n_simulations")

    def test_prob_bounded_0_to_1(self, analyzer):
        np.random.seed(42)
        result = analyzer.analyze("JEPI", {"volatility": 10}, n_simulations=1000)
        assert 0.0 <= result.prob_erosion_gt_5pct <= 1.0

    def test_unknown_risk_prob_is_zero(self, analyzer):
        result = analyzer.analyze("JEPI", {}, n_simulations=1000)
        assert result.prob_erosion_gt_5pct == 0.0

    def test_unknown_median_is_zero(self, analyzer):
        result = analyzer.analyze("JEPI", {}, n_simulations=1000)
        assert result.median_annual_nav_change_pct == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Determinism with fixed seed
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_seed_same_result(self, analyzer):
        np.random.seed(42)
        r1 = analyzer.analyze("JEPI", {"volatility": 15}, n_simulations=1000)
        np.random.seed(42)
        r2 = analyzer.analyze("JEPI", {"volatility": 15}, n_simulations=1000)
        assert r1.prob_erosion_gt_5pct == r2.prob_erosion_gt_5pct
        assert r1.median_annual_nav_change_pct == r2.median_annual_nav_change_pct
        assert r1.penalty == r2.penalty

    def test_different_seeds_may_differ(self, analyzer):
        np.random.seed(1)
        r1 = analyzer.analyze("JEPI", {"volatility": 8}, n_simulations=100)
        np.random.seed(99)
        r2 = analyzer.analyze("JEPI", {"volatility": 8}, n_simulations=100)
        # With small n the prob values will likely differ (not guaranteed but very probable)
        # We just verify both return valid results
        assert isinstance(r1, NAVErosionResult)
        assert isinstance(r2, NAVErosionResult)
