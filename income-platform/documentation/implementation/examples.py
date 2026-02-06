#!/usr/bin/env python3
"""
Example Usage Script for NAV Erosion Analysis Service

Demonstrates:
1. Direct Python API usage
2. REST API calls
3. Integration with Agent 3
4. Batch processing
"""

import requests
import json
from datetime import datetime

from monte_carlo_engine import CoveredCallETFParams, quick_nav_erosion_analysis, deep_nav_erosion_analysis
from sustainability_integration import NAVErosionSustainabilityIntegration, NAVErosionRiskClassifier
from data_collector import NAVErosionDataCollector, CoveredCallETFRegistry


# ==============================================================================
# Example 1: Direct Python API Usage (No Service)
# ==============================================================================

def example_direct_python_api():
    """
    Use Monte Carlo engine directly without HTTP service.
    Fastest for local analysis.
    """
    print("\n" + "="*70)
    print("Example 1: Direct Python API Usage")
    print("="*70)
    
    # Define parameters manually
    params = CoveredCallETFParams(
        ticker="JEPI",
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
    
    print(f"\nRunning Quick Analysis for {params.ticker}...")
    results = quick_nav_erosion_analysis(params)
    
    print(f"\nKey Results:")
    print(f"  Median Annualized NAV Change: {results['median_annualized_nav_change_pct']:.2f}%")
    print(f"  Probability of >5% Erosion: {results['probability_annual_erosion_gt_5pct']:.1f}%")
    print(f"  Probability of >10% Erosion: {results['probability_annual_erosion_gt_10pct']:.1f}%")
    print(f"  Median Total Return (with distributions): {results['median_annualized_total_return_pct']:.2f}%")
    print(f"  Upside Capped: {results['pct_months_upside_capped']:.1f}% of months")
    
    # Calculate sustainability impact
    integration = NAVErosionSustainabilityIntegration()
    penalty = integration.calculate_sustainability_penalty(results, 'COVERED_CALL_ETF')
    
    print(f"\nSustainability Impact:")
    print(f"  Penalty Points: {penalty['penalty_points']}")
    print(f"  Severity: {penalty['severity']}")
    print(f"  Rationale: {penalty['rationale']}")
    
    # Risk classification
    risk_category = NAVErosionRiskClassifier.classify_risk(results)
    print(f"\nRisk Classification: {risk_category}")
    print(f"  Description: {NAVErosionRiskClassifier.get_risk_description(risk_category)}")
    print(f"  Flag for Review: {NAVErosionRiskClassifier.should_flag_for_review(risk_category)}")


# ==============================================================================
# Example 2: REST API Calls (Service Running)
# ==============================================================================

def example_rest_api_calls():
    """
    Use HTTP service for analysis.
    Best for distributed systems and caching.
    """
    print("\n" + "="*70)
    print("Example 2: REST API Usage")
    print("="*70)
    
    base_url = "http://localhost:8003"
    
    # Health check
    print("\n1. Health Check...")
    response = requests.get(f"{base_url}/health")
    print(f"   Status: {response.json()['status']}")
    
    # Single ticker analysis
    print("\n2. Analyzing JEPI...")
    analysis_request = {
        "ticker": "JEPI",
        "analysis_type": "quick",
        "years": 3,
        "force_refresh": False
    }
    
    response = requests.post(f"{base_url}/analyze", json=analysis_request)
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Cached: {data['cached']}")
        print(f"   Median NAV Change: {data['results']['median_annualized_nav_change_pct']:.2f}%")
        print(f"   Sustainability Penalty: {data['sustainability_impact']['penalty_points']} points")
        print(f"   Risk Category: {data['risk_classification']['category']}")
    else:
        print(f"   Error: {response.status_code} - {response.text}")
    
    # Batch analysis
    print("\n3. Batch Analysis (Multiple Tickers)...")
    batch_request = {
        "tickers": ["JEPI", "JEPQ", "QYLD"],
        "analysis_type": "quick"
    }
    
    response = requests.post(f"{base_url}/batch-analyze", json=batch_request)
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Total: {data['batch_summary']['total_tickers']}")
        print(f"   Successful: {data['batch_summary']['successful']}")
        print(f"   Failed: {data['batch_summary']['failed']}")
        
        for ticker, result in data['results'].items():
            if 'error' not in result:
                print(f"\n   {ticker}:")
                print(f"     Risk: {result['risk_classification']['category']}")
                print(f"     Penalty: {result['sustainability_impact']['penalty_points']} pts")
    
    # Check ETF registry
    print("\n4. Known Covered Call ETFs...")
    response = requests.get(f"{base_url}/registry/covered-call-etfs")
    
    if response.status_code == 200:
        etfs = response.json()
        print(f"   Found {etfs['count']} ETFs in registry:")
        for ticker, metadata in list(etfs['etfs'].items())[:3]:
            print(f"   - {ticker}: {metadata['name']}")


# ==============================================================================
# Example 3: Integration with Agent 3 (Scoring)
# ==============================================================================

def example_agent3_integration():
    """
    Demonstrate how NAV erosion integrates with scoring engine.
    """
    print("\n" + "="*70)
    print("Example 3: Agent 3 Integration")
    print("="*70)
    
    # Simulated Agent 3 scoring workflow
    ticker = "JEPI"
    asset_class = "COVERED_CALL_ETF"
    
    # Step 1: Check if NAV erosion analysis should run
    integration = NAVErosionSustainabilityIntegration()
    
    if integration.should_run_analysis(ticker, asset_class):
        print(f"\n✓ {ticker} requires NAV erosion analysis (asset class: {asset_class})")
        
        # Step 2: Run analysis
        params = CoveredCallETFParams(
            ticker=ticker,
            current_nav=50.0,
            current_price=50.5,
            monthly_premium_yields=[0.007] * 12,
            underlying_monthly_returns=[0.01] * 12,
            distribution_history=[0.35] * 12,
            expense_ratio_annual=0.0035
        )
        
        print(f"\nRunning Monte Carlo analysis...")
        results = quick_nav_erosion_analysis(params)
        
        # Step 3: Calculate sustainability penalty
        penalty_result = integration.calculate_sustainability_penalty(results, asset_class)
        
        # Step 4: Apply to sustainability score
        base_sustainability_score = 85.0  # Simulated base score
        adjusted_score = base_sustainability_score - penalty_result['penalty_points']
        
        print(f"\nSustainability Score Adjustment:")
        print(f"  Base Score: {base_sustainability_score:.1f}")
        print(f"  NAV Erosion Penalty: -{penalty_result['penalty_points']:.1f}")
        print(f"  Adjusted Score: {adjusted_score:.1f}")
        print(f"  Severity: {penalty_result['severity']}")
        
        # Step 5: Overall SAIS score impact
        # Assuming Sustainability is 40% of overall score
        sustainability_weight = 0.40
        overall_impact = penalty_result['penalty_points'] * sustainability_weight
        
        print(f"\nOverall SAIS Score Impact:")
        print(f"  Sustainability Weight: {sustainability_weight*100:.0f}%")
        print(f"  Net Impact: -{overall_impact:.2f} points")
    else:
        print(f"\n✗ {ticker} does not require NAV erosion analysis")


# ==============================================================================
# Example 4: Data Quality Assessment
# ==============================================================================

def example_data_quality_assessment():
    """
    Demonstrate data collection and quality validation.
    """
    print("\n" + "="*70)
    print("Example 4: Data Quality Assessment")
    print("="*70)
    
    collector = NAVErosionDataCollector(db_connection=None)
    
    # Example with good data
    print("\n1. Good Data Quality:")
    good_params = CoveredCallETFParams(
        ticker='JEPI',
        current_nav=50.0,
        current_price=50.0,
        monthly_premium_yields=[0.007, 0.008, 0.006, 0.009, 0.007, 0.008,
                                0.007, 0.006, 0.008, 0.009, 0.007, 0.006],
        underlying_monthly_returns=[0.01] * 12,
        distribution_history=[0.35] * 12,
        expense_ratio_annual=0.0035
    )
    
    validation = collector.validate_parameters(good_params)
    print(f"   Valid: {validation['is_valid']}")
    print(f"   Completeness Score: {validation['completeness_score']}/100")
    print(f"   Warnings: {len(validation['warnings'])}")
    
    # Example with poor data
    print("\n2. Poor Data Quality:")
    poor_params = CoveredCallETFParams(
        ticker='UNKNOWN',
        current_nav=50.0,
        current_price=50.0,
        monthly_premium_yields=[0.007, 0.008],  # Only 2 months
        underlying_monthly_returns=[0.01, 0.02],
        distribution_history=[],
        expense_ratio_annual=0.0035
    )
    
    validation = collector.validate_parameters(poor_params)
    print(f"   Valid: {validation['is_valid']}")
    print(f"   Completeness Score: {validation['completeness_score']}/100")
    print(f"   Warnings: {len(validation['warnings'])}")
    for warning in validation['warnings']:
        print(f"     - {warning}")


# ==============================================================================
# Example 5: Comparative Analysis
# ==============================================================================

def example_comparative_analysis():
    """
    Compare NAV erosion across multiple covered call ETFs.
    """
    print("\n" + "="*70)
    print("Example 5: Comparative Analysis")
    print("="*70)
    
    # Simulate different ETF strategies
    etfs = {
        'JEPI (2% OTM)': CoveredCallETFParams(
            ticker='JEPI',
            current_nav=50.0,
            current_price=50.0,
            monthly_premium_yields=[0.007] * 12,
            underlying_monthly_returns=[0.015] * 12,
            distribution_history=[0.35] * 12,
            expense_ratio_annual=0.0035,
            call_moneyness_target=0.02  # 2% OTM
        ),
        'QYLD (ATM)': CoveredCallETFParams(
            ticker='QYLD',
            current_nav=17.5,
            current_price=17.5,
            monthly_premium_yields=[0.009] * 12,  # Higher premiums ATM
            underlying_monthly_returns=[0.015] * 12,
            distribution_history=[0.18] * 12,
            expense_ratio_annual=0.0060,
            call_moneyness_target=0.00  # ATM
        )
    }
    
    print("\nComparing NAV erosion across strategies:\n")
    print(f"{'ETF':<20} {'Median NAV Δ':<15} {'Prob >5%':<12} {'Risk':<12}")
    print("-" * 60)
    
    for name, params in etfs.items():
        results = quick_nav_erosion_analysis(params)
        risk = NAVErosionRiskClassifier.classify_risk(results)
        
        print(f"{name:<20} "
              f"{results['median_annualized_nav_change_pct']:>8.2f}% "
              f"{results['probability_annual_erosion_gt_5pct']:>12.1f}% "
              f"{risk:<12}")
    
    print("\nObservations:")
    print("  - ATM calls capture higher premiums but cap upside more aggressively")
    print("  - OTM calls allow more upside participation with lower premiums")
    print("  - Both strategies show expected NAV erosion patterns")


# ==============================================================================
# Main Execution
# ==============================================================================

def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("NAV Erosion Analysis Service - Example Usage")
    print("="*70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Run examples
    example_direct_python_api()
    
    # Uncomment when service is running:
    # example_rest_api_calls()
    
    example_agent3_integration()
    example_data_quality_assessment()
    example_comparative_analysis()
    
    print("\n" + "="*70)
    print("Examples Complete!")
    print("="*70)
    print("\nNext Steps:")
    print("  1. Start the service: docker-compose up nav-erosion-service")
    print("  2. Run REST API examples: uncomment example_rest_api_calls()")
    print("  3. Integrate with Agent 3 scoring pipeline")
    print("  4. Set up daily batch analysis for all covered call ETFs")
    print("")


if __name__ == "__main__":
    main()
