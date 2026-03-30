# tests/test_portfolio_health.py
from app.scoring.portfolio_health import PortfolioHealthCalculator, HoldingInput
from app.scoring.hhs_wrapper import HHSResult, HHSStatus
from app.scoring.naa_yield import NAAYieldResult


def _h(ticker, hhs_score, pos_val, unsafe=False, status=HHSStatus.SCORED,
       naa_pct=5.0, cost=None, current=None, income=0.0, tax=0.0):
    hhs = HHSResult(ticker=ticker, asset_class="REIT", status=status,
                    hhs_score=hhs_score, unsafe=unsafe,
                    income_pillar=70.0, durability_pillar=75.0)
    naa = NAAYieldResult(gross_annual_dividends=pos_val * 0.06, annual_fee_drag=0.0,
                         annual_tax_drag=0.0, net_income=pos_val * naa_pct / 100,
                         total_invested=cost or pos_val, naa_yield_pct=naa_pct,
                         pre_tax_flag=False)
    return HoldingInput(ticker=ticker, hhs=hhs, naa=naa,
                        position_value=pos_val, original_cost=cost or pos_val,
                        current_value=current or pos_val,
                        income_received=income, tax_drag=tax)


def test_aggregate_hhs_is_position_weighted():
    holdings = [_h("O", 80.0, 6000.0), _h("ARCC", 60.0, 4000.0)]
    result = PortfolioHealthCalculator().compute(holdings)
    # (80*6000 + 60*4000) / 10000 = 72.0
    assert abs(result.aggregate_hhs - 72.0) < 0.01

def test_unsafe_surfaced_regardless_of_aggregate():
    holdings = [_h("O", 85.0, 9000.0), _h("ARCC", 18.0, 1000.0, unsafe=True)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert result.unsafe_count == 1
    assert "ARCC" in result.unsafe_tickers

def test_gate_fail_excluded_from_aggregate():
    holdings = [_h("O", 80.0, 8000.0),
                _h("JUNK", None, 2000.0, status=HHSStatus.QUALITY_GATE_FAIL)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert abs(result.aggregate_hhs - 80.0) < 0.01
    assert result.gate_fail_count == 1

def test_insufficient_data_excluded_from_aggregate():
    holdings = [_h("O", 80.0, 8000.0),
                _h("NEW", None, 2000.0, status=HHSStatus.INSUFFICIENT_DATA)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert abs(result.aggregate_hhs - 80.0) < 0.01
    assert result.insufficient_data_count == 1

def test_portfolio_naa_yield_position_weighted():
    holdings = [_h("O", 80.0, 6000.0, naa_pct=5.0),
                _h("ARCC", 70.0, 4000.0, naa_pct=8.0)]
    result = PortfolioHealthCalculator().compute(holdings)
    # (5.0*6000 + 8.0*4000) / 10000 = 6.2%
    assert abs(result.portfolio_naa_yield_pct - 6.2) < 0.01

def test_hhi_flags_concentrated_holding():
    holdings = [_h("O", 80.0, 7000.0), _h("T", 75.0, 2000.0), _h("VZ", 70.0, 1000.0)]
    result = PortfolioHealthCalculator(hhi_flag_threshold=0.10).compute(holdings)
    # O = 70% weight > 10% threshold
    assert "O" in result.concentration_flags

def test_total_return_calculation():
    # (11000 - 10000 + 500 - 0) / 10000 = 15%
    holdings = [_h("O", 80.0, 11000.0, cost=10000.0, current=11000.0, income=500.0)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert abs(result.total_return_pct - 15.0) < 0.01

def test_none_aggregate_when_no_scored_holdings():
    holdings = [_h("JUNK", None, 5000.0, status=HHSStatus.QUALITY_GATE_FAIL)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert result.aggregate_hhs is None
