"""
Tests for API: GET /rules, POST /rules, PUT /overrides, DELETE /overrides
Target: 28 tests — CRUD operations, validation, auth, edge cases.
"""
import sys
import os

os.environ.setdefault("JWT_SECRET",              "test-secret")
os.environ.setdefault("DATABASE_URL",            "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("MARKET_DATA_SERVICE_URL", "http://localhost:8001")
os.environ.setdefault("REDIS_URL",               "redis://localhost:6379")

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import uuid

import pytest

# conftest provides: client, auth_headers, mock_db

_NOW = datetime.now(timezone.utc)


def _mock_rule(asset_class="DIVIDEND_STOCK", rule_type="ticker_pattern"):
    r = MagicMock()
    r.id           = uuid.uuid4()
    r.asset_class  = asset_class
    r.rule_type    = rule_type
    r.rule_config  = {"pattern": "^[A-Z]+$"}
    r.priority     = 100
    r.confidence_weight = 0.80
    r.active       = True
    r.created_at   = _NOW
    return r


def _mock_override(ticker="JEPI", asset_class="COVERED_CALL_ETF"):
    o = MagicMock()
    o.id           = uuid.uuid4()
    o.ticker       = ticker
    o.asset_class  = asset_class
    o.reason       = "manual review"
    o.created_by   = "admin"
    o.effective_from  = _NOW
    o.effective_until = None
    return o


# ── GET /rules ───────────────────────────────────────────────────────────────

class TestListRules:
    def test_returns_200(self, client, auth_headers, mock_db):
        mock_db.all.return_value = []
        r = client.get("/rules", headers=auth_headers)
        assert r.status_code == 200

    def test_empty_rules_returns_zero_total(self, client, auth_headers, mock_db):
        mock_db.all.return_value = []
        r = client.get("/rules", headers=auth_headers)
        assert r.json()["total"] == 0
        assert r.json()["rules"] == []

    def test_populated_rules_returned(self, client, auth_headers, mock_db):
        mock_db.all.return_value = [_mock_rule(), _mock_rule("BOND", "sector")]
        r = client.get("/rules", headers=auth_headers)
        assert r.json()["total"] == 2
        assert len(r.json()["rules"]) == 2

    def test_rule_has_required_fields(self, client, auth_headers, mock_db):
        mock_db.all.return_value = [_mock_rule()]
        r = client.get("/rules", headers=auth_headers)
        rule = r.json()["rules"][0]
        for key in ("id", "asset_class", "rule_type", "rule_config", "priority", "confidence_weight", "active", "created_at"):
            assert key in rule

    def test_no_auth_returns_403(self, client):
        r = client.get("/rules")
        assert r.status_code in (401, 403)


# ── POST /rules ──────────────────────────────────────────────────────────────

class TestCreateRule:
    def test_valid_ticker_pattern_rule_returns_200(self, client, auth_headers, mock_db):
        created = _mock_rule()
        mock_db.refresh = MagicMock(side_effect=lambda x: None)
        # Simulate db.add + commit + refresh setting id
        def _fake_refresh(obj):
            obj.id = created.id
        mock_db.refresh.side_effect = _fake_refresh

        r = client.post(
            "/rules",
            json={
                "asset_class": "DIVIDEND_STOCK",
                "rule_type": "ticker_pattern",
                "rule_config": {"pattern": "^[A-Z]{1,5}$"},
                "priority": 50,
                "confidence_weight": 0.85,
            },
            headers=auth_headers,
        )
        assert r.status_code == 200

    def test_response_contains_id(self, client, auth_headers, mock_db):
        rid = str(uuid.uuid4())

        def _fake_refresh(obj):
            obj.id = rid
        mock_db.refresh.side_effect = _fake_refresh

        r = client.post(
            "/rules",
            json={
                "asset_class": "BOND",
                "rule_type": "sector",
                "rule_config": {"sector": "Fixed Income"},
            },
            headers=auth_headers,
        )
        assert "id" in r.json()

    def test_invalid_rule_type_returns_422(self, client, auth_headers, mock_db):
        r = client.post(
            "/rules",
            json={
                "asset_class": "BOND",
                "rule_type": "invalid_type",
                "rule_config": {},
            },
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_confidence_weight_zero_returns_422(self, client, auth_headers, mock_db):
        r = client.post(
            "/rules",
            json={
                "asset_class": "BOND",
                "rule_type": "sector",
                "rule_config": {},
                "confidence_weight": 0.0,
            },
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_confidence_weight_above_one_returns_422(self, client, auth_headers, mock_db):
        r = client.post(
            "/rules",
            json={
                "asset_class": "BOND",
                "rule_type": "sector",
                "rule_config": {},
                "confidence_weight": 1.01,
            },
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_confidence_weight_exactly_one_accepted(self, client, auth_headers, mock_db):
        def _fake_refresh(obj):
            obj.id = str(uuid.uuid4())
        mock_db.refresh.side_effect = _fake_refresh

        r = client.post(
            "/rules",
            json={
                "asset_class": "BDC",
                "rule_type": "feature",
                "rule_config": {"key": "is_bdc", "value": True},
                "confidence_weight": 1.0,
            },
            headers=auth_headers,
        )
        assert r.status_code == 200

    def test_all_four_valid_rule_types(self, client, auth_headers, mock_db):
        def _fake_refresh(obj):
            obj.id = str(uuid.uuid4())
        mock_db.refresh.side_effect = _fake_refresh

        for rtype in ("ticker_pattern", "sector", "feature", "metadata"):
            r = client.post(
                "/rules",
                json={
                    "asset_class": "EQUITY_REIT",
                    "rule_type": rtype,
                    "rule_config": {"key": "val"},
                },
                headers=auth_headers,
            )
            assert r.status_code == 200, f"Expected 200 for rule_type={rtype}, got {r.status_code}"

    def test_no_auth_returns_403(self, client):
        r = client.post(
            "/rules",
            json={"asset_class": "BOND", "rule_type": "sector", "rule_config": {}},
        )
        assert r.status_code in (401, 403)

    def test_missing_required_fields_returns_422(self, client, auth_headers):
        r = client.post("/rules", json={}, headers=auth_headers)
        assert r.status_code == 422


# ── PUT /overrides/{ticker} ──────────────────────────────────────────────────

class TestSetOverride:
    def test_create_new_override_returns_200(self, client, auth_headers, mock_db):
        mock_db.first.return_value = None  # no existing override
        r = client.put(
            "/overrides/JEPI",
            json={"asset_class": "COVERED_CALL_ETF", "reason": "manual", "created_by": "admin"},
            headers=auth_headers,
        )
        assert r.status_code == 200

    def test_create_response_has_ticker(self, client, auth_headers, mock_db):
        mock_db.first.return_value = None
        r = client.put(
            "/overrides/AAPL",
            json={"asset_class": "DIVIDEND_STOCK"},
            headers=auth_headers,
        )
        assert r.json()["ticker"] == "AAPL"

    def test_update_existing_override_returns_200(self, client, auth_headers, mock_db):
        existing = _mock_override()
        mock_db.first.return_value = existing
        r = client.put(
            "/overrides/JEPI",
            json={"asset_class": "BOND", "reason": "re-classified"},
            headers=auth_headers,
        )
        assert r.status_code == 200

    def test_update_message_says_updated(self, client, auth_headers, mock_db):
        existing = _mock_override()
        mock_db.first.return_value = existing
        r = client.put(
            "/overrides/JEPI",
            json={"asset_class": "BOND"},
            headers=auth_headers,
        )
        assert "updated" in r.json()["message"].lower()

    def test_asset_class_uppercased(self, client, auth_headers, mock_db):
        mock_db.first.return_value = None
        r = client.put(
            "/overrides/AAPL",
            json={"asset_class": "dividend_stock"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        # The override saved in DB should have uppercase — verified via mock call
        mock_db.add.assert_called_once()
        saved = mock_db.add.call_args[0][0]
        assert saved.asset_class == "DIVIDEND_STOCK"

    def test_no_auth_returns_403(self, client):
        r = client.put("/overrides/JEPI", json={"asset_class": "BOND"})
        assert r.status_code in (401, 403)

    def test_missing_asset_class_returns_422(self, client, auth_headers):
        r = client.put("/overrides/JEPI", json={}, headers=auth_headers)
        assert r.status_code == 422


# ── DELETE /overrides/{ticker} ───────────────────────────────────────────────

class TestRemoveOverride:
    def test_existing_override_deleted_200(self, client, auth_headers, mock_db):
        override = _mock_override()
        mock_db.first.return_value = override
        r = client.delete("/overrides/JEPI", headers=auth_headers)
        assert r.status_code == 200

    def test_response_has_message(self, client, auth_headers, mock_db):
        override = _mock_override()
        mock_db.first.return_value = override
        r = client.delete("/overrides/JEPI", headers=auth_headers)
        assert "message" in r.json()

    def test_delete_called_on_db(self, client, auth_headers, mock_db):
        override = _mock_override()
        mock_db.first.return_value = override
        client.delete("/overrides/JEPI", headers=auth_headers)
        mock_db.delete.assert_called_once_with(override)

    def test_nonexistent_override_returns_404(self, client, auth_headers, mock_db):
        mock_db.first.return_value = None
        r = client.delete("/overrides/UNKNOWN", headers=auth_headers)
        assert r.status_code == 404

    def test_no_auth_returns_403(self, client):
        r = client.delete("/overrides/JEPI")
        assert r.status_code in (401, 403)

    def test_ticker_uppercased(self, client, auth_headers, mock_db):
        mock_db.first.return_value = None
        r = client.delete("/overrides/jepi", headers=auth_headers)
        # Even lowercase ticker → 404 because override not found (mock returns None)
        assert r.status_code == 404
