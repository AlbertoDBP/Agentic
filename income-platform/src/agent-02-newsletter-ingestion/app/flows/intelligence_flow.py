"""
Agent 02 — Newsletter Ingestion Service
Flow: Intelligence Flow (Prefect)

Schedule: Monday 6AM ET (0 6 * * 1)
Can also be triggered manually via POST /flows/intelligence/trigger

Pipeline (per analyst):
  1. Staleness sweep    → recompute decay_weight on all active recs
                          mark is_active=False where decay_weight=0
  2. Accuracy backtest  → for recs published > 30 days ago with no backtest:
                          fetch T+30 and T+90 prices from FMP
                          detect dividend cuts
                          compute outcome_label + accuracy_delta
                          update analyst.overall_accuracy + sector_alpha
  3. Philosophy update  → if article_count < 20: LLM summary (Claude Sonnet)
                          if article_count >= 20: K-Means K=5
                          update analysts.philosophy_* fields
  4. Consensus rebuild  → recompute consensus for all tickers this analyst
                          has active recommendations on

Flow-level error handling:
  - Per-analyst failures are caught and logged — one bad analyst
    does not abort the entire flow
  - Flow run metadata written to flow_run_log on completion

Concurrency: single-threaded per-analyst to respect FMP rate limits.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from prefect import flow, task, get_run_logger

from app.database import get_db_context
from app.models.models import Analyst
from app.processors import staleness, backtest, philosophy, consensus
from app.config import settings

logger = logging.getLogger(__name__)


# ── Tasks ──────────────────────────────────────────────────────────────────────

@task(
    name="staleness-sweep",
    tags=["intelligence", "db"],
)
def task_staleness_sweep(analyst_id: int, analyst_config: Optional[dict] = None) -> dict:
    """Recompute decay_weight for all active recommendations of one analyst."""
    log = get_run_logger()
    with get_db_context() as db:
        result = staleness.sweep_analyst_staleness(
            db=db,
            analyst_id=analyst_id,
            analyst_config=analyst_config,
        )
    log.info(
        f"Analyst {analyst_id} staleness sweep: "
        f"{result['updated']} updated, {result['deactivated']} deactivated"
    )
    return result


@task(
    name="backtest-analyst",
    retries=1,
    retry_delay_seconds=60,
    tags=["intelligence", "fmp", "db"],
)
def task_backtest_analyst(analyst_id: int) -> dict:
    """
    Run accuracy backtest for eligible recommendations.
    Eligible: published > 30 days ago, no existing backtest record.
    """
    log = get_run_logger()
    with get_db_context() as db:
        result = backtest.backtest_analyst(db=db, analyst_id=analyst_id)
    log.info(
        f"Analyst {analyst_id} backtest: "
        f"{result['backtested']} backtested, outcomes={result['outcomes']}"
    )
    return result


@task(
    name="philosophy-update",
    retries=1,
    retry_delay_seconds=30,
    tags=["intelligence", "llm", "db"],
)
def task_philosophy_update(analyst_id: int) -> dict:
    """
    Synthesize analyst philosophy.
    Routes to LLM (<20 articles) or K-Means (>=20 articles).
    """
    log = get_run_logger()
    with get_db_context() as db:
        result = philosophy.update_analyst_philosophy(db=db, analyst_id=analyst_id)
    source = result.get("philosophy_source", "unknown")
    log.info(f"Analyst {analyst_id} philosophy updated via {source}")
    return result


@task(
    name="consensus-rebuild",
    tags=["intelligence", "cache", "db"],
)
def task_consensus_rebuild(analyst_id: int) -> dict:
    """
    Rebuild consensus scores for all tickers this analyst has active recs on.
    """
    log = get_run_logger()
    with get_db_context() as db:
        result = consensus.rebuild_consensus_for_analyst(db=db, analyst_id=analyst_id)
    log.info(
        f"Analyst {analyst_id} consensus rebuilt for "
        f"{result['tickers_rebuilt']} tickers"
    )
    return result


# ── Main Flow ──────────────────────────────────────────────────────────────────

@flow(
    name="agent-02-intelligence",
    description=(
        "Intelligence Flow: staleness decay, FMP backtest, "
        "philosophy synthesis, consensus scoring. Monday 6AM ET."
    ),
    version="0.1.0",
)
def intelligence_flow(analyst_ids: Optional[list[int]] = None):
    """
    Main Intelligence Flow.

    Args:
        analyst_ids: specific analyst DB IDs to process.
                     If None, processes all active analysts.
    """
    log = get_run_logger()
    log.info("Intelligence Flow started")

    flow_start = datetime.now(timezone.utc)
    analyst_results = []

    # Load active analysts
    with get_db_context() as db:
        query = db.query(Analyst).filter(Analyst.is_active == True)
        if analyst_ids:
            query = query.filter(Analyst.id.in_(analyst_ids))
        analysts = query.all()

        analyst_data = [
            {
                "id": a.id,
                "display_name": a.display_name,
                "config": a.config or {},
                "article_count": a.article_count or 0,
            }
            for a in analysts
        ]

    log.info(f"Processing {len(analyst_data)} active analysts")

    total_deactivated = 0
    total_backtested = 0
    total_tickers_rebuilt = 0

    for analyst in analyst_data:
        analyst_id = analyst["id"]
        display_name = analyst["display_name"]
        log.info(f"Intelligence pipeline: {display_name} (id={analyst_id})")

        try:
            # Step 1: Staleness sweep
            staleness_result = task_staleness_sweep(
                analyst_id=analyst_id,
                analyst_config=analyst["config"],
            )
            total_deactivated += staleness_result.get("deactivated", 0)

            # Step 2: Accuracy backtest (FMP — may be slow due to API calls)
            backtest_result = task_backtest_analyst(analyst_id=analyst_id)
            total_backtested += backtest_result.get("backtested", 0)

            # Step 3: Philosophy update
            philosophy_result = task_philosophy_update(analyst_id=analyst_id)

            # Step 4: Consensus rebuild
            consensus_result = task_consensus_rebuild(analyst_id=analyst_id)
            total_tickers_rebuilt += consensus_result.get("tickers_rebuilt", 0)

            analyst_results.append({
                "analyst_id": analyst_id,
                "display_name": display_name,
                "staleness": staleness_result,
                "backtest": backtest_result,
                "philosophy_source": philosophy_result.get("philosophy_source"),
                "tickers_rebuilt": consensus_result.get("tickers_rebuilt", 0),
                "status": "success",
            })

        except Exception as e:
            log.error(f"Intelligence pipeline error for analyst {analyst_id}: {e}")
            analyst_results.append({
                "analyst_id": analyst_id,
                "display_name": display_name,
                "status": "error",
                "error": str(e),
            })
            continue

    # ── Write flow run log ─────────────────────────────────────────────────
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
                "name": "intelligence_flow",
                "ran_at": flow_end,
                "status": "success",
                "articles": 0,  # intelligence flow does not ingest articles
                "duration": duration_seconds,
                "meta": json.dumps({
                    "analysts": analyst_results,
                    "total_deactivated": total_deactivated,
                    "total_backtested": total_backtested,
                    "total_tickers_rebuilt": total_tickers_rebuilt,
                }),
            })
    except Exception as e:
        log.warning(f"Could not write flow_run_log: {e}")

    log.info(
        f"Intelligence Flow complete: "
        f"{len(analyst_results)} analysts | "
        f"{total_deactivated} recs deactivated | "
        f"{total_backtested} backtests | "
        f"{total_tickers_rebuilt} tickers rebuilt | "
        f"{duration_seconds:.1f}s"
    )

    return {
        "analysts_processed": len(analyst_results),
        "total_deactivated": total_deactivated,
        "total_backtested": total_backtested,
        "total_tickers_rebuilt": total_tickers_rebuilt,
        "duration_seconds": duration_seconds,
    }
