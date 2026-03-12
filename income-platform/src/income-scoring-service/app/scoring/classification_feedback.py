"""
Agent 03 — Income Scoring Service
Phase 4: Detector Confidence Learning — Classification Feedback Tracker.

Records one ClassificationFeedback row per POST /scores/evaluate call so that
the accuracy of Agent 04's asset class predictions can be measured over time.

Sources:
  AGENT04        — asset_class was auto-classified by Agent 04 (no human override)
  MANUAL_OVERRIDE — caller explicitly provided asset_class in the request

Mismatch detection (requires classification_verify_overrides=True):
  When source=MANUAL_OVERRIDE and the service also calls Agent 04, is_mismatch is
  True if Agent 04's answer differs from the caller's override.

Monthly rollup:
  compute_monthly_rollup() produces ClassifierAccuracyRun rows for one calendar
  month, broken down by asset class plus an ALL-class aggregate row.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ClassificationFeedback, ClassifierAccuracyRun

logger = logging.getLogger(__name__)

# Source token constants
SOURCE_AGENT04 = "AGENT04"
SOURCE_MANUAL = "MANUAL_OVERRIDE"


class ClassificationFeedbackTracker:
    """
    Stateless tracker — one singleton per process.

    All DB mutations are intentionally left uncommitted (just db.add + db.flush)
    so they participate in the caller's existing transaction and are rolled back
    if the surrounding evaluate_score transaction fails.
    """

    def record(
        self,
        db: Session,
        *,
        income_score_id,
        ticker: str,
        asset_class_used: str,
        source: str,
        agent04_class: Optional[str] = None,
        agent04_confidence: Optional[float] = None,
    ) -> Optional[ClassificationFeedback]:
        """
        Record one feedback row for a scoring call.

        Args:
            income_score_id:   FK to the income_scores row (must be flushed first).
            ticker:            Ticker symbol.
            asset_class_used:  Asset class actually used for scoring.
            source:            SOURCE_AGENT04 or SOURCE_MANUAL.
            agent04_class:     Agent 04's classification (null if not called).
            agent04_confidence: Agent 04's confidence score (null if not available).

        Returns the inserted ORM row, or None on failure.
        """
        is_mismatch: Optional[bool] = None
        if source == SOURCE_MANUAL and agent04_class is not None:
            is_mismatch = agent04_class.upper() != asset_class_used.upper()

        try:
            row = ClassificationFeedback(
                income_score_id=income_score_id,
                ticker=ticker,
                asset_class_used=asset_class_used.upper(),
                source=source,
                agent04_class=agent04_class.upper() if agent04_class else None,
                agent04_confidence=agent04_confidence,
                is_mismatch=is_mismatch,
                captured_at=datetime.now(timezone.utc),
            )
            db.add(row)
            db.flush()
            logger.debug(
                "ClassificationFeedback recorded: %s source=%s used=%s agent04=%s mismatch=%s",
                ticker, source, asset_class_used, agent04_class, is_mismatch,
            )
            return row
        except Exception as exc:
            logger.warning("Failed to record classification feedback for %s: %s", ticker, exc)
            return None

    def compute_monthly_rollup(
        self,
        db: Session,
        period_month: str,
        *,
        computed_by: Optional[str] = None,
    ) -> list[ClassifierAccuracyRun]:
        """
        Aggregate ClassificationFeedback rows for a calendar month into
        ClassifierAccuracyRun rows (one per asset class + one ALL aggregate).

        Args:
            db:            SQLAlchemy session.
            period_month:  "YYYY-MM" string for the target month.
            computed_by:   Optional actor label for audit trail.

        Returns list of created ClassifierAccuracyRun ORM rows.
        """
        now = datetime.now(timezone.utc)

        # Parse month bounds (YYYY-MM → datetime range)
        try:
            year, month = int(period_month[:4]), int(period_month[5:7])
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Invalid period_month format '{period_month}', expected 'YYYY-MM'") from exc

        # Build month start/end
        from calendar import monthrange
        _, last_day = monthrange(year, month)
        month_start = datetime(year, month, 1, tzinfo=timezone.utc)
        month_end   = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

        rows = (
            db.query(ClassificationFeedback)
            .filter(
                ClassificationFeedback.captured_at >= month_start,
                ClassificationFeedback.captured_at <= month_end,
            )
            .all()
        )

        # Group by asset_class
        groups: dict[str, list[ClassificationFeedback]] = {}
        for row in rows:
            ac = row.asset_class_used
            groups.setdefault(ac, []).append(row)

        runs: list[ClassifierAccuracyRun] = []

        def _make_run(asset_class: Optional[str], subset: list) -> ClassifierAccuracyRun:
            total = len(subset)
            trusted = sum(1 for r in subset if r.source == SOURCE_AGENT04)
            overrides = sum(1 for r in subset if r.source == SOURCE_MANUAL)
            mismatches = sum(1 for r in subset if r.is_mismatch is True)

            accuracy = trusted / total if total > 0 else None
            override_rate = overrides / total if total > 0 else None
            mismatch_rate = mismatches / overrides if overrides > 0 else None

            return ClassifierAccuracyRun(
                period_month=period_month,
                asset_class=asset_class,
                total_calls=total,
                agent04_trusted=trusted,
                manual_overrides=overrides,
                mismatches=mismatches,
                accuracy_rate=accuracy,
                override_rate=override_rate,
                mismatch_rate=mismatch_rate,
                computed_at=now,
                computed_by=computed_by,
            )

        # Per-class rows
        for ac, subset in groups.items():
            run = _make_run(ac, subset)
            db.add(run)
            runs.append(run)

        # All-classes aggregate
        if rows:
            aggregate = _make_run(None, rows)
            db.add(aggregate)
            runs.append(aggregate)

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("compute_monthly_rollup commit failed for %s: %s", period_month, exc)
            raise

        logger.info(
            "Classifier accuracy rollup for %s: %d class-specific rows + 1 aggregate "
            "from %d total feedback entries",
            period_month, len(runs) - (1 if rows else 0), len(rows),
        )
        return runs

    def get_recent_feedback(
        self,
        db: Session,
        *,
        ticker: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> list[ClassificationFeedback]:
        """Return recent feedback rows, optionally filtered."""
        q = db.query(ClassificationFeedback).order_by(ClassificationFeedback.captured_at.desc())
        if ticker:
            q = q.filter(ClassificationFeedback.ticker == ticker.upper())
        if source:
            q = q.filter(ClassificationFeedback.source == source.upper())
        return q.limit(limit).all()

    def get_accuracy_runs(
        self,
        db: Session,
        *,
        period_month: Optional[str] = None,
        asset_class: Optional[str] = None,
        limit: int = 20,
    ) -> list[ClassifierAccuracyRun]:
        """Return accuracy run rows, optionally filtered."""
        q = db.query(ClassifierAccuracyRun).order_by(ClassifierAccuracyRun.computed_at.desc())
        if period_month:
            q = q.filter(ClassifierAccuracyRun.period_month == period_month)
        if asset_class:
            q = q.filter(ClassifierAccuracyRun.asset_class == asset_class.upper())
        return q.limit(limit).all()


# Module-level singleton
classification_feedback_tracker = ClassificationFeedbackTracker()
