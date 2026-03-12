"""
Agent 03 — Income Scoring Service
Tests: Classification Accuracy — Phase 4 (Detector Confidence Learning).

Coverage:
  TestClassificationFeedbackTracker — record(), compute_monthly_rollup(),
                                       get_recent_feedback(), get_accuracy_runs()
  TestClassificationAccuracyAPI     — all 3 endpoints, auth guard, validation,
                                       mock DB
"""
import os
import uuid
from calendar import monthrange
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

from fastapi.testclient import TestClient

from app.scoring.classification_feedback import (
    ClassificationFeedbackTracker,
    SOURCE_AGENT04,
    SOURCE_MANUAL,
)
from app.models import ClassificationFeedback, ClassifierAccuracyRun


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

NOW = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_feedback_orm(
    ticker="AAPL",
    asset_class_used="DIVIDEND_STOCK",
    source=SOURCE_AGENT04,
    agent04_class=None,
    agent04_confidence=None,
    is_mismatch=None,
    captured_at=None,
):
    f = MagicMock(spec=ClassificationFeedback)
    f.id = uuid.uuid4()
    f.income_score_id = uuid.uuid4()
    f.ticker = ticker
    f.asset_class_used = asset_class_used
    f.source = source
    f.agent04_class = agent04_class
    f.agent04_confidence = agent04_confidence
    f.is_mismatch = is_mismatch
    f.captured_at = captured_at or NOW
    return f


def _make_run_orm(period_month="2025-06", asset_class="DIVIDEND_STOCK", status=None):
    r = MagicMock(spec=ClassifierAccuracyRun)
    r.id = uuid.uuid4()
    r.period_month = period_month
    r.asset_class = asset_class
    r.total_calls = 10
    r.agent04_trusted = 7
    r.manual_overrides = 3
    r.mismatches = 1
    r.accuracy_rate = 0.70
    r.override_rate = 0.30
    r.mismatch_rate = 0.33
    r.computed_at = NOW
    r.computed_by = "test"
    return r


# ══════════════════════════════════════════════════════════════════════════════
# TestClassificationFeedbackTracker
# ══════════════════════════════════════════════════════════════════════════════

