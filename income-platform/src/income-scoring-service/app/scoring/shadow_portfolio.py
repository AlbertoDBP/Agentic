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

from sqlalchemy.orm import Session

from app.models import ShadowPortfolioEntry

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

HOLD_PERIOD_DAYS: int = 90
CORRECT_THRESHOLD: float = 5.0    # % return → CORRECT
INCORRECT_THRESHOLD: float = -5.0  # % return → INCORRECT
MIN_ENTRY_SCORE: float = 70.0     # only ACCUMULATE+ (score ≥ 70) recorded


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
    ) -> Optional[ShadowPortfolioEntry]:
        """
        Record a shadow portfolio entry if the recommendation qualifies.

        Only AGGRESSIVE_BUY and ACCUMULATE are recorded — these are bullish
        calls the weight profile was responsible for. Returns the created entry
        or None if the recommendation doesn't qualify.
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
            hold_period_days=HOLD_PERIOD_DAYS,
            outcome_label="PENDING",
        )
        try:
            db.add(entry)
            db.flush()
            logger.debug(
                "Shadow portfolio entry recorded for %s (%s, score=%.1f)",
                ticker, entry_recommendation, entry_score,
            )
            return entry
        except Exception as exc:
            logger.warning("Failed to record shadow portfolio entry for %s: %s", ticker, exc)
            db.rollback()
            return None

    def populate_outcomes(
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
        q = (
            db.query(ShadowPortfolioEntry)
            .filter(
                ShadowPortfolioEntry.asset_class == asset_class.upper(),
                ShadowPortfolioEntry.outcome_label.in_(["CORRECT", "INCORRECT", "NEUTRAL"]),
            )
        )
        if since:
            q = q.filter(ShadowPortfolioEntry.outcome_populated_at >= since)
        return q.order_by(ShadowPortfolioEntry.outcome_populated_at).all()


# Module-level singleton
shadow_portfolio_manager = ShadowPortfolioManager()
