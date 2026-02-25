"""
Agent 02 — Newsletter Ingestion Service
Processor: Database persistence for articles and recommendations

Handles:
  - Saving AnalystArticle records with content hash
  - Saving AnalystRecommendation records with supersession logic
  - Updating analyst metadata after a successful fetch
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.models.models import AnalystArticle, AnalystRecommendation, Analyst
from app.processors.deduplicator import compute_content_hash, compute_url_hash

logger = logging.getLogger(__name__)


def save_article(
    db,
    analyst_id: int,
    sa_article_id: str,
    title: str,
    markdown_body: str,
    published_at: datetime,
    tickers_mentioned: list[str] = None,
    content_embedding=None,
    metadata: dict = None,
) -> AnalystArticle:
    """
    Persist a new article to the database.
    Computes content_hash and url_hash automatically.
    Calls db.add() + db.flush() — caller owns the transaction.
    """
    url = f"https://seekingalpha.com/article/{sa_article_id}"

    article = AnalystArticle(
        analyst_id=analyst_id,
        sa_article_id=sa_article_id,
        url_hash=compute_url_hash(url),
        content_hash=compute_content_hash(markdown_body),
        title=title,
        full_text=markdown_body,
        published_at=published_at,
        tickers_mentioned=tickers_mentioned or [],
        content_embedding=content_embedding,
        article_metadata=metadata,
    )
    db.add(article)
    db.flush()
    return article


def save_recommendation(
    db,
    analyst_id: int,
    article_id: int,
    ticker: str,
    published_at: datetime,
    extracted: dict,
    aging_days: int = 365,
    content_embedding=None,
) -> AnalystRecommendation:
    """
    Persist a single recommendation.

    Supersession model:
      - Query for existing active recs for this analyst+ticker
      - Create new rec with is_active=True, decay_weight=1.0
      - Mark prior recs superseded_by=new_id, is_active=False
    """
    expires_at = published_at + timedelta(days=aging_days)

    # Find prior active recommendations for this analyst+ticker
    prior_recs = (
        db.query(AnalystRecommendation)
        .filter(
            AnalystRecommendation.analyst_id == analyst_id,
            AnalystRecommendation.ticker == ticker,
            AnalystRecommendation.is_active == True,
        )
        .all()
    )

    rec = AnalystRecommendation(
        analyst_id=analyst_id,
        article_id=article_id,
        ticker=ticker,
        sector=extracted.get("sector"),
        asset_class=extracted.get("asset_class"),
        recommendation=extracted.get("recommendation"),
        sentiment_score=extracted.get("sentiment_score"),
        yield_at_publish=extracted.get("yield_at_publish"),
        payout_ratio=extracted.get("payout_ratio"),
        dividend_cagr_3yr=extracted.get("dividend_cagr_3yr"),
        dividend_cagr_5yr=extracted.get("dividend_cagr_5yr"),
        safety_grade=extracted.get("safety_grade"),
        source_reliability=extracted.get("source_reliability"),
        content_embedding=content_embedding,
        rec_metadata={
            "bull_case": extracted.get("bull_case"),
            "bear_case": extracted.get("bear_case"),
            "key_risks": extracted.get("key_risks") or [],
        },
        published_at=published_at,
        expires_at=expires_at,
        decay_weight=1.0,
        is_active=True,
    )
    db.add(rec)
    db.flush()

    # Supersede prior active recs
    for prior in prior_recs:
        prior.is_active = False
        prior.superseded_by = rec.id

    return rec


def save_recommendations_for_article(
    db,
    analyst_id: int,
    article,
    extracted_tickers: list[dict],
    thesis_embeddings: list,
    aging_days: int = 365,
) -> list:
    """
    Persist all recommendations extracted from a single article.
    Returns list of saved AnalystRecommendation objects.
    """
    saved = []
    for i, ticker_data in enumerate(extracted_tickers):
        ticker = ticker_data.get("ticker")
        if not ticker:
            continue
        embedding = thesis_embeddings[i] if i < len(thesis_embeddings) else None
        rec = save_recommendation(
            db=db,
            analyst_id=analyst_id,
            article_id=article.id,
            ticker=ticker,
            published_at=article.published_at,
            extracted=ticker_data,
            aging_days=aging_days,
            content_embedding=embedding,
        )
        saved.append(rec)
    return saved


def update_analyst_after_fetch(db, analyst_id: int, articles_added: int) -> None:
    """Increment article_count and refresh last_article_fetched_at for an analyst."""
    analyst = db.query(Analyst).filter(Analyst.id == analyst_id).first()
    if analyst:
        analyst.article_count = (analyst.article_count or 0) + articles_added
        analyst.last_article_fetched_at = datetime.now(timezone.utc)
