"""
Agent 03 — Income Scoring Service
Quarterly Weight Tuner: adaptive weight adjustment from shadow portfolio outcomes.

Algorithm
─────────
For each asset class with enough completed outcomes (CORRECT + INCORRECT):

1. Compute normalised pillar fraction for each entry:
       yield_frac       = valuation_yield_score      / weight_yield
       durability_frac  = financial_durability_score  / weight_durability
       technical_frac   = technical_entry_score       / weight_technical

2. Compute mean fraction per pillar for CORRECT vs INCORRECT outcomes.

3. Signal per pillar = mean_correct - mean_incorrect
       Positive → pillar predicts success   → increase weight
       Negative → pillar predicts failure   → decrease weight

4. Translate signal to integer delta (scale = MAX_DELTA_PER_REVIEW):
       delta = clamp(round(signal * scale * 2), -MAX_DELTA, +MAX_DELTA)

5. Apply deltas to current weights, clamp each pillar to [MIN_PILLAR, MAX_PILLAR].

6. Normalise to sum = 100 (adjust the pillar with the largest absolute weight).

7. If no integer delta > 0, skip (no signal).

Constraints
───────────
- MIN_SAMPLES required before any adjustment (default 10 usable outcomes)
- MAX_DELTA_PER_REVIEW = 5 pts — prevents runaway drift
- MIN_PILLAR_WEIGHT = 5  — no pillar can be zeroed out
- MAX_PILLAR_WEIGHT = 90 — no pillar can dominate entirely
- Sub-weights are NEVER changed — only top-level pillar weights are tuned
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    ShadowPortfolioEntry,
    ScoringWeightProfile,
    WeightChangeAudit,
    WeightReviewRun,
)
from app.scoring.weight_profile_loader import weight_profile_loader

logger = logging.getLogger(__name__)

# ── Tuning constants ──────────────────────────────────────────────────────────

MIN_SAMPLES: int = 10          # minimum CORRECT + INCORRECT outcomes needed
MAX_DELTA_PER_REVIEW: int = 5  # max pts change per pillar per review cycle
MIN_PILLAR_WEIGHT: int = 5     # floor for any single pillar
MAX_PILLAR_WEIGHT: int = 90    # ceiling for any single pillar


# ── Skip reasons (returned as string tokens) ──────────────────────────────────

SKIP_INSUFFICIENT = "insufficient_samples"
SKIP_NO_SIGNAL    = "no_signal"
SKIP_NO_PROFILE   = "no_active_profile"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.5


def _normalize_to_100(y: int, d: int, t: int) -> tuple[int, int, int]:
    """
    Adjust the three weights so they sum to exactly 100.

    The shortfall or excess is added to / subtracted from the pillar with the
    largest weight (the one that can most easily absorb the rounding correction).
    """
    total = y + d + t
    if total == 100:
        return y, d, t

    delta = 100 - total  # positive if sum < 100, negative if sum > 100
    # Apply to the largest pillar
    largest = max((y, "y"), (d, "d"), (t, "t"))
    pillar = largest[1]
    if pillar == "y":
        y += delta
    elif pillar == "d":
        d += delta
    else:
        t += delta
    return y, d, t


class QuarterlyWeightTuner:
    """Stateless engine — one instance per process is sufficient."""

    def compute_adjustment(
        self,
        outcomes: list[ShadowPortfolioEntry],
        current_profile: dict,
    ) -> tuple[Optional[dict], Optional[str]]:
        """
        Compute proposed pillar weight adjustments from completed outcomes.

        Args:
            outcomes:        List of ShadowPortfolioEntry with outcome_label
                             in (CORRECT, INCORRECT, NEUTRAL).
            current_profile: Profile dict from WeightProfileLoader.

        Returns:
            (proposed_profile_dict, None)  if an adjustment is warranted.
            (None, skip_reason_str)        if no adjustment should be made.
        """
        correct   = [o for o in outcomes if o.outcome_label == "CORRECT"]
        incorrect = [o for o in outcomes if o.outcome_label == "INCORRECT"]
        usable    = len(correct) + len(incorrect)

        if usable < MIN_SAMPLES:
            return None, f"{SKIP_INSUFFICIENT}:{usable}"

        wy = float(current_profile["weight_yield"])
        wd = float(current_profile["weight_durability"])
        wt = float(current_profile["weight_technical"])

        def _fracs(entries: list) -> tuple[float, float, float]:
            if not entries:
                return 0.5, 0.5, 0.5
            yf = [e.valuation_yield_score / wy      if wy > 0 else 0.5 for e in entries]
            df = [e.financial_durability_score / wd  if wd > 0 else 0.5 for e in entries]
            tf = [e.technical_entry_score / wt       if wt > 0 else 0.5 for e in entries]
            return _mean(yf), _mean(df), _mean(tf)

        cy, cd, ct = _fracs(correct)
        iy, id_, it = _fracs(incorrect)

        # Signal: positive → pillar predicts CORRECT, increase weight
        sy = cy - iy
        sd = cd - id_
        st = ct - it

        scale = MAX_DELTA_PER_REVIEW
        dy = int(max(-scale, min(scale, round(sy * scale * 2))))
        dd = int(max(-scale, min(scale, round(sd * scale * 2))))
        dt = int(max(-scale, min(scale, round(st * scale * 2))))

        if dy == 0 and dd == 0 and dt == 0:
            return None, SKIP_NO_SIGNAL

        new_wy = int(max(MIN_PILLAR_WEIGHT, min(MAX_PILLAR_WEIGHT, wy + dy)))
        new_wd = int(max(MIN_PILLAR_WEIGHT, min(MAX_PILLAR_WEIGHT, wd + dd)))
        new_wt = int(max(MIN_PILLAR_WEIGHT, min(MAX_PILLAR_WEIGHT, wt + dt)))
        new_wy, new_wd, new_wt = _normalize_to_100(new_wy, new_wd, new_wt)

        proposed = dict(current_profile)
        proposed["weight_yield"]       = new_wy
        proposed["weight_durability"]  = new_wd
        proposed["weight_technical"]   = new_wt
        return proposed, None

    def apply_review(
        self,
        db: Session,
        asset_class: str,
        outcomes: list[ShadowPortfolioEntry],
        triggered_by: Optional[str] = None,
    ) -> WeightReviewRun:
        """
        Run a full quarterly review for one asset class.

        1. Load active profile.
        2. Compute adjustment.
        3. If adjustment warranted: create new ScoringWeightProfile + audit row,
           invalidate cache.
        4. Write WeightReviewRun record.
        5. Return the review run ORM row.
        """
        now = datetime.now(timezone.utc)
        ac  = asset_class.upper()

        review = WeightReviewRun(
            asset_class=ac,
            triggered_at=now,
            triggered_by=triggered_by,
            status="RUNNING",
            outcomes_analyzed=len(outcomes),
            correct_count=sum(1 for o in outcomes if o.outcome_label == "CORRECT"),
            incorrect_count=sum(1 for o in outcomes if o.outcome_label == "INCORRECT"),
            neutral_count=sum(1 for o in outcomes if o.outcome_label == "NEUTRAL"),
        )
        db.add(review)
        db.flush()  # get review.id

        # Load current active profile from DB (not cache — need live values)
        current_orm = (
            db.query(ScoringWeightProfile)
            .filter(
                ScoringWeightProfile.asset_class == ac,
                ScoringWeightProfile.is_active.is_(True),
            )
            .first()
        )

        if current_orm is None:
            review.status = "SKIPPED"
            review.skip_reason = SKIP_NO_PROFILE
            review.completed_at = now
            db.commit()
            return review

        review.profile_before_id       = current_orm.id
        review.weight_yield_before     = current_orm.weight_yield
        review.weight_durability_before = current_orm.weight_durability
        review.weight_technical_before  = current_orm.weight_technical

        current_profile = {
            "asset_class":          ac,
            "version":              current_orm.version,
            "weight_yield":         current_orm.weight_yield,
            "weight_durability":    current_orm.weight_durability,
            "weight_technical":     current_orm.weight_technical,
            "yield_sub_weights":    current_orm.yield_sub_weights,
            "durability_sub_weights": current_orm.durability_sub_weights,
            "technical_sub_weights": current_orm.technical_sub_weights,
        }

        proposed, skip_reason = self.compute_adjustment(outcomes, current_profile)

        if skip_reason is not None:
            review.status = "SKIPPED"
            review.skip_reason = skip_reason
            review.completed_at = now
            db.commit()
            logger.info("Weight review for %s skipped: %s", ac, skip_reason)
            return review

        # ── Apply new profile ─────────────────────────────────────────────────
        try:
            next_version = current_orm.version + 1
            new_profile = ScoringWeightProfile(
                asset_class=ac,
                version=next_version,
                is_active=True,
                weight_yield=proposed["weight_yield"],
                weight_durability=proposed["weight_durability"],
                weight_technical=proposed["weight_technical"],
                yield_sub_weights=current_orm.yield_sub_weights,
                durability_sub_weights=current_orm.durability_sub_weights,
                technical_sub_weights=current_orm.technical_sub_weights,
                source="LEARNING_LOOP",
                change_reason=(
                    f"Quarterly review: {review.correct_count} correct / "
                    f"{review.incorrect_count} incorrect outcomes"
                ),
                created_by="learning_loop",
                created_at=now,
                activated_at=now,
            )
            db.add(new_profile)
            db.flush()

            # Supersede old profile
            current_orm.is_active = False
            current_orm.superseded_at = now
            current_orm.superseded_by_id = new_profile.id

            # Weight change audit row
            audit = WeightChangeAudit(
                asset_class=ac,
                old_profile_id=current_orm.id,
                new_profile_id=new_profile.id,
                delta_weight_yield=proposed["weight_yield"] - current_orm.weight_yield,
                delta_weight_durability=proposed["weight_durability"] - current_orm.weight_durability,
                delta_weight_technical=proposed["weight_technical"] - current_orm.weight_technical,
                trigger_type="QUARTERLY_REVIEW",
                trigger_details={
                    "review_run_id": str(review.id),
                    "outcomes_analyzed": review.outcomes_analyzed,
                    "correct": review.correct_count,
                    "incorrect": review.incorrect_count,
                },
                changed_at=now,
                changed_by="learning_loop",
            )
            db.add(audit)

            # Finalize review record
            review.status = "COMPLETE"
            review.profile_after_id       = new_profile.id
            review.weight_yield_after     = new_profile.weight_yield
            review.weight_durability_after = new_profile.weight_durability
            review.weight_technical_after  = new_profile.weight_technical
            review.delta_yield             = new_profile.weight_yield - current_orm.weight_yield
            review.delta_durability        = new_profile.weight_durability - current_orm.weight_durability
            review.delta_technical         = new_profile.weight_technical - current_orm.weight_technical
            review.completed_at            = now

            db.commit()

            # Invalidate loader cache so next score picks up new weights
            weight_profile_loader.invalidate(ac)

            logger.info(
                "Weight review COMPLETE for %s: Y=%d→%d D=%d→%d T=%d→%d (v%d→v%d)",
                ac,
                current_orm.weight_yield,    new_profile.weight_yield,
                current_orm.weight_durability, new_profile.weight_durability,
                current_orm.weight_technical,  new_profile.weight_technical,
                current_orm.version, next_version,
            )

        except Exception as exc:
            db.rollback()
            review.status = "FAILED"
            review.skip_reason = f"error:{exc}"
            review.completed_at = now
            try:
                db.commit()
            except Exception:
                pass
            logger.error("Weight review FAILED for %s: %s", ac, exc)

        return review


# Module-level singleton
quarterly_weight_tuner = QuarterlyWeightTuner()
