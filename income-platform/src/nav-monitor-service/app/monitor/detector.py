"""
Agent 10 — NAV Erosion Monitor
Alert detector: pure computation, no DB or network calls.

Three alert types:
  NAV_EROSION            — erosion_rate_30d / 90d breach thresholds
  PREMIUM_DISCOUNT_DRIFT — premium_discount too wide in either direction
  SCORE_DIVERGENCE       — Agent 03 penalising hard while NAV confirms deterioration
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AlertResult:
    """Single detected violation for one symbol."""
    symbol: str
    alert_type: str                 # NAV_EROSION | PREMIUM_DISCOUNT_DRIFT | SCORE_DIVERGENCE
    severity: str                   # WARNING | CRITICAL
    details: dict = field(default_factory=dict)
    score_at_alert: Optional[float] = None
    erosion_rate_used: Optional[float] = None
    threshold_used: Optional[float] = None


def _detect_nav_erosion(
    symbol: str,
    snapshot: dict,
    thresholds: dict,
) -> Optional[AlertResult]:
    """Return NAV_EROSION AlertResult when erosion thresholds are breached, else None."""
    rate_30d = snapshot.get("erosion_rate_30d")
    rate_90d = snapshot.get("erosion_rate_90d")
    thresh_30d = thresholds["nav_erosion_30d_threshold"]
    thresh_90d = thresholds["nav_erosion_90d_threshold"]

    breach_30d = rate_30d is not None and rate_30d < -thresh_30d
    breach_90d = rate_90d is not None and rate_90d < -thresh_90d

    if not breach_30d and not breach_90d:
        return None

    severity = "CRITICAL" if (breach_30d and breach_90d) else "WARNING"

    # For erosion_rate_used, prefer the worse (more negative) rate
    candidates: list[float] = []
    if breach_30d and rate_30d is not None:
        candidates.append(rate_30d)
    if breach_90d and rate_90d is not None:
        candidates.append(rate_90d)
    erosion_rate_used = min(candidates) if candidates else None

    threshold_used = -thresh_30d if breach_30d else -thresh_90d

    details: dict[str, Any] = {
        "erosion_rate_30d": rate_30d,
        "erosion_rate_90d": rate_90d,
        "threshold_30d": -thresh_30d,
        "threshold_90d": -thresh_90d,
        "breach_30d": breach_30d,
        "breach_90d": breach_90d,
    }

    return AlertResult(
        symbol=symbol,
        alert_type="NAV_EROSION",
        severity=severity,
        details=details,
        erosion_rate_used=erosion_rate_used,
        threshold_used=threshold_used,
    )


def _detect_premium_discount(
    symbol: str,
    snapshot: dict,
    thresholds: dict,
) -> Optional[AlertResult]:
    """Return PREMIUM_DISCOUNT_DRIFT AlertResult when drift is outside acceptable band."""
    pd = snapshot.get("premium_discount")
    if pd is None:
        return None

    pd = float(pd)
    warn_pct = thresholds["premium_discount_warning_pct"]
    cap_pct = thresholds["premium_discount_cap_pct"]
    critical_abs = thresholds["premium_discount_critical_abs"]

    deep_discount = pd < -warn_pct
    frothy_premium = pd > cap_pct

    if not deep_discount and not frothy_premium:
        return None

    severity = "CRITICAL" if abs(pd) > critical_abs else "WARNING"

    threshold_used = -warn_pct if deep_discount else cap_pct

    details: dict[str, Any] = {
        "premium_discount": pd,
        "deep_discount": deep_discount,
        "frothy_premium": frothy_premium,
        "warning_threshold": -warn_pct,
        "cap_threshold": cap_pct,
        "critical_abs_threshold": critical_abs,
    }

    return AlertResult(
        symbol=symbol,
        alert_type="PREMIUM_DISCOUNT_DRIFT",
        severity=severity,
        details=details,
        erosion_rate_used=None,
        threshold_used=threshold_used,
    )


def _detect_score_divergence(
    symbol: str,
    snapshot: dict,
    score: Optional[dict],
    thresholds: dict,
) -> Optional[AlertResult]:
    """Return SCORE_DIVERGENCE AlertResult when Agent 03 penalty is high and score is low."""
    if score is None:
        return None

    penalty = score.get("nav_erosion_penalty")
    total_score = score.get("total_score")

    if penalty is None or total_score is None:
        return None

    penalty = float(penalty)
    total_score = float(total_score)

    penalty_thresh = thresholds["score_divergence_penalty_threshold"]
    score_thresh = thresholds["score_divergence_score_threshold"]
    critical_score = thresholds["score_divergence_critical_score"]

    if penalty <= penalty_thresh or total_score >= score_thresh:
        return None

    severity = "CRITICAL" if total_score < critical_score else "WARNING"

    erosion_rate_30d = snapshot.get("erosion_rate_30d")

    details: dict[str, Any] = {
        "nav_erosion_penalty": penalty,
        "total_score": total_score,
        "penalty_threshold": penalty_thresh,
        "score_threshold": score_thresh,
        "erosion_rate_30d": erosion_rate_30d,
        "nav_erosion_details": score.get("nav_erosion_details"),
    }

    return AlertResult(
        symbol=symbol,
        alert_type="SCORE_DIVERGENCE",
        severity=severity,
        details=details,
        score_at_alert=total_score,
        erosion_rate_used=erosion_rate_30d,
        threshold_used=penalty_thresh,
    )


def detect_violations(
    snapshots: list[dict],
    scores: dict[str, dict],
) -> list[AlertResult]:
    """Detect all alert types across all symbols.

    Args:
        snapshots: List of nav_snapshot dicts, one per symbol (latest per symbol).
                   Each dict must have: symbol, erosion_rate_30d, erosion_rate_90d,
                   premium_discount.
        scores:    Mapping of symbol -> income_score dict from Agent 03.
                   Each dict must have: nav_erosion_penalty, total_score,
                   nav_erosion_details.

    Returns:
        List of AlertResult objects (may be multiple per symbol).
    """
    thresholds = {
        "nav_erosion_30d_threshold": settings.nav_erosion_30d_threshold,
        "nav_erosion_90d_threshold": settings.nav_erosion_90d_threshold,
        "premium_discount_warning_pct": settings.premium_discount_warning_pct,
        "premium_discount_cap_pct": settings.premium_discount_cap_pct,
        "premium_discount_critical_abs": settings.premium_discount_critical_abs,
        "score_divergence_penalty_threshold": settings.score_divergence_penalty_threshold,
        "score_divergence_score_threshold": settings.score_divergence_score_threshold,
        "score_divergence_critical_score": settings.score_divergence_critical_score,
    }

    results: list[AlertResult] = []

    for snapshot in snapshots:
        symbol = snapshot.get("symbol", "")
        if not symbol:
            continue

        score = scores.get(symbol)

        nav_alert = _detect_nav_erosion(symbol, snapshot, thresholds)
        if nav_alert:
            if score is not None:
                nav_alert.score_at_alert = score.get("total_score")
            results.append(nav_alert)
            logger.debug("NAV_EROSION alert for %s: %s", symbol, nav_alert.severity)

        pd_alert = _detect_premium_discount(symbol, snapshot, thresholds)
        if pd_alert:
            if score is not None:
                pd_alert.score_at_alert = score.get("total_score")
            results.append(pd_alert)
            logger.debug("PREMIUM_DISCOUNT_DRIFT alert for %s: %s", symbol, pd_alert.severity)

        sd_alert = _detect_score_divergence(symbol, snapshot, score, thresholds)
        if sd_alert:
            results.append(sd_alert)
            logger.debug("SCORE_DIVERGENCE alert for %s: %s", symbol, sd_alert.severity)

    return results
