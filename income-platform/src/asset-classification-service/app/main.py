"""Agent 04 — Asset Classification Service"""
import logging
import time
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import verify_connection
from app.api import health, classify, rules, entry_price
from app.auth import verify_token

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _refresh_rules_on_startup() -> None:
    """
    Sync the PREFERRED_STOCK ticker_pattern rule from seed_rules.py into the DB.
    This runs at startup so updates to seed_rules.py take effect without
    running the migration script manually.

    Also ensures hard-coded overrides for tickers that the rule engine
    consistently mis-classifies (e.g. AGNCZ -PZ suffix, ARI).
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.database import engine as _engine
        from app.models import AssetClassRule, ClassificationOverride
        import json

        if _engine is None:
            return

        from shared.asset_class_detector.seed_rules import SEED_RULES
        # Find the preferred stock suffix rule
        pref_seed = next(
            (r for r in SEED_RULES
             if r["asset_class"] == "PREFERRED_STOCK"
             and r["rule_type"] == "ticker_pattern"
             and "suffixes" in r.get("rule_config", {})),
            None,
        )
        if pref_seed is None:
            return

        with Session(_engine) as db:
            # Update the PREFERRED_STOCK ticker_pattern rule in the DB
            existing = db.query(AssetClassRule).filter(
                AssetClassRule.asset_class == "PREFERRED_STOCK",
                AssetClassRule.rule_type == "ticker_pattern",
                AssetClassRule.active.is_(True),
            ).first()
            if existing:
                existing.rule_config = pref_seed["rule_config"]
                existing.priority = pref_seed["priority"]
                existing.confidence_weight = pref_seed["confidence_weight"]
                db.commit()
                logger.info("Refreshed PREFERRED_STOCK suffix rule from seed")

            # Ensure AGNCZ override
            for ticker, asset_class, reason in [
                ("AGNCZ",  "PREFERRED_STOCK", "AGNC preferred series Z (-PZ suffix)"),
                ("ARI",    "MORTGAGE_REIT",   "Apollo Residential — commercial mortgage REIT"),
            ]:
                ov = db.query(ClassificationOverride).filter(
                    ClassificationOverride.ticker == ticker
                ).first()
                if ov:
                    ov.asset_class = asset_class
                    ov.reason = reason
                else:
                    db.add(ClassificationOverride(
                        ticker=ticker,
                        asset_class=asset_class,
                        reason=reason,
                        created_by="startup_fix",
                    ))
            db.commit()
            logger.info("Ensured classification overrides for AGNCZ, ARI")

            # Also patch securities.asset_type directly so broker service
            # and scanner read the correct class without needing a re-classify.
            try:
                from sqlalchemy import text
                db.execute(
                    text(
                        "UPDATE platform_shared.securities"
                        " SET asset_type = :ac"
                        " WHERE symbol = :t AND (asset_type IS NULL OR asset_type = 'UNKNOWN')"
                    ),
                    {"ac": "PREFERRED_STOCK", "t": "AGNCZ"},
                )
                db.execute(
                    text(
                        "UPDATE platform_shared.securities"
                        " SET asset_type = :ac"
                        " WHERE symbol = :t AND (asset_type IS NULL OR asset_type = 'UNKNOWN')"
                    ),
                    {"ac": "MORTGAGE_REIT", "t": "ARI"},
                )
                db.commit()
                logger.info("Patched securities.asset_type for AGNCZ → PREFERRED_STOCK, ARI → MORTGAGE_REIT")
            except Exception as patch_exc:
                logger.warning("securities.asset_type patch failed (non-fatal): %s", patch_exc)

    except Exception as exc:
        logger.warning("Rule refresh at startup failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.service_name}...")
    if verify_connection():
        logger.info("✅ Database connected")
        _refresh_rules_on_startup()
    else:
        logger.error("❌ Database connection failed — service degraded")
    logger.info(f"✅ {settings.service_name} started on port {settings.service_port}")
    yield
    logger.info(f"Application shutdown complete.")


app = FastAPI(
    title="Agent 04 — Asset Classification Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    return response


app.include_router(health.router, tags=["health"])
app.include_router(classify.router, tags=["classification"], dependencies=[Depends(verify_token)])
app.include_router(rules.router, tags=["rules"], dependencies=[Depends(verify_token)])
app.include_router(entry_price.router, tags=["entry-price"], dependencies=[Depends(verify_token)])
