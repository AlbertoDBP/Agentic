"""
Shared pytest fixtures for the market-data-service test suite.

IMPORTANT: JWT_SECRET must be injected into os.environ BEFORE any app module
is imported.  This file is loaded by pytest before any test module, so the
os.environ assignment at module level here guarantees the ordering is correct.

Additional env vars required by config.py (pydantic-settings) are also set
here so that the Settings() call inside config.py does not raise
ValidationError when the service has no .env file present.
"""
import base64
import hashlib
import hmac
import json
import os
import time

# ---------------------------------------------------------------------------
# Inject required environment variables BEFORE importing any service module
# ---------------------------------------------------------------------------
os.environ.setdefault("JWT_SECRET",          "test-secret")
os.environ.setdefault("DATABASE_URL",        "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("REDIS_URL",           "redis://localhost:6379/0")
os.environ.setdefault("MARKET_DATA_API_KEY", "test-av-key")
os.environ.setdefault("POLYGON_API_KEY",     "test-polygon-key")
os.environ.setdefault("FMP_API_KEY",         "test-fmp-key")
os.environ.setdefault("FINNHUB_API_KEY",     "test-finnhub-key")

# ---------------------------------------------------------------------------
# Now it is safe to import FastAPI / app modules
# ---------------------------------------------------------------------------
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

_SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

# main.py uses importlib path-loading, which means we must import it directly
# by path so that all sub-modules are registered in sys.modules before the
# TestClient mounts the app.
import importlib.util as _ilu

_main_spec = _ilu.spec_from_file_location("main", _SERVICE_DIR / "main.py")
_main_mod  = _ilu.module_from_spec(_main_spec)
sys.modules["main"] = _main_mod
_main_spec.loader.exec_module(_main_mod)

app = _main_mod.app


# ---------------------------------------------------------------------------
# JWT helper — stdlib HS256 (mirrors auth.py's verification logic exactly)
# ---------------------------------------------------------------------------

def make_token(secret: str = "test-secret", exp_offset: int = 3600) -> str:
    """Create a signed HS256 JWT using only stdlib primitives.

    The encoding/padding logic is identical to auth.py so that tokens
    generated here will pass verify_token() without modification.
    """
    header  = (
        base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": "test", "exp": int(time.time()) + exp_offset}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    sig = (
        base64.urlsafe_b64encode(
            hmac.new(
                secret.encode(),
                f"{header}.{payload}".encode(),
                hashlib.sha256,
            ).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{payload}.{sig}"


# ---------------------------------------------------------------------------
# Shared mock factories
# ---------------------------------------------------------------------------

def _mock_cache() -> MagicMock:
    """Return a CacheManager mock whose async methods return sensible defaults."""
    m = MagicMock()
    m.is_connected = AsyncMock(return_value=False)
    m.get          = AsyncMock(return_value=None)
    m.set          = AsyncMock(return_value=None)
    m.delete       = AsyncMock(return_value=None)
    m.get_stats    = AsyncMock(return_value={"connected": False})
    return m


def _mock_db() -> MagicMock:
    """Return a DatabaseManager mock that reports as disconnected."""
    m = MagicMock()
    m.is_connected   = AsyncMock(return_value=False)
    m.session_factory = None
    return m


def _mock_price_service() -> MagicMock:
    """Return a PriceService mock with a default get_current_price result."""
    m = MagicMock()
    m.get_current_price = AsyncMock(
        return_value={
            "ticker":         "AAPL",
            "price":          175.50,
            "change":         1.25,
            "change_percent": 0.72,
            "volume":         55_000_000,
            "timestamp":      "2026-03-12T14:30:00+00:00",
            "source":         "alpha_vantage",
            "cached":         False,
        }
    )
    return m


def _mock_market_data_service() -> MagicMock:
    """Return a MarketDataService mock with stub responses for all public methods."""
    m = MagicMock()
    m._router           = MagicMock(polygon=None, fmp=None, yfinance=None)
    m._finnhub          = None
    m._securities_repo  = None

    m.get_historical_prices    = AsyncMock(return_value=[])
    m.get_dividend_history     = AsyncMock(return_value=[])
    m.get_fundamentals         = AsyncMock(return_value={})
    m.get_etf_holdings         = AsyncMock(return_value={})
    m.refresh_historical_prices = AsyncMock(return_value=0)
    m.sync_symbol              = AsyncMock(
        return_value={
            "symbol":               "AAPL",
            "as_of_date":           "2026-03-12",
            "securities_updated":   False,
            "features_updated":     False,
            "credit_rating":        None,
            "credit_quality_proxy": None,
            "chowder_number":       None,
            "yield_5yr_avg":        None,
            "providers_used":       [],
            "missing_fields":       [],
        }
    )
    m.connect    = AsyncMock()
    m.disconnect = AsyncMock()
    return m


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def valid_token() -> str:
    """A valid HS256 JWT signed with the test secret, expiring in 1 hour."""
    return make_token()


@pytest.fixture(scope="session")
def auth_headers(valid_token) -> dict:
    """Authorization header dict ready for use with TestClient."""
    return {"Authorization": f"Bearer {valid_token}"}


@pytest.fixture()
def client(monkeypatch):
    """TestClient with all external dependencies mocked out.

    Patches:
      - main.cache_manager      → mock (disconnected)
      - main.db_manager         → mock (disconnected)
      - main.price_service      → mock
      - main.market_data_service → mock

    The lifespan is bypassed via the ``with TestClient(app)`` context which
    drives the ASGI lifespan events but the mocked objects are injected
    *before* lifespan runs, so startup/shutdown callbacks see the mocks.
    """
    mock_cache = _mock_cache()
    mock_db    = _mock_db()
    mock_ps    = _mock_price_service()
    mock_mds   = _mock_market_data_service()

    monkeypatch.setattr(_main_mod, "cache_manager",       mock_cache)
    monkeypatch.setattr(_main_mod, "db_manager",          mock_db)
    monkeypatch.setattr(_main_mod, "price_service",       mock_ps)
    monkeypatch.setattr(_main_mod, "market_data_service", mock_mds)

    # The lifespan calls await cache_manager.connect() / await db_manager.connect()
    # etc. on the objects returned by the constructors.  Ensure those async
    # methods exist on each mock so 'await' does not raise TypeError.
    mock_cache.connect    = AsyncMock()
    mock_cache.disconnect = AsyncMock()
    mock_db.connect       = AsyncMock()
    mock_db.disconnect    = AsyncMock()
    mock_db.session_factory = None

    # Lifespan also calls await market_data_service.connect() / .disconnect()
    mock_mds.connect    = AsyncMock()
    mock_mds.disconnect = AsyncMock()

    # Patch constructors so lifespan's 'CacheManager(url)' / 'DatabaseManager(url)'
    # calls return our pre-built mocks rather than creating real objects.
    cache_cls_mock = MagicMock(return_value=mock_cache)
    db_cls_mock    = MagicMock(return_value=mock_db)
    monkeypatch.setattr(_main_mod, "CacheManager",   cache_cls_mock)
    monkeypatch.setattr(_main_mod, "DatabaseManager", db_cls_mock)

    # MarketDataService constructor + PriceService constructor
    mds_cls_mock = MagicMock(return_value=mock_mds)
    ps_cls_mock  = MagicMock(return_value=mock_ps)
    monkeypatch.setattr(_main_mod, "MarketDataService", mds_cls_mock)
    monkeypatch.setattr(_main_mod, "PriceService",      ps_cls_mock)

    with TestClient(app, raise_server_exceptions=True) as tc:
        yield tc


@pytest.fixture()
def authed_client(client, auth_headers):
    """Convenience fixture: client already pre-loaded with auth headers.

    Usage in tests:
        def test_something(authed_client):
            resp = authed_client.get("/stocks/AAPL/price")
    """
    # Attach headers as a default so callers never need to pass them manually.
    class _AuthedClient:
        def __init__(self, tc, headers):
            self._tc      = tc
            self._headers = headers

        def get(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._tc.get(url, **kwargs)

        def post(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._tc.post(url, **kwargs)

        # Expose the raw client for tests that need it
        @property
        def raw(self):
            return self._tc

    return _AuthedClient(client, auth_headers)
