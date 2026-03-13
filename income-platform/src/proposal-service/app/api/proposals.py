"""Proposal management endpoints — Agent 12."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.config import settings
from app.database import get_db
from app.models import Proposal
from app.proposal_engine.engine import ProposalError, ProposalResult, run_proposal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/proposals", tags=["proposals"])


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
    override_rationale: Optional[str]
    user_acknowledged_veto: bool
    reviewed_by: Optional[str]
    decided_at: Optional[str]
    expires_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    entry_method: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _proposal_to_response(p: Proposal) -> ProposalResponse:
    """Convert ORM Proposal to ProposalResponse."""
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
        override_rationale=p.override_rationale,
        user_acknowledged_veto=p.user_acknowledged_veto,
        reviewed_by=p.reviewed_by,
        decided_at=p.decided_at.isoformat() if p.decided_at else None,
        expires_at=p.expires_at.isoformat() if p.expires_at else None,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


def _persist_proposal(db: Session, result: ProposalResult) -> Proposal:
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

        proposal = _persist_proposal(db, result)
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
    status: Optional[str] = Query(default=None),
    ticker: Optional[str] = Query(default=None),
    analyst_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> List[ProposalResponse]:
    """List proposals with optional filters."""
    query = db.query(Proposal)
    if status is not None:
        query = query.filter(Proposal.status == status)
    if ticker is not None:
        query = query.filter(Proposal.ticker == ticker.upper())
    if analyst_id is not None:
        query = query.filter(Proposal.analyst_id == analyst_id)
    proposals = query.order_by(Proposal.created_at.desc()).limit(limit).all()
    return [_proposal_to_response(p) for p in proposals]


@router.get("/{proposal_id}")
def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> ProposalResponse:
    """Get full proposal detail by ID."""
    proposal = _get_proposal_or_404(db, proposal_id)
    return _proposal_to_response(proposal)


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
    new_proposal = _persist_proposal(db, result)
    return _proposal_to_response(new_proposal)
