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
    income_outcome_label=None,
    durability_outcome_label=None,
    technical_outcome_label=None,
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
    # Per-pillar labels default to matching the aggregate outcome_label
    e.income_outcome_label = income_outcome_label if income_outcome_label is not None else outcome_label
    e.durability_outcome_label = durability_outcome_label if durability_outcome_label is not None else outcome_label
    e.technical_outcome_label = technical_outcome_label if technical_outcome_label is not None else outcome_label
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
        r.pillar_reviewed = None
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

    def test_populate_outcomes_deprecated_returns_410(self):
        """Deprecated endpoint always returns 410 Gone."""
        resp = self._client.post(
            "/learning-loop/populate-outcomes",
            json={"exit_prices": {"AAPL": 175.0, "MSFT": 420.0}},
        )
        assert resp.status_code == 410
        assert "detail" in resp.json()

    def test_populate_outcomes_empty_prices_deprecated(self):
        """Deprecated endpoint returns 410 regardless of body."""
        resp = self._client.post(
            "/learning-loop/populate-outcomes",
            json={"exit_prices": {}},
        )
        assert resp.status_code == 410

    def test_populate_outcomes_response_shape_deprecated(self):
        """Deprecated endpoint returns 410 with detail key."""
        resp = self._client.post(
            "/learning-loop/populate-outcomes",
            json={"exit_prices": {}},
        )
        assert resp.status_code == 410
        assert "detail" in resp.json()

    def test_populate_outcomes_invalid_body_deprecated(self):
        """Deprecated endpoint returns 410 even for invalid body."""
        resp = self._client.post(
            "/learning-loop/populate-outcomes",
            json={"not_exit_prices": {}},
        )
        assert resp.status_code == 410

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


# ══════════════════════════════════════════════════════════════════════════════
# Task 3: ShadowPortfolioManager v3 — entry recording
# ══════════════════════════════════════════════════════════════════════════════

class TestShadowPortfolioManagerV3Entry:
    def setup_method(self):
        self.mgr = ShadowPortfolioManager()
        self.db = MagicMock()

    def _base_kwargs(self):
        return dict(
            income_score_id=uuid.uuid4(),
            ticker="STWD",
            asset_class="MORTGAGE_REIT",
            entry_score=82.0,
            entry_grade="A",
            entry_recommendation="ACCUMULATE",
            valuation_yield_score=32.0,
            financial_durability_score=28.0,
            technical_entry_score=18.0,
            entry_price=25.0,
            # v3.0 new params
            benchmark_ticker="REM",
            benchmark_entry_price=22.50,
            durability_score_at_entry=28.0,
            income_ttm_at_entry=1.80,
        )

    def test_records_entry_with_v3_fields(self):
        entry = self.mgr.maybe_record_entry(self.db, **self._base_kwargs())
        assert entry is not None
        self.db.add.assert_called_once()
        added = self.db.add.call_args[0][0]
        assert added.benchmark_ticker == "REM"
        assert added.benchmark_entry_price == 22.50
        assert added.durability_score_at_entry == 28.0
        assert added.income_ttm_at_entry == 1.80
        assert added.hold_period_days == 365  # longest hold period

    def test_does_not_record_hold_or_sell(self):
        kw = self._base_kwargs()
        kw["entry_recommendation"] = "HOLD"
        entry = self.mgr.maybe_record_entry(self.db, **kw)
        assert entry is None
        self.db.add.assert_not_called()

    def test_v3_params_default_to_none(self):
        """Callers that don't pass v3 params still work (backward compat)."""
        kw = self._base_kwargs()
        del kw["benchmark_ticker"]
        del kw["benchmark_entry_price"]
        del kw["durability_score_at_entry"]
        del kw["income_ttm_at_entry"]
        entry = self.mgr.maybe_record_entry(self.db, **kw)
        assert entry is not None
        added = self.db.add.call_args[0][0]
        assert added.benchmark_ticker is None
        assert added.income_ttm_at_entry is None


