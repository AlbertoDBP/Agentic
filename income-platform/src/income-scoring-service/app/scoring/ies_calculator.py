# app/scoring/ies_calculator.py
"""
IES — Income Entry Score. On-demand only.

Formula: IES = (valuation_score × 0.60) + (technical_score × 0.40)
Output: 0–100.

Prerequisite gate: HHS > 50 AND no UNSAFE flag.
Gate-blocked response is machine-readable (consumed by Agent-12 and rebalancer).

Valuation sub-metrics (P/E vs 5yr avg, NAV premium/discount, yield vs benchmark)
and Technical sub-metrics (RSI, 200-DMA, 52wk high %) are computed externally
and passed in as pre-scored 0–100 values.
TODO Phase 3: implement sub-metric scoring using Agent-01 market data.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.scoring.hhs_wrapper import HHSResult, HHSStatus

HHS_GATE_THRESHOLD = 50


class IESStatus(str, Enum):
    SCORED = "SCORED"
    GATE_BLOCKED = "GATE_BLOCKED"


@dataclass
class IESResult:
    ticker: str = ""
    status: IESStatus = IESStatus.SCORED
    reason: Optional[str] = None
    ies_score: Optional[float] = None
    valuation_score: Optional[float] = None
    technical_score: Optional[float] = None
    action: str = "NO_ACTION"
    hhs_score_at_evaluation: Optional[float] = None


class IESCalculator:

    def evaluate(
        self,
        hhs: HHSResult,
        valuation_score: Optional[float],
        technical_score: Optional[float],
    ) -> IESResult:
        if hhs.unsafe:
            return IESResult(ticker=hhs.ticker, status=IESStatus.GATE_BLOCKED,
                             reason="UNSAFE_FLAG", action="NO_ACTION",
                             hhs_score_at_evaluation=hhs.hhs_score)

        if hhs.hhs_score is None or hhs.hhs_score <= HHS_GATE_THRESHOLD:
            return IESResult(ticker=hhs.ticker, status=IESStatus.GATE_BLOCKED,
                             reason="HHS_BELOW_THRESHOLD", action="NO_ACTION",
                             hhs_score_at_evaluation=hhs.hhs_score)

        ies_score = round(
            (valuation_score or 0.0) * 0.60 + (technical_score or 0.0) * 0.40, 2
        )
        return IESResult(
            ticker=hhs.ticker, status=IESStatus.SCORED,
            ies_score=ies_score, valuation_score=valuation_score,
            technical_score=technical_score,
            action=self._action(ies_score),
            hhs_score_at_evaluation=hhs.hhs_score,
        )

    @staticmethod
    def _action(score: float) -> str:
        if score >= 85:
            return "FULL_POSITION"
        elif score >= 70:
            return "PARTIAL_POSITION"
        return "WAIT_OR_DCA"
