"""
Agent 06 — Scenario Simulation Service
Database: SQLAlchemy sync engine + session factory + base + get_db().
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from typing import Generator

from app.config import settings


def _build_url(raw_url: str) -> str:
    if "?" in raw_url:
        return raw_url.split("?")[0]
    return raw_url


engine = create_engine(
    _build_url(settings.database_url),
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
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
