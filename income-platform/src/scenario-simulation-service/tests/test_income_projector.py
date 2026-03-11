"""
Agent 06 — Scenario Simulation Service
Tests: IncomeProjector — 8 tests.
"""
import numpy as np
import pytest
from app.simulation.income_projector import IncomeProjector


projector = IncomeProjector()


def make_position(symbol="TEST", annual_income=12000.0):
    return {"symbol": symbol, "annual_income": annual_income, "portfolio_id": "p1"}


# 1. P50 close to base_income for single position
def test_p50_close_to_base_income():
    pos = make_position("A", 12000.0)
    result = projector.project([pos], horizon_months=12)
    # P50 should be within 5% of base_income (log-normal median ≈ base)
    assert abs(result.projected_income_p50 - 12000.0) / 12000.0 < 0.05


# 2. P10 < P50 < P90 always holds
def test_percentile_ordering():
    pos = make_position("A", 12000.0)
    result = projector.project([pos], horizon_months=12)
    assert result.projected_income_p10 < result.projected_income_p50
    assert result.projected_income_p50 < result.projected_income_p90


# 3. horizon_months=6 produces ~50% of 12-month income
def test_half_year_horizon():
    pos = make_position("A", 12000.0)
    result_12 = projector.project([pos], horizon_months=12)
    result_6 = projector.project([pos], horizon_months=6)
    ratio = result_6.projected_income_p50 / result_12.projected_income_p50
    assert abs(ratio - 0.5) < 0.05


# 4. Empty positions: P10=P50=P90=0
def test_empty_positions_zero():
    result = projector.project([], horizon_months=12)
    assert result.projected_income_p10 == 0.0
    assert result.projected_income_p50 == 0.0
    assert result.projected_income_p90 == 0.0


# 5. Multiple positions: totals exceed any single position
def test_multiple_positions_exceed_single():
    positions = [
        make_position("A", 6000.0),
        make_position("B", 6000.0),
    ]
    result_multi = projector.project(positions, horizon_months=12)
    result_single = projector.project([make_position("A", 6000.0)], horizon_months=12)
    assert result_multi.projected_income_p50 > result_single.projected_income_p50


# 6. N_SIMULATIONS produces stable percentiles (seed test)
def test_stable_percentiles_with_seed():
    np.random.seed(42)
    pos = make_position("A", 12000.0)
    result1 = projector.project([pos], horizon_months=12)
    np.random.seed(42)
    result2 = projector.project([pos], horizon_months=12)
    assert result1.projected_income_p50 == result2.projected_income_p50


# 7. Zero annual_income position contributes 0 to projection
def test_zero_income_position():
    # A zero-income position should produce by_position entry with all percentiles = 0
    pos_zero = make_position("A", 0.0)
    np.random.seed(42)
    result = projector.project([pos_zero], horizon_months=12)
    assert result.projected_income_p10 == 0.0
    assert result.projected_income_p50 == 0.0
    assert result.projected_income_p90 == 0.0
    assert result.by_position[0]["p50"] == 0.0


# 8. horizon_months=1 produces ~8.3% of annual income
def test_one_month_horizon():
    pos = make_position("A", 12000.0)
    result = projector.project([pos], horizon_months=1)
    expected = 12000.0 / 12
    assert abs(result.projected_income_p50 - expected) / expected < 0.05
