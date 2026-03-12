"""
Agent 03 — Income Scoring Service
API: Signal Penalty Config endpoint.

Endpoints:
  GET /signal-config/ — return the active signal penalty configuration
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SignalPenaltyConfig

logger = logging.getLogger(__name__)

router = APIRouter()


class SignalPenaltyConfigResponse(BaseModel):
    id: str
    version: int
    is_active: bool
    bearish_strong_penalty: float
    bearish_moderate_penalty: float
    bearish_weak_penalty: float
    bullish_strong_bonus_cap: float
    min_n_analysts: int
    min_decay_weight: float
    consensus_bearish_threshold: float
    consensus_bullish_threshold: float
    created_at: Optional[datetime]
    created_by: Optional[str]
    notes: Optional[str]


@router.get("/", response_model=SignalPenaltyConfigResponse)
def get_signal_config(db: Session = Depends(get_db)):
    """Return the active signal penalty configuration."""
    config = (
        db.query(SignalPenaltyConfig)
        .filter(SignalPenaltyConfig.is_active.is_(True))
        .first()
    )
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active signal penalty configuration found.",
        )
    return SignalPenaltyConfigResponse(
        id=str(config.id),
        version=config.version,
        is_active=config.is_active,
        bearish_strong_penalty=float(config.bearish_strong_penalty),
        bearish_moderate_penalty=float(config.bearish_moderate_penalty),
        bearish_weak_penalty=float(config.bearish_weak_penalty),
        bullish_strong_bonus_cap=float(config.bullish_strong_bonus_cap),
        min_n_analysts=config.min_n_analysts,
        min_decay_weight=float(config.min_decay_weight),
        consensus_bearish_threshold=float(config.consensus_bearish_threshold),
        consensus_bullish_threshold=float(config.consensus_bullish_threshold),
        created_at=config.created_at,
        created_by=config.created_by,
        notes=config.notes,
    )