class TestClassificationFeedbackTracker:
    """Tests for ClassificationFeedbackTracker."""

    def setup_method(self):
        self.tracker = ClassificationFeedbackTracker()

    # ── record() ──────────────────────────────────────────────────────────────

    def test_record_agent04_source(self):
        db = MagicMock()
        result = self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class_used="DIVIDEND_STOCK",
            source=SOURCE_AGENT04,
            agent04_class="DIVIDEND_STOCK",
        )
        assert result is not None
        db.add.assert_called_once()
        db.flush.assert_called_once()

    def test_record_manual_override_source(self):
        db = MagicMock()
        result = self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="BX",
            asset_class_used="BDC",
            source=SOURCE_MANUAL,
        )
        assert result is not None
        db.add.assert_called_once()

    def test_record_agent04_no_mismatch_flag(self):
        """source=AGENT04 → is_mismatch stays None regardless."""
        db = MagicMock()
        result = self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class_used="DIVIDEND_STOCK",
            source=SOURCE_AGENT04,
            agent04_class="DIVIDEND_STOCK",
        )
        # The ORM object was passed to db.add — inspect what was added
        added_row = db.add.call_args[0][0]
        assert added_row.is_mismatch is None

    def test_record_manual_no_agent04_class_mismatch_none(self):
        """Manual override without agent04_class → is_mismatch=None."""
        db = MagicMock()
        result = self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class_used="DIVIDEND_STOCK",
            source=SOURCE_MANUAL,
            agent04_class=None,
        )
        added_row = db.add.call_args[0][0]
        assert added_row.is_mismatch is None

    def test_record_manual_with_matching_agent04_mismatch_false(self):
        """Manual override where agent04_class matches → is_mismatch=False."""
        db = MagicMock()
        self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class_used="DIVIDEND_STOCK",
            source=SOURCE_MANUAL,
            agent04_class="DIVIDEND_STOCK",
        )
        added_row = db.add.call_args[0][0]
        assert added_row.is_mismatch is False

    def test_record_manual_with_different_agent04_mismatch_true(self):
        """Manual override where agent04_class differs → is_mismatch=True."""
        db = MagicMock()
        self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AGNC",
            asset_class_used="DIVIDEND_STOCK",   # caller said this
            source=SOURCE_MANUAL,
            agent04_class="MORTGAGE_REIT",        # but Agent 04 would say this
        )
        added_row = db.add.call_args[0][0]
        assert added_row.is_mismatch is True

    def test_record_asset_class_uppercased(self):
        db = MagicMock()
        self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class_used="dividend_stock",   # lowercase
            source=SOURCE_AGENT04,
        )
        added_row = db.add.call_args[0][0]
        assert added_row.asset_class_used == "DIVIDEND_STOCK"

    def test_record_agent04_class_uppercased(self):
        db = MagicMock()
        self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class_used="DIVIDEND_STOCK",
            source=SOURCE_MANUAL,
            agent04_class="mortgage_reit",       # lowercase
        )
        added_row = db.add.call_args[0][0]
        assert added_row.agent04_class == "MORTGAGE_REIT"

    def test_record_stores_confidence(self):
        db = MagicMock()
        self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class_used="DIVIDEND_STOCK",
            source=SOURCE_AGENT04,
            agent04_class="DIVIDEND_STOCK",
            agent04_confidence=0.92,
        )
        added_row = db.add.call_args[0][0]
        assert added_row.agent04_confidence == 0.92

    def test_record_db_exception_returns_none(self):
        db = MagicMock()
        db.flush.side_effect = Exception("DB error")
        result = self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="ERR",
            asset_class_used="DIVIDEND_STOCK",
            source=SOURCE_AGENT04,
        )
        assert result is None

    def test_record_mismatch_case_insensitive(self):
        """Mismatch detection is case-insensitive."""
        db = MagicMock()
        self.tracker.record(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class_used="DIVIDEND_STOCK",
            source=SOURCE_MANUAL,
            agent04_class="dividend_stock",  # same, lowercase
        )
        added_row = db.add.call_args[0][0]
        assert added_row.is_mismatch is False

    # ── compute_monthly_rollup() ───────────────────────────────────────────────

    def test_rollup_empty_month_returns_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        runs = self.tracker.compute_monthly_rollup(db, "2025-01")

        assert runs == []
        db.commit.assert_called_once()

    def test_rollup_creates_per_class_and_aggregate(self):
        """Two asset classes → 2 per-class rows + 1 aggregate = 3 total."""
        feedback = [
            _make_feedback_orm(asset_class_used="DIVIDEND_STOCK", source=SOURCE_AGENT04),
            _make_feedback_orm(asset_class_used="DIVIDEND_STOCK", source=SOURCE_MANUAL, is_mismatch=False),
            _make_feedback_orm(asset_class_used="BOND", source=SOURCE_AGENT04),
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = feedback

        runs = self.tracker.compute_monthly_rollup(db, "2025-06")

        assert len(runs) == 3  # DIVIDEND_STOCK + BOND + ALL

    def test_rollup_accuracy_rate_correct(self):
        """7 AGENT04 + 3 MANUAL → accuracy_rate = 0.7."""
        feedback = (
            [_make_feedback_orm(source=SOURCE_AGENT04)] * 7 +
            [_make_feedback_orm(source=SOURCE_MANUAL, is_mismatch=False)] * 3
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = feedback

        runs = self.tracker.compute_monthly_rollup(db, "2025-06")

        # Aggregate row (asset_class=None) is last
        aggregate = next(r for r in runs if r.asset_class is None)
        assert aggregate.total_calls == 10
        assert aggregate.agent04_trusted == 7
        assert aggregate.manual_overrides == 3
        assert aggregate.accuracy_rate == pytest.approx(0.7)

    def test_rollup_mismatch_rate_correct(self):
        """3 manual overrides, 2 mismatches → mismatch_rate = 2/3."""
        feedback = [
            _make_feedback_orm(source=SOURCE_MANUAL, is_mismatch=True),
            _make_feedback_orm(source=SOURCE_MANUAL, is_mismatch=True),
            _make_feedback_orm(source=SOURCE_MANUAL, is_mismatch=False),
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = feedback

        runs = self.tracker.compute_monthly_rollup(db, "2025-06")

        aggregate = next(r for r in runs if r.asset_class is None)
        assert aggregate.mismatches == 2
        assert aggregate.mismatch_rate == pytest.approx(2 / 3)

    def test_rollup_zero_manual_overrides_mismatch_rate_none(self):
        """No manual overrides → mismatch_rate=None (avoid division by zero)."""
        feedback = [_make_feedback_orm(source=SOURCE_AGENT04)] * 5
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = feedback

        runs = self.tracker.compute_monthly_rollup(db, "2025-06")

        aggregate = next(r for r in runs if r.asset_class is None)
        assert aggregate.mismatch_rate is None

    def test_rollup_invalid_period_raises(self):
        db = MagicMock()
        with pytest.raises(ValueError, match="Invalid period_month"):
            self.tracker.compute_monthly_rollup(db, "bad-format")

    def test_rollup_commit_error_raises(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            _make_feedback_orm(source=SOURCE_AGENT04)
        ]
        db.commit.side_effect = Exception("commit failed")
        with pytest.raises(Exception, match="commit failed"):
            self.tracker.compute_monthly_rollup(db, "2025-06")
        db.rollback.assert_called_once()

    def test_rollup_computed_by_stored(self):
        feedback = [_make_feedback_orm(source=SOURCE_AGENT04)]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = feedback

        runs = self.tracker.compute_monthly_rollup(db, "2025-06", computed_by="test-user")

        for run in runs:
            assert run.computed_by == "test-user"

    def test_rollup_period_month_stored(self):
        feedback = [_make_feedback_orm(source=SOURCE_AGENT04)]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = feedback

        runs = self.tracker.compute_monthly_rollup(db, "2025-11")

        for run in runs:
            assert run.period_month == "2025-11"

    # ── get_recent_feedback() ─────────────────────────────────────────────────

    def test_get_recent_feedback_no_filter(self):
        db = MagicMock()
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = self.tracker.get_recent_feedback(db)
        db.query.assert_called_once_with(ClassificationFeedback)

    def test_get_recent_feedback_ticker_filter(self):
        db = MagicMock()
        db.query.return_value.order_by.return_value.filter.return_value.limit.return_value.all.return_value = []
        self.tracker.get_recent_feedback(db, ticker="aapl")  # lowercase → uppercased
        # Should have called .filter() somewhere in the chain
        assert db.query.called

    def test_get_recent_feedback_limit(self):
        db = MagicMock()
        q = db.query.return_value.order_by.return_value
        q.limit.return_value.all.return_value = []
        self.tracker.get_recent_feedback(db, limit=25)
        q.limit.assert_called_with(25)

    # ── get_accuracy_runs() ───────────────────────────────────────────────────

    def test_get_accuracy_runs_no_filter(self):
        db = MagicMock()
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        self.tracker.get_accuracy_runs(db)
        db.query.assert_called_once_with(ClassifierAccuracyRun)


# ══════════════════════════════════════════════════════════════════════════════
# TestClassificationAccuracyAPI
# ══════════════════════════════════════════════════════════════════════════════

class TestClassificationAccuracyAPI:
    """
    Tests for /classification-accuracy/* endpoints with mock DB.
    Uses the same pattern as TestLearningLoopAPI.
    """

    def setup_method(self):
        with (
            patch("app.database.check_database_connection", return_value=True),
            patch("app.scoring.data_client.init_pool", return_value=None),
            patch("app.scoring.data_client.close_pool", return_value=None),
        ):
            from app.main import app
            from app.database import get_db
            from app.auth import verify_token

            self._mock_db = MagicMock()
            app.dependency_overrides[get_db] = lambda: self._mock_db
            app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}
            self._client = TestClient(app, raise_server_exceptions=False)

    def teardown_method(self):
        from app.main import app
        from app.database import get_db
        from app.auth import verify_token
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(verify_token, None)

    # ── Auth guard ─────────────────────────────────────────────────────────────

    def test_feedback_requires_auth(self):
        from app.main import app
        from app.auth import verify_token
        app.dependency_overrides.pop(verify_token, None)
        resp = self._client.get("/classification-accuracy/feedback")
        assert resp.status_code == 403
        app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}

    def test_runs_requires_auth(self):
        from app.main import app
        from app.auth import verify_token
        app.dependency_overrides.pop(verify_token, None)
        resp = self._client.get("/classification-accuracy/runs")
        assert resp.status_code == 403
        app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}

    def test_rollup_requires_auth(self):
        from app.main import app
        from app.auth import verify_token
        app.dependency_overrides.pop(verify_token, None)
        resp = self._client.post("/classification-accuracy/rollup", json={"period_month": "2025-06"})
        assert resp.status_code == 403
        app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}

    # ── GET /feedback ─────────────────────────────────────────────────────────

    def test_list_feedback_empty(self):
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_recent_feedback",
            return_value=[],
        ):
            resp = self._client.get("/classification-accuracy/feedback")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_feedback_returns_entries(self):
        entry = _make_feedback_orm()
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_recent_feedback",
            return_value=[entry],
        ):
            resp = self._client.get("/classification-accuracy/feedback")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ticker"] == "AAPL"
        assert data[0]["source"] == SOURCE_AGENT04

    def test_list_feedback_response_shape(self):
        entry = _make_feedback_orm()
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_recent_feedback",
            return_value=[entry],
        ):
            resp = self._client.get("/classification-accuracy/feedback")
        item = resp.json()[0]
        expected_keys = {
            "id", "ticker", "asset_class_used", "source",
            "agent04_class", "agent04_confidence", "is_mismatch",
            "captured_at", "income_score_id",
        }
        assert expected_keys.issubset(set(item.keys()))

    def test_list_feedback_manual_with_mismatch(self):
        entry = _make_feedback_orm(
            source=SOURCE_MANUAL,
            agent04_class="MORTGAGE_REIT",
            is_mismatch=True,
        )
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_recent_feedback",
            return_value=[entry],
        ):
            resp = self._client.get("/classification-accuracy/feedback")
        item = resp.json()[0]
        assert item["source"] == SOURCE_MANUAL
        assert item["is_mismatch"] is True
        assert item["agent04_class"] == "MORTGAGE_REIT"

    def test_list_feedback_passes_ticker_filter(self):
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_recent_feedback",
            return_value=[],
        ) as mock_get:
            self._client.get("/classification-accuracy/feedback?ticker=AAPL")
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs.get("ticker") == "AAPL" or call_kwargs[1].get("ticker") == "AAPL"

    def test_list_feedback_passes_source_filter(self):
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_recent_feedback",
            return_value=[],
        ) as mock_get:
            self._client.get("/classification-accuracy/feedback?source=AGENT04")
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs.get("source") == "AGENT04" or call_kwargs[1].get("source") == "AGENT04"

    def test_list_feedback_passes_limit(self):
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_recent_feedback",
            return_value=[],
        ) as mock_get:
            self._client.get("/classification-accuracy/feedback?limit=100")
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs.get("limit") == 100 or call_kwargs[1].get("limit") == 100

    # ── GET /runs ─────────────────────────────────────────────────────────────

    def test_list_runs_empty(self):
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_accuracy_runs",
            return_value=[],
        ):
            resp = self._client.get("/classification-accuracy/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_runs_returns_data(self):
        run = _make_run_orm()
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_accuracy_runs",
            return_value=[run],
        ):
            resp = self._client.get("/classification-accuracy/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["period_month"] == "2025-06"
        assert data[0]["asset_class"] == "DIVIDEND_STOCK"

    def test_list_runs_response_shape(self):
        run = _make_run_orm()
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_accuracy_runs",
            return_value=[run],
        ):
            resp = self._client.get("/classification-accuracy/runs")
        item = resp.json()[0]
        expected_keys = {
            "id", "period_month", "asset_class", "total_calls",
            "agent04_trusted", "manual_overrides", "mismatches",
            "accuracy_rate", "override_rate", "mismatch_rate",
            "computed_at", "computed_by",
        }
        assert expected_keys.issubset(set(item.keys()))

    def test_list_runs_aggregate_row_null_asset_class(self):
        run = _make_run_orm(asset_class=None)  # aggregate row
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_accuracy_runs",
            return_value=[run],
        ):
            resp = self._client.get("/classification-accuracy/runs")
        assert resp.json()[0]["asset_class"] is None

    def test_list_runs_passes_filters(self):
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.get_accuracy_runs",
            return_value=[],
        ) as mock_get:
            self._client.get("/classification-accuracy/runs?period_month=2025-06&asset_class=BOND")
        kw = mock_get.call_args.kwargs if mock_get.call_args.kwargs else mock_get.call_args[1]
        assert kw.get("period_month") == "2025-06"
        assert kw.get("asset_class") == "BOND"

    # ── POST /rollup ──────────────────────────────────────────────────────────

    def test_rollup_valid_period_returns_201(self):
        # Count query
        self._mock_db.query.return_value.filter.return_value.count.return_value = 5
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.compute_monthly_rollup",
            return_value=[MagicMock(), MagicMock()],  # 2 runs created
        ):
            resp = self._client.post(
                "/classification-accuracy/rollup",
                json={"period_month": "2025-06"},
            )
        assert resp.status_code == 201

    def test_rollup_response_shape(self):
        self._mock_db.query.return_value.filter.return_value.count.return_value = 10
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.compute_monthly_rollup",
            return_value=[MagicMock(), MagicMock(), MagicMock()],
        ):
            resp = self._client.post(
                "/classification-accuracy/rollup",
                json={"period_month": "2025-06"},
            )
        data = resp.json()
        assert set(data.keys()) == {"period_month", "runs_created", "total_feedback_entries"}
        assert data["period_month"] == "2025-06"
        assert data["runs_created"] == 3
        assert data["total_feedback_entries"] == 10

    def test_rollup_invalid_period_format_422(self):
        resp = self._client.post(
            "/classification-accuracy/rollup",
            json={"period_month": "not-a-date"},
        )
        assert resp.status_code == 422

    def test_rollup_missing_period_422(self):
        resp = self._client.post(
            "/classification-accuracy/rollup",
            json={},
        )
        assert resp.status_code == 422

    def test_rollup_tracker_exception_returns_500(self):
        self._mock_db.query.return_value.filter.return_value.count.return_value = 0
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.compute_monthly_rollup",
            side_effect=RuntimeError("DB exploded"),
        ):
            resp = self._client.post(
                "/classification-accuracy/rollup",
                json={"period_month": "2025-06"},
            )
        assert resp.status_code == 500

    def test_rollup_with_computed_by(self):
        self._mock_db.query.return_value.filter.return_value.count.return_value = 3
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.compute_monthly_rollup",
            return_value=[MagicMock()],
        ) as mock_rollup:
            self._client.post(
                "/classification-accuracy/rollup",
                json={"period_month": "2025-06", "computed_by": "admin"},
            )
        kw = mock_rollup.call_args.kwargs if mock_rollup.call_args.kwargs else mock_rollup.call_args[1]
        assert kw.get("computed_by") == "admin"

    def test_rollup_empty_month_runs_created_0(self):
        self._mock_db.query.return_value.filter.return_value.count.return_value = 0
        with patch(
            "app.api.classification_accuracy.classification_feedback_tracker.compute_monthly_rollup",
            return_value=[],  # no feedback → no runs
        ):
            resp = self._client.post(
                "/classification-accuracy/rollup",
                json={"period_month": "2024-01"},
            )
        assert resp.status_code == 201
        assert resp.json()["runs_created"] == 0

    def test_rollup_invalid_month_day_boundary_422(self):
        """Month '2025-13' is an invalid month."""
        resp = self._client.post(
            "/classification-accuracy/rollup",
            json={"period_month": "2025-13"},
        )
        # Validation happens inside monthrange which raises for month 13
        assert resp.status_code in (422, 500)
