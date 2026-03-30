# app/scoring/hhs_weights.py
"""
HHS pillar weight defaults and UNSAFE threshold defaults.

Phase 1: weights read from these in-code defaults (DB lookup deferred to Phase 3).
Phase 3: HHSWeightProfile DB table (seeded in scripts/seed_hhs_weights.py) replaces
         these defaults via a DB-backed loader.

Income + Durability weights always sum to 100.
durability_weight is always derived as 100 - income_weight.

unsafe_threshold: Durability score (0–100) at or below which UNSAFE flag fires.
Default: 20. Phase 3 learning loop: ±1 pt/quarter, floor 10, ceiling 35.
"""
from dataclasses import dataclass
from enum import Enum


class RiskProfile(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class HHSWeights:
    asset_class: str
    income_weight: int   # 0–100
    unsafe_threshold: int

    @property
    def durability_weight(self) -> int:
        return 100 - self.income_weight


# Spec §3.4 — income_weight per asset class. durability_weight = 100 - income_weight.
_DEFAULTS: dict[str, int] = {
    "DIVIDEND_STOCK":    45,
    "COVERED_CALL_ETF":  40,
    "MREIT":             35,
    "BDC":               35,
    "BOND":              35,
    "PREFERRED":         40,
    "REIT":              40,
}
_DEFAULT_INCOME_WEIGHT = 40  # fallback for unknown classes
_DEFAULT_UNSAFE_THRESHOLD = 20


class HHSWeightDefaults:
    @staticmethod
    def get(asset_class: str, risk_profile: RiskProfile = RiskProfile.MODERATE) -> HHSWeights:
        """Return HHS weight config for an asset class.
        risk_profile reserved for Phase 3 per-profile differentiation.
        """
        income_w = _DEFAULTS.get(asset_class.upper(), _DEFAULT_INCOME_WEIGHT)
        return HHSWeights(
            asset_class=asset_class,
            income_weight=income_w,
            unsafe_threshold=_DEFAULT_UNSAFE_THRESHOLD,
        )

    @staticmethod
    def unsafe_threshold(risk_profile: RiskProfile = RiskProfile.MODERATE) -> int:
        return _DEFAULT_UNSAFE_THRESHOLD
