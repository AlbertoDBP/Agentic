"""Agent 04 — Database connection and session factory"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _build_url(raw_url: str) -> tuple[str, dict]:
    """Strip query params from URL; return (clean_url, connect_args with sslmode + keepalives)."""
    import re
    m = re.search(r'[?&]sslmode=([^&]+)', raw_url)
    sslmode = m.group(1) if m else "disable"
    clean = raw_url.split("?")[0] if "?" in raw_url else raw_url
    connect_args = {
        "sslmode": sslmode,
        # TCP keepalives prevent Docker/pgbouncer from silently dropping idle connections
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
    return clean, connect_args


_db_url, _connect_args = _build_url(settings.database_url)
engine = create_engine(
    _db_url,
    connect_args=_connect_args,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=300,  # recycle connections every 5 min, below pgbouncer server_idle_timeout
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False
