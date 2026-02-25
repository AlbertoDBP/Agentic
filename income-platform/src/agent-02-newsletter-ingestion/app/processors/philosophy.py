"""
Agent 02 — Newsletter Ingestion Service
Processor: Analyst philosophy synthesis

Two synthesis modes (locked in architecture session):
  - LLM summary   (article_count <  20): Claude Sonnet → philosophy_summary
                    philosophy_source = 'llm'
  - K-Means       (article_count >= 20): K=5 on content_embedding centroids
                    philosophy_source = 'kmeans'
                    philosophy_vector = centroid of analyst's embeddings
                    philosophy_tags   = {style, sectors, asset_classes, themes}

The philosophy_vector (centroid) allows Agent 12 to compute analyst
similarity via cosine distance for portfolio diversification.

philosophy_tags JSONB schema:
  {
    "style": "dividend-growth | high-yield | value | sector-specialist",
    "sectors": ["REIT", "MLP"],
    "asset_classes": ["CommonStock", "BDC"],
    "themes": ["covered-calls", "income-growth"]
  }
"""
import json
import logging
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models.models import Analyst, AnalystArticle
from app.config import settings

logger = logging.getLogger(__name__)

# Module-level Anthropic client — patched in tests
try:
    from anthropic import Anthropic as _Anthropic
    _client = _Anthropic(api_key=settings.anthropic_api_key)
except Exception:
    _client = None

_PHILOSOPHY_PROMPT = """You are an investment analyst profiler for an income investment platform.

Based on the article titles and themes below, synthesize this analyst's investment philosophy.

Return ONLY valid JSON (no markdown fences):
{{
  "summary": "2-3 sentence description of the analyst's income investment philosophy and style.",
  "style": "dividend-growth|high-yield|value|sector-specialist",
  "sectors": ["REIT", "MLP"],
  "asset_classes": ["CommonStock", "BDC"],
  "themes": ["covered-calls", "income-growth"]
}}

Keep summary concise (under 100 words). Only include sectors/asset_classes/themes you are confident about.
Use null for style if unclear.

ANALYST ARTICLES:
{articles_text}"""


def _build_articles_text(articles: list[AnalystArticle], max_articles: int = 15) -> str:
    """
    Build a text summary of recent articles for the LLM prompt.
    Uses title + tickers_mentioned for each article.
    """
    recent = sorted(articles, key=lambda a: a.published_at, reverse=True)[:max_articles]
    lines = []
    for a in recent:
        tickers = ", ".join(a.tickers_mentioned or [])
        ticker_note = f" [tickers: {tickers}]" if tickers else ""
        lines.append(f"- {a.title}{ticker_note}")
    return "\n".join(lines) if lines else "(no articles)"


