"""SQLAlchemy sync engine for direct DB queries."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings


def _build_url(raw_url: str) -> str:
    return raw_url.split("?")[0] if "?" in raw_url else raw_url


engine = create_engine(
    _build_url(settings.database_url),
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def check_db_health() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
