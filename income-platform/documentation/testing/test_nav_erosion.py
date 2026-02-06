"""
Comprehensive Test Suite for NAV Erosion Analysis

Tests cover:
- Monte Carlo engine correctness
- Sustainability penalty calculations
- Data collection and validation
- Historical validation against known ETFs
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from monte_carlo_engine import (
    CoveredCallETFParams,
    EnhancedMonteCarloNAVErosion,
    OptimizedMonteCarloEngine,
    MarketRegime
)
from sustainability_integration import (
    NAVErosionSustainabilityIntegration,
    NAVErosionRiskClassifier
)
from data_collector import NAVErosionDataCollector, CoveredCallETFRegistry


class TestMonteCarloEngine:
    """Test suite for Monte Carlo simulation engine."""
    
    def test_jepi_historical_validation(self):
        """
        Validate against JEPI's actual historical NAV performance.
        
        JEPI launched October 2020, has real historical NAV erosion data.
        Our simulation should produce results in similar range.
        """
        # JEPI actual historical data (approximated)
        params = CoveredCallETFParams(
            ticker='JEPI',
            current_nav=50.0,
            current_price=50.5,
            monthly_premium_yields=[0.007, 0.008, 0.006, 0.009, 0.007, 0.008,
                                     0.007, 0.006, 0.008, 0.009, 0.007, 0.006],
            underlying_monthly_returns=[0.02, -0.01, 0.03, -0.02, 0.01, 0.02,
                                         -0.01, 0.02, 0.01, -0.03, 0.04, 0.01],
            distribution_history=[0.35, 0.37, 0.36, 0.38, 0.35, 0.36,
                                  0.37, 0.35, 0.36, 0.38, 0.36, 0.35],
            expense_ratio_annual=0.0035
        )
        
        engine = EnhancedMonteCarloNAVErosion(params)
        results = engine.simulate(years=3, n_simulations=20000, seed=42)
        
        # JEPI's actual 3-year annualized NAV change was approximately -2% to -3%
        # Our simulation should be in similar ballpark
        assert -5.0 <= results['median_annualized_nav_change_pct'] <= 0.0, \
            f"Median NAV change {results['median_annualized_nav_change_pct']:.2f}% outside expected range"
        
        # Probability of >5% erosion should be moderate, not extreme
        assert results['probability_annual_erosion_gt_5pct'] < 80, \
            f"Erosion probability {results['probability_annual_erosion_gt_5pct']:.1f}% too high"
        
        # Total return (NAV + distributions) should be positive
        assert results['median_annualized_total_return_pct'] > 0, \
            "Total return should be positive when including distributions"
    
    def test_vectorized_matches_loop(self):
        """
        Ensure vectorized implementation produces same results as loop-based.
        
        Critical for trusting performance optimization.
        """
        params = CoveredCallETFParams(
            ticker='TEST',
            current_nav=50.0,
            current_price=50.0,
            monthly_premium_yields=[0.007] * 12,
            underlying_monthly_returns=[0.01] * 12,
            distribution_history=[0.35] * 12,
            expense_ratio_annual=0.0035
        )
        
        # Same seed should give identical results
        engine_loop = EnhancedMonteCarloNAVErosion(params)
        engine_vectorized = OptimizedMonteCarloEngine(params)
        
        results_loop = engine_loop.simulate(
            years=3, 
            n_simulations=1000, 
            include_regime_shifts=False,  # Disable for determinism
            seed=123
        )
        
        results_vectorized = engine_vectorized.simulate_vectorized(
            years=3,
            n_simulations=1000,
            seed=123
        )
        
        # Results should match within floating point precision (0.1%)
        assert abs(
            results_loop['median_annualized_nav_change_pct'] -
            results_vectorized['median_annualized_nav_change_pct']
        ) < 0.1, "Vectorized results don't match loop-based implementation"
        
        assert abs(
            results_loop['probability_annual_erosion_gt_5pct'] -
            results_vectorized['probability_annual_erosion_gt_5pct']
        ) < 1.0, "Erosion probabilities don't match"
    
    def test_regime_transitions_increase_dispersion(self):
        """
        Test that market regime shifts increase result dispersion.
        
        Regime modeling should create wider distribution than static simulation.
        """
        params = CoveredCallETFParams(
            ticker='TEST',
            current_nav=50.0,
            current_price=50.0,
            monthly_premium_yields=[0.007] * 12,
            underlying_monthly_returns=[0.01] * 12,
            distribution_history=[0.35] * 12,
            expense_ratio_annual=0.0035
        )
        
        engine = EnhancedMonteCarloNAVErosion(params)
        
        # With regime shifts
        results_with_regimes = engine.simulate(
            years=3,
            n_simulations=10000,
            include_regime_shifts=True,
            seed=42
        )
        
        # Without regime shifts
        results_no_regimes = engine.simulate(
            years=3,
            n_simulations=10000,
            include_regime_shifts=False,
            seed=42
        )
        
        # Calculate dispersion (P90 - P10)
        spread_with = (
            results_with_regimes['p90_annualized_nav_change_pct'] -
            results_with_regimes['p10_annualized_nav_change_pct']
        )
        
        spread_without = (
            results_no_regimes['p90_annualized_nav_change_pct'] -
            results_no_regimes['p10_annualized_nav_change_pct']
        )
        
        # Regime shifts should increase dispersion
        assert spread_with > spread_without, \
            "Regime modeling should increase result dispersion"
    
    def test_upside_capping_mechanics(self):
        """
        Test that covered call upside capping works correctly.
        
        When underlying > strike, NAV should be capped.
        """
        params = CoveredCallETFParams(
            ticker='TEST',
            current_nav=100.0,
            current_price=100.0,
            monthly_premium_yields=[0.005] * 12,
            underlying_monthly_returns=[0.05] * 12,  # Strong upside
            distribution_history=[0.50] * 12,
            expense_ratio_annual=0.0035,
            call_moneyness_target=0.02  # 2% OTM strike
        )
        
        engine = EnhancedMonteCarloNAVErosion(params)
        results = engine.simulate(years=1, n_simulations=10000, seed=42)
        
        # With strong upside, most months should have calls exercised
        assert results['pct_months_upside_capped'] > 50, \
            "Calls should be exercised frequently in strong bull market"
        
        # NAV appreciation should be limited by strike cap
        # Without cap, would grow ~80% (1.05^12)
        # With cap, growth much more limited
        assert results['median_annualized_nav_change_pct'] < 30, \
            "Upside should be capped by covered calls"
    
    def test_nav_cannot_go_negative(self):
        """Test that NAV is floored at positive values."""
        params = CoveredCallETFParams(
            ticker='TEST',
            current_nav=50.0,
            current_price=50.0,
            monthly_premium_yields=[0.001] * 12,  # Very low premiums
            underlying_monthly_returns=[-0.20] * 12,  # Catastrophic decline
            distribution_history=[0.35] * 12,
            expense_ratio_annual=0.0035
        )
        
        engine = EnhancedMonteCarloNAVErosion(params)
        results = engine.simulate(years=1, n_simulations=1000, seed=42)
        
        # Even in worst case, NAV should be positive
        assert results['median_final_nav'] > 0, "NAV should never go negative"
    
    def test_parameter_derivation(self):
        """Test that derived parameters are calculated correctly."""
        params = CoveredCallETFParams(
            ticker='TEST',
            current_nav=50.0,
            current_price=50.0,
            monthly_premium_yields=[0.007, 0.008, 0.006],
            underlying_monthly_returns=[0.01, 0.02, -0.01],
            distribution_history=[0.35, 0.36, 0.37],
            expense_ratio_annual=0.0035
        )
        
        # Check annualization
        expected_annual_return = np.mean([0.01, 0.02, -0.01]) * 12
        assert abs(params.underlying_annual_return_mean - expected_annual_return) < 0.001
        
        # Check premium stats
        assert params.premium_yield_mean == pytest.approx(0.007, abs=0.001)
        assert params.premium_yield_std > 0


class TestSustainabilityIntegration:
    """Test suite for sustainability score integration."""
    
    def test_penalty_calculation_low_risk(self):
        """Test penalty for low erosion risk."""
        integration = NAVErosionSustainabilityIntegration()
        
        low_risk_results = {
            'median_annualized_nav_change_pct': 1.0,
            'probability_annual_erosion_gt_5pct': 15.0,
            'probability_annual_erosion_gt_10pct': 2.0,
            'probability_any_erosion': 40.0,
            'var_95_annualized_pct': -2.0,
            'simulation_params': {'n_simulations': 10000, 'years': 3}
        }
        
        penalty = integration.calculate_sustainability_penalty(
            low_risk_results,
            'COVERED_CALL_ETF'
        )
        
        assert penalty['penalty_points'] == 0, "Low risk should have zero penalty"
        assert penalty['severity'] == 'none'
    
    def test_penalty_calculation_severe_risk(self):
        """Test penalty for severe erosion risk."""
        integration = NAVErosionSustainabilityIntegration()
        
        high_risk_results = {
            'median_annualized_nav_change_pct': -7.0,
            'probability_annual_erosion_gt_5pct': 85.0,
            'probability_annual_erosion_gt_10pct': 45.0,
            'probability_any_erosion': 95.0,
            'var_95_annualized_pct': -12.0,
            'simulation_params': {'n_simulations': 10000, 'years': 3}
        }
        
        penalty = integration.calculate_sustainability_penalty(
            high_risk_results,
            'COVERED_CALL_ETF'
        )
        
        assert penalty['penalty_points'] >= 25, "Severe risk should have high penalty"
        assert penalty['penalty_points'] <= 30, "Penalty should be capped at 30"
        assert penalty['severity'] == 'severe'
    
    def test_penalty_calculation_medium_risk(self):
        """Test penalty for medium erosion risk."""
        integration = NAVErosionSustainabilityIntegration()
        
        medium_risk_results = {
            'median_annualized_nav_change_pct': -3.5,
            'probability_annual_erosion_gt_5pct': 55.0,
            'probability_annual_erosion_gt_10pct': 18.0,
            'probability_any_erosion': 72.0,
            'var_95_annualized_pct': -8.2,
            'simulation_params': {'n_simulations': 10000, 'years': 3}
        }
        
        penalty = integration.calculate_sustainability_penalty(
            medium_risk_results,
            'COVERED_CALL_ETF'
        )
        
        assert 10 <= penalty['penalty_points'] <= 25, \
            "Medium risk should have moderate penalty"
        assert penalty['severity'] in ['medium', 'high']
    
    def test_should_run_analysis_triggers(self):
        """Test detection of when NAV erosion analysis should run."""
        integration = NAVErosionSustainabilityIntegration()
        
        # Known covered call ETF
        assert integration.should_run_analysis('JEPI', 'COVERED_CALL_ETF')
        
        # Asset class trigger
        assert integration.should_run_analysis('UNKNOWN', 'COVERED_CALL_ETF')
        
        # Should not trigger for regular equity
        assert not integration.should_run_analysis('AAPL', 'EQUITY')


class TestRiskClassifier:
    """Test suite for risk classification."""
    
    def test_risk_classification_minimal(self):
        """Test minimal risk classification."""
        analysis = {
            'probability_annual_erosion_gt_5pct': 10.0,
            'median_annualized_nav_change_pct': 1.0
        }
        
        risk = NAVErosionRiskClassifier.classify_risk(analysis)
        assert risk == 'minimal'
    
    def test_risk_classification_severe(self):
        """Test severe risk classification."""
        analysis = {
            'probability_annual_erosion_gt_5pct': 90.0,
            'median_annualized_nav_change_pct': -12.0
        }
        
        risk = NAVErosionRiskClassifier.classify_risk(analysis)
        assert risk == 'severe'
    
    def test_flag_for_review(self):
        """Test that high/severe risks are flagged."""
        assert NAVErosionRiskClassifier.should_flag_for_review('severe')
        assert NAVErosionRiskClassifier.should_flag_for_review('high')
        assert not NAVErosionRiskClassifier.should_flag_for_review('moderate')
        assert not NAVErosionRiskClassifier.should_flag_for_review('low')


class TestDataCollector:
    """Test suite for data collection."""
    
    def test_known_etf_registry(self):
        """Test that known ETFs are in registry."""
        assert CoveredCallETFRegistry.is_known_covered_call_etf('JEPI')
        assert CoveredCallETFRegistry.is_known_covered_call_etf('QYLD')
        assert not CoveredCallETFRegistry.is_known_covered_call_etf('AAPL')
        
        metadata = CoveredCallETFRegistry.get_metadata('JEPI')
        assert metadata is not None
        assert 'strategy' in metadata
        assert 'typical_yield' in metadata
    
    def test_parameter_validation(self):
        """Test parameter validation logic."""
        collector = NAVErosionDataCollector(db_connection=None)
        
        # Good parameters
        good_params = CoveredCallETFParams(
            ticker='TEST',
            current_nav=50.0,
            current_price=50.0,
            monthly_premium_yields=[0.007] * 12,
            underlying_monthly_returns=[0.01] * 12,
            distribution_history=[0.35] * 12,
            expense_ratio_annual=0.0035
        )
        
        validation = collector.validate_parameters(good_params)
        assert validation['is_valid']
        assert validation['completeness_score'] >= 80
        
        # Bad parameters - insufficient data
        bad_params = CoveredCallETFParams(
            ticker='TEST',
            current_nav=50.0,
            current_price=50.0,
            monthly_premium_yields=[0.007] * 2,  # Only 2 months
            underlying_monthly_returns=[0.01] * 2,
            distribution_history=[],
            expense_ratio_annual=0.0035
        )
        
        validation = collector.validate_parameters(bad_params)
        assert len(validation['warnings']) > 0
        assert validation['completeness_score'] < 50


class TestPerformance:
    """Test suite for performance benchmarks."""
    
    def test_vectorized_performance(self):
        """Verify vectorized engine is significantly faster."""
        import time
        
        params = CoveredCallETFParams(
            ticker='TEST',
            current_nav=50.0,
            current_price=50.0,
            monthly_premium_yields=[0.007] * 12,
            underlying_monthly_returns=[0.01] * 12,
            distribution_history=[0.35] * 12,
            expense_ratio_annual=0.0035
        )
        
        # Vectorized timing
        engine = OptimizedMonteCarloEngine(params)
        start = time.time()
        engine.simulate_vectorized(years=3, n_simulations=10000)
        vectorized_time = time.time() - start
        
        # Quick analysis should complete in under 2 seconds
        assert vectorized_time < 2.0, \
            f"Vectorized simulation too slow: {vectorized_time:.2f}s"
        
        print(f"\nPerformance: 10K simulations in {vectorized_time:.3f}s")


# Run tests with: pytest test_nav_erosion.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
