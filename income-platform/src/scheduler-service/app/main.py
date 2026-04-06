"""
Scheduler Service — APScheduler-based cron for all platform batch jobs.
Port 8099 — lightweight health + status API.
"""
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.jobs import (
    job_classify_new,
    job_data_quality_promote,
    job_data_quality_retry,
    job_data_quality_scan,
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

# Tracks last successful execution time per job id
_last_run: dict[str, str] = {}

# Mutable copy of cron kwargs — updated by reschedule endpoint
_schedule_config: dict[str, dict] = {}

# Persistent config file — survives restarts
CONFIG_FILE = Path(os.getenv("SCHEDULE_CONFIG_FILE", "/data/schedule_config.json"))


def _load_persisted_config() -> dict:
    """Load schedule overrides from disk. Returns {} if file missing."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            logger.info("Loaded persisted schedule config from %s", CONFIG_FILE)
            return cfg
    except Exception as exc:
        logger.warning("Could not load schedule config: %s", exc)
    return {}


def _save_persisted_config() -> None:
    """Write _schedule_config to disk so changes survive container restarts."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(_schedule_config, f, indent=2)
    except Exception as exc:
        logger.warning("Could not save schedule config: %s", exc)


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
     {"day_of_week": "mon,wed,fri", "hour": 7, "minute": 0},
     "newsletter-harvest",
     "Fetch Seeking Alpha articles (Mon, Wed, Fri 07:00 ET)"),

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

    (job_data_quality_scan,
     {"day_of_week": "mon-fri", "hour": 18, "minute": 35},
     "data-quality-scan",
     "Data quality scan after market data refresh (Mon-Fri 18:35 ET)"),

    (job_data_quality_retry,
     {"day_of_week": "mon-fri", "hour": "18-20", "minute": "*/15"},
     "data-quality-retry",
     "Retry open data quality issues (Mon-Fri every 15 min 18:00-20:00 ET)"),

    (job_data_quality_promote,
     {"hour": 2, "minute": 0},
     "data-quality-promote",
     "Promote feature gap entries to field requirements (nightly 02:00 ET)"),
]


def _tracked(job_id: str, func):
    """Wrap a job function to record last_run timestamp after execution."""
    def wrapper():
        try:
            func()
        finally:
            _last_run[job_id] = datetime.now(timezone.utc).isoformat()
    return wrapper


@asynccontextmanager
async def lifespan(app: FastAPI):
    persisted = _load_persisted_config()

    for func, cron_kwargs, job_id, desc in JOBS:
        # Apply persisted overrides on top of code defaults
        effective = {**cron_kwargs, **persisted.get(job_id, {})}
        _schedule_config[job_id] = effective
        scheduler.add_job(
            _tracked(job_id, func),
            trigger=CronTrigger(**effective, timezone="America/New_York"),
            id=job_id,
            name=desc,
            replace_existing=True,
        )
        logger.info("Registered: %s — %s", job_id, effective)

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(JOBS))
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
    """List all scheduled jobs with next/last run times and schedule config."""
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        job_id = job.id
        jobs.append({
            "id": job_id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
            "last_run": _last_run.get(job_id),
            "trigger": str(job.trigger),
            "schedule": _schedule_config.get(job_id, {}),
        })
    return {"jobs": jobs, "count": len(jobs)}


@app.post("/jobs/{job_id}/run")
def run_job_now(job_id: str):
    """Trigger a job immediately (on-demand)."""
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    job.func()
    _last_run[job_id] = datetime.now(timezone.utc).isoformat()
    return {
        "status": "executed",
        "job_id": job_id,
        "executed_at": _last_run[job_id],
    }


class RescheduleRequest(BaseModel):
    hour: int
    minute: int
    day_of_week: str | None = None


@app.post("/jobs/{job_id}/reschedule")
def reschedule_job(job_id: str, req: RescheduleRequest):
    """Change the schedule for a job. Changes are persisted to disk."""
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    current = _schedule_config.get(job_id, {})
    new_config = {**current, "hour": req.hour, "minute": req.minute}
    if req.day_of_week is not None:
        new_config["day_of_week"] = req.day_of_week

    _schedule_config[job_id] = new_config
    scheduler.reschedule_job(
        job_id,
        trigger=CronTrigger(**new_config, timezone="America/New_York"),
    )
    _save_persisted_config()
    logger.info("Rescheduled %s → %s (persisted)", job_id, new_config)
    return {"status": "rescheduled", "job_id": job_id, "schedule": new_config}
