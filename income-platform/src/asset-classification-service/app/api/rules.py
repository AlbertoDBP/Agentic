"""Agent 04 — Rules and Overrides API Router"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AssetClassRule, ClassificationOverride

logger = logging.getLogger(__name__)
router = APIRouter()


class RuleCreate(BaseModel):
    asset_class: str
    rule_type: str      # ticker_pattern | sector | feature | metadata
    rule_config: dict
    priority: int = 100
    confidence_weight: float = 0.80


class OverrideCreate(BaseModel):
    asset_class: str
    reason: Optional[str] = None
    created_by: Optional[str] = None


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    """List all active classification rules."""
    rules = db.query(AssetClassRule).filter(AssetClassRule.active == True).order_by(
        AssetClassRule.priority
    ).all()
    return {
        "total": len(rules),
        "rules": [
            {
                "id": str(r.id),
                "asset_class": r.asset_class,
                "rule_type": r.rule_type,
                "rule_config": r.rule_config,
                "priority": r.priority,
                "confidence_weight": r.confidence_weight,
                "active": r.active,
                "created_at": r.created_at.isoformat(),
            }
            for r in rules
        ],
    }


@router.post("/rules")
def create_rule(rule: RuleCreate, db: Session = Depends(get_db)):
    """Add a new classification rule. Takes effect immediately — no redeploy needed."""
    valid_types = {"ticker_pattern", "sector", "feature", "metadata"}
    if rule.rule_type not in valid_types:
        raise HTTPException(status_code=422, detail=f"rule_type must be one of {valid_types}")
    if not 0 < rule.confidence_weight <= 1.0:
        raise HTTPException(status_code=422, detail="confidence_weight must be between 0 and 1")

    db_rule = AssetClassRule(
        asset_class=rule.asset_class.upper(),
        rule_type=rule.rule_type,
        rule_config=rule.rule_config,
        priority=rule.priority,
        confidence_weight=rule.confidence_weight,
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    logger.info(f"New rule added: {rule.asset_class} / {rule.rule_type}")
    return {"id": str(db_rule.id), "message": "Rule created successfully"}


@router.put("/overrides/{ticker}")
def set_override(ticker: str, override: OverrideCreate, db: Session = Depends(get_db)):
    """
    Set manual override for a ticker. confidence=1.0, bypasses all rules.
    Existing override for ticker is replaced.
    """
    ticker = ticker.upper().strip()
    existing = db.query(ClassificationOverride).filter(
        ClassificationOverride.ticker == ticker
    ).first()

    if existing:
        existing.asset_class = override.asset_class.upper()
        existing.reason = override.reason
        existing.created_by = override.created_by
        existing.effective_until = None
        db.commit()
        logger.info(f"Override updated: {ticker} → {override.asset_class}")
        return {"ticker": ticker, "message": "Override updated"}
    else:
        record = ClassificationOverride(
            ticker=ticker,
            asset_class=override.asset_class.upper(),
            reason=override.reason,
            created_by=override.created_by,
        )
        db.add(record)
        db.commit()
        logger.info(f"Override created: {ticker} → {override.asset_class}")
        return {"ticker": ticker, "message": "Override created"}


@router.delete("/overrides/{ticker}")
def remove_override(ticker: str, db: Session = Depends(get_db)):
    """Remove manual override. Ticker will be re-classified by rules on next request."""
    ticker = ticker.upper().strip()
    existing = db.query(ClassificationOverride).filter(
        ClassificationOverride.ticker == ticker
    ).first()
    if not existing:
        raise HTTPException(status_code=404, detail=f"No override found for {ticker}")
    db.delete(existing)
    db.commit()
    logger.info(f"Override removed: {ticker}")
    return {"ticker": ticker, "message": "Override removed"}