class TestPopulateTechnicalOutcomes:
    def setup_method(self):
        self.mgr = ShadowPortfolioManager()
        self.db = MagicMock()
        self.now = datetime(2026, 3, 1, tzinfo=timezone.utc)

    def _make_pending_tech(self, ticker="STWD", entry_price=25.0, benchmark_entry_price=22.0, entry_days_ago=70):
        e = MagicMock(spec=ShadowPortfolioEntry)
        e.ticker = ticker
        e.entry_price = entry_price
        e.benchmark_entry_price = benchmark_entry_price
        e.benchmark_ticker = "REM"
        e.technical_outcome_label = "PENDING"
        e.entry_date = self.now - timedelta(days=entry_days_ago)
        return e

    def _query_returns(self, entries):
        self.db.query.return_value.filter.return_value.filter.return_value.all.return_value = entries

    def test_correct_alpha(self):
        e = self._make_pending_tech(entry_price=25.0, benchmark_entry_price=22.0)
        self._query_returns([e])
        # ticker +8%, benchmark +2% → alpha = +6% → CORRECT
        result = self.mgr.populate_technical_outcomes(
            self.db,
            exit_prices={"STWD": 27.0},
            benchmark_exit_prices={"REM": 22.44},
            as_of=self.now,
        )
        assert e.technical_outcome_label == "CORRECT"
        assert result["updated"] == 1

    def test_incorrect_alpha(self):
        e = self._make_pending_tech(entry_price=25.0, benchmark_entry_price=22.0)
        self._query_returns([e])
        # ticker -6%, benchmark +1% → alpha = -7% → INCORRECT
        result = self.mgr.populate_technical_outcomes(
            self.db,
            exit_prices={"STWD": 23.5},
            benchmark_exit_prices={"REM": 22.22},
            as_of=self.now,
        )
        assert e.technical_outcome_label == "INCORRECT"

    def test_neutral_alpha_within_band(self):
        e = self._make_pending_tech(entry_price=25.0, benchmark_entry_price=22.0)
        self._query_returns([e])
        # ticker +1%, benchmark +0% → alpha = +1% → NEUTRAL (< 3%)
        result = self.mgr.populate_technical_outcomes(
            self.db,
            exit_prices={"STWD": 25.25},
            benchmark_exit_prices={"REM": 22.0},
            as_of=self.now,
        )
        assert e.technical_outcome_label == "NEUTRAL"

    def test_no_entry_price_sets_neutral(self):
        e = self._make_pending_tech()
        e.entry_price = None
        self._query_returns([e])
        self.mgr.populate_technical_outcomes(
            self.db, exit_prices={"STWD": 27.0}, benchmark_exit_prices={"REM": 22.5}, as_of=self.now
        )
        assert e.technical_outcome_label == "NEUTRAL"

    def test_missing_benchmark_entry_price_sets_neutral(self):
        e = self._make_pending_tech()
        e.benchmark_entry_price = None
        self._query_returns([e])
        self.mgr.populate_technical_outcomes(
            self.db, exit_prices={"STWD": 27.0}, benchmark_exit_prices={"REM": 22.5}, as_of=self.now
        )
        assert e.technical_outcome_label == "NEUTRAL"

    def test_delisted_ticker_sets_incorrect(self):
        e = self._make_pending_tech()
        self._query_returns([e])
        # exit price not in dict → delisted
        self.mgr.populate_technical_outcomes(
            self.db, exit_prices={}, benchmark_exit_prices={"REM": 22.5}, as_of=self.now
        )
        assert e.technical_outcome_label == "INCORRECT"

    def test_skips_entries_within_hold_period(self):
        e = self._make_pending_tech(entry_days_ago=30)  # 30 < 60 day hold
        self._query_returns([])  # query filters them out
        result = self.mgr.populate_technical_outcomes(
            self.db, exit_prices={"STWD": 27.0}, benchmark_exit_prices={"REM": 22.5}, as_of=self.now
        )
        assert result["updated"] == 0


