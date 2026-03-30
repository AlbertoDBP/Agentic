# tests/test_hhs_weights.py
from app.scoring.hhs_weights import HHSWeightDefaults, RiskProfile

ALL_CLASSES = ["DIVIDEND_STOCK", "COVERED_CALL_ETF", "MREIT", "BDC",
               "BOND", "PREFERRED", "REIT"]

def test_all_spec_asset_classes_present():
    """All 7 asset classes from spec §3.4 must have defaults."""
    for ac in ALL_CLASSES:
        weights = HHSWeightDefaults.get(ac, RiskProfile.MODERATE)
        assert weights is not None, f"Missing default for {ac}"

def test_default_weights_sum_to_100():
    for ac in ALL_CLASSES:
        weights = HHSWeightDefaults.get(ac, RiskProfile.MODERATE)
        assert weights.income_weight + weights.durability_weight == 100, \
            f"{ac}: income={weights.income_weight} + durability={weights.durability_weight} != 100"

def test_unsafe_threshold_defaults():
    assert HHSWeightDefaults.unsafe_threshold(RiskProfile.CONSERVATIVE) == 20
    assert HHSWeightDefaults.unsafe_threshold(RiskProfile.MODERATE) == 20
    assert HHSWeightDefaults.unsafe_threshold(RiskProfile.AGGRESSIVE) == 20

def test_unknown_asset_class_falls_back_to_default():
    weights = HHSWeightDefaults.get("UNKNOWN_CLASS", RiskProfile.MODERATE)
    assert weights.income_weight == 40
    assert weights.durability_weight == 60

def test_durability_weight_is_complement_of_income():
    for ac in ALL_CLASSES:
        w = HHSWeightDefaults.get(ac, RiskProfile.MODERATE)
        assert w.durability_weight == 100 - w.income_weight
