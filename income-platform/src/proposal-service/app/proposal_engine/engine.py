"""Proposal engine: orchestrates data fetching, alignment computation,
and returns a ProposalResult dataclass ready for DB persistence.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import settings
from app.proposal_engine import data_fetcher
from app.proposal_engine.alignment import compute_alignment
from app.proposal_engine.veto_enforcer import detect_veto_flags

logger = logging.getLogger(__name__)


class ProposalError(Exception):
    """Raised when proposal cannot be generated (e.g. Agent 02 failure)."""


@dataclass
class ProposalResult:
    ticker: str
    analyst_signal_id: Optional[int]
    analyst_id: Optional[int]
    platform_score: Optional[float]
    platform_alignment: Optional[str]  # Aligned | Partial | Divergent | Vetoed
    veto_flags: Optional[dict]
    divergence_notes: Optional[str]
    # Lens 1
    analyst_recommendation: Optional[str]
    analyst_sentiment: Optional[float]
    analyst_thesis_summary: Optional[str]
    analyst_yield_estimate: Optional[float]
    analyst_safety_grade: Optional[str]
    # Lens 2
    platform_yield_estimate: Optional[float]
    platform_safety_result: Optional[dict]
    platform_income_grade: Optional[str]
    # Execution
    entry_price_low: Optional[float]
    entry_price_high: Optional[float]
    position_size_pct: Optional[float]
    recommended_account: Optional[str]
    sizing_rationale: Optional[str]
    # State
    status: str = "pending"
    trigger_mode: str = "on_demand"
    trigger_ref_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    entry_method: Optional[str] = None  # "market_fallback" when Agent 04 fails


def _extract_recommendation(signal: dict) -> dict:
    """Pull analyst recommendation fields from AnalystSignalResponse."""
    rec = signal.get("recommendation") or {}
    return rec


def _extract_analyst(signal: dict) -> dict:
    """Pull analyst fields from AnalystSignalResponse."""
    return signal.get("analyst") or {}


def _build_divergence_notes(
    alignment: str,
    analyst_sentiment: Optional[float],
    platform_score: Optional[float],
) -> Optional[str]:
    if alignment == "Aligned":
        return None
    if alignment == "Vetoed":
        return "Platform VETO flags detected — analyst override requires hard acknowledgment."
    if analyst_sentiment is None or platform_score is None:
        return "Incomplete platform data — alignment cannot be fully determined."
    platform_sentiment = (platform_score - 50) / 50
    divergence = abs(analyst_sentiment - platform_sentiment)
    return (
        f"Analyst sentiment {analyst_sentiment:.3f} vs platform sentiment "
        f"{platform_sentiment:.3f} (score {platform_score:.1f}) — "
        f"divergence {divergence:.3f} → {alignment}."
    )


async def run_proposal(
    ticker: str,
    portfolio_id: Optional[str] = None,
    scan_id: Optional[str] = None,
    alert_id: Optional[int] = None,
    trigger_mode: str = "on_demand",
) -> ProposalResult:
    """Generate a single proposal for the given ticker.

    Raises ProposalError if Agent 02 is unavailable (fatal).
    """
    ticker = ticker.upper().strip()

    try:
        signal, score, entry_price, tax = await data_fetcher.fetch_all(
            ticker, portfolio_id=portfolio_id
        )
    except Exception as exc:
        raise ProposalError(f"Agent 02 signal unavailable for {ticker}: {exc}") from exc

    # --- Analyst lens ---
    rec = _extract_recommendation(signal)
    analyst_info = _extract_analyst(signal)

    analyst_signal_id: Optional[int] = rec.get("id")
    analyst_id: Optional[int] = analyst_info.get("id")
    analyst_recommendation: Optional[str] = (rec.get("label") or rec.get("recommendation"))
    analyst_sentiment_raw = rec.get("sentiment_score")
    analyst_sentiment: Optional[float] = (
        float(analyst_sentiment_raw) if analyst_sentiment_raw is not None else None
    )
    analyst_yield_raw = rec.get("yield_at_publish")
    analyst_yield_estimate: Optional[float] = (
        float(analyst_yield_raw) if analyst_yield_raw is not None else None
    )
    analyst_safety_grade: Optional[str] = rec.get("safety_grade")
    analyst_thesis_summary: Optional[str] = (
        rec.get("thesis_summary")
        or rec.get("bull_case")
    )

    # --- Platform lens (Agent 03) ---
    platform_score: Optional[float] = None
    platform_income_grade: Optional[str] = None
    platform_yield_estimate: Optional[float] = None
    platform_safety_result: Optional[dict] = None
    veto_flags: Optional[dict] = None

    if score is not None:
        raw_score = score.get("total_score") or score.get("score")
        platform_score = float(raw_score) if raw_score is not None else None
        platform_income_grade = score.get("grade") or score.get("income_grade")
        platform_yield_estimate_raw = score.get("yield_estimate") or score.get("platform_yield_estimate")
        platform_yield_estimate = (
            float(platform_yield_estimate_raw) if platform_yield_estimate_raw is not None else None
        )
        platform_safety_result = score.get("safety_result") or score.get("factor_details")
        veto_flags = detect_veto_flags(score)

    # --- Alignment ---
    alignment = compute_alignment(analyst_sentiment, platform_score, veto_flags)
    divergence_notes = _build_divergence_notes(alignment, analyst_sentiment, platform_score)

    # --- Execution params (Agent 04) ---
    entry_price_low: Optional[float] = None
    entry_price_high: Optional[float] = None
    position_size_pct: Optional[float] = None
    sizing_rationale: Optional[str] = None
    entry_method: Optional[str] = None

    if entry_price is not None:
        low = entry_price.get("entry_price_low")
        high = entry_price.get("entry_price_high")
        entry_price_low = float(low) if low is not None else None
        entry_price_high = float(high) if high is not None else None
        size = entry_price.get("position_size_pct")
        position_size_pct = float(size) if size is not None else None
        sizing_rationale = entry_price.get("notes")
        entry_method = entry_price.get("entry_method")
    else:
        # Agent 04 failed — market fallback flag
        entry_method = "market_fallback"

    # --- Tax placement (Agent 05) ---
    recommended_account: Optional[str] = None
    if tax is not None:
        recommended_account = (
            tax.get("recommended_account")
            or tax.get("account_type")
        )

    # --- Trigger ref ---
    trigger_ref_id: Optional[str] = None
    if scan_id:
        trigger_ref_id = f"scan:{scan_id}"
    elif alert_id:
        trigger_ref_id = f"alert:{alert_id}"

    # --- Expiry ---
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.proposal_expiry_days)

    return ProposalResult(
        ticker=ticker,
        analyst_signal_id=analyst_signal_id,
        analyst_id=analyst_id,
        platform_score=platform_score,
        platform_alignment=alignment,
        veto_flags=veto_flags,
        divergence_notes=divergence_notes,
        analyst_recommendation=analyst_recommendation,
        analyst_sentiment=analyst_sentiment,
        analyst_thesis_summary=analyst_thesis_summary,
        analyst_yield_estimate=analyst_yield_estimate,
        analyst_safety_grade=analyst_safety_grade,
        platform_yield_estimate=platform_yield_estimate,
        platform_safety_result=platform_safety_result,
        platform_income_grade=platform_income_grade,
        entry_price_low=entry_price_low,
        entry_price_high=entry_price_high,
        position_size_pct=position_size_pct,
        recommended_account=recommended_account,
        sizing_rationale=sizing_rationale,
        status="pending",
        trigger_mode=trigger_mode,
        trigger_ref_id=trigger_ref_id,
        expires_at=expires_at,
        entry_method=entry_method,
    )
