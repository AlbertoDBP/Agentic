"""
Agent 03 — Income Scoring Service
Signal Penalty Engine: Applies newsletter analyst signal penalties to scores.

Architecture constraint (v2.0): signals can ONLY REDUCE scores, never inflate.
bullish_strong_bonus_cap = 0.0 is enforced by design.

Penalty amounts from active SignalPenaltyConfig:
  BEARISH strong   → bearish_strong_penalty   (default 8.0 pts)
  BEARISH moderate → bearish_moderate_penalty  (default 5.0 pts)
  BEARISH weak     → bearish_weak_penalty      (default 2.0 pts)
  BULLISH          → 0.0  (bonus cap = 0 — risk-conservative mode)
  NEUTRAL          → 0.0
  INSUFFICIENT     → 0.0
  UNAVAILABLE      → 0.0  (Agent 02 down or disabled)

Signal type resolved from consensus.score:
  < consensus_bearish_threshold  → BEARISH
  > consensus_bullish_threshold  → BULLISH
  otherwise                      → NEUTRAL
  signal_strength=="insufficient"→ INSUFFICIENT (overrides score-based resolution)

Eligibility (ALL must be true for a penalty to be applied):
  - signal_type == BEARISH
  - signal_strength in (strong, moderate, weak) — not insufficient/None
  - n_analysts >= config.min_n_analysts
  - decay_weight >= config.min_decay_weight
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PenaltyResult:
    """Result of one signal penalty computation."""
    signal_type: str            # BEARISH | NEUTRAL | BULLISH | INSUFFICIENT | UNAVAILABLE
    signal_strength: Optional[str]  # strong | moderate | weak | insufficient | None
    consensus_score: Optional[float]
    n_analysts: int
    decay_weight: Optional[float]
    penalty: float              # points deducted (≥ 0.0)
    score_before: float
    score_after: float          # max(0.0, score_before - penalty)
    eligible: bool              # True if signal passed all eligibility thresholds
    agent02_available: bool     # False when signal_response was None
    details: dict = field(default_factory=dict)


class SignalPenaltyEngine:
    """Stateless engine — one instance reused for all scoring requests."""

    def compute(
        self,
        score_before: float,
        signal_response: Optional[dict],
        config,                 # SignalPenaltyConfig ORM row (or compatible object)
    ) -> PenaltyResult:
        """Compute the signal penalty for one scoring request.

        Args:
            score_before:     Current total score (post NAV erosion, pre-signal).
            signal_response:  Parsed Agent 02 JSON dict, or None (unavailable).
            config:           Active SignalPenaltyConfig ORM row.

        Returns:
            PenaltyResult with penalty=0.0 when signal is unavailable/ineligible.
        """
        if signal_response is None:
            return PenaltyResult(
                signal_type="UNAVAILABLE",
                signal_strength=None,
                consensus_score=None,
                n_analysts=0,
                decay_weight=None,
                penalty=0.0,
                score_before=score_before,
                score_after=score_before,
                eligible=False,
                agent02_available=False,
                details={"reason": "Agent 02 unavailable or no signal data"},
            )

        # ── Extract fields from Agent 02 AnalystSignalResponse ───────────────

        signal_strength = signal_response.get("signal_strength")
        consensus = signal_response.get("consensus") or {}
        recommendation = signal_response.get("recommendation") or {}

        raw_consensus_score = consensus.get("score")
        n_analysts = int(consensus.get("n_analysts") or 0)
        raw_decay_weight = recommendation.get("decay_weight")

        # Coerce Decimal/string → float for arithmetic
        consensus_score = float(raw_consensus_score) if raw_consensus_score is not None else None
        decay_weight = float(raw_decay_weight) if raw_decay_weight is not None else None

        # ── Resolve signal type ───────────────────────────────────────────────

        bearish_threshold = float(config.consensus_bearish_threshold)
        bullish_threshold = float(config.consensus_bullish_threshold)

        if signal_strength == "insufficient" or consensus_score is None:
            signal_type = "INSUFFICIENT"
        elif consensus_score < bearish_threshold:
            signal_type = "BEARISH"
        elif consensus_score > bullish_threshold:
            signal_type = "BULLISH"
        else:
            signal_type = "NEUTRAL"

        # ── Eligibility ───────────────────────────────────────────────────────

        min_n = int(config.min_n_analysts)
        min_dw = float(config.min_decay_weight)

        eligible = (
            signal_type == "BEARISH"
            and signal_strength not in (None, "insufficient")
            and n_analysts >= min_n
            and (decay_weight is not None and decay_weight >= min_dw)
        )

        # ── Penalty lookup ────────────────────────────────────────────────────

        penalty = 0.0
        if eligible:
            if signal_strength == "strong":
                penalty = float(config.bearish_strong_penalty)
            elif signal_strength == "moderate":
                penalty = float(config.bearish_moderate_penalty)
            elif signal_strength == "weak":
                penalty = float(config.bearish_weak_penalty)

        score_after = max(0.0, score_before - penalty)

        details = {
            "signal_type": signal_type,
            "signal_strength": signal_strength,
            "consensus_score": consensus_score,
            "n_analysts": n_analysts,
            "decay_weight": decay_weight,
            "penalty_applied": penalty,
            "score_before": score_before,
            "score_after": score_after,
            "eligible": eligible,
            "config_thresholds": {
                "bearish_threshold": bearish_threshold,
                "bullish_threshold": bullish_threshold,
                "min_n_analysts": min_n,
                "min_decay_weight": min_dw,
            },
        }

        return PenaltyResult(
            signal_type=signal_type,
            signal_strength=signal_strength,
            consensus_score=consensus_score,
            n_analysts=n_analysts,
            decay_weight=decay_weight,
            penalty=penalty,
            score_before=score_before,
            score_after=score_after,
            eligible=eligible,
            agent02_available=True,
            details=details,
        )
