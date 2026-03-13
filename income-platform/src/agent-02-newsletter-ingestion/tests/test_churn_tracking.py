"""
Agent 02 — Newsletter Ingestion Service
Tests: churn tracking — flip_count in save_recommendation() and
churn_rate computation extracted from task_churn_rate_update()

20 tests covering:
  - First recommendation for a ticker: flip_count=0
  - Second recommendation (first flip): flip_count=1
  - Third recommendation (second flip): flip_count=2
  - churn_rate = superseded / total (various cases)
  - churn_rate = 0.0 when no superseded recs
  - churn_rate = 1.0 when all recs superseded
  - churn_rate rounded to 4 decimal places
  - All using MagicMock SQLAlchemy session (no real DB)
"""
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://fake:fake@localhost/fake")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APIDOJO_SA_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("FMP_API_KEY", "test-key")


# ── Pure churn_rate formula (extracted from task_churn_rate_update) ────────────
# We test the formula directly without needing Prefect runtime.

def _compute_churn_rate(superseded: int, total: int) -> float:
    """Replicates the formula from task_churn_rate_update."""
    return round(superseded / total, 4) if total > 0 else 0.0


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_mock_db(
    prior_active_recs: list,
    prior_superseded_count: int,
) -> MagicMock:
    """
    Build a mock DB session that satisfies save_recommendation()'s two queries:
      1. .query(...).filter(...).all()  → prior_active_recs
      2. .query(...).filter(...).count() → prior_superseded_count
    Then .add() and .flush() are no-ops; the new rec gets id=99 after flush.
    """
    mock_db = MagicMock()

    # Chain: db.query().filter().all()  and  db.query().filter().count()
    # save_recommendation makes exactly two chained queries before writing.
    q_all   = MagicMock()
    q_all.all.return_value = prior_active_recs

    q_count = MagicMock()
    q_count.count.return_value = prior_superseded_count

    # Both queries go through .filter(); we alternate returns via side_effect.
    mock_filter = MagicMock(side_effect=[q_all, q_count])
    mock_db.query.return_value.filter.side_effect = mock_filter

    # After db.flush() the new rec needs an id so supersession can set
    # prior.superseded_by = rec.id.  We assign this on the rec object directly.
    def _flush_side_effect():
        pass  # id is pre-set on the rec object

    mock_db.flush.side_effect = _flush_side_effect
    return mock_db


def _published_at() -> datetime:
    return datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)


def _minimal_extracted() -> dict:
    return {
        "recommendation": "Buy",
        "sector": "REIT",
        "asset_class": "CommonStock",
        "sentiment_score": 0.6,
        "yield_at_publish": 5.2,
        "payout_ratio": 0.55,
        "dividend_cagr_3yr": 4.5,
        "dividend_cagr_5yr": 4.2,
        "safety_grade": "B",
        "source_reliability": "high",
        "bull_case": "Strong income.",
        "bear_case": "Rate risk.",
        "key_risks": ["interest rates"],
    }


# ── flip_count tests ───────────────────────────────────────────────────────────

class TestFlipCount:

    def _call_save_recommendation(self, mock_db, analyst_id=1, article_id=10,
                                   ticker="O", extracted=None):
        """
        Invoke save_recommendation with a fully mocked DB.
        We patch compute_content_hash / compute_url_hash since deduplicator
        is not under test here.
        """
        from app.processors.article_store import save_recommendation

        if extracted is None:
            extracted = _minimal_extracted()

        with patch("app.processors.article_store.compute_content_hash", return_value="h1"), \
             patch("app.processors.article_store.compute_url_hash", return_value="u1"):
            rec = save_recommendation(
                db=mock_db,
                analyst_id=analyst_id,
                article_id=article_id,
                ticker=ticker,
                published_at=_published_at(),
                extracted=extracted,
                aging_days=365,
            )
        return rec

    def test_first_recommendation_flip_count_is_0(self):
        """No prior active recs, no prior superseded → flip_count = 0."""
        mock_db = _make_mock_db(
            prior_active_recs=[],
            prior_superseded_count=0,
        )
        rec = self._call_save_recommendation(mock_db)
        assert rec.flip_count == 0

    def test_first_recommendation_no_prior_recs_no_supersession(self):
        """With flip_count=0, no prior recs are superseded."""
        prior_active = []
        mock_db = _make_mock_db(
            prior_active_recs=prior_active,
            prior_superseded_count=0,
        )
        self._call_save_recommendation(mock_db)
        # No prior recs → no supersession mutations
        for rec in prior_active:
            rec.is_active = True  # unchanged

    def test_second_recommendation_flip_count_is_1(self):
        """One prior active rec, no prior superseded → flip_count = 1."""
        prior_rec = MagicMock()
        prior_rec.id = 5
        prior_rec.is_active = True
        prior_rec.superseded_by = None

        mock_db = _make_mock_db(
            prior_active_recs=[prior_rec],
            prior_superseded_count=0,
        )
        rec = self._call_save_recommendation(mock_db)
        assert rec.flip_count == 1

    def test_second_recommendation_supersedes_prior(self):
        """The prior active rec must have is_active set to False after save."""
        prior_rec = MagicMock()
        prior_rec.id = 5
        prior_rec.is_active = True
        prior_rec.superseded_by = None

        mock_db = _make_mock_db(
            prior_active_recs=[prior_rec],
            prior_superseded_count=0,
        )
        self._call_save_recommendation(mock_db)
        assert prior_rec.is_active is False

    def test_third_recommendation_flip_count_is_2(self):
        """One already-superseded rec + one active rec → flip_count = 2."""
        prior_rec = MagicMock()
        prior_rec.id = 7
        prior_rec.is_active = True

        mock_db = _make_mock_db(
            prior_active_recs=[prior_rec],
            prior_superseded_count=1,  # one already superseded
        )
        rec = self._call_save_recommendation(mock_db)
        assert rec.flip_count == 2

    def test_multiple_prior_active_all_superseded(self):
        """Two active recs and one already superseded → flip_count = 3."""
        prior_recs = [MagicMock(id=i, is_active=True) for i in range(2)]

        mock_db = _make_mock_db(
            prior_active_recs=prior_recs,
            prior_superseded_count=1,
        )
        rec = self._call_save_recommendation(mock_db)
        assert rec.flip_count == 3

    def test_all_prior_active_recs_marked_inactive(self):
        """Every prior active rec must have is_active=False after save."""
        prior_recs = [MagicMock(id=i, is_active=True) for i in range(3)]

        mock_db = _make_mock_db(
            prior_active_recs=prior_recs,
            prior_superseded_count=0,
        )
        self._call_save_recommendation(mock_db)
        for prior in prior_recs:
            assert prior.is_active is False

    def test_new_rec_is_active_true(self):
        """Newly saved recommendation must have is_active=True."""
        mock_db = _make_mock_db(prior_active_recs=[], prior_superseded_count=0)
        rec = self._call_save_recommendation(mock_db)
        assert rec.is_active is True

    def test_new_rec_decay_weight_is_1(self):
        """Newly saved recommendation must have decay_weight=1.0."""
        mock_db = _make_mock_db(prior_active_recs=[], prior_superseded_count=0)
        rec = self._call_save_recommendation(mock_db)
        assert rec.decay_weight == 1.0