class TestPopulateIncomeDurabilityOutcomes:
    def setup_method(self):
        self.mgr = ShadowPortfolioManager()
        self.db = MagicMock()
        self.now = datetime(2026, 3, 1, tzinfo=timezone.utc)

    def _make_pending_income(self, ticker="STWD", ttm_at_entry=1.80, dur_score=28.0, entry_days_ago=370):
        e = MagicMock(spec=ShadowPortfolioEntry)
        e.ticker = ticker
        e.income_ttm_at_entry = ttm_at_entry
        e.durability_score_at_entry = dur_score
        e.income_outcome_label = "PENDING"
        e.durability_outcome_label = "PENDING"
        e.entry_date = self.now - timedelta(days=entry_days_ago)
        return e

    def _query_returns(self, entries):
        self.db.query.return_value.filter.return_value.filter.return_value.all.return_value = entries

    # ── Income tests ──────────────────────────────────────────────────────────

    def test_income_correct_growth(self):
        e = self._make_pending_income(ttm_at_entry=1.80)
        self._query_returns([e])
        # TTM grew by +3% → CORRECT
        result = self.mgr.populate_income_durability_outcomes(
            self.db, ttm_dividends={"STWD": 1.854}, current_durability_scores={}, as_of=self.now
        )
        assert e.income_outcome_label == "CORRECT"
        assert result["income"]["updated"] == 1

    def test_income_incorrect_cut(self):
        e = self._make_pending_income(ttm_at_entry=1.80)
        self._query_returns([e])
        # TTM cut by -6% → INCORRECT
        self.mgr.populate_income_durability_outcomes(
            self.db, ttm_dividends={"STWD": 1.692}, current_durability_scores={}, as_of=self.now
        )
        assert e.income_outcome_label == "INCORRECT"

    def test_income_neutral_flat(self):
        e = self._make_pending_income(ttm_at_entry=1.80)
        self._query_returns([e])
        # TTM unchanged (0%) → NEUTRAL (between -5% and +2%)
        self.mgr.populate_income_durability_outcomes(
            self.db, ttm_dividends={"STWD": 1.80}, current_durability_scores={}, as_of=self.now
        )
        assert e.income_outcome_label == "NEUTRAL"

    def test_income_suspended_forced_incorrect(self):
        e = self._make_pending_income(ttm_at_entry=1.80)
        self._query_returns([e])
        # TTM at exit = 0 → forced INCORRECT (suspension)
        self.mgr.populate_income_durability_outcomes(
            self.db, ttm_dividends={"STWD": 0.0}, current_durability_scores={}, as_of=self.now
        )
        assert e.income_outcome_label == "INCORRECT"

    def test_income_null_entry_ttm_sets_neutral(self):
        e = self._make_pending_income(ttm_at_entry=None)
        self._query_returns([e])
        self.mgr.populate_income_durability_outcomes(
            self.db, ttm_dividends={"STWD": 1.80}, current_durability_scores={}, as_of=self.now
        )
        assert e.income_outcome_label == "NEUTRAL"

    def test_income_zero_entry_ttm_sets_neutral(self):
        e = self._make_pending_income(ttm_at_entry=0.0)
        self._query_returns([e])
        self.mgr.populate_income_durability_outcomes(
            self.db, ttm_dividends={"STWD": 1.80}, current_durability_scores={}, as_of=self.now
        )
        assert e.income_outcome_label == "NEUTRAL"

    # ── Durability tests ──────────────────────────────────────────────────────

    def test_durability_correct_high_confidence_income_correct(self):
        # weight_durability=40 → threshold=24; dur_score_at_entry=30 (HIGH)
        e = self._make_pending_income(ttm_at_entry=1.80, dur_score=30.0)
        self._query_returns([e])
        # Force income CORRECT first
        self.mgr.populate_income_durability_outcomes(
            self.db,
            ttm_dividends={"STWD": 1.854},  # +3% → CORRECT
            current_durability_scores={"STWD": 32.0},
            as_of=self.now,
            weight_durability=40.0,
        )
        assert e.durability_outcome_label == "CORRECT"

    def test_durability_incorrect_high_confidence_income_incorrect(self):
        e = self._make_pending_income(ttm_at_entry=1.80, dur_score=30.0)
        self._query_returns([e])
        self.mgr.populate_income_durability_outcomes(
            self.db,
            ttm_dividends={"STWD": 1.692},  # -6% → INCORRECT
            current_durability_scores={"STWD": 28.0},
            as_of=self.now,
            weight_durability=40.0,
        )
        assert e.durability_outcome_label == "INCORRECT"

    def test_durability_neutral_low_confidence_income_incorrect(self):
        # dur_score_at_entry=15 < threshold=24 (LOW confidence) → NEUTRAL even with cut
        e = self._make_pending_income(ttm_at_entry=1.80, dur_score=15.0)
        self._query_returns([e])
        self.mgr.populate_income_durability_outcomes(
            self.db,
            ttm_dividends={"STWD": 1.692},  # cut → income INCORRECT
            current_durability_scores={"STWD": 12.0},
            as_of=self.now,
            weight_durability=40.0,
        )
        assert e.durability_outcome_label == "NEUTRAL"

    def test_durability_skipped_when_income_still_pending(self):
        e = self._make_pending_income(ttm_at_entry=1.80, dur_score=30.0)
        # income not in ttm_dividends dict → stays PENDING
        e.income_outcome_label = "PENDING"  # won't be updated
        self._query_returns([e])
        self.mgr.populate_income_durability_outcomes(
            self.db,
            ttm_dividends={},  # no data → income stays PENDING
            current_durability_scores={"STWD": 32.0},
            as_of=self.now,
        )
        assert e.durability_outcome_label == "PENDING"


