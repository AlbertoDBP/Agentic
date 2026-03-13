"""
Tests for POST /entry-price/{ticker}

40 tests covering:
  - Auth (5)
  - CommonStock yield-based (8)
  - BDC nav-discount (5)
  - CEF nav-discount (5)
  - ETF 4-signal composite score (12)
  - Position size from portfolio constraints (3)
  - Graceful degradation when nav_snapshots unavailable (2)
"""
import os
import sys
import time
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt as _jwt
import pytest

# Env vars injected before any app import (mirrors conftest.py)
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("MARKET_DATA_SERVICE_URL", "http://localhost:8001")

# conftest provides: client, auth_headers, expired_headers, mock_db
# Token helpers (duplicated here to avoid conftest import — pytest injects conftest
# as a plugin, not as a normal module importable by name).

def make_token(secret: str = "test-secret", exp_offset: int = 3600) -> str:
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
# Shared classification stubs
# ---------------------------------------------------------------------------

def _clf(asset_class: str = "CommonStock") -> dict:
    return {
        "ticker": "O",
        "asset_class": asset_class,
        "parent_class": "Equity",
        "confidence": 0.95,
        "is_hybrid": False,
        "characteristics": {},
        "benchmarks": None,
        "sub_scores": None,
        "tax_efficiency": {},
        "source": "rule_engine_v1",
        "is_override": False,
        "classified_at": "2026-03-01T00:00:00+00:00",
        "valid_until": "2026-03-02T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# DB row factory — returns object that supports ._mapping dict access
# ---------------------------------------------------------------------------

class _Row:
    """Minimal row proxy mimicking SQLAlchemy Row._mapping."""

    def __init__(self, data: dict):
        self._mapping = data

    def __bool__(self):
        return True


def _make_db(
    features: Optional[dict] = None,
    last_price: Optional[float] = None,
    nav: Optional[dict] = None,
    income_scores: Optional[dict] = None,
    portfolio: Optional[dict] = None,
):
    """Return a MagicMock DB session with execute() pre-configured.

    Each call to db.execute() is dispatched based on the SQL string it
    receives so different queries return different rows.
    """
    db = MagicMock()

    def _execute(stmt, params=None):
        sql = str(stmt).lower()
        result = MagicMock()

        if "features_historical" in sql:
            result.fetchone.return_value = _Row(features) if features is not None else None
        elif "securities" in sql:
            result.fetchone.return_value = (
                _Row({"last_price": last_price}) if last_price is not None else None
            )
        elif "nav_snapshots" in sql:
            result.fetchone.return_value = _Row(nav) if nav is not None else None
        elif "income_scores" in sql:
            result.fetchone.return_value = (
                _Row(income_scores) if income_scores is not None else None
            )
        elif "portfolio_constraints" in sql:
            result.fetchone.return_value = (
                _Row(portfolio) if portfolio is not None else None
            )
        else:
            result.fetchone.return_value = None

        return result

    db.execute.side_effect = _execute
    # ORM-style query chain (used by ClassificationEngine for cache/override)
    db.query.return_value = db
    db.filter.return_value = db
    db.order_by.return_value = db
    db.first.return_value = None
    db.all.return_value = []
    return db


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _client_with_db(app, get_db_dep, db_mock):
    """Return a TestClient with get_db overridden to db_mock."""
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db_dep] = lambda: db_mock
    with patch("app.main.verify_connection", return_value=True):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Reusable fixtures that individual tests can use directly
# ---------------------------------------------------------------------------

@pytest.fixture
def ep_client(mock_db):
    """TestClient wired to a neutral mock_db (same as classify tests)."""
    from app.main import app
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    with patch("app.main.verify_connection", return_value=True):
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. AUTH TESTS (5)
# ---------------------------------------------------------------------------

