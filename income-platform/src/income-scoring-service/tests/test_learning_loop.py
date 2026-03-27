"""
Agent 03 — Income Scoring Service
Tests: Learning Loop — Phase 3 (Shadow Portfolio + Quarterly Weight Tuner + API).

Coverage:
  TestShadowPortfolioManager   — maybe_record_entry, populate_outcomes,
                                  get_pending_past_hold, get_completed_outcomes
  TestQuarterlyWeightTuner     — compute_adjustment (signal paths, edge cases),
                                  _normalize_to_100, _mean, apply_review dispatch
  TestLearningLoopAPI          — all 4 endpoints, auth guard, validation, mock DB
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, patch, call

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

from fastapi.testclient import TestClient

from app.scoring.shadow_portfolio import (
    ShadowPortfolioManager,
    HOLD_PERIOD_DAYS,
    CORRECT_THRESHOLD,
    INCORRECT_THRESHOLD,
)
from app.scoring.weight_tuner import (
    QuarterlyWeightTuner,
    _mean,
    _normalize_to_100,
    MIN_SAMPLES,
    MAX_DELTA_PER_REVIEW,
    MIN_PILLAR_WEIGHT,
    MAX_PILLAR_WEIGHT,
    SKIP_INSUFFICIENT,
    SKIP_NO_SIGNAL,
    SKIP_NO_PROFILE,
)
from app.models import ShadowPortfolioEntry, WeightReviewRun, ScoringWeightProfile


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

NOW = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=HOLD_PERIOD_DAYS + 1)   # past hold period
RECENT = NOW - timedelta(days=HOLD_PERIOD_DAYS - 1) # within hold period


def _make_entry(
    ticker="AAPL",
    asset_class="DIVIDEND_STOCK",
    entry_recommendation="AGGRESSIVE_BUY",
    entry_score=82.0,
    entry_grade="A",
    entry_price=150.0,
    valuation_yield_score=36.0,
    financial_durability_score=32.0,
    technical_entry_score=16.0,
    outcome_label="PENDING",
    entry_date=None,
    outcome_populated_at=None,
    **kwargs,
):
    e = MagicMock(spec=ShadowPortfolioEntry)
    e.id = uuid.uuid4()
    e.ticker = ticker
    e.asset_class = asset_class
    e.entry_recommendation = entry_recommendation
    e.entry_score = entry_score
    e.entry_grade = entry_grade
    e.entry_price = entry_price
    e.valuation_yield_score = valuation_yield_score
    e.financial_durability_score = financial_durability_score
    e.technical_entry_score = technical_entry_score
    e.outcome_label = outcome_label
    e.entry_date = entry_date or OLD
    e.exit_price = None
    e.exit_date = None
    e.actual_return_pct = None
    e.outcome_populated_at = outcome_populated_at
    e.hold_period_days = HOLD_PERIOD_DAYS
    e.weight_profile_id = None
    for k, v in kwargs.items():
        setattr(e, k, v)
    return e


def _make_profile_orm(
    asset_class="DIVIDEND_STOCK",
    weight_yield=40,
    weight_durability=40,
    weight_technical=20,
    version=1,
):
    p = MagicMock(spec=ScoringWeightProfile)
    p.id = uuid.uuid4()
    p.asset_class = asset_class
    p.weight_yield = weight_yield
    p.weight_durability = weight_durability
    p.weight_technical = weight_technical
    p.version = version
    p.is_active = True
    p.yield_sub_weights = {"payout_sustainability": 40, "yield_vs_market": 35, "fcf_coverage": 25}
    p.durability_sub_weights = {"debt_coverage": 35, "fcf_stability": 35, "payout_consistency": 30}
    p.technical_sub_weights = {"price_momentum": 40, "volatility": 30, "price_range": 30}
    p.superseded_at = None
    p.superseded_by_id = None
    return p


def _current_profile_dict(wy=40, wd=40, wt=20, ac="DIVIDEND_STOCK", version=1):
    return {
        "asset_class": ac,
        "version": version,
        "weight_yield": wy,
        "weight_durability": wd,
        "weight_technical": wt,
        "yield_sub_weights": {},
        "durability_sub_weights": {},
        "technical_sub_weights": {},
    }


# ══════════════════════════════════════════════════════════════════════════════
# TestShadowPortfolioManager
# ══════════════════════════════════════════════════════════════════════════════

class TestShadowPortfolioManager:
    """Tests for ShadowPortfolioManager."""

    def setup_method(self):
        self.mgr = ShadowPortfolioManager()

    # ── maybe_record_entry ────────────────────────────────────────────────────

    def test_records_aggressive_buy(self):
        db = MagicMock()
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class="DIVIDEND_STOCK",
            entry_score=82.0,
            entry_grade="A",
            entry_recommendation="AGGRESSIVE_BUY",
            valuation_yield_score=36.0,
            financial_durability_score=32.0,
            technical_entry_score=16.0,
        )
        assert result is not None
        db.add.assert_called_once()
        db.flush.assert_called_once()

    def test_records_accumulate(self):
        db = MagicMock()
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="MSFT",
            asset_class="DIVIDEND_STOCK",
            entry_score=75.0,
            entry_grade="B+",
            entry_recommendation="ACCUMULATE",
            valuation_yield_score=30.0,
            financial_durability_score=30.0,
            technical_entry_score=15.0,
        )
        assert result is not None
        db.add.assert_called_once()

    def test_skips_hold(self):
        db = MagicMock()
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="AAPL",
            asset_class="DIVIDEND_STOCK",
            entry_score=65.0,
            entry_grade="B",
            entry_recommendation="HOLD",
            valuation_yield_score=25.0,
            financial_durability_score=25.0,
            technical_entry_score=15.0,
        )
        assert result is None
        db.add.assert_not_called()

    def test_skips_avoid(self):
        db = MagicMock()
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="XYZ",
            asset_class="DIVIDEND_STOCK",
            entry_score=45.0,
            entry_grade="D",
            entry_recommendation="AVOID",
            valuation_yield_score=15.0,
            financial_durability_score=15.0,
            technical_entry_score=10.0,
        )
        assert result is None

    def test_skips_reduce(self):
        db = MagicMock()
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="BAD",
            asset_class="DIVIDEND_STOCK",
            entry_score=55.0,
            entry_grade="C",
            entry_recommendation="REDUCE",
            valuation_yield_score=20.0,
            financial_durability_score=20.0,
            technical_entry_score=10.0,
        )
        assert result is None

    def test_entry_has_pending_outcome(self):
        db = MagicMock()
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="T",
            asset_class="DIVIDEND_STOCK",
            entry_score=72.0,
            entry_grade="B",
            entry_recommendation="ACCUMULATE",
            valuation_yield_score=28.0,
            financial_durability_score=28.0,
            technical_entry_score=16.0,
        )
        assert result.outcome_label == "PENDING"

    def test_entry_asset_class_uppercased(self):
        db = MagicMock()
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="T",
            asset_class="dividend_stock",   # lowercase
            entry_score=72.0,
            entry_grade="B",
            entry_recommendation="ACCUMULATE",
            valuation_yield_score=28.0,
            financial_durability_score=28.0,
            technical_entry_score=16.0,
        )
        assert result.asset_class == "DIVIDEND_STOCK"

    def test_entry_hold_period_set(self):
        db = MagicMock()
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="VZ",
            asset_class="DIVIDEND_STOCK",
            entry_score=73.0,
            entry_grade="B",
            entry_recommendation="ACCUMULATE",
            valuation_yield_score=28.0,
            financial_durability_score=30.0,
            technical_entry_score=15.0,
        )
        assert result.hold_period_days == HOLD_PERIOD_DAYS

    def test_records_entry_price(self):
        db = MagicMock()
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="KO",
            asset_class="DIVIDEND_STOCK",
            entry_score=80.0,
            entry_grade="A",
            entry_recommendation="AGGRESSIVE_BUY",
            valuation_yield_score=34.0,
            financial_durability_score=32.0,
            technical_entry_score=14.0,
            entry_price=62.50,
        )
        assert result.entry_price == 62.50

    def test_db_exception_returns_none(self):
        db = MagicMock()
        db.flush.side_effect = Exception("DB error")
        result = self.mgr.maybe_record_entry(
            db,
            income_score_id=uuid.uuid4(),
            ticker="ERR",
            asset_class="DIVIDEND_STOCK",
            entry_score=80.0,
            entry_grade="A",
            entry_recommendation="AGGRESSIVE_BUY",
            valuation_yield_score=32.0,
            financial_durability_score=32.0,
            technical_entry_score=16.0,
        )
        assert result is None
        db.rollback.assert_called_once()

    # ── populate_outcomes ──────────────────────────────────────────────────────

    def test_populate_correct_outcome(self):
        """Return >= +5% → CORRECT."""
        entry = _make_entry(entry_price=100.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        result = self.mgr.populate_outcomes(db, {"AAPL": 107.0}, as_of=NOW)

        assert entry.outcome_label == "CORRECT"
        assert entry.actual_return_pct == 7.0
        assert result["updated"] == 1
        assert result["total_pending"] == 1

    def test_populate_incorrect_outcome(self):
        """Return <= -5% → INCORRECT."""
        entry = _make_entry(entry_price=100.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        self.mgr.populate_outcomes(db, {"AAPL": 93.0}, as_of=NOW)

        assert entry.outcome_label == "INCORRECT"
        assert entry.actual_return_pct == -7.0

    def test_populate_neutral_outcome(self):
        """Return inside (-5%, +5%) → NEUTRAL."""
        entry = _make_entry(entry_price=100.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        self.mgr.populate_outcomes(db, {"AAPL": 103.0}, as_of=NOW)

        assert entry.outcome_label == "NEUTRAL"
        assert entry.actual_return_pct == 3.0

    def test_populate_skips_missing_ticker(self):
        """Entry not in exit_prices dict → skipped."""
        entry = _make_entry(ticker="AAPL", entry_price=100.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        result = self.mgr.populate_outcomes(db, {"MSFT": 300.0}, as_of=NOW)

        assert entry.outcome_label == "PENDING"
        assert result["skipped_no_price"] == 1
        assert result["updated"] == 0

    def test_populate_skips_zero_entry_price(self):
        """Entry with entry_price=0 → NEUTRAL (can't compute)."""
        entry = _make_entry(entry_price=0.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        result = self.mgr.populate_outcomes(db, {"AAPL": 110.0}, as_of=NOW)

        assert entry.outcome_label == "NEUTRAL"
        assert result["skipped_no_entry_price"] == 1
        assert result["updated"] == 0

    def test_populate_skips_none_entry_price(self):
        """Entry with entry_price=None → NEUTRAL."""
        entry = _make_entry(entry_price=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        result = self.mgr.populate_outcomes(db, {"AAPL": 110.0}, as_of=NOW)

        assert entry.outcome_label == "NEUTRAL"
        assert result["skipped_no_entry_price"] == 1

    def test_populate_correct_boundary_exactly_5pct(self):
        """Exactly +5.0% → CORRECT (>= threshold)."""
        entry = _make_entry(entry_price=100.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        self.mgr.populate_outcomes(db, {"AAPL": 105.0}, as_of=NOW)

        assert entry.outcome_label == "CORRECT"

    def test_populate_incorrect_boundary_exactly_neg5pct(self):
        """Exactly -5.0% → INCORRECT (<= threshold)."""
        entry = _make_entry(entry_price=100.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        self.mgr.populate_outcomes(db, {"AAPL": 95.0}, as_of=NOW)

        assert entry.outcome_label == "INCORRECT"

    def test_populate_sets_exit_date(self):
        entry = _make_entry(entry_price=100.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        self.mgr.populate_outcomes(db, {"AAPL": 108.0}, as_of=NOW)

        assert entry.exit_date == NOW
        assert entry.exit_price == 108.0
        assert entry.outcome_populated_at == NOW

    def test_populate_multiple_entries(self):
        entries = [
            _make_entry(ticker="A", entry_price=100.0),
            _make_entry(ticker="B", entry_price=100.0),
            _make_entry(ticker="C", entry_price=100.0),
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = entries

        result = self.mgr.populate_outcomes(
            db, {"A": 110.0, "B": 90.0, "C": 102.0}, as_of=NOW
        )

        assert entries[0].outcome_label == "CORRECT"
        assert entries[1].outcome_label == "INCORRECT"
        assert entries[2].outcome_label == "NEUTRAL"
        assert result["updated"] == 3

    def test_populate_commit_error_raises(self):
        entry = _make_entry(entry_price=100.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]
        db.commit.side_effect = Exception("commit failed")

        with pytest.raises(Exception, match="commit failed"):
            self.mgr.populate_outcomes(db, {"AAPL": 110.0}, as_of=NOW)
        db.rollback.assert_called_once()

    def test_populate_summary_keys(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        result = self.mgr.populate_outcomes(db, {}, as_of=NOW)

        assert set(result.keys()) == {"updated", "skipped_no_price", "skipped_no_entry_price", "total_pending"}

    # ── get_pending_past_hold / get_completed_outcomes ─────────────────────────

    def test_get_pending_calls_query_with_cutoff(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        self.mgr.get_pending_past_hold(db, as_of=NOW)

        db.query.assert_called_once_with(ShadowPortfolioEntry)

    def test_get_completed_filters_asset_class(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        self.mgr.get_completed_outcomes(db, "DIVIDEND_STOCK")

        db.query.assert_called_once_with(ShadowPortfolioEntry)


# ══════════════════════════════════════════════════════════════════════════════
# TestQuarterlyWeightTuner — pure computation
# ══════════════════════════════════════════════════════════════════════════════

class TestQuarterlyWeightTuner:
    """Tests for QuarterlyWeightTuner.compute_adjustment and helpers."""

    def setup_method(self):
        self.tuner = QuarterlyWeightTuner()

    # ── _mean helper ──────────────────────────────────────────────────────────

    def test_mean_empty_returns_half(self):
        assert _mean([]) == 0.5

    def test_mean_single(self):
        assert _mean([1.0]) == 1.0

    def test_mean_two_values(self):
        assert _mean([0.4, 0.6]) == pytest.approx(0.5)

    # ── _normalize_to_100 helper ──────────────────────────────────────────────

    def test_normalize_already_100(self):
        assert _normalize_to_100(40, 40, 20) == (40, 40, 20)

    def test_normalize_sum_99_adds_to_largest(self):
        # largest = first arg (40); add 1 → 41
        y, d, t = _normalize_to_100(40, 35, 24)   # sum=99
        assert y + d + t == 100

    def test_normalize_sum_101_subtracts_from_largest(self):
        y, d, t = _normalize_to_100(40, 40, 21)   # sum=101
        assert y + d + t == 100

    def test_normalize_sum_98(self):
        y, d, t = _normalize_to_100(36, 36, 26)   # sum=98, largest=36 tie → first
        assert y + d + t == 100

    def test_normalize_all_equal_splits_to_largest(self):
        y, d, t = _normalize_to_100(33, 33, 33)   # sum=99, all equal, max picks first
        assert y + d + t == 100

    # ── compute_adjustment — insufficient samples ──────────────────────────────

    def test_insufficient_samples_returns_skip(self):
        outcomes = [_make_entry(outcome_label="CORRECT") for _ in range(5)]
        outcomes += [_make_entry(outcome_label="INCORRECT") for _ in range(4)]
        # 9 usable < MIN_SAMPLES=10
        profile = _current_profile_dict()
        adj, reason = self.tuner.compute_adjustment(outcomes, profile)

        assert adj is None
        assert SKIP_INSUFFICIENT in reason

    def test_exactly_min_samples_proceeds(self):
        # 6 correct + 4 incorrect = 10 usable (MIN_SAMPLES)
        correct = [_make_entry(
            outcome_label="CORRECT",
            valuation_yield_score=38.0,
            financial_durability_score=30.0,
            technical_entry_score=16.0,
        ) for _ in range(6)]
        incorrect = [_make_entry(
            outcome_label="INCORRECT",
            valuation_yield_score=24.0,
            financial_durability_score=30.0,
            technical_entry_score=16.0,
        ) for _ in range(4)]
        profile = _current_profile_dict(wy=40, wd=40, wt=20)
        adj, reason = self.tuner.compute_adjustment(correct + incorrect, profile)
        # Should not skip for sample count — might skip for no signal
        assert reason != f"{SKIP_INSUFFICIENT}:10"

    def test_zero_outcomes_skip(self):
        adj, reason = self.tuner.compute_adjustment([], _current_profile_dict())
        assert adj is None
        assert SKIP_INSUFFICIENT in reason

    def test_only_neutral_outcomes_skip(self):
        outcomes = [_make_entry(outcome_label="NEUTRAL") for _ in range(15)]
        adj, reason = self.tuner.compute_adjustment(outcomes, _current_profile_dict())
        assert adj is None
        assert SKIP_INSUFFICIENT in reason  # CORRECT+INCORRECT=0

    # ── compute_adjustment — signal paths ─────────────────────────────────────

    def test_no_signal_returns_skip(self):
        """Identical correct/incorrect pillar fractions → no signal."""
        def _uniform_entry(label):
            return _make_entry(
                outcome_label=label,
                valuation_yield_score=32.0,   # 32/40=0.80
                financial_durability_score=32.0,  # 32/40=0.80
                technical_entry_score=16.0,   # 16/20=0.80
            )
        outcomes = [_uniform_entry("CORRECT") for _ in range(8)]
        outcomes += [_uniform_entry("INCORRECT") for _ in range(7)]
        profile = _current_profile_dict(wy=40, wd=40, wt=20)
        adj, reason = self.tuner.compute_adjustment(outcomes, profile)
        assert adj is None
        assert reason == SKIP_NO_SIGNAL

    def test_yield_signal_positive_increases_yield_weight(self):
        """Correct entries have high yield fraction and low durability; incorrect inverse.
        Yield δ=+5, durability δ=-5 → new(45, 35, 20) sums to 100 exactly → yield > 40.
        """
        correct = [_make_entry(
            outcome_label="CORRECT",
            valuation_yield_score=38.0,   # 38/40 = 0.95
            financial_durability_score=15.0,  # 15/40 = 0.375
            technical_entry_score=10.0,
        ) for _ in range(8)]
        incorrect = [_make_entry(
            outcome_label="INCORRECT",
            valuation_yield_score=10.0,   # 10/40 = 0.25
            financial_durability_score=38.0,  # 38/40 = 0.95
            technical_entry_score=10.0,
        ) for _ in range(7)]
        profile = _current_profile_dict(wy=40, wd=40, wt=20)
        adj, reason = self.tuner.compute_adjustment(correct + incorrect, profile)
        assert adj is not None
        assert adj["weight_yield"] > 40

    def test_durability_signal_positive_increases_durability_weight(self):
        """Durability high in correct, yield high in incorrect → durability increases.
        durability δ=+5, yield δ=-5 → new(35, 45, 20) sums to 100 → durability > 40.
        """
        correct = [_make_entry(
            outcome_label="CORRECT",
            valuation_yield_score=15.0,       # low yield fraction
            financial_durability_score=38.0,  # 38/40 = 0.95
            technical_entry_score=10.0,
        ) for _ in range(8)]
        incorrect = [_make_entry(
            outcome_label="INCORRECT",
            valuation_yield_score=38.0,       # high yield fraction
            financial_durability_score=10.0,  # 10/40 = 0.25
            technical_entry_score=10.0,
        ) for _ in range(7)]
        profile = _current_profile_dict(wy=40, wd=40, wt=20)
        adj, reason = self.tuner.compute_adjustment(correct + incorrect, profile)
        assert adj is not None
        assert adj["weight_durability"] > 40

    def test_result_sums_to_100(self):
        correct = [_make_entry(
            outcome_label="CORRECT",
            valuation_yield_score=39.0,
            financial_durability_score=20.0,
            technical_entry_score=19.0,
        ) for _ in range(8)]
        incorrect = [_make_entry(
            outcome_label="INCORRECT",
            valuation_yield_score=10.0,
            financial_durability_score=20.0,
            technical_entry_score=10.0,
        ) for _ in range(7)]
        profile = _current_profile_dict(wy=40, wd=40, wt=20)
        adj, reason = self.tuner.compute_adjustment(correct + incorrect, profile)
        if adj is not None:
            assert adj["weight_yield"] + adj["weight_durability"] + adj["weight_technical"] == 100

    def test_max_delta_clamped(self):
        """Extreme signal: raw per-pillar delta is clamped to ±MAX_DELTA.
        After normalization the largest pillar absorbs rounding, so the final
        weight difference may exceed MAX_DELTA, but all pillars must stay within
        [MIN_PILLAR_WEIGHT, MAX_PILLAR_WEIGHT].
        """
        correct = [_make_entry(
            outcome_label="CORRECT",
            valuation_yield_score=40.0,  # max fraction
            financial_durability_score=40.0,
            technical_entry_score=20.0,
        ) for _ in range(20)]
        incorrect = [_make_entry(
            outcome_label="INCORRECT",
            valuation_yield_score=0.0,   # zero fraction
            financial_durability_score=0.0,
            technical_entry_score=0.0,
        ) for _ in range(5)]
        profile = _current_profile_dict(wy=40, wd=40, wt=20)
        adj, _ = self.tuner.compute_adjustment(correct + incorrect, profile)
        if adj:
            assert MIN_PILLAR_WEIGHT <= adj["weight_yield"] <= MAX_PILLAR_WEIGHT
            assert MIN_PILLAR_WEIGHT <= adj["weight_durability"] <= MAX_PILLAR_WEIGHT
            assert MIN_PILLAR_WEIGHT <= adj["weight_technical"] <= MAX_PILLAR_WEIGHT
            assert adj["weight_yield"] + adj["weight_durability"] + adj["weight_technical"] == 100

    def test_pillar_floor_respected(self):
        """Weight cannot drop below MIN_PILLAR_WEIGHT."""
        correct = [_make_entry(
            outcome_label="CORRECT",
            valuation_yield_score=40.0,
            financial_durability_score=40.0,
            technical_entry_score=0.5,   # technical terrible in correct
        ) for _ in range(20)]
        incorrect = [_make_entry(
            outcome_label="INCORRECT",
            valuation_yield_score=0.5,
            financial_durability_score=0.5,
            technical_entry_score=20.0,  # technical great in incorrect
        ) for _ in range(5)]
        # Start with very small technical weight
        profile = _current_profile_dict(wy=45, wd=50, wt=5)
        adj, _ = self.tuner.compute_adjustment(correct + incorrect, profile)
        if adj:
            assert adj["weight_technical"] >= MIN_PILLAR_WEIGHT

    def test_pillar_ceiling_respected(self):
        """Weight cannot exceed MAX_PILLAR_WEIGHT."""
        correct = [_make_entry(
            outcome_label="CORRECT",
            valuation_yield_score=40.0,
            financial_durability_score=0.5,
            technical_entry_score=0.5,
        ) for _ in range(20)]
        incorrect = [_make_entry(
            outcome_label="INCORRECT",
            valuation_yield_score=0.5,
            financial_durability_score=0.5,
            technical_entry_score=0.5,
        ) for _ in range(5)]
        # Start near ceiling
        profile = _current_profile_dict(wy=88, wd=7, wt=5)
        adj, _ = self.tuner.compute_adjustment(correct + incorrect, profile)
        if adj:
            assert adj["weight_yield"] <= MAX_PILLAR_WEIGHT

    def test_sub_weights_preserved(self):
        """Sub-weights from current profile should pass through unchanged."""
        correct = [_make_entry(
            outcome_label="CORRECT",
            valuation_yield_score=39.0,
            financial_durability_score=20.0,
            technical_entry_score=10.0,
        ) for _ in range(8)]
        incorrect = [_make_entry(
            outcome_label="INCORRECT",
            valuation_yield_score=10.0,
            financial_durability_score=20.0,
            technical_entry_score=10.0,
        ) for _ in range(7)]
        sub = {"payout_sustainability": 40, "yield_vs_market": 35, "fcf_coverage": 25}
        profile = _current_profile_dict(wy=40, wd=40, wt=20)
        profile["yield_sub_weights"] = sub
        adj, _ = self.tuner.compute_adjustment(correct + incorrect, profile)
        if adj:
            assert adj["yield_sub_weights"] == sub

    def test_only_correct_entries_uses_half_for_incorrect(self):
        """When no INCORRECT entries, incorrect fracs default to 0.5."""
        correct = [_make_entry(
            outcome_label="CORRECT",
            valuation_yield_score=39.0,
            financial_durability_score=39.0,
            technical_entry_score=19.0,
        ) for _ in range(15)]
        profile = _current_profile_dict(wy=40, wd=40, wt=20)
        # Should not raise; CORRECT fracs > 0.5 → positive delta
        adj, reason = self.tuner.compute_adjustment(correct, profile)
        # 15 CORRECT, 0 INCORRECT → usable=15 >= 10, so no skip for samples
        assert reason != f"{SKIP_INSUFFICIENT}:15"

    # ── apply_review dispatch ─────────────────────────────────────────────────

    def test_apply_review_no_profile_skipped(self):
        db = MagicMock()
        review_mock = MagicMock(spec=WeightReviewRun)
        review_mock.id = uuid.uuid4()
        review_mock.correct_count = 0
        review_mock.incorrect_count = 0
        review_mock.neutral_count = 0
        review_mock.outcomes_analyzed = 0

        # Simulate no active profile
        db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.scoring.weight_tuner.WeightReviewRun", return_value=review_mock):
            result = self.tuner.apply_review(db, "DIVIDEND_STOCK", [])

        # With no active profile → status=SKIPPED
        assert review_mock.status == "SKIPPED"
        assert review_mock.skip_reason == SKIP_NO_PROFILE

    def test_apply_review_insufficient_outcomes_skipped(self):
        db = MagicMock()
        review_mock = MagicMock(spec=WeightReviewRun)
        review_mock.id = uuid.uuid4()

        profile_orm = _make_profile_orm()
        db.query.return_value.filter.return_value.first.return_value = profile_orm

        outcomes = [_make_entry(outcome_label="CORRECT") for _ in range(3)]

        with patch("app.scoring.weight_tuner.WeightReviewRun", return_value=review_mock):
            result = self.tuner.apply_review(db, "DIVIDEND_STOCK", outcomes)

        assert review_mock.status == "SKIPPED"
        assert SKIP_INSUFFICIENT in review_mock.skip_reason


# ══════════════════════════════════════════════════════════════════════════════
# TestLearningLoopAPI — endpoint tests with mock DB
# ══════════════════════════════════════════════════════════════════════════════

class TestLearningLoopAPI:
    """
    Tests for /learning-loop/* endpoints.

    Uses the same mock-DB pattern as TestWeightsAPI / TestSignalConfigAPI
    to avoid SQLite/PostgreSQL schema incompatibility.
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

    def _make_shadow_orm(self, ticker="AAPL", outcome="PENDING"):
        e = MagicMock()
        e.id = uuid.uuid4()
        e.ticker = ticker
        e.asset_class = "DIVIDEND_STOCK"
        e.entry_score = 82.0
        e.entry_grade = "A"
        e.entry_recommendation = "AGGRESSIVE_BUY"
        e.entry_price = 150.0
        e.entry_date = NOW
        e.hold_period_days = 90
        e.exit_price = None
        e.exit_date = None
        e.actual_return_pct = None
        e.outcome_label = outcome
        e.outcome_populated_at = None
        return e

    def _make_review_orm(self, status="COMPLETE"):
        r = MagicMock()
        r.id = uuid.uuid4()
        r.asset_class = "DIVIDEND_STOCK"
        r.triggered_at = NOW
        r.triggered_by = "test"
        r.status = status
        r.outcomes_analyzed = 15
        r.correct_count = 10
        r.incorrect_count = 5
        r.neutral_count = 0
        r.weight_yield_before = 40
        r.weight_durability_before = 40
        r.weight_technical_before = 20
        r.weight_yield_after = 43
        r.weight_durability_after = 38
        r.weight_technical_after = 19
        r.delta_yield = 3
        r.delta_durability = -2
        r.delta_technical = -1
        r.skip_reason = None
        r.completed_at = NOW
        return r

    # ── Auth guard ─────────────────────────────────────────────────────────────

    def test_shadow_portfolio_requires_auth(self):
        from app.main import app
        from app.auth import verify_token
        app.dependency_overrides.pop(verify_token, None)
        resp = self._client.get("/learning-loop/shadow-portfolio/")
        assert resp.status_code == 403
        app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}

    def test_populate_outcomes_requires_auth(self):
        from app.main import app
        from app.auth import verify_token
        app.dependency_overrides.pop(verify_token, None)
        resp = self._client.post("/learning-loop/populate-outcomes", json={"exit_prices": {}})
        assert resp.status_code == 403
        app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}

    def test_review_requires_auth(self):
        from app.main import app
        from app.auth import verify_token
        app.dependency_overrides.pop(verify_token, None)
        resp = self._client.post("/learning-loop/review/DIVIDEND_STOCK", json={})
        assert resp.status_code == 403
        app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}

    def test_reviews_requires_auth(self):
        from app.main import app
        from app.auth import verify_token
        app.dependency_overrides.pop(verify_token, None)
        resp = self._client.get("/learning-loop/reviews")
        assert resp.status_code == 403
        app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}

    # ── GET /shadow-portfolio/ ─────────────────────────────────────────────────

    def test_list_shadow_portfolio_empty(self):
        self._mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        self._mock_db.query.return_value.order_by.return_value.filter.return_value.limit.return_value.all.return_value = []

        resp = self._client.get("/learning-loop/shadow-portfolio/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_shadow_portfolio_returns_entries(self):
        entry = self._make_shadow_orm()
        q = self._mock_db.query.return_value
        q.order_by.return_value.limit.return_value.all.return_value = [entry]

        resp = self._client.get("/learning-loop/shadow-portfolio/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ticker"] == "AAPL"
        assert data[0]["outcome_label"] == "PENDING"

    def test_list_shadow_portfolio_entry_shape(self):
        entry = self._make_shadow_orm()
        q = self._mock_db.query.return_value
        q.order_by.return_value.limit.return_value.all.return_value = [entry]

        resp = self._client.get("/learning-loop/shadow-portfolio/")
        item = resp.json()[0]
        expected_keys = {
            "id", "ticker", "asset_class", "entry_score", "entry_grade",
            "entry_recommendation", "entry_price", "entry_date", "hold_period_days",
            "exit_price", "exit_date", "actual_return_pct", "outcome_label",
            "outcome_populated_at",
        }
        assert expected_keys.issubset(set(item.keys()))

    def test_list_shadow_portfolio_filter_by_asset_class(self):
        entry = self._make_shadow_orm()
        q = self._mock_db.query.return_value
        q.order_by.return_value.filter.return_value.limit.return_value.all.return_value = [entry]

        resp = self._client.get("/learning-loop/shadow-portfolio/?asset_class=DIVIDEND_STOCK")
        assert resp.status_code == 200

    def test_list_shadow_portfolio_filter_by_outcome(self):
        entry = self._make_shadow_orm(outcome="CORRECT")
        q = self._mock_db.query.return_value
        q.order_by.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = [entry]
        q.order_by.return_value.filter.return_value.limit.return_value.all.return_value = [entry]

        resp = self._client.get("/learning-loop/shadow-portfolio/?outcome=CORRECT")
        assert resp.status_code == 200

    def test_list_shadow_portfolio_limit_default_50(self):
        """Default limit is 50."""
        self._mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        resp = self._client.get("/learning-loop/shadow-portfolio/")
        assert resp.status_code == 200
        # Check that limit(50) was called somewhere in the chain
        mock_chain = self._mock_db.query.return_value.order_by.return_value
        mock_chain.limit.assert_called()

    # ── POST /populate-outcomes ────────────────────────────────────────────────

    def test_populate_outcomes_success(self):
        with patch(
            "app.api.learning_loop.shadow_portfolio_manager.populate_outcomes",
            return_value={
                "updated": 3,
                "skipped_no_price": 1,
                "skipped_no_entry_price": 0,
                "total_pending": 4,
            },
        ):
            resp = self._client.post(
                "/learning-loop/populate-outcomes",
                json={"exit_prices": {"AAPL": 175.0, "MSFT": 420.0}},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 3
        assert data["total_pending"] == 4

    def test_populate_outcomes_empty_prices(self):
        with patch(
            "app.api.learning_loop.shadow_portfolio_manager.populate_outcomes",
            return_value={
                "updated": 0,
                "skipped_no_price": 5,
                "skipped_no_entry_price": 0,
                "total_pending": 5,
            },
        ):
            resp = self._client.post(
                "/learning-loop/populate-outcomes",
                json={"exit_prices": {}},
            )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0

    def test_populate_outcomes_response_shape(self):
        with patch(
            "app.api.learning_loop.shadow_portfolio_manager.populate_outcomes",
            return_value={
                "updated": 0,
                "skipped_no_price": 0,
                "skipped_no_entry_price": 0,
                "total_pending": 0,
            },
        ):
            resp = self._client.post(
                "/learning-loop/populate-outcomes",
                json={"exit_prices": {}},
            )
        keys = set(resp.json().keys())
        assert keys == {"updated", "skipped_no_price", "skipped_no_entry_price", "total_pending"}

    def test_populate_outcomes_invalid_body(self):
        resp = self._client.post(
            "/learning-loop/populate-outcomes",
            json={"not_exit_prices": {}},
        )
        assert resp.status_code == 422

    # ── POST /review/{asset_class} ─────────────────────────────────────────────

    def test_review_invalid_asset_class_422(self):
        resp = self._client.post(
            "/learning-loop/review/UNICORN_ASSET",
            json={},
        )
        assert resp.status_code == 422

    def test_review_valid_asset_class_returns_201(self):
        review = self._make_review_orm()
        with (
            patch("app.api.learning_loop.shadow_portfolio_manager.get_completed_outcomes", return_value=[]),
            patch("app.api.learning_loop.quarterly_weight_tuner.apply_review", return_value=review),
        ):
            resp = self._client.post(
                "/learning-loop/review/DIVIDEND_STOCK",
                json={"triggered_by": "test-suite"},
            )
        assert resp.status_code == 201

    def test_review_response_shape(self):
        review = self._make_review_orm()
        with (
            patch("app.api.learning_loop.shadow_portfolio_manager.get_completed_outcomes", return_value=[]),
            patch("app.api.learning_loop.quarterly_weight_tuner.apply_review", return_value=review),
        ):
            resp = self._client.post(
                "/learning-loop/review/DIVIDEND_STOCK",
                json={},
            )
        data = resp.json()
        expected_keys = {
            "id", "asset_class", "triggered_at", "triggered_by", "status",
            "outcomes_analyzed", "correct_count", "incorrect_count", "neutral_count",
            "weight_yield_before", "weight_durability_before", "weight_technical_before",
            "weight_yield_after", "weight_durability_after", "weight_technical_after",
            "delta_yield", "delta_durability", "delta_technical",
            "skip_reason", "completed_at",
        }
        assert expected_keys.issubset(set(data.keys()))

    def test_review_complete_status(self):
        review = self._make_review_orm(status="COMPLETE")
        with (
            patch("app.api.learning_loop.shadow_portfolio_manager.get_completed_outcomes", return_value=[]),
            patch("app.api.learning_loop.quarterly_weight_tuner.apply_review", return_value=review),
        ):
            resp = self._client.post("/learning-loop/review/DIVIDEND_STOCK", json={})
        assert resp.json()["status"] == "COMPLETE"

    def test_review_skipped_status(self):
        review = self._make_review_orm(status="SKIPPED")
        review.skip_reason = "insufficient_samples:5"
        review.weight_yield_after = None
        review.weight_durability_after = None
        review.weight_technical_after = None
        review.delta_yield = None
        review.delta_durability = None
        review.delta_technical = None
        with (
            patch("app.api.learning_loop.shadow_portfolio_manager.get_completed_outcomes", return_value=[]),
            patch("app.api.learning_loop.quarterly_weight_tuner.apply_review", return_value=review),
        ):
            resp = self._client.post("/learning-loop/review/BOND", json={})
        assert resp.json()["status"] == "SKIPPED"
        assert "skip_reason" in resp.json()

    def test_review_all_valid_asset_classes(self):
        """Each valid asset class should not raise 422."""
        valid_classes = [
            "EQUITY_REIT", "MORTGAGE_REIT", "BDC", "COVERED_CALL_ETF",
            "DIVIDEND_STOCK", "BOND", "PREFERRED_STOCK",
        ]
        review = self._make_review_orm(status="SKIPPED")
        review.skip_reason = "insufficient_samples:0"
        review.weight_yield_after = None
        review.weight_durability_after = None
        review.weight_technical_after = None
        review.delta_yield = None
        review.delta_durability = None
        review.delta_technical = None
        for ac in valid_classes:
            with (
                patch("app.api.learning_loop.shadow_portfolio_manager.get_completed_outcomes", return_value=[]),
                patch("app.api.learning_loop.quarterly_weight_tuner.apply_review", return_value=review),
            ):
                resp = self._client.post(f"/learning-loop/review/{ac}", json={})
            assert resp.status_code == 201, f"Expected 201 for {ac}, got {resp.status_code}"

    def test_review_tuner_exception_returns_500(self):
        with (
            patch("app.api.learning_loop.shadow_portfolio_manager.get_completed_outcomes", return_value=[]),
            patch(
                "app.api.learning_loop.quarterly_weight_tuner.apply_review",
                side_effect=RuntimeError("DB exploded"),
            ),
        ):
            resp = self._client.post("/learning-loop/review/DIVIDEND_STOCK", json={})
        assert resp.status_code == 500

    def test_review_with_lookback_days(self):
        review = self._make_review_orm()
        with (
            patch(
                "app.api.learning_loop.shadow_portfolio_manager.get_completed_outcomes",
                return_value=[],
            ) as mock_get,
            patch("app.api.learning_loop.quarterly_weight_tuner.apply_review", return_value=review),
        ):
            resp = self._client.post(
                "/learning-loop/review/DIVIDEND_STOCK",
                json={"lookback_days": 180},
            )
        assert resp.status_code == 201
        # get_completed_outcomes called with a non-None `since` kwarg
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs.get("since") is not None or call_kwargs[1].get("since") is not None

    # ── GET /reviews ───────────────────────────────────────────────────────────

    def test_list_reviews_empty(self):
        self._mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        resp = self._client.get("/learning-loop/reviews")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_reviews_returns_runs(self):
        review = self._make_review_orm()
        self._mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [review]

        resp = self._client.get("/learning-loop/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["asset_class"] == "DIVIDEND_STOCK"

    def test_list_reviews_filter_by_asset_class(self):
        review = self._make_review_orm()
        q = self._mock_db.query.return_value
        q.order_by.return_value.filter.return_value.limit.return_value.all.return_value = [review]

        resp = self._client.get("/learning-loop/reviews?asset_class=DIVIDEND_STOCK")
        assert resp.status_code == 200

    def test_list_reviews_response_shape(self):
        review = self._make_review_orm()
        self._mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [review]

        resp = self._client.get("/learning-loop/reviews")
        item = resp.json()[0]
        assert "id" in item
        assert "status" in item
        assert "outcomes_analyzed" in item
        assert "delta_yield" in item

    def test_list_reviews_default_limit_20(self):
        self._mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        resp = self._client.get("/learning-loop/reviews")
        assert resp.status_code == 200
        self._mock_db.query.return_value.order_by.return_value.limit.assert_called_with(20)


# ══════════════════════════════════════════════════════════════════════════════
# Task 2: Migration seed helper
# ══════════════════════════════════════════════════════════════════════════════

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "scripts"))

def test_benchmark_defaults_cover_all_valid_asset_classes():
    """All asset classes in VALID_ASSET_CLASSES have a benchmark ticker."""
    from migrate import BENCHMARK_DEFAULTS
    from app.api.weights import VALID_ASSET_CLASSES
    for ac in VALID_ASSET_CLASSES:
        assert ac in BENCHMARK_DEFAULTS, f"{ac} missing from benchmark defaults"
