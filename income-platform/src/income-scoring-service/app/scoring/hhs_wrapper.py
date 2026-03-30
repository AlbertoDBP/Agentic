# app/scoring/hhs_wrapper.py
"""
HHS Wrapper — Holding Health Score computation.

Reads ScoreResult from IncomeScorer, remaps to two pillars:
  Income pillar    = valuation_yield_score re-normalized to 0–100
  Durability pillar = financial_durability_score re-normalized to 0–100
  Technical Entry  = DISCARDED

Phase 1 note: Agent-03's Valuation & Yield pillar sub-components
(payout_sustainability, yield_vs_market, fcf_coverage) are all yield-quality
metrics. Price valuation (P/E, NAV premium) is not computed by Agent-03 —
it lives in IES. Using full valuation_yield_score as Income pillar proxy
is correct for Phase 1 with no data loss.

CB CAUTION interface: cb_caution_modifier parameter (default 0.0) reserved
for Phase 3 CB CAUTION −5pt Durability integration.

HHSStatus is defined here alongside HHSWrapper, consistent with the pattern
of GateStatus defined alongside QualityGateEngine in quality_gate.py.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.scoring.hhs_weights import HHSWeights
from app.scoring.income_scorer import ScoreResult
from app.scoring.quality_gate import GateResult, GateStatus


class HHSStatus(str, Enum):
    SCORED = "SCORED"
    QUALITY_GATE_FAIL = "QUALITY_GATE_FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STALE = "STALE"


@dataclass
class HHSResult:
    ticker: str = ""
    asset_class: str = ""
    status: HHSStatus = HHSStatus.SCORED
    income_pillar: Optional[float] = None
    durability_pillar: Optional[float] = None
    hhs_score: Optional[float] = None
    unsafe: bool = False
    unsafe_threshold_used: int = 20
    income_weight_used: int = 0
    durability_weight_used: int = 0
    gate_fail_reasons: list[str] = field(default_factory=list)


class HHSWrapper:

    def compute(
        self,
        score: ScoreResult,
        hhs_weights: HHSWeights,
        cb_caution_modifier: float = 0.0,
    ) -> HHSResult:
        """
        Map ScoreResult pillars to HHS Income + Durability pillars.

        cb_caution_modifier: applied to durability_pillar after normalization.
        Default 0.0. Phase 3: pass −5.0 when CB CAUTION is active.
        """
        wp = score.weight_profile or {}
        weight_yield = float(wp.get("weight_yield", 40))
        weight_durability = float(wp.get("weight_durability", 40))

        income_pillar = (score.valuation_yield_score / weight_yield * 100) if weight_yield > 0 else 0.0
        durability_pillar = (score.financial_durability_score / weight_durability * 100) if weight_durability > 0 else 0.0

        # Apply CB CAUTION modifier (Phase 3: −5.0 when CAUTION active)
        durability_pillar += cb_caution_modifier

        # Clamp to 0–100
        income_pillar = max(0.0, min(100.0, income_pillar))
        durability_pillar = max(0.0, min(100.0, durability_pillar))

        iw = hhs_weights.income_weight / 100.0
        dw = hhs_weights.durability_weight / 100.0
        hhs_score = round(income_pillar * iw + durability_pillar * dw, 2)

        unsafe = durability_pillar <= hhs_weights.unsafe_threshold

        return HHSResult(
            ticker=getattr(score, "ticker", ""),
            asset_class=score.asset_class,
            status=HHSStatus.SCORED,
            income_pillar=round(income_pillar, 2),
            durability_pillar=round(durability_pillar, 2),
            hhs_score=hhs_score,
            unsafe=unsafe,
            unsafe_threshold_used=hhs_weights.unsafe_threshold,
            income_weight_used=hhs_weights.income_weight,
            durability_weight_used=hhs_weights.durability_weight,
        )

    def from_gate_result(
        self, gate: GateResult, asset_class: str = "", ticker: str = ""
    ) -> HHSResult:
        if gate.status == GateStatus.FAIL:
            status = HHSStatus.QUALITY_GATE_FAIL
        elif gate.status == GateStatus.INSUFFICIENT_DATA:
            status = HHSStatus.INSUFFICIENT_DATA
        else:
            raise ValueError(f"Unexpected gate status: {gate.status}")
        return HHSResult(
            ticker=ticker, asset_class=asset_class, status=status,
            hhs_score=None, unsafe=False, gate_fail_reasons=gate.fail_reasons or [],
        )