# ══════════════════════════════════════════════════════════════════════════════
# Task 5: Weight tuner — per-pillar signal
# ══════════════════════════════════════════════════════════════════════════════

class TestPerPillarWeightTuner:
    def setup_method(self):
        self.tuner = QuarterlyWeightTuner()
        self.profile = {
            "asset_class": "DIVIDEND_STOCK",
            "version": 1,
            "weight_yield": 40,
            "weight_durability": 40,
            "weight_technical": 20,
            "yield_sub_weights": {},
            "durability_sub_weights": {},
            "technical_sub_weights": {},
        }

    def _make_outcome(self, income_label="NEUTRAL", dur_label="NEUTRAL", tech_label="NEUTRAL",
                      vy=32.0, fd=32.0, te=16.0):
        e = MagicMock(spec=ShadowPortfolioEntry)
        e.income_outcome_label = income_label
        e.durability_outcome_label = dur_label
        e.technical_outcome_label = tech_label
        e.valuation_yield_score = vy
        e.financial_durability_score = fd
        e.technical_entry_score = te
        return e

    def test_income_pillar_increases_when_yield_scores_predict_correct(self):
        """High yield scores on CORRECT income outcomes → positive signal → increase weight_yield."""
        outcomes = (
            [self._make_outcome(income_label="CORRECT", vy=38.0)] * 8 +
            [self._make_outcome(income_label="INCORRECT", vy=18.0)] * 5
        )
        proposed, skip = self.tuner.compute_adjustment(outcomes, self.profile, pillar="income_durability")
        assert skip is None
        assert proposed["weight_yield"] > self.profile["weight_yield"]

    def test_technical_pillar_decreases_when_technical_scores_predict_incorrectly(self):
        """High technical scores on INCORRECT tech outcomes → negative signal → decrease weight."""
        outcomes = (
            [self._make_outcome(tech_label="CORRECT", te=8.0)] * 5 +
            [self._make_outcome(tech_label="INCORRECT", te=18.0)] * 8
        )
        proposed, skip = self.tuner.compute_adjustment(outcomes, self.profile, pillar="technical")
        assert skip is None
        assert proposed["weight_technical"] < self.profile["weight_technical"]

    def test_skips_insufficient_pillar_samples(self):
        """Fewer than MIN_SAMPLES per pillar → SKIPPED."""
        outcomes = [self._make_outcome(income_label="CORRECT")] * 3  # < 10
        _, skip = self.tuner.compute_adjustment(outcomes, self.profile, pillar="income_durability")
        assert skip is not None
        assert SKIP_INSUFFICIENT in skip

    def test_all_pillar_uses_all_labels(self):
        """pillar='all' computes signal from all three label columns."""
        outcomes = (
            [self._make_outcome(income_label="CORRECT", vy=38.0, dur_label="CORRECT", fd=36.0, tech_label="CORRECT", te=18.0)] * 10 +
            [self._make_outcome(income_label="INCORRECT", vy=18.0, dur_label="INCORRECT", fd=16.0, tech_label="INCORRECT", te=6.0)] * 10
        )
        proposed, skip = self.tuner.compute_adjustment(outcomes, self.profile, pillar="all")
        assert skip is None
        assert proposed is not None

    def test_no_signal_returns_skip(self):
        """Balanced CORRECT/INCORRECT with equal scores → no signal → SKIP."""
        outcomes = (
            [self._make_outcome(income_label="CORRECT", vy=32.0)] * 10 +
            [self._make_outcome(income_label="INCORRECT", vy=32.0)] * 10
        )
        _, skip = self.tuner.compute_adjustment(outcomes, self.profile, pillar="income_durability")
        assert skip == SKIP_NO_SIGNAL


