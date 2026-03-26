"""
Scheduled job definitions — each job calls an agent HTTP endpoint.
"""
import logging
import time

import httpx
import jwt

from app.config import settings

logger = logging.getLogger("scheduler.jobs")


def _token() -> str:
    """Generate a short-lived JWT for service-to-service calls."""
    now = int(time.time())
    return jwt.encode(
        {"sub": "scheduler", "iat": now, "exp": now + 300},
        settings.jwt_secret,
        algorithm="HS256",
    )


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }


def _call(method: str, url: str, label: str, **kwargs):
    """Fire an HTTP request to an agent endpoint."""
    try:
        with httpx.Client(timeout=settings.http_timeout) as client:
            resp = client.request(method, url, headers=_headers(), **kwargs)
            if resp.status_code < 300:
                logger.info(f"[OK]  {label} → {resp.status_code}")
            else:
                logger.warning(
                    f"[WARN] {label} → {resp.status_code}: {resp.text[:200]}"
                )
    except Exception as e:
        logger.error(f"[FAIL] {label} → {e}")


# ═══════════════════════════════════════════════════════════════════════
# JOB DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════


def job_market_data_refresh():
    """Agent 07 — Force-refresh market_data_cache for all tracked tickers after market close.
    Schedule: Every weekday at 18:30 ET (after market close, captures end-of-day prices).
    """
    _call("POST", f"{settings.agent07_url}/cache/refresh?force=true", "Market Data Refresh")


def job_newsletter_harvest():
    """Agent 02 — Fetch latest articles from Seeking Alpha.
    Schedule: Tue & Fri at 07:00 ET.
    """
    _call("POST", f"{settings.agent02_url}/flows/harvester/trigger", "Newsletter Harvest")


def job_score_portfolio():
    """Agent 03 — Re-score all active portfolio positions.
    Schedule: Daily at 19:00 ET (after market data refresh).
    """
    _call("POST", f"{settings.agent03_url}/scores/refresh-portfolio", "Portfolio Score Refresh")


def job_classify_new():
    """Agent 04 — Classify any unclassified securities.
    Schedule: Daily at 19:15 ET.
    """
    _call("POST", f"{settings.agent04_url}/classify/batch", "Classification Batch",
          json={"mode": "unclassified"})


def job_opportunity_scan():
    """Agent 07 — Scan full universe for new income opportunities.
    Schedule: Mon & Thu at 08:00 ET.
    """
    _call("POST", f"{settings.agent07_url}/scan", "Opportunity Scan",
          json={"min_score": 60, "use_universe": True})


def job_nav_monitor_scan():
    """Agent 10 — Scan NAV erosion for CEFs/BDCs.
    Schedule: Daily at 19:30 ET.
    """
    _call("POST", f"{settings.agent10_url}/monitor/scan", "NAV Monitor Scan")


def job_smart_alert_scan():
    """Agent 11 — Run circuit breaker + aggregation scan.
    Schedule: Daily at 20:00 ET.
    """
    _call("POST", f"{settings.agent11_url}/alerts/scan", "Smart Alert Scan")


def job_market_cache_refresh():
    """Agent 07 — Refresh market_data_cache for all tracked tickers.
    Schedule: Every weekday at 06:30 ET (before market open, uses prior-day close data).
    """
    _call("POST", f"{settings.agent07_url}/cache/refresh", "Market Cache Refresh")
