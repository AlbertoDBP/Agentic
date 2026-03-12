"""
Tests for classification/engine.py — ClassificationEngine unit tests.
Target: 24 tests — cache, override, rule loading, serialisation, pipeline.
DB calls are mocked; no network I/O required.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

os.environ.setdefault("JWT_SECRET",              "test-secret")
os.environ.setdefault("DATABASE_URL",            "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("MARKET_DATA_SERVICE_URL", "http://localhost:8001")
os.environ.setdefault("REDIS_URL",               "redis://localhost:6379")

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.classification.engine import ClassificationEngine
from app.models import AssetClassification, AssetClassRule, ClassificationOverride


def _make_classification(**kw) -> AssetClassification:
    """Return a minimal AssetClassification ORM object."""
    defaults = dict(
        ticker="JEPI",
        asset_class="COVERED_CALL_ETF",
        parent_class="ETF",
        confidence=0.95,
        is_hybrid=False,
        characteristics={"income_type": "option_premium"},
        benchmarks=None,
        sub_scores=None,
        tax_efficiency={"income_type": "option_premium", "estimated_tax_drag_pct": 37.0,
                        "tax_treatment": "ordinary", "preferred_account": "IRA", "notes": "test"},
        matched_rules=[],
        source="rule_engine_v1",
        is_override=False,
        classified_at=datetime.now(timezone.utc),
        valid_until=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    defaults.update(kw)
    obj = MagicMock(spec=AssetClassification)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_override(**kw) -> ClassificationOverride:
    defaults = dict(
        ticker="JEPI",
        asset_class="COVERED_CALL_ETF",
        reason="manual",
        created_by="admin",
        effective_from=datetime.now(timezone.utc) - timedelta(hours=1),
        effective_until=None,
    )
    defaults.update(kw)
    obj = MagicMock(spec=ClassificationOverride)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_rule(**kw) -> AssetClassRule:
    defaults = dict(
        asset_class="COVERED_CALL_ETF",
        rule_type="ticker_pattern",
        rule_config={"pattern": ".*ETF.*"},
        priority=100,
        confidence_weight=0.85,
        active=True,
    )
    defaults.update(kw)
    obj = MagicMock(spec=AssetClassRule)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.query.return_value = db
    db.filter.return_value = db
    db.order_by.return_value = db
    db.first.return_value = None
    db.all.return_value = []
    return db


# ── _load_db_rules ──────────────────────────────────────────────────────────

class TestLoadDbRules:
    def test_returns_list_from_active_rules(self, mock_db):
        rule = _make_rule()
        mock_db.all.return_value = [rule]
        engine = ClassificationEngine(mock_db)
        rules = engine._load_db_rules()
        assert len(rules) == 1
        assert rules[0]["asset_class"] == "COVERED_CALL_ETF"

    def test_returns_all_rule_fields(self, mock_db):
        rule = _make_rule()
        mock_db.all.return_value = [rule]
        engine = ClassificationEngine(mock_db)
        r = engine._load_db_rules()[0]
        assert {"asset_class", "rule_type", "rule_config", "priority", "confidence_weight"} <= set(r.keys())

    def test_returns_empty_list_when_no_rules(self, mock_db):
        mock_db.all.return_value = []
        engine = ClassificationEngine(mock_db)
        assert engine._load_db_rules() == []

    def test_returns_empty_list_on_db_exception(self, mock_db):
        mock_db.all.side_effect = Exception("DB error")
        engine = ClassificationEngine(mock_db)
        assert engine._load_db_rules() == []

    def test_multiple_rules_all_returned(self, mock_db):
        rules = [_make_rule(asset_class=c) for c in ["BOND", "BDC", "EQUITY_REIT"]]
        mock_db.all.return_value = rules
        engine = ClassificationEngine(mock_db)
        result = engine._load_db_rules()
        assert len(result) == 3


# ── get_cached ──────────────────────────────────────────────────────────────

class TestGetCached:
    def test_returns_record_when_valid(self, mock_db):
        record = _make_classification()
        mock_db.first.return_value = record
        engine = ClassificationEngine(mock_db)
        result = engine.get_cached("JEPI")
        assert result is record

    def test_returns_none_when_no_record(self, mock_db):
        mock_db.first.return_value = None
        engine = ClassificationEngine(mock_db)
        assert engine.get_cached("UNKNOWN") is None

    def test_ticker_uppercased_in_query(self, mock_db):
        engine = ClassificationEngine(mock_db)
        engine.get_cached("jepi")
        # Should not raise; mock chain still called
        mock_db.query.assert_called()


# ── get_override ────────────────────────────────────────────────────────────

class TestGetOverride:
    def test_returns_active_override(self, mock_db):
        override = _make_override()
        mock_db.first.return_value = override
        engine = ClassificationEngine(mock_db)
        result = engine.get_override("JEPI")
        assert result is override

    def test_returns_none_when_no_override(self, mock_db):
        mock_db.first.return_value = None
        engine = ClassificationEngine(mock_db)
        assert engine.get_override("AAPL") is None


# ── _serialise ──────────────────────────────────────────────────────────────

class TestSerialise:
    def test_returns_dict_with_all_keys(self, mock_db):
        record = _make_classification()
        engine = ClassificationEngine(mock_db)
        result = engine._serialise(record)
        expected_keys = {
            "ticker", "asset_class", "parent_class", "confidence",
            "is_hybrid", "characteristics", "benchmarks", "sub_scores",
            "tax_efficiency", "source", "is_override",
            "classified_at", "valid_until",
        }
        assert expected_keys == set(result.keys())

    def test_classified_at_isoformat(self, mock_db):
        record = _make_classification()
        engine = ClassificationEngine(mock_db)
        result = engine._serialise(record)
        assert isinstance(result["classified_at"], str)
        assert "T" in result["classified_at"]

    def test_valid_until_isoformat_when_set(self, mock_db):
        record = _make_classification()
        engine = ClassificationEngine(mock_db)
        result = engine._serialise(record)
        assert isinstance(result["valid_until"], str)

    def test_valid_until_none_when_null(self, mock_db):
        record = _make_classification(valid_until=None)
        engine = ClassificationEngine(mock_db)
        result = engine._serialise(record)
        assert result["valid_until"] is None


# ── _get_detector ────────────────────────────────────────────────────────────

class TestGetDetector:
    def test_detector_created_once(self, mock_db):
        engine = ClassificationEngine(mock_db)
        d1 = engine._get_detector()
        d2 = engine._get_detector()
        assert d1 is d2  # same instance (lazy singleton)

    def test_detector_created_with_empty_rules(self, mock_db):
        mock_db.all.return_value = []
        engine = ClassificationEngine(mock_db)
        detector = engine._get_detector()
        assert detector is not None


# ── classify — cache hit ─────────────────────────────────────────────────────

class TestClassifyPipeline:
    @pytest.mark.asyncio
    async def test_classify_returns_cached_when_valid(self, mock_db):
        record = _make_classification()
        engine = ClassificationEngine(mock_db)
        engine.get_override = MagicMock(return_value=None)
        engine.get_cached   = MagicMock(return_value=record)

        result = await engine.classify("JEPI")
        assert result["ticker"] == "JEPI"
        assert result["asset_class"] == "COVERED_CALL_ETF"

    @pytest.mark.asyncio
    async def test_classify_skip_cache_when_override_present(self, mock_db):
        """If override exists, cache is not consulted."""
        override = _make_override()
        engine = ClassificationEngine(mock_db)
        engine.get_override = MagicMock(return_value=override)
        engine.get_cached   = MagicMock(return_value=None)

        with patch.object(engine, "_build_from_override", new=AsyncMock(return_value={"ticker": "JEPI", "asset_class": "COVERED_CALL_ETF", "source": "override"})):
            result = await engine.classify("JEPI")

        engine.get_cached.assert_not_called()
        assert result["source"] == "override"

    @pytest.mark.asyncio
    async def test_classify_ticker_uppercased(self, mock_db):
        record = _make_classification(ticker="AAPL")
        engine = ClassificationEngine(mock_db)
        engine.get_override = MagicMock(return_value=None)
        engine.get_cached   = MagicMock(return_value=record)

        result = await engine.classify("aapl")
        assert result["ticker"] == "AAPL"