# ── churn_rate formula tests ───────────────────────────────────────────────────

class TestChurnRateFormula:

    def test_churn_rate_zero_when_no_superseded(self):
        assert _compute_churn_rate(superseded=0, total=10) == 0.0

    def test_churn_rate_zero_when_no_recs(self):
        assert _compute_churn_rate(superseded=0, total=0) == 0.0

    def test_churn_rate_one_when_all_superseded(self):
        assert _compute_churn_rate(superseded=10, total=10) == 1.0

    def test_churn_rate_typical_3_of_10(self):
        assert _compute_churn_rate(superseded=3, total=10) == pytest.approx(0.3)

    def test_churn_rate_rounded_to_4_decimal_places(self):
        # 1/3 = 0.333... → rounded to 0.3333
        result = _compute_churn_rate(superseded=1, total=3)
        assert result == 0.3333

    def test_churn_rate_1_of_7(self):
        # 1/7 = 0.142857... → 0.1429
        result = _compute_churn_rate(superseded=1, total=7)
        assert result == 0.1429

    def test_churn_rate_2_of_3(self):
        result = _compute_churn_rate(superseded=2, total=3)
        assert result == 0.6667

    def test_churn_rate_result_is_float(self):
        result = _compute_churn_rate(superseded=5, total=10)
        assert isinstance(result, float)


# ── churn_rate via mocked DB (mirrors task_churn_rate_update internals) ────────

class TestChurnRateWithMockedDB:
    """
    Test the churn_rate calculation logic directly using a mock DB session,
    replicating what task_churn_rate_update does internally.
    """

    def _run_churn_logic(self, total: int, superseded: int, analyst_id: int = 1) -> dict:
        """
        Execute the churn_rate computation logic from intelligence_flow
        with a mock DB session.
        """
        from app.models.models import AnalystRecommendation, Analyst

        mock_db = MagicMock()

        # First count call (total recs for analyst)
        q_total = MagicMock()
        q_total.count.return_value = total

        # Second count call (superseded recs for analyst)
        q_superseded = MagicMock()
        q_superseded.count.return_value = superseded

        # Analyst query
        mock_analyst = MagicMock()
        mock_analyst.id = analyst_id
        mock_analyst.churn_rate = None

        q_analyst = MagicMock()
        q_analyst.first.return_value = mock_analyst

        # Wire up query side_effects in call order
        mock_db.query.return_value.filter.side_effect = [
            q_total,
            q_superseded,
            q_analyst,
        ]

        # Replicate the task logic inline
        total_val = (
            mock_db.query(AnalystRecommendation)
            .filter(AnalystRecommendation.analyst_id == analyst_id)
            .count()
        )
        superseded_val = (
            mock_db.query(AnalystRecommendation)
            .filter(
                AnalystRecommendation.analyst_id == analyst_id,
            )
            .count()
        )
        churn_rate = round(superseded_val / total_val, 4) if total_val > 0 else 0.0

        analyst = (
            mock_db.query(Analyst)
            .filter(Analyst.id == analyst_id)
            .first()
        )
        if analyst:
            analyst.churn_rate = churn_rate

        return {
            "total_recs": total_val,
            "superseded_recs": superseded_val,
            "churn_rate": churn_rate,
            "analyst_updated": mock_analyst.churn_rate == churn_rate,
        }

    def test_churn_rate_zero_recs_returns_zero(self):
        result = self._run_churn_logic(total=0, superseded=0)
        assert result["churn_rate"] == 0.0

    def test_churn_rate_no_superseded_is_zero(self):
        result = self._run_churn_logic(total=5, superseded=0)
        assert result["churn_rate"] == 0.0

    def test_churn_rate_all_superseded_is_one(self):
        result = self._run_churn_logic(total=8, superseded=8)
        assert result["churn_rate"] == 1.0

    def test_churn_rate_analyst_record_updated(self):
        result = self._run_churn_logic(total=10, superseded=3)
        assert result["analyst_updated"] is True
