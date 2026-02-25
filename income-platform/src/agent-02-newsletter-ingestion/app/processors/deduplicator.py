"""
Agent 02 — Newsletter Ingestion Service
Processor: Deduplication helpers

Provides SHA-256 hashing and DB-backed duplicate checks used by the
Harvester Flow to avoid re-ingesting articles already in the database.
"""
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def compute_content_hash(text: str) -> str:
    """SHA-256 of article body — dedup by content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_url_hash(url: str) -> str:
    """SHA-256 of article URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def is_duplicate_by_sa_id(db, sa_article_id: str) -> bool:
    """Return True if an article with this SA ID already exists."""
    from app.models.models import AnalystArticle
    result = (
        db.query(AnalystArticle.id)
        .filter(AnalystArticle.sa_article_id == sa_article_id)
        .first()
    )
    return result is not None


def is_duplicate_by_content(db, content_hash: str) -> bool:
    """Return True if an article with this content hash already exists."""
    from app.models.models import AnalystArticle
    result = (
        db.query(AnalystArticle.id)
        .filter(AnalystArticle.content_hash == content_hash)
        .first()
    )
    return result is not None


def get_last_fetched_article_id(db, analyst_id: int) -> Optional[str]:
    """
    Return the SA article ID of the most recently published article
    for this analyst. Used as the dedup boundary for incremental fetches.
    """
    from app.models.models import AnalystArticle
    result = (
        db.query(AnalystArticle.sa_article_id)
        .filter(AnalystArticle.analyst_id == analyst_id)
        .order_by(AnalystArticle.published_at.desc())
        .first()
    )
    return result[0] if result else None


def filter_new_articles(
    db,
    analyst_id: int,
    raw_articles: list[dict],
    content_bodies: dict = None,
) -> list[dict]:
    """
    Filter a list of raw SA article dicts, returning only those not
    already present in the database (checked by SA article ID).
    """
    new_articles = []
    for article in raw_articles:
        sa_id = str(article.get("id", ""))
        if not is_duplicate_by_sa_id(db, sa_id):
            new_articles.append(article)
    return new_articles
