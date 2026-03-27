"""
Agent 02 — Newsletter Ingestion Service
Processor: Analyst Suggestion Store

Writes BUY/SELL analyst recommendations to platform_shared.analyst_suggestions.
HOLD signals are excluded — no investment action implied.

Uniqueness: partial unique index on (analyst_id, ticker) WHERE is_active=TRUE.
Subsequent BUY/SELL on same ticker upserts (refreshes) the existing active row.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_BUY_LABELS = {"StrongBuy", "Buy", "STRONG_BUY", "BUY"}
_SELL_LABELS = {"StrongSell", "Sell", "STRONG_SELL", "SELL"}


def should_write_suggestion(recommendation: Optional[str]) -> bool:
    """True if this recommendation warrants a suggestion row (BUY or SELL only)."""
    if not recommendation:
        return False
    return recommendation in (_BUY_LABELS | _SELL_LABELS)


def _get_ttl_days(db: Session, asset_class: str) -> int:
    """Read TTL days for asset_class from DB. Falls back to _default row, then 45."""
    row = db.execute(text(
        "SELECT ttl_days FROM platform_shared.suggestion_ttl_config "
        "WHERE asset_class = :ac OR asset_class = '_default' "
        "ORDER BY CASE WHEN asset_class = :ac THEN 0 ELSE 1 END ASC LIMIT 1"
    ), {"ac": asset_class}).fetchone()
    return row.ttl_days if row else 45


def compute_expires_at(db: Session, sourced_at: datetime, asset_class: Optional[str]) -> datetime:
    """Return expiry timestamp based on configured TTL for asset class."""
    ttl_days = _get_ttl_days(db, asset_class or "")
    return sourced_at + timedelta(days=ttl_days)


def upsert_suggestion(
    db: Session,
    analyst_id: int,
    article_framework_id: int,
    ticker: str,
    asset_class: Optional[str],
    recommendation: str,
    sentiment_score: Optional[float],
    price_guidance_type: Optional[str],
    price_guidance_value: Optional[dict],
    sourced_at: datetime,
) -> None:
    """
    Upsert an analyst suggestion row.
    ON CONFLICT (analyst_id, ticker) WHERE is_active=TRUE:
      refresh staleness_weight, expires_at, framework_id, sentiment, price guidance.
    """
    expires_at = compute_expires_at(db, sourced_at, asset_class)

    db.execute(text("""
        INSERT INTO platform_shared.analyst_suggestions
            (analyst_id, article_framework_id, ticker, asset_class,
             recommendation, sentiment_score, price_guidance_type,
             price_guidance_value, staleness_weight, is_active,
             sourced_at, expires_at)
        VALUES
            (:analyst_id, :framework_id, :ticker, :asset_class,
             :recommendation, :sentiment_score, :price_guidance_type,
             CAST(:price_guidance_value AS JSONB), 1.0, TRUE,
             :sourced_at, :expires_at)
        ON CONFLICT ON CONSTRAINT uix_analyst_suggestions_active
        DO UPDATE SET
            article_framework_id = EXCLUDED.article_framework_id,
            recommendation       = EXCLUDED.recommendation,
            sentiment_score      = EXCLUDED.sentiment_score,
            price_guidance_type  = EXCLUDED.price_guidance_type,
            price_guidance_value = EXCLUDED.price_guidance_value,
            staleness_weight     = 1.0,
            sourced_at           = EXCLUDED.sourced_at,
            expires_at           = EXCLUDED.expires_at
    """), {
        "analyst_id": analyst_id,
        "framework_id": article_framework_id,
        "ticker": ticker,
        "asset_class": asset_class,
        "recommendation": recommendation,
        "sentiment_score": sentiment_score,
        "price_guidance_type": price_guidance_type,
        "price_guidance_value": json.dumps(price_guidance_value) if price_guidance_value else None,
        "sourced_at": sourced_at,
        "expires_at": expires_at,
    })
    logger.debug(f"Upserted suggestion: analyst={analyst_id} ticker={ticker} rec={recommendation}")
