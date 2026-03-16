"""
Scheduler Service — APScheduler-based cron for all platform batch jobs.
Port 8099 — lightweight health + status API.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.config import settings
from app.jobs import (
    job_classify_new,
    job_market_cache_refresh,
    job_market_data_refresh,
    job_nav_monitor_scan,
    job_newsletter_harvest,
    job_opportunity_scan,
    job_score_portfolio,
    job_smart_alert_scan,
)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler(timezone="America/New_York")

# ═══════════════════════════════════════════════════════════════════════
# SCHEDULE DEFINITIONS  (all times US/Eastern)
# ═══════════════════════════════════════════════════════════════════════
JOBS = [
    # (job_func, cron_kwargs, id, description)
    (job_market_cache_refresh,
     {"day_of_week": "mon-fri", "hour": 6, "minute": 30},
     "market-cache-refresh",
     "Refresh market data cache (Mon-Fri 06:30 ET)"),

    (job_market_data_refresh,
     {"day_of_week": "mon-fri", "hour": 18, "minute": 30},
     "market-data-refresh",
     "Refresh prices after market close (Mon-Fri 18:30 ET)"),

    (job_newsletter_harvest,
     {"day_of_week": "tue,fri", "hour": 7, "minute": 0},
     "newsletter-harvest",
     "Fetch Seeking Alpha articles (Tue & Fri 07:00 ET)"),

    (job_score_portfolio,
     {"day_of_week": "mon-fri", "hour": 19, "minute": 0},
     "score-portfolio",
     "Re-score portfolio positions (Mon-Fri 19:00 ET)"),

    (job_classify_new,
     {"day_of_week": "mon-fri", "hour": 19, "minute": 15},
     "classify-new",
     "Classify unclassified securities (Mon-Fri 19:15 ET)"),

    (job_opportunity_scan,
     {"day_of_week": "mon,thu", "hour": 8, "minute": 0},
     "opportunity-scan",
     "Scan for income opportunities (Mon & Thu 08:00 ET)"),

    (job_nav_monitor_scan,
     {"day_of_week": "mon-fri", "hour": 19, "minute": 30},
     "nav-monitor-scan",
     "NAV erosion scan for CEFs/BDCs (Mon-Fri 19:30 ET)"),

    (job_smart_alert_scan,
     {"day_of_week": "mon-fri", "hour": 20, "minute": 0},
     "smart-alert-scan",
     "Circuit breaker + alert aggregation (Mon-Fri 20:00 ET)"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    for func, cron_kwargs, job_id, desc in JOBS:
        scheduler.add_job(
            func,
            trigger=CronTrigger(**cron_kwargs),
            id=job_id,
            name=desc,
            replace_existing=True,
        )
        logger.info(f"Registered: {job_id} — {desc}")

    scheduler.start()
    logger.info(f"Scheduler started with {len(JOBS)} jobs")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(title="Income Platform Scheduler", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "scheduler",
        "jobs_registered": len(scheduler.get_jobs()),
        "running": scheduler.running,
    }


@app.get("/jobs")
def list_jobs():
    """List all scheduled jobs and their next run times."""
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
            "trigger": str(job.trigger),
        })
    return {"jobs": jobs, "count": len(jobs)}


@app.post("/jobs/{job_id}/run")
def run_job_now(job_id: str):
    """Trigger a job immediately (on-demand)."""
    job = scheduler.get_job(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    job.func()
    return {
        "status": "executed",
        "job_id": job_id,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
