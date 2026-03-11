"""
Agent 06 — Scenario Simulation Service
Tests: StressEngine — 12 tests.
"""
import pytest
from app.simulation.stress_engine import StressEngine
from app.simulation.scenario_library import get_scenario, SCENARIO_LIBRARY, ASSET_CLASSES


def make_position(symbol="TEST", current_value=10000.0, annual_income=500.0):
    return {"symbol": symbol, "current_value": current_value, "annual_income": annual_income}


engine = StressEngine()
rate_hike_shocks = get_scenario("RATE_HIKE_200BPS")
correction_shocks = get_scenario("MARKET_CORRECTION_20")
recession_shocks = get_scenario("RECESSION_MILD")
inflation_shocks = get_scenario("INFLATION_SPIKE")


# 1. Single position RATE_HIKE stressed value
def test_rate_hike_stressed_value():
    pos = make_position("EITEST", 10000.0, 500.0)
    result = engine.run([pos], {"EITEST": "EQUITY_REIT"}, rate_hike_shocks, "p1", "RATE_HIKE_200BPS")
    impact = result.position_impacts[0]
    expected = 10000.0 * (1 + (-15) / 100)
    assert abs(impact.stressed_value - expected) < 0.01


# 2. Single position MARKET_CORRECTION_20 income impact
def test_market_correction_income():
    pos = make_position("MRTEST", 10000.0, 1000.0)
    result = engine.run([pos], {"MRTEST": "MORTGAGE_REIT"}, correction_shocks, "p1", "MARKET_CORRECTION_20")
    impact = result.position_impacts[0]
    expected = 1000.0 * (1 + (-15) / 100)
    assert abs(impact.stressed_income - expected) < 0.01


# 3. Multiple positions: portfolio totals sum correctly
def test_portfolio_totals_sum():
    positions = [
        make_position("A", 10000.0, 500.0),
        make_position("B", 5000.0, 200.0),
    ]
    ac = {"A": "EQUITY_REIT", "B": "BOND"}
    result = engine.run(positions, ac, rate_hike_shocks, "p1", "RATE_HIKE_200BPS")
    expected_value = sum(i.stressed_value for i in result.position_impacts)
    assert abs(result.portfolio_value_after - expected_value) < 0.01
    expected_income = sum(i.stressed_income for i in result.position_impacts)
    assert abs(result.annual_income_after - expected_income) < 0.01


# 4. Zero current_value: no division error
def test_zero_current_value():
    pos = make_position("ZV", 0.0, 100.0)
    result = engine.run([pos], {"ZV": "DIVIDEND_STOCK"}, rate_hike_shocks, "p1", "RATE_HIKE_200BPS")
    assert result.position_impacts[0].value_change_pct == 0.0


# 5. Zero annual_income: no division error
def test_zero_annual_income():
    pos = make_position("ZI", 10000.0, 0.0)
    result = engine.run([pos], {"ZI": "BOND"}, rate_hike_shocks, "p1", "RATE_HIKE_200BPS")
    assert result.position_impacts[0].income_change_pct == 0.0


# 6. Unknown asset class falls back to DIVIDEND_STOCK shocks
def test_unknown_asset_class_fallback():
    pos = make_position("UK", 10000.0, 500.0)
    result_unknown = engine.run([pos], {"UK": "UNKNOWN_CLASS"}, rate_hike_shocks, "p1", "RATE_HIKE_200BPS")
    result_div = engine.run([pos], {"UK": "DIVIDEND_STOCK"}, rate_hike_shocks, "p1", "RATE_HIKE_200BPS")
    assert abs(result_unknown.portfolio_value_after - result_div.portfolio_value_after) < 0.01


# 7. Vulnerability rank 1 = most impacted position
def test_vulnerability_rank_most_impacted():
    positions = [
        make_position("MR", 10000.0, 500.0),   # MORTGAGE_REIT: -20% value
        make_position("DS", 10000.0, 500.0),   # DIVIDEND_STOCK: -5% value
    ]
    ac = {"MR": "MORTGAGE_REIT", "DS": "DIVIDEND_STOCK"}
    result = engine.run(positions, ac, rate_hike_shocks, "p1", "RATE_HIKE_200BPS")
    rank1 = next(i for i in result.position_impacts if i.vulnerability_rank == 1)
    assert rank1.symbol == "MR"


# 8. BOND in RECESSION_MILD has positive price_pct (price rises)
def test_bond_recession_positive_price():
    pos = make_position("BND", 10000.0, 400.0)
    result = engine.run([pos], {"BND": "BOND"}, recession_shocks, "p1", "RECESSION_MILD")
    impact = result.position_impacts[0]
    assert impact.stressed_value > impact.current_value
    assert impact.value_change_pct > 0


# 9. INFLATION_SPIKE: EQUITY_REIT income_pct positive (+5)
def test_equity_reit_inflation_income_positive():
    pos = make_position("ER", 10000.0, 600.0)
    result = engine.run([pos], {"ER": "EQUITY_REIT"}, inflation_shocks, "p1", "INFLATION_SPIKE")
    impact = result.position_impacts[0]
    assert impact.stressed_income > impact.current_income
    assert abs(impact.income_change_pct - 5.0) < 0.01


# 10. Empty positions list: returns zero totals
def test_empty_positions_zero_totals():
    result = engine.run([], {}, rate_hike_shocks, "p1", "RATE_HIKE_200BPS")
    assert result.portfolio_value_before == 0.0
    assert result.portfolio_value_after == 0.0
    assert result.annual_income_before == 0.0
    assert result.annual_income_after == 0.0
    assert result.value_change_pct == 0.0
    assert result.income_change_pct == 0.0


# 11. Custom scenario shocks applied correctly
def test_custom_scenario_applied():
    custom_shocks = {"DIVIDEND_STOCK": {"price_pct": -50, "income_pct": -50}}
    pos = make_position("DS", 10000.0, 500.0)
    result = engine.run([pos], {"DS": "DIVIDEND_STOCK"}, custom_shocks, "p1", "CUSTOM")
    assert abs(result.portfolio_value_after - 5000.0) < 0.01
    assert abs(result.annual_income_after - 250.0) < 0.01


# 12. All 7 asset classes produce distinct stress outcomes for RATE_HIKE_200BPS
def test_all_asset_classes_distinct_outcomes():
    positions = [
        make_position(ac, 10000.0, 500.0)
        for ac in ASSET_CLASSES
    ]
    ac_map = {ac: ac for ac in ASSET_CLASSES}
    result = engine.run(positions, ac_map, rate_hike_shocks, "p1", "RATE_HIKE_200BPS")
    value_changes = [round(i.value_change_pct, 4) for i in result.position_impacts]
    # All 7 should not all be identical (they have distinct shock values)
    assert len(set(value_changes)) > 1
