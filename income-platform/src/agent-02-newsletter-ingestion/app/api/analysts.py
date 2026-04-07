"""
Agent 02 — Newsletter Ingestion Service
API: Analyst endpoints

GET  /analysts                      List all active analysts
POST /analysts                      Add new analyst by SA author ID
GET  /analysts/{id}                 Single analyst profile + accuracy stats
GET  /analysts/{id}/recommendations All active recommendations by analyst
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, text

from app.database import get_db
from app.models.models import Analyst, AnalystArticle, AnalystRecommendation
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


@router.get("/articles", tags=["Articles"])
def list_articles(
    analyst_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT
            a.id,
            a.sa_article_id,
            a.analyst_id,
            an.display_name    AS analyst_name,
            a.title,
            a.published_at,
            COALESCE(LENGTH(a.full_text), 0) AS char_count,
            COUNT(DISTINCT r.id)             AS recommendation_count,
            COUNT(DISTINCT f.id)             AS framework_count
        FROM platform_shared.analyst_articles a
        JOIN platform_shared.analysts an ON an.id = a.analyst_id
        LEFT JOIN platform_shared.analyst_recommendations r ON r.article_id = a.id
        LEFT JOIN platform_shared.article_frameworks f ON f.article_id = a.id
        WHERE (:analyst_id IS NULL OR a.analyst_id = :analyst_id)
        GROUP BY a.id, an.display_name
        ORDER BY a.published_at DESC
        LIMIT :limit
    """), {"analyst_id": analyst_id, "limit": limit}).fetchall()

    results = []
    for row in rows:
        article_id = row.id
        rec_count = row.recommendation_count
        fw_count = row.framework_count

        ticker_rows = db.execute(text("""
            SELECT
                r.ticker,
                r.recommendation,
                r.sentiment_score,
                r.asset_class,
                f.conviction_level,
                f.price_guidance_type,
                f.evaluation_narrative,
                f.valuation_metrics_cited
            FROM platform_shared.analyst_recommendations r
            LEFT JOIN platform_shared.article_frameworks f
                ON f.article_id = r.article_id AND f.ticker = r.ticker
            WHERE r.article_id = :article_id
        """), {"article_id": article_id}).fetchall()

        tickers = []
        for t in ticker_rows:
            tickers.append({
                "ticker": t.ticker,
                "recommendation": t.recommendation,
                "sentiment_score": float(t.sentiment_score) if t.sentiment_score is not None else None,
                "asset_class": t.asset_class,
                "conviction_level": t.conviction_level,
                "price_guidance_type": t.price_guidance_type,
                "evaluation_narrative": t.evaluation_narrative,
                "valuation_metrics_cited": t.valuation_metrics_cited or [],
            })

        results.append({
            "id": article_id,
            "sa_article_id": row.sa_article_id,
            "analyst_id": row.analyst_id,
            "analyst_name": row.analyst_name,
            "title": row.title,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "char_count": row.char_count,
            "recommendation_count": rec_count,
            "framework_count": fw_count,
            "article_type": "recommendations" if rec_count > 0 else "analysis",
            "tickers": tickers,
        })

    return results


