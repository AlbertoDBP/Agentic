"""SQLAlchemy sync engine + session factory."""
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings


def _build_url(raw_url: str) -> tuple[str, dict]:
    """Strip query params; extract sslmode for connect_args (pgbouncer disables SSL)."""
    import re
    m = re.search(r'[?&]sslmode=([^&]+)', raw_url)
    sslmode = m.group(1) if m else "disable"
    clean = raw_url.split("?")[0] if "?" in raw_url else raw_url
    return clean, {"sslmode": sslmode}


_db_url, _connect_args = _build_url(settings.database_url)
engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    connect_args=_connect_args,
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