class TestEntryPriceAuth:
    def test_no_auth_header_returns_403(self, ep_client):
        r = ep_client.post("/entry-price/O")
        assert r.status_code in (401, 403)

    def test_invalid_token_returns_401(self, ep_client):
        r = ep_client.post(
            "/entry-price/O",
            headers={"Authorization": "Bearer this.is.garbage"},
        )
        assert r.status_code == 401

    def test_expired_token_returns_401(self, ep_client, expired_headers):
        r = ep_client.post("/entry-price/O", headers=expired_headers)
        assert r.status_code == 401

    def test_wrong_scheme_returns_403(self, ep_client):
        token = make_token()
        r = ep_client.post(
            "/entry-price/O",
            headers={"Authorization": f"Basic {token}"},
        )
        assert r.status_code in (401, 403)

    def test_valid_token_passes_auth(self, mock_db, auth_headers):
        """A valid token reaches the endpoint (even if data is missing → 200 with Nones)."""
        from app.main import app
        from app.database import get_db

        db = _make_db()  # no data → graceful degradation
        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("CommonStock")),
                ):
                    r = c.post("/entry-price/O", headers=auth_headers)
        app.dependency_overrides.clear()
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# 2. COMMONSTOCK YIELD-BASED (8)
# ---------------------------------------------------------------------------

class TestCommonStockYieldBased:
    """CommonStock / REIT / MLP use yield_based logic."""

    def _make_client(self, app, get_db_dep, db):
        app.dependency_overrides[get_db_dep] = lambda: db
        from fastapi.testclient import TestClient
        with patch("app.main.verify_connection", return_value=True):
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c
        app.dependency_overrides.clear()

    def _post(self, app, get_db_dep, db, auth_headers, ticker="O", body=None):
        from app.main import app as _app
        from app.database import get_db

        _app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(_app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("CommonStock")),
                ):
                    r = c.post(f"/entry-price/{ticker}", json=body or {}, headers=auth_headers)
        _app.dependency_overrides.clear()
        return r

    def test_entry_method_is_yield_based(self, auth_headers):
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=57.0,
        )
        r = self._post(None, None, db, auth_headers)
        assert r.status_code == 200
        assert r.json()["entry_method"] == "yield_based"

    def test_entry_price_high_formula(self, auth_headers):
        """entry_price_high = (yield_forward * price) / (target_yield/100)."""
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=57.0,
        )
        r = self._post(None, None, db, auth_headers, body={"target_yield_pct": 5.5})
        assert r.status_code == 200
        body = r.json()
        # annual_div = 0.055 * 57.0 = 3.135; entry_high = 3.135 / 0.055 = 57.0
        assert body["entry_price_high"] == pytest.approx(57.0, abs=0.05)

    def test_entry_price_low_is_95pct_of_high(self, auth_headers):
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=57.0,
        )
        r = self._post(None, None, db, auth_headers, body={"target_yield_pct": 5.5})
        body = r.json()
        assert body["entry_price_low"] == pytest.approx(
            body["entry_price_high"] * 0.95, abs=0.05
        )

    def test_missing_yield_forward_returns_none_prices(self, auth_headers):
        """When yield_forward is absent, both entry prices are None."""
        db = _make_db(features={}, last_price=57.0)
        r = self._post(None, None, db, auth_headers)
        body = r.json()
        assert body["entry_price_low"] is None
        assert body["entry_price_high"] is None

    def test_missing_price_returns_none_prices(self, auth_headers):
        db = _make_db(features={"yield_forward": 0.055}, last_price=None)
        r = self._post(None, None, db, auth_headers)
        body = r.json()
        assert body["entry_price_low"] is None
        assert body["entry_price_high"] is None

    def test_with_portfolio_id_uses_portfolio_yield(self, auth_headers):
        pid = str(uuid4())
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=57.0,
            portfolio={"target_income_yield_pct": 6.0, "max_position_pct": 3.0},
        )
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("CommonStock")),
                ):
                    r = c.post(
                        f"/entry-price/O?portfolio_id={pid}",
                        json={},
                        headers=auth_headers,
                    )
        app.dependency_overrides.clear()
        body = r.json()
        assert body["target_yield_used"] == pytest.approx(6.0, abs=0.01)

    def test_body_overrides_portfolio_yield(self, auth_headers):
        pid = str(uuid4())
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=57.0,
            portfolio={"target_income_yield_pct": 6.0, "max_position_pct": 3.0},
        )
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("CommonStock")),
                ):
                    r = c.post(
                        f"/entry-price/O?portfolio_id={pid}",
                        json={"target_yield_pct": 7.0},
                        headers=auth_headers,
                    )
        app.dependency_overrides.clear()
        # Body overrides portfolio; target_yield_used should be 7.0
        assert r.json()["target_yield_used"] == pytest.approx(7.0, abs=0.01)

    def test_annual_income_estimate_populated(self, auth_headers):
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=60.0,
        )
        r = self._post(None, None, db, auth_headers)
        body = r.json()
        assert body["annual_income_estimate"] == pytest.approx(60.0 * 0.055, abs=0.001)

    def test_preferred_stock_capped_at_25(self, auth_headers):
        """Preferred stocks get entry_price_high capped at par ($25)."""
        db = _make_db(
            features={"yield_forward": 0.06, "yield_5yr_avg": 0.06},
            last_price=26.0,
        )
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("PREFERRED_STOCK")),
                ):
                    r = c.post("/entry-price/PSA-PR", json={}, headers=auth_headers)
        app.dependency_overrides.clear()
        body = r.json()
        # annual_div = 0.06*26 = 1.56; entry_high = 1.56/0.05 = 31.2 → capped to 25.0
        assert body["entry_price_high"] <= 25.0


