# tests/test_hhs_wrapper.py
from app.scoring.hhs_wrapper import HHSWrapper, HHSResult, HHSStatus
from app.scoring.hhs_weights import HHSWeights
from app.scoring.income_scorer import ScoreResult
from app.scoring.quality_gate import GateResult, GateStatus, AssetClass


def _score(vy=32.0, fd=30.0, te=15.0, wy=40, wd=40) -> ScoreResult:
    """Build a minimal ScoreResult for testing."""
    r = ScoreResult()
    r.asset_class = "DIVIDEND_STOCK"
    r.ticker = "O"
    r.valuation_yield_score = vy
    r.financial_durability_score = fd
    r.technical_entry_score = te
    r.total_score_raw = vy + fd + te
    r.total_score = vy + fd + te
    r.weight_profile = {"weight_yield": wy, "weight_durability": wd, "weight_technical": 20}
    return r


def _weights(income_w=45, threshold=20) -> HHSWeights:
    return HHSWeights(asset_class="DIVIDEND_STOCK", income_weight=income_w, unsafe_threshold=threshold)


def test_income_pillar_normalized_correctly():
    # 32 / 40 * 100 = 80.0
    result = HHSWrapper().compute(_score(vy=32.0), _weights())
    assert abs(result.income_pillar - 80.0) < 0.01

def test_durability_pillar_normalized_correctly():
    # 30 / 40 * 100 = 75.0
    result = HHSWrapper().compute(_score(fd=30.0), _weights())
    assert abs(result.durability_pillar - 75.0) < 0.01

def test_technical_entry_discarded():
    # Changing technical score must not affect HHS
    r1 = HHSWrapper().compute(_score(te=20.0), _weights())
    r2 = HHSWrapper().compute(_score(te=0.0), _weights())
    assert abs(r1.hhs_score - r2.hhs_score) < 0.01

def test_hhs_composite_uses_pillar_weights():
    # income=80 * 0.45 + durability=75 * 0.55 = 36 + 41.25 = 77.25
    result = HHSWrapper().compute(_score(vy=32.0, fd=30.0), _weights(income_w=45))
    assert abs(result.hhs_score - 77.25) < 0.01

def test_unsafe_flag_at_threshold():
    # 8/40 * 100 = 20.0 <= threshold 20 → UNSAFE
    result = HHSWrapper().compute(_score(fd=8.0), _weights(threshold=20))
    assert result.unsafe is True

def test_unsafe_flag_not_triggered_above_threshold():
    # 9/40 * 100 = 22.5 > threshold 20 → not UNSAFE
    result = HHSWrapper().compute(_score(fd=9.0), _weights(threshold=20))
    assert result.unsafe is False

def test_cb_caution_modifier_reduces_durability():
    # Without modifier: durability = 30/40*100 = 75
    # With −5pt: durability = 70
    w = _weights(threshold=20)
    r_no_mod = HHSWrapper().compute(_score(fd=30.0), w, cb_caution_modifier=0.0)
    r_with_mod = HHSWrapper().compute(_score(fd=30.0), w, cb_caution_modifier=-5.0)
    assert abs(r_no_mod.durability_pillar - 75.0) < 0.01
    assert abs(r_with_mod.durability_pillar - 70.0) < 0.01

def test_gate_fail_status():
    gate = GateResult(ticker="O", asset_class=AssetClass.DIVIDEND_STOCK,
                      status=GateStatus.FAIL, passed=False,
                      fail_reasons=["Dividend history < 10 years"])
    result = HHSWrapper().from_gate_result(gate, asset_class="DIVIDEND_STOCK", ticker="O")
    assert result.status == HHSStatus.QUALITY_GATE_FAIL
    assert result.hhs_score is None
    assert "Dividend history" in result.gate_fail_reasons[0]

def test_insufficient_data_status():
    gate = GateResult(ticker="O", asset_class=AssetClass.DIVIDEND_STOCK,
                      status=GateStatus.INSUFFICIENT_DATA, passed=False, fail_reasons=[])
    result = HHSWrapper().from_gate_result(gate, asset_class="DIVIDEND_STOCK", ticker="O")
    assert result.status == HHSStatus.INSUFFICIENT_DATA
    assert result.hhs_score is None

def test_scored_status_set_on_success():
    result = HHSWrapper().compute(_score(), _weights())
    assert result.status == HHSStatus.SCORED