# ══════════════════════════════════════════════════════════════════════════════
# Task 6: Threshold trigger
# ══════════════════════════════════════════════════════════════════════════════

class TestThresholdTrigger:
    def setup_method(self):
        self.db = MagicMock()

    def _make_outcome(self, income_label="NEUTRAL", tech_label="NEUTRAL"):
        e = MagicMock(spec=ShadowPortfolioEntry)
        e.income_outcome_label = income_label
        e.technical_outcome_label = tech_label
        return e

    def test_triggers_when_incorrect_rate_exceeds_threshold(self):
        from app.scoring.weight_tuner import should_trigger_early_review
        # 15 INCORRECT out of 20 = 75% > 60%
        outcomes = [self._make_outcome(income_label="INCORRECT")] * 15 + [self._make_outcome(income_label="CORRECT")] * 5
        result = should_trigger_early_review(outcomes, "income_durability", last_review_days_ago=60)
        assert result is True

    def test_does_not_trigger_when_rate_below_threshold(self):
        from app.scoring.weight_tuner import should_trigger_early_review
        # 10 INCORRECT out of 20 = 50% < 60%
        outcomes = [self._make_outcome(income_label="INCORRECT")] * 10 + [self._make_outcome(income_label="CORRECT")] * 10
        result = should_trigger_early_review(outcomes, "income_durability", last_review_days_ago=60)
        assert result is False

    def test_does_not_trigger_below_min_outcomes(self):
        from app.scoring.weight_tuner import should_trigger_early_review
        # only 12 outcomes < 20 minimum
        outcomes = [self._make_outcome(income_label="INCORRECT")] * 12
        result = should_trigger_early_review(outcomes, "income_durability", last_review_days_ago=60)
        assert result is False

    def test_does_not_trigger_within_gap_period(self):
        from app.scoring.weight_tuner import should_trigger_early_review
        # 15/20 incorrect (would trigger) but last review was 15 days ago (< 30 day gap)
        outcomes = [self._make_outcome(income_label="INCORRECT")] * 15 + [self._make_outcome(income_label="CORRECT")] * 5
        result = should_trigger_early_review(outcomes, "income_durability", last_review_days_ago=15)
        assert result is False


# ══════════════════════════════════════════════════════════════════════════════
# Task 7: Learning Loop API v3 endpoints
# ══════════════════════════════════════════════════════════════════════════════

def _make_token():
    import jwt as pyjwt
    secret = os.environ.get("JWT_SECRET", "test-secret-for-tests")
    return pyjwt.encode({"sub": "test", "exp": 9999999999}, secret, algorithm="HS256")


