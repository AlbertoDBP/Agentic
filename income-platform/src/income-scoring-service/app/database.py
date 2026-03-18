"""
Agent 03 — Income Scoring Service
Database: SQLAlchemy engine, session factory, and base model.

Uses synchronous psycopg2 driver matching Agent 01 & 02 pattern.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
import logging

from app.config import settings

logger = logging.getLogger(__name__)


# ── Engine ────────────────────────────────────────────────────────────────────

def _build_url(raw_url: str) -> tuple[str, dict]:
    """Strip query params from URL; return (clean_url, connect_args with sslmode)."""
    import re
    m = re.search(r'[?&]sslmode=([^&]+)', raw_url)
    sslmode = m.group(1) if m else "disable"
    clean = raw_url.split("?")[0] if "?" in raw_url else raw_url
    return clean, {"sslmode": sslmode}


_db_url, _connect_args = _build_url(settings.database_url)
engine = create_engine(
    _db_url,
    poolclass=QueuePool,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=(settings.log_level == "DEBUG"),
    connect_args=_connect_args,
)


# ── Session Factory ───────────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ── Declarative Base ──────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """All SQLAlchemy models inherit from this base."""
    pass


# ── Session Dependency (FastAPI) ──────────────────────────────────────────────

def get_db() -> Generator:
    """
    FastAPI dependency that provides a database session.
    Automatically closes session after request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Context Manager (background tasks / batch scoring) ───────────────────────

@contextmanager
def get_db_context():
    """
    Context manager for database sessions in batch scoring jobs
    and background tasks where FastAPI DI is unavailable.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Health Check ──────────────────────────────────────────────────────────────

def check_database_connection() -> dict:
    """Verify database connectivity. Called by /health endpoint."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()

            schema_result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = :schema"
                ),
                {"schema": settings.db_schema},
            ).fetchone()

            # Check Agent 01 market data tables exist (upstream dependency)
            market_data_table = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'market_data_daily'"
                ),
            ).fetchone()

        return {
            "status": "healthy",
            "connectivity": result == 1,
            "schema_exists": schema_result is not None,
            "upstream_market_data_table": market_data_table is not None,
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }
