"""
Agent 07 — Opportunity Scanner Service
Database: SQLAlchemy sync engine + session factory + base + get_db().
"""
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _build_url(raw_url: str) -> str:
    if "?" in raw_url:
        return raw_url.split("?")[0]
    return raw_url


engine = create_engine(
    _build_url(settings.database_url),
    pool_pre_ping=True,
    connect_args={},  # sslmode driven by DATABASE_URL (?sslmode=require or ?sslmode=disable)
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


def check_db_health() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