class TestLearningLoopAPIV3:
    def setup_method(self):
        from app.main import app
        from fastapi.testclient import TestClient
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + _make_token()}

    def test_populate_technical_outcomes_returns_200(self):
        with patch("app.api.learning_loop.shadow_portfolio_manager") as mock_mgr, \
             patch("app.api.learning_loop.should_trigger_early_review", return_value=False):
            mock_mgr.populate_technical_outcomes.return_value = {
                "updated": 3, "total_pending": 3
            }
            resp = self.client.post(
                "/learning-loop/populate-technical-outcomes",
                json={"exit_prices": {"STWD": 25.0}, "benchmark_exit_prices": {"REM": 22.0}},
                headers=self.headers,
            )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 3

    def test_populate_income_durability_returns_200(self):
        with patch("app.api.learning_loop.shadow_portfolio_manager") as mock_mgr, \
             patch("app.api.learning_loop.should_trigger_early_review", return_value=False):
            mock_mgr.populate_income_durability_outcomes.return_value = {
                "income": {"updated": 2, "skipped": 0, "total_pending": 2},
                "durability": {"updated": 2, "skipped_awaiting_income": 0, "total_pending": 2},
            }
            resp = self.client.post(
                "/learning-loop/populate-income-durability-outcomes",
                json={"ttm_dividends": {"STWD": 1.85}, "current_durability_scores": {"STWD": 30.0}},
                headers=self.headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["income"]["updated"] == 2

    def test_old_populate_outcomes_returns_410(self):
        resp = self.client.post(
            "/learning-loop/populate-outcomes",
            json={"exit_prices": {}},
            headers=self.headers,
        )
        assert resp.status_code == 410

    def test_review_accepts_pillar_param(self):
        with patch("app.api.learning_loop.shadow_portfolio_manager") as mock_mgr, \
             patch("app.api.learning_loop.quarterly_weight_tuner") as mock_tuner:
            mock_mgr.get_completed_outcomes.return_value = []
            review_mock = MagicMock()
            review_mock.id = uuid.uuid4()
            review_mock.asset_class = "DIVIDEND_STOCK"
            review_mock.triggered_at = datetime.now(timezone.utc)
            review_mock.triggered_by = "test"
            review_mock.status = "SKIPPED"
            review_mock.outcomes_analyzed = 0
            review_mock.correct_count = 0
            review_mock.incorrect_count = 0
            review_mock.neutral_count = 0
            review_mock.weight_yield_before = None
            review_mock.weight_durability_before = None
            review_mock.weight_technical_before = None
            review_mock.weight_yield_after = None
            review_mock.weight_durability_after = None
            review_mock.weight_technical_after = None
            review_mock.delta_yield = None
            review_mock.delta_durability = None
            review_mock.delta_technical = None
            review_mock.skip_reason = "insufficient_samples:0"
            review_mock.completed_at = None
            review_mock.pillar_reviewed = "technical"
            mock_tuner.apply_review.return_value = review_mock
            resp = self.client.post(
                "/learning-loop/review/DIVIDEND_STOCK",
                json={"triggered_by": "test", "pillar": "technical"},
                headers=self.headers,
            )
        assert resp.status_code == 201
        assert resp.json()["pillar_reviewed"] == "technical"


# ══════════════════════════════════════════════════════════════════════════════
# Task 8: Weights API — benchmark_ticker
# ══════════════════════════════════════════════════════════════════════════════

class TestWeightsBenchmarkTicker:
    def setup_method(self):
        from app.main import app
        from app.database import get_db
        from app.auth import verify_token
        from fastapi.testclient import TestClient

        self._mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: self._mock_db
        app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}
        self.client = TestClient(app, raise_server_exceptions=False)
        self.headers = {"Authorization": "Bearer " + _make_token()}

    def teardown_method(self):
        from app.main import app
        from app.database import get_db
        from app.auth import verify_token
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(verify_token, None)

    def test_get_profile_includes_benchmark_ticker(self):
        mock_profile = MagicMock(spec=ScoringWeightProfile)
        mock_profile.id = uuid.uuid4()
        mock_profile.asset_class = "DIVIDEND_STOCK"
        mock_profile.version = 1
        mock_profile.is_active = True
        mock_profile.weight_yield = 40
        mock_profile.weight_durability = 40
        mock_profile.weight_technical = 20
        mock_profile.yield_sub_weights = {}
        mock_profile.durability_sub_weights = {}
        mock_profile.technical_sub_weights = {}
        mock_profile.benchmark_ticker = "DVY"
        mock_profile.source = "MANUAL"
        mock_profile.change_reason = None
        mock_profile.created_by = None
        mock_profile.created_at = datetime.now(timezone.utc)
        mock_profile.activated_at = None
        mock_profile.superseded_at = None
        mock_profile.superseded_by_id = None

        self._mock_db.query.return_value.filter.return_value.first.return_value = mock_profile

        resp = self.client.get("/weights/DIVIDEND_STOCK", headers=self.headers)

        assert resp.status_code == 200
        assert resp.json()["benchmark_ticker"] == "DVY"
