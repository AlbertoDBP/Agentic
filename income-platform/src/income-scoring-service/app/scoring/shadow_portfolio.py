"""
Agent 03 — Income Scoring Service
Shadow Portfolio Manager: records scored recommendations and populates outcomes.

The learning loop uses shadow portfolio entries to assess whether each asset
class's weight profile made accurate predictions over a 90-day hold period.

Entry recording:
  Only AGGRESSIVE_BUY and ACCUMULATE recommendations are recorded (bullish
  calls that the scorer was confident enough to endorse).

Outcome labels (set after hold_period_days):
  CORRECT   — actual_return_pct >= CORRECT_THRESHOLD  (+5.0%)
  INCORRECT — actual_return_pct <= INCORRECT_THRESHOLD (-5.0%)
  NEUTRAL   — return in (-5%, +5%) — inconclusive for learning
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import ShadowPortfolioEntry

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

TECHNICAL_HOLD_DAYS: int = 60
INCOME_DURABILITY_HOLD_DAYS: int = 365
TECHNICAL_CORRECT_ALPHA: float = 3.0
TECHNICAL_INCORRECT_ALPHA: float = -3.0

# Keep for backward compat
HOLD_PERIOD_DAYS: int = INCOME_DURABILITY_HOLD_DAYS

CORRECT_THRESHOLD: float = 5.0    # % return → CORRECT
INCORRECT_THRESHOLD: float = -5.0  # % return → INCORRECT
MIN_ENTRY_SCORE: float = 70.0     # only ACCUMULATE+ (score ≥ 70) recorded

INCOME_CORRECT_CHANGE_PCT: float = 2.0
INCOME_INCORRECT_CHANGE_PCT: float = -5.0
DURABILITY_CONFIDENCE_RATIO: float = 0.60


class ShadowPortfolioManager:
    """Records scoring outcomes and computes prediction labels."""

    def maybe_record_entry(
        self,
        db: Session,
        *,
        income_score_id,
        ticker: str,
        asset_class: str,
        entry_score: float,
        entry_grade: str,
        entry_recommendation: str,
        valuation_yield_score: float,
        financial_durability_score: float,
        technical_entry_score: float,
        weight_profile_id=None,
        entry_price: Optional[float] = None,
        # v3.0 per-pillar capture
        benchmark_ticker: Optional[str] = None,
        benchmark_entry_price: Optional[float] = None,
        durability_score_at_entry: Optional[float] = None,
        income_ttm_at_entry: Optional[float] = None,
    ) -> Optional[ShadowPortfolioEntry]:
        """
        Record a shadow portfolio entry if the recommendation is ACCUMULATE or AGGRESSIVE_BUY.
        Returns None (and does not call db.add) for HOLD, SELL, or any other recommendation.
        """
        if entry_recommendation not in ("AGGRESSIVE_BUY", "ACCUMULATE"):
            return None

        entry = ShadowPortfolioEntry(
            income_score_id=income_score_id,
            ticker=ticker,
            asset_class=asset_class.upper(),
            weight_profile_id=weight_profile_id,
            entry_score=entry_score,
            entry_grade=entry_grade,
            entry_recommendation=entry_recommendation,
            valuation_yield_score=valuation_yield_score,
            financial_durability_score=financial_durability_score,
            technical_entry_score=technical_entry_score,
            entry_price=entry_price,
            entry_date=datetime.now(timezone.utc),
            hold_period_days=INCOME_DURABILITY_HOLD_DAYS,
            outcome_label="PENDING",
            # v3.0
            benchmark_ticker=benchmark_ticker,
            benchmark_entry_price=benchmark_entry_price,
            durability_score_at_entry=durability_score_at_entry,
            income_ttm_at_entry=income_ttm_at_entry,
            technical_outcome_label="PENDING",
            income_outcome_label="PENDING",
            durability_outcome_label="PENDING",
        )
        try:
            db.add(entry)
            db.flush()
            logger.debug(
                "Shadow entry recorded for %s (%s, score=%.1f)",
                ticker, entry_recommendation, entry_score,
            )
            return entry
        except Exception as exc:
            logger.warning("Failed to record shadow entry for %s: %s", ticker, exc)
            db.rollback()
            return None

    def populate_technical_outcomes(
        self,
        db: Session,
        exit_prices: dict[str, float],
        benchmark_exit_prices: dict[str, float],
        *,
        as_of: Optional[datetime] = None,
    ) -> dict:
        """
        Populate technical_outcome_label for PENDING entries past T+60.

        exit_prices: {ticker: current_price}
        benchmark_exit_prices: {benchmark_ticker: current_price}
        """
        now = as_of or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=TECHNICAL_HOLD_DAYS)

        pending = (
            db.query(ShadowPortfolioEntry)
            .filter(ShadowPortfolioEntry.technical_outcome_label == "PENDING")
            .filter(ShadowPortfolioEntry.entry_date <= cutoff)
            .all()
        )

        updated = 0

        for entry in pending:
            exit_price = exit_prices.get(entry.ticker)

            # Delisted or zero price: no valid exit price → INCORRECT
            if not exit_price or exit_price <= 0:
                entry.technical_outcome_label = "INCORRECT"
                entry.technical_outcome_at = now
                updated += 1
                continue

            # Missing entry data → NEUTRAL
            if not entry.entry_price or entry.entry_price <= 0:
                entry.technical_outcome_label = "NEUTRAL"
                entry.technical_outcome_at = now
                updated += 1
                continue

            if not entry.benchmark_entry_price or entry.benchmark_entry_price <= 0:
                entry.technical_outcome_label = "NEUTRAL"
                entry.technical_outcome_at = now
                updated += 1
                continue

            bm_exit = benchmark_exit_prices.get(entry.benchmark_ticker or "")
            if bm_exit is None or bm_exit <= 0:
                entry.technical_outcome_label = "NEUTRAL"
                entry.technical_outcome_at = now
                updated += 1
                continue

            ticker_return = (exit_price - entry.entry_price) / entry.entry_price * 100.0
            bm_return = (bm_exit - entry.benchmark_entry_price) / entry.benchmark_entry_price * 100.0
            alpha = round(ticker_return - bm_return, 4)

            entry.technical_exit_price = exit_price
            entry.benchmark_exit_price = bm_exit
            entry.technical_return_pct = round(ticker_return, 4)
            entry.technical_benchmark_return_pct = round(bm_return, 4)
            entry.technical_alpha_pct = alpha
            entry.technical_outcome_at = now

            if alpha >= TECHNICAL_CORRECT_ALPHA:
                entry.technical_outcome_label = "CORRECT"
            elif alpha <= TECHNICAL_INCORRECT_ALPHA:
                entry.technical_outcome_label = "INCORRECT"
            else:
                entry.technical_outcome_label = "NEUTRAL"

            updated += 1

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("populate_technical_outcomes commit failed: %s", exc)
            raise

        logger.info("Technical outcomes: %d updated, %d pending total", updated, len(pending))
        return {"updated": updated, "total_pending": len(pending)}

    def populate_income_durability_outcomes(
        self,
        db: Session,
        ttm_dividends: dict[str, float],
        current_durability_scores: dict[str, float],
        *,
        as_of: Optional[datetime] = None,
        weight_durability: float = 40.0,
    ) -> dict:
        """
        Populate income_outcome_label and durability_outcome_label for entries past T+365.

        Income is computed first; Durability is derived from the income outcome.
        ttm_dividends: {ticker: ttm_sum_at_exit}
        current_durability_scores: {ticker: financial_durability_score_now}
        weight_durability: active weight for this asset class (used for confidence threshold)
        """
        now = as_of or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=INCOME_DURABILITY_HOLD_DAYS)

        pending = (
            db.query(ShadowPortfolioEntry)
            .filter(ShadowPortfolioEntry.income_outcome_label == "PENDING")
            .filter(ShadowPortfolioEntry.entry_date <= cutoff)
            .all()
        )

        income_updated = income_skipped = 0
        dur_updated = dur_skipped_awaiting = 0

        confidence_threshold = DURABILITY_CONFIDENCE_RATIO * weight_durability

        for entry in pending:
            # ── Income ────────────────────────────────────────────────────────
            ttm_at_exit = ttm_dividends.get(entry.ticker)
            if ttm_at_exit is None:
                income_skipped += 1
                continue

            ttm_at_entry = entry.income_ttm_at_entry

            # Guard 1: entry TTM null or zero → NEUTRAL (no formula possible)
            if not ttm_at_entry or ttm_at_entry <= 0:
                entry.income_outcome_label = "NEUTRAL"
                entry.income_ttm_at_exit = ttm_at_exit
                entry.income_outcome_at = now
                income_updated += 1
            # Guard 2: exit TTM zero → suspended → INCORRECT
            elif ttm_at_exit == 0.0:
                entry.income_outcome_label = "INCORRECT"
                entry.income_ttm_at_exit = ttm_at_exit
                entry.income_change_pct = -100.0
                entry.income_outcome_at = now
                income_updated += 1
            else:
                change_pct = (ttm_at_exit - ttm_at_entry) / ttm_at_entry * 100.0
                entry.income_ttm_at_exit = ttm_at_exit
                entry.income_change_pct = round(change_pct, 4)
                entry.income_outcome_at = now
                if change_pct >= INCOME_CORRECT_CHANGE_PCT:
                    entry.income_outcome_label = "CORRECT"
                elif change_pct <= INCOME_INCORRECT_CHANGE_PCT:
                    entry.income_outcome_label = "INCORRECT"
                else:
                    entry.income_outcome_label = "NEUTRAL"
                income_updated += 1

            # ── Durability (derived from income outcome) ───────────────────
            if entry.income_outcome_label == "PENDING":
                dur_skipped_awaiting += 1
                continue

            dur_score_at_exit = current_durability_scores.get(entry.ticker)
            if dur_score_at_exit is not None:
                entry.durability_score_at_exit = dur_score_at_exit

            dur_entry = entry.durability_score_at_entry or 0.0
            high_confidence = dur_entry >= confidence_threshold
            income_label = entry.income_outcome_label

            if income_label == "NEUTRAL":
                entry.durability_outcome_label = "NEUTRAL"
            elif high_confidence and income_label == "CORRECT":
                entry.durability_outcome_label = "CORRECT"
            elif high_confidence and income_label == "INCORRECT":
                entry.durability_outcome_label = "INCORRECT"
            else:
                # low confidence regardless of income outcome
                entry.durability_outcome_label = "NEUTRAL"

            entry.durability_outcome_at = now
            dur_updated += 1

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("populate_income_durability_outcomes commit failed: %s", exc)
            raise

        logger.info(
            "Income/Durability outcomes: income=%d updated, %d skipped; dur=%d updated, %d skipped",
            income_updated, income_skipped, dur_updated, dur_skipped_awaiting,
        )
        return {
            "income": {"updated": income_updated, "skipped": income_skipped, "total_pending": len(pending)},
            "durability": {"updated": dur_updated, "skipped_awaiting_income": dur_skipped_awaiting, "total_pending": len(pending)},
        }

    def populate_outcomes_legacy(
        self,
        db: Session,
        exit_prices: dict[str, float],
        *,
        as_of: Optional[datetime] = None,
    ) -> dict:
        """
        Populate outcome labels for PENDING entries past their hold period.

        Args:
            db:          SQLAlchemy session.
            exit_prices: Dict of {ticker: current_price} for entries needing outcomes.
                         Entries whose ticker is not in this dict are skipped.
            as_of:       Reference date for hold period check (defaults to now UTC).

        Returns:
            Summary dict: {updated, skipped_no_price, skipped_no_entry_price, total_pending}
        """
        now = as_of or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=HOLD_PERIOD_DAYS)

        pending = (
            db.query(ShadowPortfolioEntry)
            .filter(
                ShadowPortfolioEntry.outcome_label == "PENDING",
                ShadowPortfolioEntry.entry_date <= cutoff,
            )
            .all()
        )

        updated = skipped_no_price = skipped_no_entry_price = 0

        for entry in pending:
            exit_price = exit_prices.get(entry.ticker)
            if exit_price is None:
                skipped_no_price += 1
                continue
            if not entry.entry_price or entry.entry_price <= 0:
                skipped_no_entry_price += 1
                entry.outcome_label = "NEUTRAL"  # can't compute return
                entry.exit_price = exit_price
                entry.exit_date = now
                entry.outcome_populated_at = now
                continue

            return_pct = (exit_price - entry.entry_price) / entry.entry_price * 100.0
            entry.exit_price = exit_price
            entry.exit_date = now
            entry.actual_return_pct = round(return_pct, 4)
            entry.outcome_populated_at = now

            if return_pct >= CORRECT_THRESHOLD:
                entry.outcome_label = "CORRECT"
            elif return_pct <= INCORRECT_THRESHOLD:
                entry.outcome_label = "INCORRECT"
            else:
                entry.outcome_label = "NEUTRAL"

            updated += 1

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("populate_outcomes commit failed: %s", exc)
            raise

        logger.info(
            "Shadow portfolio outcome population: %d updated, %d skipped (no price), "
            "%d skipped (no entry price), %d total pending",
            updated, skipped_no_price, skipped_no_entry_price, len(pending),
        )
        return {
            "updated": updated,
            "skipped_no_price": skipped_no_price,
            "skipped_no_entry_price": skipped_no_entry_price,
            "total_pending": len(pending),
        }

    # Backward-compat alias: existing call sites use populate_outcomes until Task 7
    def populate_outcomes(self, *args, **kwargs):
        return self.populate_outcomes_legacy(*args, **kwargs)

    def get_pending_past_hold(self, db: Session, as_of: Optional[datetime] = None) -> list:
        """Return PENDING entries whose hold period has elapsed."""
        now = as_of or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=HOLD_PERIOD_DAYS)
        return (
            db.query(ShadowPortfolioEntry)
            .filter(
                ShadowPortfolioEntry.outcome_label == "PENDING",
                ShadowPortfolioEntry.entry_date <= cutoff,
            )
            .order_by(ShadowPortfolioEntry.entry_date)
            .all()
        )

    def get_completed_outcomes(
        self,
        db: Session,
        asset_class: str,
        since: Optional[datetime] = None,
    ) -> list:
        """
        Return completed (non-PENDING) entries for a given asset class.
        Optionally filtered to entries since a given date.
        """
        resolved_states = ["CORRECT", "INCORRECT", "NEUTRAL"]
        q = (
            db.query(ShadowPortfolioEntry)
            .filter(
                ShadowPortfolioEntry.asset_class == asset_class.upper(),
                or_(
                    ShadowPortfolioEntry.outcome_label.in_(resolved_states),
                    ShadowPortfolioEntry.technical_outcome_label.in_(resolved_states),
                    ShadowPortfolioEntry.income_outcome_label.in_(resolved_states),
                    ShadowPortfolioEntry.durability_outcome_label.in_(resolved_states),
                )
            )
        )
        if since:
            q = q.filter(ShadowPortfolioEntry.outcome_populated_at >= since)
        return q.order_by(ShadowPortfolioEntry.outcome_populated_at).all()


# Module-level singleton
shadow_portfolio_manager = ShadowPortfolioManager()
