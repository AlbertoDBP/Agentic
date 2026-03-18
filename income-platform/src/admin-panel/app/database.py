"""SQLAlchemy sync engine for direct DB queries."""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger("admin.database")


def _build_url(raw_url: str) -> tuple[str, dict]:
    import re
    m = re.search(r'[?&]sslmode=([^&]+)', raw_url)
    sslmode = m.group(1) if m else "disable"
    clean = raw_url.split("?")[0] if "?" in raw_url else raw_url
    connect_args = {
        "sslmode": sslmode,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
    return clean, connect_args


_url, _connect_args = _build_url(settings.database_url)
if _url:
    logger.info(f"DB engine URL: {_url[:40]}...")
    engine = create_engine(
        _url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=_connect_args,
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
