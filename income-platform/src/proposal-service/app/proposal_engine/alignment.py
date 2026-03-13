"""Alignment computation per Agent 12 spec."""
from typing import Optional


def compute_alignment(
    analyst_sentiment: Optional[float],
    platform_score: Optional[float],
    veto_flags: Optional[dict],
) -> str:
    """Return platform_alignment: Aligned | Partial | Divergent | Vetoed.

    Args:
        analyst_sentiment: float in range -1.0 to 1.0 from Agent 02
        platform_score:    float in range 0-100 from Agent 03
        veto_flags:        dict of VETO reasons; truthy means Vetoed

    Returns:
        alignment string
    """
    if veto_flags:
        return "Vetoed"

    if analyst_sentiment is None or platform_score is None:
        return "Partial"

    # Normalize platform_score 0–100 → -1.0 to +1.0
    platform_sentiment = (platform_score - 50) / 50

    divergence = abs(analyst_sentiment - platform_sentiment)

    if divergence <= 0.25:
        return "Aligned"
    elif divergence <= 0.50:
        return "Partial"
    else:
        return "Divergent"