@router.post("/articles/ingest", tags=["Articles"])
def ingest_article_by_id(payload: dict, db: Session = Depends(get_db)):
    from app.clients import seeking_alpha as sa_client
    from app.processors import extractor, article_store, deduplicator, framework_extractor, suggestion_store

    sa_article_id = str(payload.get("sa_article_id", "")).strip()
    analyst_id = int(payload.get("analyst_id"))

    if not sa_article_id:
        raise HTTPException(status_code=400, detail="sa_article_id is required")

    analyst = db.query(Analyst).filter(Analyst.id == analyst_id).first()
    if not analyst:
        raise HTTPException(status_code=404, detail=f"Analyst {analyst_id} not found")

    if deduplicator.is_duplicate_by_sa_id(db, sa_article_id):
        raise HTTPException(status_code=409, detail=f"Article {sa_article_id} already ingested")

    detail = sa_client.fetch_article_detail(sa_article_id)
    if not detail:
        raise HTTPException(status_code=502, detail=f"Could not fetch article {sa_article_id} from Seeking Alpha")

    html = detail["content"]
    title = detail.get("title", "")
    published_at = sa_client.parse_published_at(detail.get("published_date", ""))
    if not published_at:
        published_at = datetime.now(timezone.utc)

    markdown = extractor.html_to_markdown(html)
    pass1 = extractor.extract_signals(markdown, sa_article_id=sa_article_id)

    extracted_tickers = []
    if pass1 and isinstance(pass1, dict):
        extracted_tickers = pass1.get("tickers") or []

    tickers_mentioned = [t.get("ticker") for t in extracted_tickers if t.get("ticker")]

    article = article_store.save_article(
        db,
        analyst_id=analyst_id,
        sa_article_id=sa_article_id,
        title=title,
        markdown_body=markdown,
        published_at=published_at,
        tickers_mentioned=tickers_mentioned,
        content_embedding=None,
        metadata={"source": "manual_ingest", "char_count": len(markdown)},
    )

    saved_recs = article_store.save_recommendations_for_article(
        db,
        analyst_id=analyst_id,
        article=article,
        extracted_tickers=extracted_tickers,
        thesis_embeddings=[],
        aging_days=365,
    )

    frameworks = framework_extractor.extract_frameworks(markdown, pass1 or {}, sa_article_id)

    suggestions_written = 0
    for fw in frameworks:
        ticker = fw.get("ticker")
        result = db.execute(text("""
            INSERT INTO platform_shared.article_frameworks
                (article_id, analyst_id, ticker, valuation_metrics_cited,
                 thresholds_identified, reasoning_structure, conviction_level,
                 catalysts, price_guidance_type, price_guidance_value,
                 risk_factors_cited, macro_factors, evaluation_narrative)
            VALUES (:article_id, :analyst_id, :ticker,
                CAST(:metrics AS JSONB), CAST(:thresholds AS JSONB),
                :reasoning, :conviction, CAST(:catalysts AS JSONB),
                :guidance_type, CAST(:guidance_value AS JSONB),
                CAST(:risks AS JSONB), CAST(:macro AS JSONB), :narrative)
            ON CONFLICT DO NOTHING RETURNING id
        """), {
            "article_id": article.id,
            "analyst_id": analyst_id,
            "ticker": ticker,
            "metrics": json.dumps(fw.get("valuation_metrics_cited") or []),
            "thresholds": json.dumps(fw.get("thresholds_identified") or {}),
            "reasoning": fw.get("reasoning_structure"),
            "conviction": fw.get("conviction_level"),
            "catalysts": json.dumps(fw.get("catalysts") or []),
            "guidance_type": fw.get("price_guidance_type"),
            "guidance_value": json.dumps(fw.get("price_guidance_value")),
            "risks": json.dumps(fw.get("risk_factors_cited") or []),
            "macro": json.dumps(fw.get("macro_factors") or []),
            "narrative": fw.get("evaluation_narrative"),
        })
        inserted = result.fetchone()
        if inserted:
            framework_id = inserted[0]
            rec_for_ticker = next(
                (r for r in saved_recs if r.ticker == ticker), None
            )
            rec_label = rec_for_ticker.recommendation if rec_for_ticker else None
            if suggestion_store.should_write_suggestion(rec_label):
                suggestion_store.upsert_suggestion(
                    db=db,
                    analyst_id=analyst_id,
                    article_framework_id=framework_id,
                    ticker=ticker,
                    asset_class=rec_for_ticker.asset_class if rec_for_ticker else fw.get("asset_class"),
                    recommendation=rec_label,
                    sentiment_score=float(rec_for_ticker.sentiment_score) if rec_for_ticker and rec_for_ticker.sentiment_score is not None else None,
                    price_guidance_type=fw.get("price_guidance_type"),
                    price_guidance_value=fw.get("price_guidance_value"),
                    sourced_at=published_at,
                )
                suggestions_written += 1

    article_store.update_analyst_after_fetch(db, analyst_id, articles_added=1)
    db.commit()

    logger.info(f"Manual ingest: article {sa_article_id} saved as id={article.id}, "
                f"tickers={len(extracted_tickers)}, frameworks={len(frameworks)}, suggestions={suggestions_written}")

    return {
        "success": True,
        "article_id": article.id,
        "tickers_found": len(extracted_tickers),
        "frameworks_extracted": len(frameworks),
        "suggestions_written": suggestions_written,
    }


