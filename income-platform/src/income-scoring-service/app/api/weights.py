"""
Agent 03 — Income Scoring Service
API: Weight Profile endpoints (v2.0).

Endpoints:
  GET  /weights/              — list all active class-specific weight profiles
  GET  /weights/{asset_class} — get the active profile for one asset class
  POST /weights/{asset_class} — create a new profile version (admin)
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ScoringWeightProfile, WeightChangeAudit
from app.scoring.weight_profile_loader import weight_profile_loader

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Known asset classes ───────────────────────────────────────────────────────

VALID_ASSET_CLASSES = {
    "EQUITY_REIT", "MORTGAGE_REIT", "BDC", "COVERED_CALL_ETF",
    "DIVIDEND_STOCK", "BOND", "PREFERRED_STOCK",
}


# ── Pydantic models ───────────────────────────────────────────────────────────

class YieldSubWeights(BaseModel):
    payout_sustainability: int
    yield_vs_market: int
    fcf_coverage: int

    @model_validator(mode="after")
    def check_sum(self):
        total = self.payout_sustainability + self.yield_vs_market + self.fcf_coverage
        if total != 100:
            raise ValueError(f"yield_sub_weights must sum to 100, got {total}")
        return self


class DurabilitySubWeights(BaseModel):
    debt_safety: int
    dividend_consistency: int
    volatility_score: int

    @model_validator(mode="after")
    def check_sum(self):
        total = self.debt_safety + self.dividend_consistency + self.volatility_score
        if total != 100:
            raise ValueError(f"durability_sub_weights must sum to 100, got {total}")
        return self


class TechnicalSubWeights(BaseModel):
    price_momentum: int
    price_range_position: int

    @model_validator(mode="after")
    def check_sum(self):
        total = self.price_momentum + self.price_range_position
        if total != 100:
            raise ValueError(f"technical_sub_weights must sum to 100, got {total}")
        return self


class WeightProfileRequest(BaseModel):
    weight_yield: int
    weight_durability: int
    weight_technical: int
    yield_sub_weights: YieldSubWeights
    durability_sub_weights: DurabilitySubWeights
    technical_sub_weights: TechnicalSubWeights
    change_reason: Optional[str] = None
    created_by: Optional[str] = None
    benchmark_ticker: Optional[str] = None

    @model_validator(mode="after")
    def check_pillar_sum(self):
        total = self.weight_yield + self.weight_durability + self.weight_technical
        if total != 100:
            raise ValueError(
                f"Pillar weights must sum to 100, got {total} "
                f"(yield={self.weight_yield}, durability={self.weight_durability}, "
                f"technical={self.weight_technical})"
            )
        for w in (self.weight_yield, self.weight_durability, self.weight_technical):
            if not (1 <= w <= 98):
                raise ValueError("Each pillar weight must be between 1 and 98")
        return self


class WeightProfileResponse(BaseModel):
    id: str
    asset_class: str
    version: int
    is_active: bool
    source: str
    weight_yield: int
    weight_durability: int
    weight_technical: int
    yield_sub_weights: dict
    durability_sub_weights: dict
    technical_sub_weights: dict
    benchmark_ticker: Optional[str] = None
    change_reason: Optional[str]
    created_by: Optional[str]
    created_at: Optional[datetime]
    activated_at: Optional[datetime]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _orm_to_response(profile: ScoringWeightProfile) -> WeightProfileResponse:
    return WeightProfileResponse(
        id=str(profile.id),
        asset_class=profile.asset_class,
        version=profile.version,
        is_active=profile.is_active,
        source=profile.source,
        weight_yield=profile.weight_yield,
        weight_durability=profile.weight_durability,
        weight_technical=profile.weight_technical,
        yield_sub_weights=profile.yield_sub_weights or {},
        durability_sub_weights=profile.durability_sub_weights or {},
        technical_sub_weights=profile.technical_sub_weights or {},
        benchmark_ticker=profile.benchmark_ticker,
        change_reason=profile.change_reason,
        created_by=profile.created_by,
        created_at=profile.created_at,
        activated_at=profile.activated_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[WeightProfileResponse])
def list_weight_profiles(db: Session = Depends(get_db)):
    """Return all active class-specific weight profiles."""
    profiles = (
        db.query(ScoringWeightProfile)
        .filter(ScoringWeightProfile.is_active.is_(True))
        .order_by(ScoringWeightProfile.asset_class)
        .all()
    )
    return [_orm_to_response(p) for p in profiles]


@router.get("/{asset_class}", response_model=WeightProfileResponse)
def get_weight_profile(asset_class: str, db: Session = Depends(get_db)):
    """Return the active weight profile for the given asset class."""
    ac = asset_class.upper()
    profile = (
        db.query(ScoringWeightProfile)
        .filter(
            ScoringWeightProfile.asset_class == ac,
            ScoringWeightProfile.is_active.is_(True),
        )
        .first()
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active weight profile for asset class '{ac}'. "
                   f"Valid classes: {sorted(VALID_ASSET_CLASSES)}",
        )
    return _orm_to_response(profile)


@router.post("/{asset_class}", response_model=WeightProfileResponse, status_code=201)
def create_weight_profile(
    asset_class: str,
    req: WeightProfileRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new weight profile version for the given asset class.

    The current active profile is superseded atomically. Cache is invalidated
    so the next scoring request picks up the new weights immediately.
    """
    ac = asset_class.upper()
    if ac not in VALID_ASSET_CLASSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown asset class '{ac}'. Valid: {sorted(VALID_ASSET_CLASSES)}",
        )

    now = datetime.now(timezone.utc)

    # Find current active profile (may be None for a new class)
    old_profile = (
        db.query(ScoringWeightProfile)
        .filter(
            ScoringWeightProfile.asset_class == ac,
            ScoringWeightProfile.is_active.is_(True),
        )
        .first()
    )
    next_version = (old_profile.version + 1) if old_profile else 1

    try:
        # Create the new profile
        new_profile = ScoringWeightProfile(
            asset_class=ac,
            version=next_version,
            is_active=True,
            weight_yield=req.weight_yield,
            weight_durability=req.weight_durability,
            weight_technical=req.weight_technical,
            yield_sub_weights=req.yield_sub_weights.model_dump(),
            durability_sub_weights=req.durability_sub_weights.model_dump(),
            technical_sub_weights=req.technical_sub_weights.model_dump(),
            benchmark_ticker=req.benchmark_ticker,
            source="MANUAL",
            change_reason=req.change_reason,
            created_by=req.created_by,
            created_at=now,
            activated_at=now,
        )
        db.add(new_profile)
        db.flush()  # get new_profile.id before updating old

        # Supersede the old profile
        if old_profile is not None:
            old_profile.is_active = False
            old_profile.superseded_at = now
            old_profile.superseded_by_id = new_profile.id

        # Write audit row
        audit = WeightChangeAudit(
            asset_class=ac,
            old_profile_id=old_profile.id if old_profile else None,
            new_profile_id=new_profile.id,
            delta_weight_yield=(
                req.weight_yield - old_profile.weight_yield if old_profile else None
            ),
            delta_weight_durability=(
                req.weight_durability - old_profile.weight_durability if old_profile else None
            ),
            delta_weight_technical=(
                req.weight_technical - old_profile.weight_technical if old_profile else None
            ),
            trigger_type="MANUAL",
            trigger_details={"change_reason": req.change_reason, "created_by": req.created_by},
            changed_at=now,
            changed_by=req.created_by,
        )
        db.add(audit)
        db.commit()
        db.refresh(new_profile)

        # Invalidate loader cache so next score picks up new weights
        weight_profile_loader.invalidate(ac)
        logger.info(
            "New weight profile for %s: v%d (Y=%d/D=%d/T=%d) — old v%s superseded",
            ac, next_version, req.weight_yield, req.weight_durability, req.weight_technical,
            old_profile.version if old_profile else "none",
        )
        return _orm_to_response(new_profile)

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Failed to create weight profile for %s: %s", ac, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create weight profile: {exc}",
        )