def synthesize_philosophy_llm(
    analyst: Analyst,
    articles: list[AnalystArticle],
) -> dict:
    """
    Generate philosophy summary via Claude Sonnet for analysts with < 20 articles.

    Updates analyst fields:
      philosophy_summary, philosophy_source, philosophy_tags

    Returns dict with updated fields (db commit is caller's responsibility).
    """
    if not _client:
        logger.error("Anthropic client not initialized — cannot synthesize philosophy")
        return {}

    articles_text = _build_articles_text(articles)
    prompt = _PHILOSOPHY_PROMPT.format(articles_text=articles_text)

    try:
        response = _client.messages.create(
            model=settings.philosophy_model,
            max_tokens=settings.philosophy_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()

        # Strip markdown fences if the model wraps with them
        import re
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        parsed = json.loads(raw_text)

    except json.JSONDecodeError as e:
        logger.warning(f"Analyst {analyst.id} LLM philosophy: invalid JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Analyst {analyst.id} LLM philosophy error: {e}")
        return {}

    summary = parsed.get("summary", "")
    tags = {
        "style": parsed.get("style"),
        "sectors": parsed.get("sectors", []),
        "asset_classes": parsed.get("asset_classes", []),
        "themes": parsed.get("themes", []),
    }

    analyst.philosophy_summary = summary
    analyst.philosophy_source = "llm"
    analyst.philosophy_tags = tags

    logger.info(
        f"Analyst {analyst.id} ({analyst.display_name}): "
        f"LLM philosophy synthesized. style={tags.get('style')}"
    )
    return {"philosophy_summary": summary, "philosophy_source": "llm", "philosophy_tags": tags}


def synthesize_philosophy_kmeans(
    analyst: Analyst,
    articles: list[AnalystArticle],
    k: int = None,
) -> dict:
    """
    Cluster analyst article embeddings with K-Means (K=5 default).
    Updates analyst fields:
      philosophy_vector (centroid), philosophy_source, philosophy_tags, philosophy_cluster

    Returns dict with updated fields (db commit is caller's responsibility).
    """
    from sklearn.cluster import KMeans

    k = k or settings.default_kmeans_k

    # Gather articles that have content embeddings
    embeddable = [
        a for a in articles
        if a.content_embedding is not None
    ]

    if len(embeddable) < k:
        logger.warning(
            f"Analyst {analyst.id}: only {len(embeddable)} embedded articles "
            f"(need ≥ {k} for K-Means). Falling back to global centroid."
        )
        # Fall back: compute global centroid without clustering
        all_vectors = np.array([
            list(a.content_embedding) for a in embeddable
        ], dtype=np.float32)
        centroid = all_vectors.mean(axis=0).tolist()
        analyst.philosophy_vector = centroid
        analyst.philosophy_source = "kmeans"
        analyst.philosophy_cluster = 0
        return {
            "philosophy_source": "kmeans",
            "philosophy_cluster": 0,
            "philosophy_vector_dim": len(centroid),
        }

    vectors = np.array([
        list(a.content_embedding) for a in embeddable
    ], dtype=np.float32)

    try:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = kmeans.fit_predict(vectors)
    except Exception as e:
        logger.error(f"Analyst {analyst.id} K-Means error: {e}")
        return {}

    # Find dominant cluster (most articles)
    cluster_counts = {}
    for label in labels:
        cluster_counts[int(label)] = cluster_counts.get(int(label), 0) + 1
    dominant_cluster = max(cluster_counts, key=cluster_counts.get)

    # Centroid of the dominant cluster
    centroid = kmeans.cluster_centers_[dominant_cluster].tolist()

    # Extract representative tickers/sectors from dominant cluster articles
    dominant_articles = [
        embeddable[i] for i, lbl in enumerate(labels) if lbl == dominant_cluster
    ]
    sectors_seen: dict[str, int] = {}
    asset_classes_seen: dict[str, int] = {}

    for a in dominant_articles:
        tickers = a.tickers_mentioned or []
        for t in tickers:
            # tickers_mentioned is ticker symbols — use as proxy for sectors
            pass

    # Build philosophy_tags from tickers_mentioned across all dominant articles
    all_tickers_flat = []
    for a in dominant_articles:
        all_tickers_flat.extend(a.tickers_mentioned or [])

    # Top tickers by frequency (proxy for analyst focus)
    ticker_freq: dict[str, int] = {}
    for t in all_tickers_flat:
        ticker_freq[t] = ticker_freq.get(t, 0) + 1
    top_tickers = sorted(ticker_freq, key=ticker_freq.get, reverse=True)[:10]

    tags = {
        "style": None,  # K-Means mode does not generate LLM-derived style label
        "sectors": [],
        "asset_classes": [],
        "themes": [],
        "top_tickers": top_tickers,
        "cluster_count": k,
        "dominant_cluster": dominant_cluster,
        "dominant_cluster_size": cluster_counts[dominant_cluster],
    }

    analyst.philosophy_vector = centroid
    analyst.philosophy_source = "kmeans"
    analyst.philosophy_cluster = dominant_cluster
    analyst.philosophy_tags = tags

    logger.info(
        f"Analyst {analyst.id} ({analyst.display_name}): "
        f"K-Means philosophy complete. "
        f"dominant_cluster={dominant_cluster} "
        f"({cluster_counts[dominant_cluster]}/{len(embeddable)} articles)"
    )
    return {
        "philosophy_source": "kmeans",
        "philosophy_cluster": dominant_cluster,
        "philosophy_vector_dim": len(centroid),
        "philosophy_tags": tags,
    }


def update_analyst_philosophy(
    db: Session,
    analyst_id: int,
) -> dict:
    """
    Synthesize philosophy for one analyst. Chooses mode based on article_count.

    Dispatches to:
      - synthesize_philosophy_llm()   if article_count <  20
      - synthesize_philosophy_kmeans() if article_count >= 20

    Returns summary dict.
    """
    analyst = db.query(Analyst).filter(Analyst.id == analyst_id).first()
    if not analyst:
        logger.warning(f"Analyst {analyst_id} not found")
        return {}

    articles = (
        db.query(AnalystArticle)
        .filter(AnalystArticle.analyst_id == analyst_id)
        .order_by(AnalystArticle.published_at.desc())
        .all()
    )

    # Use analyst.article_count for routing (maintained by harvester, always accurate)
    # Fall back to len(articles) if field is not set yet
    article_count = analyst.article_count if analyst.article_count else len(articles)
    threshold = settings.default_kmeans_min_articles

    logger.info(
        f"Analyst {analyst.id} ({analyst.display_name}): "
        f"{article_count} articles — "
        f"using {'K-Means' if article_count >= threshold else 'LLM'} synthesis"
    )

    if article_count >= threshold:
        return synthesize_philosophy_kmeans(analyst, articles)
    else:
        return synthesize_philosophy_llm(analyst, articles)
