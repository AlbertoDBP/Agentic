"""Proposal management endpoints — Agent 12."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.config import settings
from app.database import get_db
from app.models import Proposal
from app.proposal_engine.engine import ProposalError, ProposalResult, run_proposal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/proposals", tags=["proposals"])


# ---------------------------------------------------------------------------
# Enrichment helpers
# ---------------------------------------------------------------------------

def _compute_zone(
    current_price: Optional[float],
    entry_low: Optional[float],
    entry_high: Optional[float],
) -> tuple[str, Optional[float]]:
    """Classify current price relative to the proposal entry range."""
    if current_price is None or entry_low is None or entry_low == 0:
        return "UNKNOWN", None
    pct = (current_price - entry_low) / entry_low
    if current_price < entry_low:
        status = "BELOW_ENTRY"
    elif current_price <= (entry_high or entry_low):
        status = "IN_ZONE"
    else:
        status = "ABOVE_ENTRY"
    return status, round(pct, 4)


def _enrich_proposals(db: Session, tickers: list[str]) -> dict[str, dict]:
    """
    Batch-fetch market price and latest score sub-components for a list of tickers.
    Returns dict keyed by ticker. Missing tickers get no entry (caller treats as None).
    Uses LEFT JOIN so missing market data or scores return NULL rows gracefully.
    """
    if not tickers:
        return {}
    placeholders = ", ".join(f":t{i}" for i in range(len(tickers)))
    params = {f"t{i}": t for i, t in enumerate(tickers)}
    try:
        rows = db.execute(text(f"""
            SELECT
                m.symbol AS ticker,
                m.price            AS current_price,
                m.week52_high,
                m.week52_low,
                m.nav_value,
                m.nav_discount_pct,
                s.valuation_yield_score,
                s.financial_durability_score,
                s.technical_entry_score
            FROM platform_shared.market_data_cache m
            LEFT JOIN LATERAL (
                SELECT valuation_yield_score, financial_durability_score, technical_entry_score
                FROM platform_shared.income_scores
                WHERE ticker = m.symbol
                ORDER BY scored_at DESC
                LIMIT 1
            ) s ON true
            WHERE m.symbol IN ({placeholders})
        """), params).mappings().all()
    except OperationalError as exc:
        msg = str(exc).lower()
        if "does not exist" in msg or "no such table" in msg:
            logger.debug("_enrich_proposals: market data tables unavailable; skipping enrichment")
        else:
            logger.warning("_enrich_proposals: unexpected DB error during enrichment: %s", exc)
        return {}
    return {row["ticker"]: dict(row) for row in rows}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    ticker: Optional[str] = None
    tickers: Optional[List[str]] = None
    portfolio_id: Optional[str] = None
    scan_id: Optional[str] = None
    alert_id: Optional[int] = None
    trigger_mode: str = "on_demand"

    @field_validator("trigger_mode")
    @classmethod
    def validate_trigger_mode(cls, v: str) -> str:
        allowed = {"signal_driven", "on_demand", "re_evaluation"}
        if v not in allowed:
            raise ValueError(f"trigger_mode must be one of {allowed}")
        return v


class ExecuteRequest(BaseModel):
    user_acknowledged_veto: bool = False


class OverrideRequest(BaseModel):
    rationale: str

    @field_validator("rationale")
    @classmethod
    def validate_rationale_length(cls, v: str) -> str:
        if len(v) < settings.min_override_rationale_len:
            raise ValueError(
                f"rationale must be at least {settings.min_override_rationale_len} characters"
            )
        return v


class RejectRequest(BaseModel):
    reason: Optional[str] = None


class FillConfirmedRequest(BaseModel):
    filled_qty: float
    avg_fill_price: float
    filled_at: str          # ISO datetime string from broker
    status: str             # filled | partially_filled | cancelled

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"filled", "partially_filled", "cancelled"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class ProposalResponse(BaseModel):
    id: int
    ticker: str
    analyst_signal_id: Optional[int]
    analyst_id: Optional[int]
    platform_score: Optional[float]
    platform_alignment: Optional[str]
    veto_flags: Optional[Any]
    divergence_notes: Optional[str]
    analyst_recommendation: Optional[str]
    analyst_sentiment: Optional[float]
    analyst_thesis_summary: Optional[str]
    analyst_yield_estimate: Optional[float]
    analyst_safety_grade: Optional[str]
    platform_yield_estimate: Optional[float]
    platform_safety_result: Optional[Any]
    platform_income_grade: Optional[str]
    entry_price_low: Optional[float]
    entry_price_high: Optional[float]
    position_size_pct: Optional[float]
    recommended_account: Optional[str]
    sizing_rationale: Optional[str]
    status: str
    trigger_mode: Optional[str]
    trigger_ref_id: Optional[str]
    portfolio_id: Optional[str] = None
    override_rationale: Optional[str]
    user_acknowledged_veto: bool
    reviewed_by: Optional[str]
    decided_at: Optional[str]
    expires_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    entry_method: Optional[str] = None
    # Market enrichment (from market_data_cache + income_scores)
    current_price: Optional[float] = None
    zone_status: Optional[str] = None
    pct_from_entry: Optional[float] = None
    valuation_yield_score: Optional[float] = None
    financial_durability_score: Optional[float] = None
    technical_entry_score: Optional[float] = None
    week52_high: Optional[float] = None
    week52_low: Optional[float] = None
    nav_value: Optional[float] = None
    nav_discount_pct: Optional[float] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _proposal_to_response(p: Proposal, enrichment: Optional[dict] = None) -> ProposalResponse:
    """Convert ORM Proposal to ProposalResponse."""
    enc = enrichment or {}
    current_price = enc.get("current_price")
    if current_price is not None:
        current_price = float(current_price)
    zone_status, pct_from_entry = _compute_zone(
        current_price,
        float(p.entry_price_low) if p.entry_price_low is not None else None,
        float(p.entry_price_high) if p.entry_price_high is not None else None,
    )
    return ProposalResponse(
        id=p.id,
        ticker=p.ticker,
        analyst_signal_id=p.analyst_signal_id,
        analyst_id=p.analyst_id,
        platform_score=float(p.platform_score) if p.platform_score is not None else None,
        platform_alignment=p.platform_alignment,
        veto_flags=p.veto_flags,
        divergence_notes=p.divergence_notes,
        analyst_recommendation=p.analyst_recommendation,
        analyst_sentiment=float(p.analyst_sentiment) if p.analyst_sentiment is not None else None,
        analyst_thesis_summary=p.analyst_thesis_summary,
        analyst_yield_estimate=float(p.analyst_yield_estimate) if p.analyst_yield_estimate is not None else None,
        analyst_safety_grade=p.analyst_safety_grade,
        platform_yield_estimate=float(p.platform_yield_estimate) if p.platform_yield_estimate is not None else None,
        platform_safety_result=p.platform_safety_result,
        platform_income_grade=p.platform_income_grade,
        entry_price_low=float(p.entry_price_low) if p.entry_price_low is not None else None,
        entry_price_high=float(p.entry_price_high) if p.entry_price_high is not None else None,
        position_size_pct=float(p.position_size_pct) if p.position_size_pct is not None else None,
        recommended_account=p.recommended_account,
        sizing_rationale=p.sizing_rationale,
        status=p.status,
        trigger_mode=p.trigger_mode,
        trigger_ref_id=p.trigger_ref_id,
        portfolio_id=p.portfolio_id,
        override_rationale=p.override_rationale,
        user_acknowledged_veto=bool(p.user_acknowledged_veto) if p.user_acknowledged_veto is not None else False,
        reviewed_by=p.reviewed_by,
        decided_at=p.decided_at.isoformat() if p.decided_at else None,
        expires_at=p.expires_at.isoformat() if p.expires_at else None,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
        current_price=current_price,
        zone_status=zone_status,
        pct_from_entry=pct_from_entry,
        valuation_yield_score=float(enc["valuation_yield_score"]) if enc.get("valuation_yield_score") is not None else None,
        financial_durability_score=float(enc["financial_durability_score"]) if enc.get("financial_durability_score") is not None else None,
        technical_entry_score=float(enc["technical_entry_score"]) if enc.get("technical_entry_score") is not None else None,
        week52_high=float(enc["week52_high"]) if enc.get("week52_high") is not None else None,
        week52_low=float(enc["week52_low"]) if enc.get("week52_low") is not None else None,
        nav_value=float(enc["nav_value"]) if enc.get("nav_value") is not None else None,
        nav_discount_pct=float(enc["nav_discount_pct"]) if enc.get("nav_discount_pct") is not None else None,
    )


def _persist_proposal(db: Session, result: ProposalResult, portfolio_id: Optional[str] = None) -> Proposal:
    """Write a ProposalResult to the DB and return the ORM object."""
    now = datetime.now(timezone.utc)
    proposal = Proposal(
        ticker=result.ticker,
        analyst_signal_id=result.analyst_signal_id,
        analyst_id=result.analyst_id,
        platform_score=result.platform_score,
        platform_alignment=result.platform_alignment,
        veto_flags=result.veto_flags,
        divergence_notes=result.divergence_notes,
        analyst_recommendation=result.analyst_recommendation,
        analyst_sentiment=result.analyst_sentiment,
        analyst_thesis_summary=result.analyst_thesis_summary,
        analyst_yield_estimate=result.analyst_yield_estimate,
        analyst_safety_grade=result.analyst_safety_grade,
        platform_yield_estimate=result.platform_yield_estimate,
        platform_safety_result=result.platform_safety_result,
        platform_income_grade=result.platform_income_grade,
        entry_price_low=result.entry_price_low,
        entry_price_high=result.entry_price_high,
        position_size_pct=result.position_size_pct,
        recommended_account=result.recommended_account,
        sizing_rationale=result.sizing_rationale,
        status=result.status,
        trigger_mode=result.trigger_mode,
        trigger_ref_id=result.trigger_ref_id,
        portfolio_id=portfolio_id,
        expires_at=result.expires_at,
        created_at=now,
        updated_at=now,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


def _get_proposal_or_404(db: Session, proposal_id: int) -> Proposal:
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return proposal


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_proposal(
    body: GenerateRequest,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
):
    """Generate one or more proposals.

    If `tickers` list is provided, generate a proposal for each ticker and
    return a list. Otherwise generate for the single `ticker` field.
    """
    tickers_to_process: List[str] = []
    if body.tickers:
        tickers_to_process = [t.upper().strip() for t in body.tickers]
    elif body.ticker:
        tickers_to_process = [body.ticker.upper().strip()]
    else:
        raise HTTPException(
            status_code=422,
            detail="Either 'ticker' or 'tickers' must be provided.",
        )

    results = []
    for ticker in tickers_to_process:
        try:
            result = await run_proposal(
                ticker=ticker,
                portfolio_id=body.portfolio_id,
                scan_id=body.scan_id,
                alert_id=body.alert_id,
                trigger_mode=body.trigger_mode,
            )
        except ProposalError as exc:
            if len(tickers_to_process) == 1:
                raise HTTPException(
                    status_code=503,
                    detail=f"Cannot generate proposal: {exc}",
                )
            # In batch mode, skip failed tickers
            logger.error("Proposal generation failed for %s: %s", ticker, exc)
            continue

        proposal = _persist_proposal(db, result, portfolio_id=body.portfolio_id)
        resp = _proposal_to_response(proposal)
        # Attach entry_method from engine result (not stored in DB)
        resp.entry_method = result.entry_method
        results.append(resp)

    if not results and len(tickers_to_process) == 1:
        raise HTTPException(status_code=503, detail="No proposals could be generated.")

    if body.tickers:
        return results
    return results[0] if results else None


@router.get("")
def list_proposals(
    status: Optional[List[str]] = Query(default=None),
    ticker: Optional[str] = Query(default=None),
    analyst_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> List[ProposalResponse]:
    """List proposals with optional filters."""
    query = db.query(Proposal)
    if status is not None:
        if len(status) == 1:
            query = query.filter(Proposal.status == status[0])
        else:
            query = query.filter(Proposal.status.in_(status))
    if ticker is not None:
        query = query.filter(Proposal.ticker == ticker.upper())
    if analyst_id is not None:
        query = query.filter(Proposal.analyst_id == analyst_id)
    proposals = query.order_by(Proposal.created_at.desc()).limit(limit).all()
    enrichments = _enrich_proposals(db, [p.ticker for p in proposals])
    return [_proposal_to_response(p, enrichment=enrichments.get(p.ticker)) for p in proposals]


@router.get("/{proposal_id}")
def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> ProposalResponse:
    """Get full proposal detail by ID."""
    proposal = _get_proposal_or_404(db, proposal_id)
    enc = _enrich_proposals(db, [proposal.ticker])
    return _proposal_to_response(proposal, enrichment=enc.get(proposal.ticker))


@router.post("/{proposal_id}/execute")
def execute_proposal(
    proposal_id: int,
    body: ExecuteRequest = ExecuteRequest(),
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> ProposalResponse:
    """Execute Path A — platform-aligned.

    Blocked if status=VETO and user_acknowledged_veto=false.
    """
    proposal = _get_proposal_or_404(db, proposal_id)

    if proposal.status == "rejected":
        raise HTTPException(
            status_code=409,
            detail="Cannot execute a rejected proposal.",
        )
    if proposal.status in ("executed_aligned", "executed_override"):
        raise HTTPException(
            status_code=409,
            detail="Proposal has already been executed.",
        )

    # VETO block
    if proposal.platform_alignment == "Vetoed" and not body.user_acknowledged_veto:
        if not proposal.user_acknowledged_veto:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Proposal is VETOED. Set user_acknowledged_veto=true to override "
                    "VETO and execute via Path A."
                ),
            )

    now = datetime.now(timezone.utc)
    proposal.status = "executed_aligned"
    proposal.decided_at = now
    proposal.updated_at = now
    if body.user_acknowledged_veto:
        proposal.user_acknowledged_veto = True
    db.commit()
    db.refresh(proposal)
    return _proposal_to_response(proposal)


@router.post("/{proposal_id}/override")
def override_proposal(
    proposal_id: int,
    body: OverrideRequest,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> ProposalResponse:
    """Execute Path B — analyst override.

    Rationale must be >= min_override_rationale_len characters.
    """
    proposal = _get_proposal_or_404(db, proposal_id)

    if proposal.status == "rejected":
        raise HTTPException(
            status_code=409,
            detail="Cannot override a rejected proposal.",
        )
    if proposal.status in ("executed_aligned", "executed_override"):
        raise HTTPException(
            status_code=409,
            detail="Proposal has already been executed.",
        )

    now = datetime.now(timezone.utc)
    proposal.status = "executed_override"
    proposal.override_rationale = body.rationale
    proposal.decided_at = now
    proposal.updated_at = now
    db.commit()
    db.refresh(proposal)
    return _proposal_to_response(proposal)


@router.post("/{proposal_id}/reject")
def reject_proposal(
    proposal_id: int,
    body: RejectRequest = RejectRequest(),
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> ProposalResponse:
    """Reject a proposal."""
    proposal = _get_proposal_or_404(db, proposal_id)

    if proposal.status in ("executed_aligned", "executed_override"):
        raise HTTPException(
            status_code=409,
            detail="Cannot reject an already-executed proposal.",
        )

    now = datetime.now(timezone.utc)
    proposal.status = "rejected"
    proposal.decided_at = now
    proposal.updated_at = now
    if body.reason:
        proposal.divergence_notes = (
            (proposal.divergence_notes or "") + f" | Rejection reason: {body.reason}"
        ).strip(" |")
    db.commit()
    db.refresh(proposal)
    return _proposal_to_response(proposal)


@router.get("/{proposal_id}/re-evaluate")
async def re_evaluate_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> ProposalResponse:
    """Force fresh re-evaluation: creates new proposal row, marks old as expired."""
    old = _get_proposal_or_404(db, proposal_id)

    try:
        result = await run_proposal(
            ticker=old.ticker,
            trigger_mode="re_evaluation",
        )
    except ProposalError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Re-evaluation failed: {exc}",
        )

    # Mark old proposal expired
    now = datetime.now(timezone.utc)
    old.status = "expired"
    old.updated_at = now
    db.commit()

    # Persist new proposal
    new_proposal = _persist_proposal(db, result, portfolio_id=old.portfolio_id)
    return _proposal_to_response(new_proposal)


@router.post("/{proposal_id}/fill-confirmed")
def fill_confirmed(
    proposal_id: int,
    body: FillConfirmedRequest,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> ProposalResponse:
    """Mark a proposal as fill-confirmed after broker order completes.

    Transitions:
      executed_aligned → executed_filled    (body.status == "filled")
      executed_aligned → partially_filled   (body.status == "partially_filled")
      executed_aligned → cancelled          (body.status == "cancelled")
    """
    proposal = _get_proposal_or_404(db, proposal_id)

    if proposal.status not in ("executed_aligned", "executed_override", "partially_filled"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot confirm fill on proposal with status '{proposal.status}'",
        )

    status_map = {
        "filled": "executed_filled",
        "partially_filled": "partially_filled",
        "cancelled": "cancelled",
    }

    now = datetime.now(timezone.utc)
    proposal.status = status_map[body.status]
    proposal.decided_at = now
    proposal.updated_at = now
    db.commit()
    db.refresh(proposal)
    return _proposal_to_response(proposal)
