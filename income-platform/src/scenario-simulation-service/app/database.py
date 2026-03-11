"""
Agent 06 — Scenario Simulation Service
Database: SQLAlchemy sync engine + session factory + base + get_db().
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from typing import Generator

from app.config import settings


def _build_url() -> str:
    """Strip ?sslmode=require query param; SSL is passed via connect_args."""
    url = settings.database_url
    if "?" in url:
        url = url.split("?")[0]
    return url


engine = create_engine(
    _build_url(),
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