# ---------------------------------------------------------------------------
# 3. BDC NAV-DISCOUNT (5)
# ---------------------------------------------------------------------------

class TestBDCNavDiscount:
    def _post(self, db, auth_headers, ticker="ARCC", body=None):
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("BDC")),
                ):
                    r = c.post(f"/entry-price/{ticker}", json=body or {}, headers=auth_headers)
        app.dependency_overrides.clear()
        return r

    def test_entry_method_is_nav_discount(self, auth_headers):
        db = _make_db(nav={"nav": 20.0, "market_price": 19.5, "premium_discount": -2.5}, last_price=19.5)
        r = self._post(db, auth_headers)
        assert r.json()["entry_method"] == "nav_discount"

    def test_entry_price_high_at_3pct_discount(self, auth_headers):
        db = _make_db(nav={"nav": 20.0, "market_price": 19.5, "premium_discount": -2.5}, last_price=19.5)
        r = self._post(db, auth_headers)
        assert r.json()["entry_price_high"] == pytest.approx(20.0 * 0.97, abs=0.01)

    def test_entry_price_low_at_8pct_discount(self, auth_headers):
        db = _make_db(nav={"nav": 20.0, "market_price": 19.5, "premium_discount": -2.5}, last_price=19.5)
        r = self._post(db, auth_headers)
        assert r.json()["entry_price_low"] == pytest.approx(20.0 * 0.92, abs=0.01)

    def test_nav_delta_pct_computed(self, auth_headers):
        nav_val = 20.0
        price = 19.0
        db = _make_db(
            nav={"nav": nav_val, "market_price": price, "premium_discount": -5.0},
            last_price=price,
        )
        r = self._post(db, auth_headers)
        expected = (price - nav_val) / nav_val * 100
        assert r.json()["nav_delta_pct"] == pytest.approx(expected, abs=0.01)

    def test_no_nav_returns_none_prices(self, auth_headers):
        db = _make_db(last_price=19.5)  # no nav_data
        r = self._post(db, auth_headers)
        body = r.json()
        assert body["entry_price_low"] is None
        assert body["entry_price_high"] is None


# ---------------------------------------------------------------------------
# 4. CEF NAV-DISCOUNT (5)
# ---------------------------------------------------------------------------

