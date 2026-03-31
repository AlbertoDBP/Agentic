# src/agent-14-data-quality/app/database.py
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings

logger = logging.getLogger(__name__)


engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=(settings.log_level == "DEBUG"),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> dict:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            schema = conn.execute(
                text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :s"),
                {"s": settings.db_schema},
            ).fetchone()
        return {"status": "healthy", "connectivity": result == 1, "schema_exists": schema is not None}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
