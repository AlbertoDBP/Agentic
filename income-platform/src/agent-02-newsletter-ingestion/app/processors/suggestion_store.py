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

# Default TTL in days by asset class
_TTL_DAYS: dict[str, int] = {
    "BDC": 45,
    "MORTGAGE_REIT": 45,
    "PREFERRED_STOCK": 45,
    "DIVIDEND_STOCK": 60,
    "EQUITY_REIT": 60,
    "BOND": 30,
    "CEF": 30,
    "COVERED_CALL_ETF": 30,
}
_DEFAULT_TTL_DAYS = 45

_BUY_LABELS = {"StrongBuy", "Buy", "STRONG_BUY", "BUY"}
_SELL_LABELS = {"StrongSell", "Sell", "STRONG_SELL", "SELL"}


def should_write_suggestion(recommendation: Optional[str]) -> bool:
    """True if this recommendation warrants a suggestion row (BUY or SELL only)."""
    if not recommendation:
        return False
    return recommendation in (_BUY_LABELS | _SELL_LABELS)


def compute_expires_at(sourced_at: datetime, asset_class: Optional[str]) -> datetime:
    """Return expiry timestamp based on asset class TTL."""
    ttl_days = _TTL_DAYS.get(asset_class or "", _DEFAULT_TTL_DAYS)
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
    expires_at = compute_expires_at(sourced_at, asset_class)

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