class TestCEFNavDiscount:
    def _post(self, db, auth_headers, ticker="PDI", body=None):
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("CEF")),
                ):
                    r = c.post(f"/entry-price/{ticker}", json=body or {}, headers=auth_headers)
        app.dependency_overrides.clear()
        return r

    def test_entry_method_is_nav_discount(self, auth_headers):
        db = _make_db(nav={"nav": 25.0, "market_price": 23.5, "premium_discount": -6.0}, last_price=23.5)
        r = self._post(db, auth_headers)
        assert r.json()["entry_method"] == "nav_discount"

    def test_entry_price_high_at_8pct_discount(self, auth_headers):
        db = _make_db(nav={"nav": 25.0, "market_price": 23.5, "premium_discount": -6.0}, last_price=23.5)
        r = self._post(db, auth_headers)
        assert r.json()["entry_price_high"] == pytest.approx(25.0 * 0.92, abs=0.01)

    def test_entry_price_low_at_15pct_discount(self, auth_headers):
        db = _make_db(nav={"nav": 25.0, "market_price": 23.5, "premium_discount": -6.0}, last_price=23.5)
        r = self._post(db, auth_headers)
        assert r.json()["entry_price_low"] == pytest.approx(25.0 * 0.85, abs=0.01)

    def test_nav_delta_pct_computed(self, auth_headers):
        nav_val = 25.0
        price = 23.0
        db = _make_db(
            nav={"nav": nav_val, "market_price": price, "premium_discount": -8.0},
            last_price=price,
        )
        r = self._post(db, auth_headers)
        expected = (price - nav_val) / nav_val * 100
        assert r.json()["nav_delta_pct"] == pytest.approx(expected, abs=0.01)

    def test_no_nav_returns_none_prices(self, auth_headers):
        db = _make_db(last_price=23.5)
        r = self._post(db, auth_headers)
        body = r.json()
        assert body["entry_price_low"] is None
        assert body["entry_price_high"] is None


# ---------------------------------------------------------------------------
# 5. ETF 4-SIGNAL COMPOSITE SCORE (12)
# ---------------------------------------------------------------------------

def _etf_post(asset_class, db, auth_headers, ticker="JEPI", body=None):
    from app.main import app
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    with patch("app.main.verify_connection", return_value=True):
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            with patch(
                "app.classification.engine.ClassificationEngine.classify",
                new=AsyncMock(return_value=_clf(asset_class)),
            ):
                r = c.post(f"/entry-price/{ticker}", json=body or {}, headers=auth_headers)
    app.dependency_overrides.clear()
    return r


