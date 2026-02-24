"""
Agent 02 — Newsletter Ingestion Service
Database: SQLAlchemy engine, session factory, and base model

Uses synchronous psycopg2 driver to match Agent 01 pattern.
pgvector extension must be installed on the PostgreSQL instance.
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

engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,                    # validate connections before use
    pool_recycle=3600,                     # recycle connections every hour
    echo=(settings.log_level == "DEBUG"),  # SQL logging in debug mode only
    connect_args={
        "options": f"-csearch_path={settings.db_schema},public"
    }
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

    Usage:
        @app.get("/endpoint")
        def handler(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Context Manager (Prefect flows) ──────────────────────────────────────────

@contextmanager
def get_db_context():
    """
    Context manager for database sessions in Prefect flows and
    background tasks where FastAPI dependency injection is unavailable.

    Usage:
        with get_db_context() as db:
            db.query(Analyst).all()
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
    """
    Verify database connectivity and pgvector extension.
    Called by /health endpoint.
    """
    try:
        with engine.connect() as conn:
            # Basic connectivity
            result = conn.execute(text("SELECT 1")).scalar()

            # pgvector extension check (required for embeddings)
            vector_result = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()

            # Schema existence check
            schema_result = conn.execute(
                text(f"SELECT schema_name FROM information_schema.schemata "
                     f"WHERE schema_name = '{settings.db_schema}'")
            ).fetchone()

        return {
            "status": "healthy",
            "connectivity": result == 1,
            "pgvector_installed": vector_result is not None,
            "schema_exists": schema_result is not None,
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }
