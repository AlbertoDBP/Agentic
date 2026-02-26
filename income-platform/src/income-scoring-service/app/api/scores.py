"""
Agent 03 — Income Scoring Service
API: Scores endpoints.

Phase 1: Stub endpoints — returns 501 with clear message.
Phase 2: Full scoring engine (valuation + durability + technical).
"""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/")
def list_scores():
    """List recent income scores. Implemented in Phase 2."""
    raise HTTPException(
        status_code=501,
        detail="Scoring engine not yet implemented. Quality Gate (Phase 1) is available at /quality-gate/",
    )


@router.get("/{ticker}")
def get_score(ticker: str):
    """Get income score for a ticker. Implemented in Phase 2."""
    raise HTTPException(
        status_code=501,
        detail=f"Scoring engine not yet implemented. Run quality gate first: POST /quality-gate/evaluate",
    )