class TestETFEntryScore:
    # --- Attractive zone (score >= 7.5) ---

    def test_attractive_zone_label(self, auth_headers):
        """Low range position + high yield spread → Attractive."""
        db = _make_db(
            features={
                "yield_forward": 0.09,
                "yield_5yr_avg": 0.06,     # +50% spread → score 10
                "price_range_position": 0.20,  # < 0.25 → score 10
            },
            last_price=50.0,
            nav={"nav": 52.0, "market_price": 50.0, "premium_discount": -3.8},
            income_scores={"factor_details": None, "total_score": 8.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        assert r.json()["etf_entry_zone"] == "Attractive"

    def test_attractive_entry_price_low_5pct_discount(self, auth_headers):
        db = _make_db(
            features={
                "yield_forward": 0.09,
                "yield_5yr_avg": 0.06,
                "price_range_position": 0.20,
            },
            last_price=50.0,
            nav={"nav": 52.0, "market_price": 50.0, "premium_discount": -3.8},
            income_scores={"factor_details": None, "total_score": 8.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        body = r.json()
        assert body["entry_price_low"] == pytest.approx(50.0 * 0.95, abs=0.05)

    def test_attractive_entry_price_high_equals_nav(self, auth_headers):
        db = _make_db(
            features={
                "yield_forward": 0.09,
                "yield_5yr_avg": 0.06,
                "price_range_position": 0.20,
            },
            last_price=50.0,
            nav={"nav": 52.0, "market_price": 50.0, "premium_discount": -3.8},
            income_scores={"factor_details": None, "total_score": 8.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        assert r.json()["entry_price_high"] == pytest.approx(52.0, abs=0.01)

    # --- Neutral zone (5.0 <= score < 7.5) ---

    def test_neutral_zone_label(self, auth_headers):
        db = _make_db(
            features={
                "yield_forward": 0.055,
                "yield_5yr_avg": 0.055,    # spread=0 → 6
                "price_range_position": 0.50,  # → 6
            },
            last_price=50.0,
            nav={"nav": 51.0, "market_price": 50.0, "premium_discount": -2.0},
            income_scores={"factor_details": None, "total_score": 5.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        assert r.json()["etf_entry_zone"] == "Neutral"

    def test_neutral_entry_price_low_2pct_discount(self, auth_headers):
        db = _make_db(
            features={
                "yield_forward": 0.055,
                "yield_5yr_avg": 0.055,
                "price_range_position": 0.50,
            },
            last_price=50.0,
            nav={"nav": 51.0, "market_price": 50.0, "premium_discount": -2.0},
            income_scores={"factor_details": None, "total_score": 5.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        assert r.json()["entry_price_low"] == pytest.approx(50.0 * 0.98, abs=0.05)

    # --- Expensive zone (score < 5.0) ---

    def test_expensive_zone_label(self, auth_headers):
        """High range position + low yield spread → Expensive."""
        db = _make_db(
            features={
                "yield_forward": 0.04,
                "yield_5yr_avg": 0.06,    # spread = -33% → score 2
                "price_range_position": 0.90,  # > 0.70 → score 2
                "price_change_pct": 0.15,      # > +10% → score 2
            },
            last_price=55.0,
            nav={"nav": 50.0, "market_price": 55.0, "premium_discount": 10.0},
            income_scores={"factor_details": None, "total_score": 2.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        assert r.json()["etf_entry_zone"] == "Expensive"

    def test_expensive_entry_prices_are_none(self, auth_headers):
        db = _make_db(
            features={
                "yield_forward": 0.04,
                "yield_5yr_avg": 0.06,
                "price_range_position": 0.90,
                "price_change_pct": 0.15,
            },
            last_price=55.0,
            nav={"nav": 50.0, "market_price": 55.0, "premium_discount": 10.0},
            income_scores={"factor_details": None, "total_score": 2.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        body = r.json()
        assert body["entry_price_low"] is None
        assert body["entry_price_high"] is None

    def test_entry_method_is_etf_entry_score(self, auth_headers):
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=50.0,
            income_scores={"factor_details": None, "total_score": 6.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        assert r.json()["entry_method"] == "etf_entry_score"

    def test_etf_score_returned_in_response(self, auth_headers):
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=50.0,
            income_scores={"factor_details": None, "total_score": 6.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        assert r.json()["etf_entry_score"] is not None

    def test_factor_details_used_for_signal1(self, auth_headers):
        """income_scores.factor_details price_range_position score is used for Signal 1."""
        fd = {"price_range_position": {"score": 8.0}}  # 8/8 → 10 on 1-10 scale
        db = _make_db(
            features={"yield_forward": 0.07, "yield_5yr_avg": 0.05},
            last_price=50.0,
            nav={"nav": 52.0, "market_price": 50.0, "premium_discount": -3.8},
            income_scores={"factor_details": fd, "total_score": 9.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        # High signal 1 + positive yield spread → should be Attractive or Neutral
        assert r.json()["etf_entry_zone"] in ("Attractive", "Neutral")

    def test_sma_fallback_when_factor_details_unavailable(self, auth_headers):
        """When factor_details is empty/None, SMA signal uses neutral fallback."""
        db = _make_db(
            features={"yield_forward": 0.07, "yield_5yr_avg": 0.055},
            last_price=50.0,
            nav={"nav": 52.0, "market_price": 50.0, "premium_discount": -3.8},
            income_scores={"factor_details": {}, "total_score": 7.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        # Should not crash; score should be numeric
        body = r.json()
        assert body["etf_entry_score"] is not None
        assert body["etf_entry_zone"] is not None

    def test_no_nav_fallback_to_current_price_ceiling(self, auth_headers):
        """When nav_snapshots unavailable, entry_price_high falls back to current_price."""
        db = _make_db(
            features={
                "yield_forward": 0.09,
                "yield_5yr_avg": 0.06,
                "price_range_position": 0.20,
            },
            last_price=50.0,
            # no nav_data
            income_scores={"factor_details": None, "total_score": 8.0},
        )
        r = _etf_post("ETF", db, auth_headers)
        body = r.json()
        if body["etf_entry_zone"] != "Expensive":
            assert body["entry_price_high"] == pytest.approx(50.0, abs=0.01)


# ---------------------------------------------------------------------------
# 6. POSITION SIZE FROM PORTFOLIO CONSTRAINTS (3)
# ---------------------------------------------------------------------------

class TestPositionSizeConstraints:
    def _post_with_portfolio(self, auth_headers, portfolio, asset_class="CommonStock"):
        pid = str(uuid4())
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=57.0,
            portfolio=portfolio,
        )
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf(asset_class)),
                ):
                    r = c.post(
                        f"/entry-price/O?portfolio_id={pid}",
                        json={},
                        headers=auth_headers,
                    )
        app.dependency_overrides.clear()
        return r

    def test_portfolio_max_position_used(self, auth_headers):
        r = self._post_with_portfolio(
            auth_headers,
            {"target_income_yield_pct": 5.5, "max_position_pct": 3.5},
        )
        assert r.json()["position_size_pct"] == pytest.approx(3.5, abs=0.01)

    def test_body_overrides_max_position(self, auth_headers):
        pid = str(uuid4())
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=57.0,
            portfolio={"target_income_yield_pct": 5.5, "max_position_pct": 3.5},
        )
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("CommonStock")),
                ):
                    r = c.post(
                        f"/entry-price/O?portfolio_id={pid}",
                        json={"max_position_pct": 2.0},
                        headers=auth_headers,
                    )
        app.dependency_overrides.clear()
        assert r.json()["position_size_pct"] == pytest.approx(2.0, abs=0.01)

    def test_default_position_size_when_no_portfolio(self, auth_headers):
        db = _make_db(
            features={"yield_forward": 0.055, "yield_5yr_avg": 0.05},
            last_price=57.0,
        )
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("CommonStock")),
                ):
                    r = c.post("/entry-price/O", json={}, headers=auth_headers)
        app.dependency_overrides.clear()
        # Default is 4.0 from settings
        assert r.json()["position_size_pct"] == pytest.approx(4.0, abs=0.01)


# ---------------------------------------------------------------------------
# 7. GRACEFUL DEGRADATION WHEN NAV UNAVAILABLE (2)
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    def test_bdc_no_nav_returns_200(self, auth_headers):
        db = _make_db(last_price=19.0)  # no nav_data
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("BDC")),
                ):
                    r = c.post("/entry-price/ARCC", json={}, headers=auth_headers)
        app.dependency_overrides.clear()
        assert r.status_code == 200

    def test_cef_no_nav_returns_200(self, auth_headers):
        db = _make_db(last_price=22.0)  # no nav_data
        from app.main import app
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: db
        with patch("app.main.verify_connection", return_value=True):
            from fastapi.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as c:
                with patch(
                    "app.classification.engine.ClassificationEngine.classify",
                    new=AsyncMock(return_value=_clf("CEF")),
                ):
                    r = c.post("/entry-price/PDI", json={}, headers=auth_headers)
        app.dependency_overrides.clear()
        assert r.status_code == 200
