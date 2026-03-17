"""Broker Service — synchronous SQLAlchemy session (matches platform pattern)."""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

_engine = None
_SessionLocal = None


def init_db():
    global _engine, _SessionLocal
    _engine = create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_db():
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session():
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised")
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
