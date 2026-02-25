"""
Agent 02 — Newsletter Ingestion Service
Flow: Harvester Flow (Prefect)

Schedule: Tuesday + Friday 7AM ET (0 7 * * 2,5)
Can also be triggered manually via POST /flows/harvester/trigger

Pipeline per analyst:
  1. Fetch article list from APIDojo SA API
  2. Dedup against existing articles
  3. Fetch full article detail (HTML)
  4. Convert HTML → Markdown
  5. Extract signals via Claude Haiku
  6. Embed article body + recommendation thesis via OpenAI
  7. Persist article + recommendations to database
  8. Update analyst metadata

Flow-level error handling:
  - Per-analyst failures are caught and logged — one bad analyst
    does not abort the entire flow
  - Per-article failures are caught similarly
  - Flow run metadata written to flow_run_log table on completion
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from prefect import flow, task, get_run_logger
from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.models import Analyst
from app.clients import seeking_alpha as sa_client
from app.processors import deduplicator, extractor, vectorizer, article_store
from app.config import settings

logger = logging.getLogger(__name__)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@task(
    name="fetch-analyst-articles",
    retries=2,
    retry_delay_seconds=30,
    tags=["harvester", "api"],
)
def fetch_analyst_articles(
    sa_publishing_id: str,
    limit: int,
    until_article_id: Optional[str],
) -> list[dict]:
    """Fetch article list from APIDojo SA API for one analyst."""
    log = get_run_logger()
    articles = sa_client.fetch_articles_by_author(
        sa_author_id=sa_publishing_id,
        limit=limit,
        until_article_id=until_article_id,
    )
    log.info(f"Fetched {len(articles)} articles for {sa_publishing_id}")
    return articles


@task(
    name="fetch-article-detail",
    retries=2,
    retry_delay_seconds=15,
    tags=["harvester", "api"],
)
def fetch_article_detail(sa_article_id: str) -> Optional[dict]:
    """Fetch full article content from APIDojo SA API."""
    return sa_client.fetch_article_detail(sa_article_id)


@task(name="convert-and-extract", tags=["harvester", "llm"])
def convert_and_extract(
    html_body: str,
    sa_article_id: str,
) -> tuple[str, Optional[dict]]:
    """
    Convert HTML → Markdown, then extract signals via Claude Haiku.
    Returns (markdown_text, extraction_result).
    """
    log = get_run_logger()

    # Step 1: HTML → Markdown
    markdown = extractor.html_to_markdown(html_body)
    log.debug(f"Article {sa_article_id}: {len(html_body)} HTML chars → {len(markdown)} MD chars")

    # Step 2: Extract signals
    extracted = extractor.extract_signals(markdown, sa_article_id)
    ticker_count = len(extracted.get("tickers", [])) if extracted else 0
    log.info(f"Article {sa_article_id}: extracted {ticker_count} ticker signals")

    return markdown, extracted


@task(name="embed-article", tags=["harvester", "embedding"])
def embed_article_and_theses(
    markdown_body: str,
    extracted_tickers: list[dict],
) -> tuple[Optional[list[float]], list[Optional[list[float]]]]:
    """
    Generate embeddings for:
      - Article body (for semantic article search)
      - Each recommendation thesis (for thesis similarity)

    Returns (article_embedding, [thesis_embedding, ...])
    """
    # Article body embedding
    article_embedding = vectorizer.embed_text(markdown_body)

    # Thesis embeddings — build thesis text for each ticker then batch embed
    thesis_texts = [
        vectorizer.build_recommendation_thesis(t) for t in extracted_tickers
    ]
    thesis_embeddings = vectorizer.embed_batch(thesis_texts) if thesis_texts else []

    return article_embedding, thesis_embeddings


@task(name="persist-article", tags=["harvester", "db"])
def persist_article(
    analyst_id: int,
    sa_article_id: str,
    title: str,
    markdown_body: str,
    published_at: datetime,
    extracted: Optional[dict],
    article_embedding: Optional[list[float]],
    thesis_embeddings: list[Optional[list[float]]],
    aging_days: int,
) -> dict:
    """
    Persist article and all extracted recommendations to the database.
    Returns summary dict for flow reporting.
    """
    log = get_run_logger()

    with get_db_context() as db:
        # Extract tickers and validate
        raw_tickers = extracted.get("tickers", []) if extracted else []
        validated_tickers = [
            extractor.validate_extracted_ticker(t) for t in raw_tickers
        ]
        ticker_symbols = [t["ticker"] for t in validated_tickers if t.get("ticker")]

        # Save article
        article = article_store.save_article(
            db=db,
            analyst_id=analyst_id,
            sa_article_id=sa_article_id,
            title=title,
            markdown_body=markdown_body,
            published_at=published_at,
            tickers_mentioned=ticker_symbols,
            content_embedding=article_embedding,
            metadata={
                "word_count": len(markdown_body.split()),
                "article_themes": extracted.get("article_themes", []) if extracted else [],
                "overall_sentiment": extracted.get("overall_sentiment") if extracted else None,
            },
        )

        # Save recommendations
        saved_recs = article_store.save_recommendations_for_article(
            db=db,
            analyst_id=analyst_id,
            article=article,
            extracted_tickers=validated_tickers,
            thesis_embeddings=thesis_embeddings,
            aging_days=aging_days,
        )

        log.info(
            f"Persisted article {sa_article_id}: "
            f"{len(saved_recs)} recommendations saved"
        )

        return {
            "article_id": article.id,
            "sa_article_id": sa_article_id,
            "recs_saved": len(saved_recs),
            "tickers": ticker_symbols,
        }


# ── Main Flow ──────────────────────────────────────────────────────────────────

@flow(
    name="agent-02-harvester",
    description="Ingests SA analyst articles, extracts income signals, persists to DB",
    version="0.1.0",
)
def harvester_flow(analyst_ids: Optional[list[int]] = None):
    """
    Main Harvester Flow.

    Args:
        analyst_ids: specific analyst DB IDs to process.
                     If None, processes all active analysts.
    """
    log = get_run_logger()
    log.info("Harvester Flow started")

    flow_start = datetime.now(timezone.utc)
    total_articles = 0
    total_recs = 0
    analyst_results = []

    # Load active analysts
    with get_db_context() as db:
        query = db.query(Analyst).filter(Analyst.is_active == True)
        if analyst_ids:
            query = query.filter(Analyst.id.in_(analyst_ids))
        analysts = query.all()

        # Snapshot data we need before session closes
        analyst_data = [
            {
                "id": a.id,
                "sa_publishing_id": a.sa_publishing_id,
                "display_name": a.display_name,
                "config": a.config or {},
                "article_count": a.article_count or 0,
            }
            for a in analysts
        ]

    log.info(f"Processing {len(analyst_data)} active analysts")

    # ── Per-analyst processing ──────────────────────────────────────────────
    for analyst in analyst_data:
        analyst_id = analyst["id"]
        sa_id = analyst["sa_publishing_id"]
        config = analyst["config"]

        # Per-analyst config overrides (fall back to service defaults)
        fetch_limit = config.get("fetch_limit", settings.sa_fetch_limit_per_analyst)
        aging_days = config.get("aging_days", settings.default_aging_days)

        log.info(f"Processing analyst: {analyst['display_name']} (SA: {sa_id})")
        analyst_articles_added = 0
        analyst_recs_added = 0

        try:
            # Get last known article ID for this analyst (dedup boundary)
            with get_db_context() as db:
                last_article_id = deduplicator.get_last_fetched_article_id(db, analyst_id)

            # 1. Fetch article list
            raw_articles = fetch_analyst_articles(
                sa_publishing_id=sa_id,
                limit=fetch_limit,
                until_article_id=last_article_id,
            )

            if not raw_articles:
                log.info(f"No new articles for {sa_id}")
                continue

            # 2. Process each article
            for raw_article in raw_articles:
                article_sa_id = str(raw_article.get("id", ""))
                article_title = raw_article.get("title", "Untitled")

                # Quick SA-ID dedup before fetching full content
                with get_db_context() as db:
                    if deduplicator.is_duplicate_by_sa_id(db, article_sa_id):
                        log.debug(f"Skipping known article {article_sa_id}")
                        continue

                try:
                    # 3. Fetch full article detail (HTML)
                    detail = fetch_article_detail(article_sa_id)
                    if not detail:
                        log.warning(f"No detail returned for article {article_sa_id}")
                        continue

                    html_body = detail.get("content", "")
                    published_at = sa_client.parse_published_at(
                        raw_article.get("published_date", "")
                    )

                    if not html_body or not published_at:
                        log.warning(
                            f"Missing body or date for article {article_sa_id} — skipping"
                        )
                        continue

                    # Content hash dedup (now we have the body)
                    markdown_preview = extractor.html_to_markdown(html_body[:500])
                    with get_db_context() as db:
                        content_hash = deduplicator.compute_content_hash(markdown_preview)
                        if deduplicator.is_duplicate_by_content(db, content_hash):
                            log.debug(f"Skipping duplicate content for article {article_sa_id}")
                            continue

                    # 4+5. Convert HTML → Markdown + Extract signals
                    markdown, extracted = convert_and_extract(html_body, article_sa_id)

                    # 6. Embed article body + theses
                    raw_tickers = extracted.get("tickers", []) if extracted else []
                    article_embedding, thesis_embeddings = embed_article_and_theses(
                        markdown, raw_tickers
                    )

                    # 7. Persist to DB
                    result = persist_article(
                        analyst_id=analyst_id,
                        sa_article_id=article_sa_id,
                        title=article_title,
                        markdown_body=markdown,
                        published_at=published_at,
                        extracted=extracted,
                        article_embedding=article_embedding,
                        thesis_embeddings=thesis_embeddings,
                        aging_days=aging_days,
                    )

                    analyst_articles_added += 1
                    analyst_recs_added += result["recs_saved"]

                except Exception as e:
                    log.error(f"Error processing article {article_sa_id}: {e}")
                    continue  # next article — don't abort analyst

            # 8. Update analyst metadata
            if analyst_articles_added > 0:
                with get_db_context() as db:
                    article_store.update_analyst_after_fetch(
                        db, analyst_id, analyst_articles_added
                    )

            log.info(
                f"Analyst {analyst['display_name']}: "
                f"+{analyst_articles_added} articles, "
                f"+{analyst_recs_added} recommendations"
            )

        except Exception as e:
            log.error(f"Error processing analyst {sa_id}: {e}")
            continue  # next analyst — don't abort flow

        total_articles += analyst_articles_added
        total_recs += analyst_recs_added
        analyst_results.append({
            "analyst_id": analyst_id,
            "display_name": analyst["display_name"],
            "articles_added": analyst_articles_added,
            "recs_added": analyst_recs_added,
        })

    # ── Write flow run log ────────────────────────────────────────────────────
    flow_end = datetime.now(timezone.utc)
    duration_seconds = (flow_end - flow_start).total_seconds()

    try:
        from sqlalchemy import text
        with get_db_context() as db:
            db.execute(text("""
                INSERT INTO platform_shared.flow_run_log
                    (flow_name, last_run_at, last_run_status, articles_processed,
                     duration_seconds, metadata)
                VALUES
                    (:name, :ran_at, :status, :articles, :duration, CAST(:meta AS JSONB))
                ON CONFLICT (flow_name) DO UPDATE SET
                    last_run_at = EXCLUDED.last_run_at,
                    last_run_status = EXCLUDED.last_run_status,
                    articles_processed = EXCLUDED.articles_processed,
                    duration_seconds = EXCLUDED.duration_seconds,
                    metadata = EXCLUDED.metadata
            """), {
                "name": "harvester_flow",
                "ran_at": flow_end,
                "status": "success",
                "articles": total_articles,
                "duration": duration_seconds,
                "meta": json.dumps({"analysts": analyst_results}),
            })
    except Exception as e:
        log.warning(f"Could not write flow_run_log (table may not exist yet): {e}")

    log.info(
        f"Harvester Flow complete: "
        f"{total_articles} articles + {total_recs} recommendations | "
        f"{duration_seconds:.1f}s"
    )

    return {
        "total_articles": total_articles,
        "total_recommendations": total_recs,
        "analysts_processed": len(analyst_results),
        "duration_seconds": duration_seconds,
    }
