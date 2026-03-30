# tests/test_naa_yield.py
from app.scoring.naa_yield import NAAYieldCalculator, NAAYieldResult, TaxProfile


def test_basic_calculation():
    # (1200 - 50 - 180) / 20000 = 970 / 20000 = 4.85%
    result = NAAYieldCalculator().compute(
        gross_annual_dividends=1200.0, annual_fee_drag=50.0,
        annual_tax_drag=180.0, total_invested=20000.0,
    )
    assert abs(result.naa_yield_pct - 4.85) < 0.01
    assert result.pre_tax_flag is False

def test_zero_fee_and_tax():
    result = NAAYieldCalculator().compute(1000.0, 0.0, 0.0, 10000.0)
    assert abs(result.naa_yield_pct - 10.0) < 0.01

def test_pre_tax_flag_when_tax_unavailable():
    # tax_drag=None → pre_tax_flag=True, no tax applied
    result = NAAYieldCalculator().compute(1000.0, 50.0, None, 10000.0)
    assert result.pre_tax_flag is True
    assert abs(result.naa_yield_pct - 9.5) < 0.01  # (1000-50)/10000

def test_floors_at_zero_if_negative():
    result = NAAYieldCalculator().compute(100.0, 200.0, 50.0, 10000.0)
    assert result.naa_yield_pct == 0.0

def test_tax_drag_estimate_from_profile():
    # qualified 100%, rate 15% → tax = 1000 * 0.15 = 150
    drag = NAAYieldCalculator.estimate_tax_drag(
        1000.0,
        TaxProfile(roc_pct=0.0, qualified_pct=1.0, ordinary_pct=0.0,
                   qualified_rate=0.15, ordinary_rate=0.22),
    )
    assert abs(drag - 150.0) < 0.01

def test_roc_has_zero_tax_drag():
    # 100% ROC → no current tax
    drag = NAAYieldCalculator.estimate_tax_drag(
        1000.0,
        TaxProfile(roc_pct=1.0, qualified_pct=0.0, ordinary_pct=0.0,
                   qualified_rate=0.15, ordinary_rate=0.22),
    )
    assert drag == 0.0
