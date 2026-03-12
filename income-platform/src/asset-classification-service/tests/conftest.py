"""
Shared pytest fixtures for the asset-classification-service test suite.

JWT_SECRET and other required env vars are injected BEFORE any app module
is imported, so pydantic-settings validation never fails in CI.
"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. Inject env vars BEFORE any app import
# ---------------------------------------------------------------------------
os.environ.setdefault("JWT_SECRET",                  "test-secret")
os.environ.setdefault("DATABASE_URL",                "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("REDIS_URL",                   "redis://localhost:6379")
os.environ.setdefault("MARKET_DATA_SERVICE_URL",     "http://localhost:8001")

# ---------------------------------------------------------------------------
# 2. Add service root + src/ to sys.path
#    asset-classification-service/  ← _SERVICE_DIR (app.* imports work)
#    src/                           ← _SRC_DIR     (shared.* imports work)
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR     = _SERVICE_DIR.parent

for _p in (str(_SERVICE_DIR), str(_SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# 3. Import app (verify_connection patched so lifespan never dials Postgres)
# ---------------------------------------------------------------------------
with patch("app.database.verify_connection", return_value=True):
    from app.main import app
    from app.database import get_db


# ---------------------------------------------------------------------------
# JWT helper — uses PyJWT (already in requirements.txt)
# ---------------------------------------------------------------------------
import jwt as _jwt


def make_token(secret: str = "test-secret", exp_offset: int = 3600) -> str:
    """Return a signed HS256 JWT valid for *exp_offset* seconds."""
    return _jwt.encode(
        {"sub": "test", "exp": int(time.time()) + exp_offset},
        secret,
        algorithm="HS256",
    )


def make_expired_token(secret: str = "test-secret") -> str:
    return _jwt.encode(
        {"sub": "test", "exp": int(time.time()) - 10},
        secret,
        algorithm="HS256",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers() -> dict:
    return {"Authorization": f"Bearer {make_token()}"}


@pytest.fixture
def expired_headers() -> dict:
    return {"Authorization": f"Bearer {make_expired_token()}"}


@pytest.fixture
def mock_db() -> MagicMock:
    """A minimal SQLAlchemy session mock."""
    db = MagicMock()
    db.query.return_value = db
    db.filter.return_value = db
    db.order_by.return_value = db
    db.first.return_value = None
    db.all.return_value = []
    return db


@pytest.fixture
def client(mock_db):
    """TestClient with get_db overridden and lifespan patched."""
    app.dependency_overrides[get_db] = lambda: mock_db
    with patch("app.main.verify_connection", return_value=True):
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    app.dependency_overrides.clear()
