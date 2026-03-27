"""
Agent 02 — Newsletter Ingestion Service
API: Analyst endpoints

GET  /analysts                      List all active analysts
POST /analysts                      Add new analyst by SA author ID
GET  /analysts/{id}                 Single analyst profile + accuracy stats
GET  /analysts/{id}/recommendations All active recommendations by analyst
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.models import Analyst, AnalystRecommendation
from app.models.schemas import (
    AnalystCreate, AnalystUpdate, AnalystResponse, AnalystListResponse,
    RecommendationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=AnalystListResponse, tags=["Analysts"])
def list_analysts(
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """
    List all analysts in the registry.
    Filter by active_only=false to include deactivated analysts.
    """
    query = db.query(Analyst)
    if active_only:
        query = query.filter(Analyst.is_active == True)
    analysts = query.order_by(Analyst.display_name).all()
    return AnalystListResponse(analysts=analysts, total=len(analysts))


@router.post("", response_model=AnalystResponse, status_code=201, tags=["Analysts"])
def add_analyst(
    payload: AnalystCreate,
    db: Session = Depends(get_db),
):
    """
    Add a new analyst by SA author ID.
    Returns 409 if analyst already exists.
    """
    existing = (
        db.query(Analyst)
        .filter(Analyst.sa_publishing_id == payload.sa_publishing_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Analyst with SA ID {payload.sa_publishing_id} already exists (id={existing.id})"
        )

    analyst = Analyst(
        sa_publishing_id=payload.sa_publishing_id,
        display_name=payload.display_name,
        is_active=True,
        config=payload.config,
    )
    db.add(analyst)
    db.commit()
    db.refresh(analyst)

    logger.info(f"Added analyst: {analyst.display_name} (SA ID: {analyst.sa_publishing_id})")
    return analyst


@router.get("/lookup", tags=["Analysts"])
def lookup_analyst_name(sa_id: str):
    """
    Look up the SA display name for a given SA publishing ID.
    Makes a live API call to Seeking Alpha. Returns null display_name on failure.
    """
    from app.clients import seeking_alpha as sa_client
    name = sa_client.fetch_author_name(sa_id)
    return {"sa_id": sa_id, "display_name": name}


@router.put("/{analyst_id}", response_model=AnalystResponse, tags=["Analysts"])
def update_analyst(
    analyst_id: int,
    payload: AnalystUpdate,
    db: Session = Depends(get_db),
):
    """Update analyst display_name, sa_publishing_id, and/or is_active status."""
    analyst = db.query(Analyst).filter(Analyst.id == analyst_id).first()
    if not analyst:
        raise HTTPException(status_code=404, detail=f"Analyst {analyst_id} not found")

    if payload.display_name is not None:
        analyst.display_name = payload.display_name
    if payload.sa_publishing_id is not None:
        conflict = (
            db.query(Analyst)
            .filter(Analyst.sa_publishing_id == payload.sa_publishing_id,
                    Analyst.id != analyst_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"SA ID {payload.sa_publishing_id} already used by analyst {conflict.id}"
            )
        analyst.sa_publishing_id = payload.sa_publishing_id
    if payload.is_active is not None:
        analyst.is_active = payload.is_active

    analyst.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(analyst)
    logger.info(f"Updated analyst {analyst_id}: {analyst.display_name}")
    return analyst


@router.get("/{analyst_id}", response_model=AnalystResponse, tags=["Analysts"])
def get_analyst(
    analyst_id: int,
    db: Session = Depends(get_db),
):
    """Get single analyst profile with accuracy stats and philosophy summary."""
    analyst = db.query(Analyst).filter(Analyst.id == analyst_id).first()
    if not analyst:
        raise HTTPException(status_code=404, detail=f"Analyst {analyst_id} not found")
    return analyst


@router.get("/{analyst_id}/recommendations", tags=["Analysts"])
def get_analyst_recommendations(
    analyst_id: int,
    active_only: bool = True,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Get all recommendations by a specific analyst.
    Ordered by published_at descending (most recent first).
    """
    analyst = db.query(Analyst).filter(Analyst.id == analyst_id).first()
    if not analyst:
        raise HTTPException(status_code=404, detail=f"Analyst {analyst_id} not found")

    query = (
        db.query(AnalystRecommendation)
        .filter(AnalystRecommendation.analyst_id == analyst_id)
    )
    if active_only:
        query = query.filter(AnalystRecommendation.is_active == True)

    recs = query.order_by(desc(AnalystRecommendation.published_at)).limit(limit).all()

    return {
        "analyst_id": analyst_id,
        "analyst_name": analyst.display_name,
        "total": len(recs),
        "recommendations": [RecommendationResponse.model_validate(r) for r in recs],
    }


@router.patch("/{analyst_id}/deactivate", tags=["Analysts"])
def deactivate_analyst(
    analyst_id: int,
    db: Session = Depends(get_db),
):
    """Deactivate an analyst — stops future harvesting for this analyst."""
    analyst = db.query(Analyst).filter(Analyst.id == analyst_id).first()
    if not analyst:
        raise HTTPException(status_code=404, detail=f"Analyst {analyst_id} not found")

    analyst.is_active = False
    analyst.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(f"Deactivated analyst {analyst_id}: {analyst.display_name}")
    return {"analyst_id": analyst_id, "is_active": False, "message": "Analyst deactivated"}
