# tests/test_ies_calculator.py
from app.scoring.ies_calculator import IESCalculator, IESResult, IESStatus
from app.scoring.hhs_wrapper import HHSResult, HHSStatus


def _hhs(score=75.0, unsafe=False) -> HHSResult:
    return HHSResult(ticker="O", asset_class="REIT", status=HHSStatus.SCORED,
                     hhs_score=score, unsafe=unsafe,
                     income_pillar=80.0, durability_pillar=70.0)


def test_blocked_when_hhs_below_threshold():
    result = IESCalculator().evaluate(_hhs(score=45.0), None, None)
    assert result.status == IESStatus.GATE_BLOCKED
    assert result.reason == "HHS_BELOW_THRESHOLD"
    assert result.ies_score is None
    assert result.action == "NO_ACTION"

def test_blocked_when_unsafe():
    result = IESCalculator().evaluate(_hhs(score=75.0, unsafe=True), None, None)
    assert result.status == IESStatus.GATE_BLOCKED
    assert result.reason == "UNSAFE_FLAG"
    assert result.action == "NO_ACTION"

def test_full_position_at_85_plus():
    # 90*0.60 + 78*0.40 = 54 + 31.2 = 85.2
    result = IESCalculator().evaluate(_hhs(), valuation_score=90.0, technical_score=78.0)
    assert result.status == IESStatus.SCORED
    assert abs(result.ies_score - 85.2) < 0.01
    assert result.action == "FULL_POSITION"

def test_partial_position_at_70_to_84():
    # 80*0.60 + 60*0.40 = 48 + 24 = 72.0
    result = IESCalculator().evaluate(_hhs(), valuation_score=80.0, technical_score=60.0)
    assert abs(result.ies_score - 72.0) < 0.01
    assert result.action == "PARTIAL_POSITION"

def test_wait_below_70():
    # 60*0.60 + 55*0.40 = 36 + 22 = 58.0
    result = IESCalculator().evaluate(_hhs(), valuation_score=60.0, technical_score=55.0)
    assert abs(result.ies_score - 58.0) < 0.01
    assert result.action == "WAIT_OR_DCA"

def test_gate_blocked_response_is_machine_readable():
    result = IESCalculator().evaluate(_hhs(score=30.0), None, None)
    # Must be a structured IESResult, not an exception
    assert isinstance(result, IESResult)
    assert result.ies_score is None
    assert result.hhs_score_at_evaluation == 30.0