@router.post("/articles/{article_id}/sync-suggestions", tags=["Articles"])
def sync_suggestions_for_article(article_id: int, db: Session = Depends(get_db)):
    """
    Backfill missing analyst_suggestions for an already-ingested article.
    For each article_framework row, if no active suggestion exists for that
    (analyst_id, ticker) pair, write one now.  Safe to call multiple times.
    """
    from app.processors import suggestion_store

    article = db.query(AnalystArticle).filter(AnalystArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found")

    # Load tickers: frameworks first, then any BUY recommendations with no framework
    rows = db.execute(text("""
        SELECT
            af.id            AS fw_id,
            COALESCE(af.ticker, ar.ticker) AS ticker,
            af.price_guidance_type,
            af.price_guidance_value,
            ar.recommendation,
            ar.sentiment_score,
            ar.asset_class,
            aa.published_at
        FROM platform_shared.analyst_articles aa
        LEFT JOIN platform_shared.analyst_recommendations ar
               ON ar.article_id = aa.id
        LEFT JOIN platform_shared.article_frameworks af
               ON af.article_id = aa.id AND af.ticker = ar.ticker
        WHERE aa.id = :aid
          AND ar.ticker IS NOT NULL
    """), {"aid": article_id}).fetchall()

    if not rows:
        return {"synced": 0, "detail": "No recommendations found for this article"}

    synced = 0
    for row in rows:
        if not suggestion_store.should_write_suggestion(row.recommendation):
            continue
        # Only write if no active suggestion already exists for this analyst+ticker
        existing = db.execute(text("""
            SELECT 1 FROM platform_shared.analyst_suggestions
            WHERE analyst_id = :aid AND ticker = :ticker AND is_active = TRUE
            LIMIT 1
        """), {"aid": article.analyst_id, "ticker": row.ticker}).fetchone()
        if existing:
            continue

        fw_id = row.fw_id
        if fw_id is None:
            # No framework exists — create a minimal one so the FK constraint is satisfied
            import json as _json
            result = db.execute(text("""
                INSERT INTO platform_shared.article_frameworks
                    (article_id, analyst_id, ticker, valuation_metrics_cited,
                     thresholds_identified, catalysts, risk_factors_cited, macro_factors)
                VALUES (:article_id, :analyst_id, :ticker,
                    '[]'::jsonb, '{}'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)
                ON CONFLICT DO NOTHING RETURNING id
            """), {"article_id": article_id, "analyst_id": article.analyst_id, "ticker": row.ticker})
            inserted = result.fetchone()
            db.flush()
            if inserted:
                fw_id = inserted[0]
            else:
                # Already exists after race — fetch it
                fw_id = db.execute(text("""
                    SELECT id FROM platform_shared.article_frameworks
                    WHERE article_id = :aid AND ticker = :ticker LIMIT 1
                """), {"aid": article_id, "ticker": row.ticker}).scalar()
            if not fw_id:
                continue

        suggestion_store.upsert_suggestion(
            db=db,
            analyst_id=article.analyst_id,
            article_framework_id=fw_id,
            ticker=row.ticker,
            asset_class=row.asset_class,
            recommendation=row.recommendation,
            sentiment_score=float(row.sentiment_score) if row.sentiment_score is not None else None,
            price_guidance_type=row.price_guidance_type,
            price_guidance_value=row.price_guidance_value,
            sourced_at=row.published_at,
        )
        db.commit()
        synced += 1
        logger.info(f"sync-suggestions: wrote suggestion for article={article_id} ticker={row.ticker}")

    return {"synced": synced, "article_id": article_id, "analyst_id": article.analyst_id}


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
