"""
Agent 06 — Scenario Simulation Service
Tests: ScenarioLibrary — 6 tests.
"""
import pytest
from app.simulation.scenario_library import (
    get_scenario,
    list_scenarios,
    build_custom_scenario,
    ASSET_CLASSES,
    SCENARIO_LIBRARY,
)
from app.simulation.stress_engine import StressEngine


# 1. get_scenario returns correct shocks for RATE_HIKE_200BPS
def test_get_scenario_rate_hike():
    shocks = get_scenario("RATE_HIKE_200BPS")
    assert shocks["EQUITY_REIT"]["price_pct"] == -15
    assert shocks["MORTGAGE_REIT"]["income_pct"] == -12
    assert shocks["BOND"]["income_pct"] == 0


# 2. get_scenario raises ValueError for unknown scenario
def test_get_scenario_unknown_raises():
    with pytest.raises(ValueError, match="Unknown scenario"):
        get_scenario("DOES_NOT_EXIST")


# 3. list_scenarios returns all 5 predefined scenarios
def test_list_scenarios_count():
    scenarios = list_scenarios()
    assert len(scenarios) == 5
    names = {s["name"] for s in scenarios}
    expected = {
        "RATE_HIKE_200BPS", "MARKET_CORRECTION_20", "RECESSION_MILD",
        "INFLATION_SPIKE", "CREDIT_STRESS",
    }
    assert names == expected


# 4. build_custom_scenario validates required asset class keys
def test_build_custom_scenario_valid():
    custom = build_custom_scenario({
        "EQUITY_REIT": {"price_pct": -10, "income_pct": -5},
    })
    assert custom["EQUITY_REIT"]["price_pct"] == -10.0
    assert custom["EQUITY_REIT"]["income_pct"] == -5.0


def test_build_custom_scenario_missing_keys():
    with pytest.raises(ValueError):
        build_custom_scenario({
            "EQUITY_REIT": {"price_pct": -10},  # missing income_pct
        })


# 5. CUSTOM scenario shocks pass through stress engine unchanged
def test_custom_shocks_pass_through():
    custom_shocks = build_custom_scenario({
        "DIVIDEND_STOCK": {"price_pct": -99, "income_pct": -99},
    })
    pos = {"symbol": "X", "current_value": 10000.0, "annual_income": 500.0}
    engine = StressEngine()
    result = engine.run([pos], {"X": "DIVIDEND_STOCK"}, custom_shocks, "p1", "CUSTOM")
    assert result.portfolio_value_after < 200.0  # ~1% of 10000


# 6. All predefined scenarios contain all 7 asset classes
def test_all_scenarios_contain_all_asset_classes():
    for name, entry in SCENARIO_LIBRARY.items():
        for ac in ASSET_CLASSES:
            assert ac in entry["shocks"], f"Scenario {name} missing asset class {ac}"
