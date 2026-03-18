"""SQLAlchemy sync engine for direct DB queries."""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger("admin.database")


def _build_url(raw_url: str) -> str:
    return raw_url.split("?")[0] if "?" in raw_url else raw_url


_url = _build_url(settings.database_url)
if _url:
    logger.info(f"DB engine URL: {_url[:40]}...")
    engine = create_engine(
        _url,
        pool_pre_ping=True,
        connect_args={},  # sslmode driven by DATABASE_URL (?sslmode=require or ?sslmode=disable)
    )
    # Startup connectivity check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("DB connection OK")
    except Exception as e:
        logger.error(f"DB connection FAILED at startup: {e}")
else:
    logger.error("DATABASE_URL is empty — no DB connection available")
    engine = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


def check_db_health() -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
