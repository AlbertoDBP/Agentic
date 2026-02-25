"""
Agent 02 — Newsletter Ingestion Service
Processor: Accuracy backtest

For each recommendation published > 30 days ago that has no backtest record:
  1. Fetch price at T+30 and T+90 from FMP
  2. Detect dividend cuts in the observation window
  3. Compute outcome_label: Correct | Incorrect | Partial | Inconclusive
  4. Compute accuracy_delta applied to analyst overall_accuracy
  5. Insert analyst_accuracy_log row
  6. Update analyst.overall_accuracy and sector_alpha

Outcome labelling logic:
  - StrongBuy / Buy  → Correct if T+30 price ≥ publish price + 2%,
                        Incorrect if T+30 price <  publish price - 5%,
                        Partial otherwise.
  - StrongSell / Sell → mirror logic (Correct = price fell, Incorrect = price rose)
  - Hold             → Correct if |price change| < 5%
  - Dividend cut with bullish rec → always Incorrect (overrides price signal)
  - Missing price data → Inconclusive

accuracy_delta:
  Correct  → +0.10
  Partial  → +0.02
  Incorrect→ -0.10
  Inconclusive → 0.0

overall_accuracy is updated as exponential moving average:
  new = old * 0.85 + delta * 0.15
  Clamped to [0.0, 1.0].
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Analyst, AnalystRecommendation, AnalystAccuracyLog
from app.clients import fmp_client
from app.config import settings

logger = logging.getLogger(__name__)

# Accuracy delta constants
_DELTA_CORRECT = 0.10
_DELTA_PARTIAL = 0.02
_DELTA_INCORRECT = -0.10
_DELTA_INCONCLUSIVE = 0.0

# Outcome thresholds
_BULLISH_WIN_PCT = 0.02     # +2% → Correct for Buy signals
_BULLISH_LOSS_PCT = -0.05   # -5% → Incorrect for Buy signals
_HOLD_FLAT_PCT = 0.05       # ±5% → Correct for Hold signals

_BULLISH_RECS = {"StrongBuy", "Buy"}
_BEARISH_RECS = {"StrongSell", "Sell"}
_HOLD_RECS = {"Hold"}

_MIN_DAYS_FOR_BACKTEST = 30  # recommendations must be this old to backtest


def _price_change_pct(price_at_publish: float, price_at_t: float) -> Optional[float]:
    """Compute percentage price change. Returns None if base is zero."""
    if not price_at_publish or price_at_publish == 0:
        return None
    return (price_at_t - price_at_publish) / price_at_publish


def compute_outcome_label(
    recommendation: Optional[str],
    price_at_publish: Optional[float],
    price_at_t30: Optional[float],
    dividend_cut_occurred: bool,
) -> tuple[str, float]:
    """
    Compute outcome label and accuracy delta for a recommendation.

    Returns:
        (outcome_label, accuracy_delta)
        outcome_label: Correct | Incorrect | Partial | Inconclusive
    """
    rec = (recommendation or "").strip()

    # Dividend cut overrides for bullish recommendations
    if dividend_cut_occurred and rec in _BULLISH_RECS:
        return "Incorrect", _DELTA_INCORRECT

    # Need prices to evaluate
    if not price_at_publish or not price_at_t30:
        return "Inconclusive", _DELTA_INCONCLUSIVE

    pct = _price_change_pct(price_at_publish, price_at_t30)
    if pct is None:
        return "Inconclusive", _DELTA_INCONCLUSIVE

    if rec in _BULLISH_RECS:
        if pct >= _BULLISH_WIN_PCT:
            return "Correct", _DELTA_CORRECT
        if pct <= _BULLISH_LOSS_PCT:
            return "Incorrect", _DELTA_INCORRECT
        return "Partial", _DELTA_PARTIAL

    if rec in _BEARISH_RECS:
        if pct <= -_BULLISH_WIN_PCT:           # price fell ≥ 2% → correct bear call
            return "Correct", _DELTA_CORRECT
        if pct >= abs(_BULLISH_LOSS_PCT):      # price rose ≥ 5% → wrong bear call
            return "Incorrect", _DELTA_INCORRECT
        return "Partial", _DELTA_PARTIAL

    if rec in _HOLD_RECS:
        if abs(pct) <= _HOLD_FLAT_PCT:
            return "Correct", _DELTA_CORRECT
        return "Incorrect", _DELTA_INCORRECT

    # Unknown recommendation type
    return "Inconclusive", _DELTA_INCONCLUSIVE


def _update_overall_accuracy(
    current: Optional[float],
    delta: float,
    alpha: float = 0.15,
) -> float:
    """
    Exponential moving average update for overall_accuracy.
    new = old * (1 - alpha) + delta_contribution * alpha
    delta_contribution maps delta to [0, 1] range: 0.5 + delta/2
    """
    base = float(current) if current is not None else 0.5
    # Map delta to a [0, 1] contribution: correct → 0.6, incorrect → 0.4
    contribution = 0.5 + (delta / (2 * abs(_DELTA_CORRECT)))
    contribution = max(0.0, min(1.0, contribution))
    new_accuracy = base * (1 - alpha) + contribution * alpha
    return round(max(0.0, min(1.0, new_accuracy)), 4)


def _update_sector_alpha(
    sector_alpha: Optional[dict],
    sector: Optional[str],
    outcome_label: str,
    alpha: float = 0.15,
) -> dict:
    """
    Update sector_alpha JSONB dict with new outcome for `sector`.
    sector_alpha: {"REIT": 0.72, "MLP": 0.65, ...}
    """
    result = dict(sector_alpha or {})
    if not sector:
        return result

    current = result.get(sector, 0.5)
    delta = _DELTA_CORRECT if outcome_label == "Correct" else (
        _DELTA_PARTIAL if outcome_label == "Partial" else _DELTA_INCORRECT
    )
    contribution = 0.5 + (delta / (2 * abs(_DELTA_CORRECT)))
    contribution = max(0.0, min(1.0, contribution))
    new_val = float(current) * (1 - alpha) + contribution * alpha
    result[sector] = round(max(0.0, min(1.0, new_val)), 4)
    return result


def backtest_recommendation(
    db: Session,
    rec: AnalystRecommendation,
) -> Optional[AnalystAccuracyLog]:
    """
    Run backtest for a single recommendation.

    Fetches FMP price data, computes outcome, inserts accuracy log row,
    and updates the parent analyst's overall_accuracy and sector_alpha.

    Returns the created AnalystAccuracyLog row, or None if skipped.
    """
    ticker = rec.ticker

    # Fetch T+30 and T+90 prices from FMP
    price_t30, price_t90 = fmp_client.fetch_price_at_t30_t90(ticker, rec.published_at)

    # Detect dividend cuts in 90-day window after publish
    dividend_cut_occurred, cut_at = fmp_client.detect_dividend_cut(
        ticker, rec.published_at, lookback_days=90
    )

    # Price at publish: use yield_at_publish proxy or attempt T+0 fetch
    # We use T+30 as primary outcome; T+90 is stored for later analysis
    price_at_publish = fmp_client.fetch_price_at_date(ticker, rec.published_at)

    outcome_label, accuracy_delta = compute_outcome_label(
        recommendation=rec.recommendation,
        price_at_publish=price_at_publish,
        price_at_t30=price_t30,
        dividend_cut_occurred=dividend_cut_occurred,
    )

    logger.info(
        f"Backtest {ticker} rec={rec.recommendation} "
        f"T+30={price_t30} outcome={outcome_label} delta={accuracy_delta:+.2f}"
    )

    # Build accuracy log entry
    log_entry = AnalystAccuracyLog(
        analyst_id=rec.analyst_id,
        recommendation_id=rec.id,
        ticker=ticker,
        sector=rec.sector,
        asset_class=rec.asset_class,
        original_recommendation=rec.recommendation,
        price_at_publish=price_at_publish,
        price_at_t30=price_t30,
        price_at_t90=price_t90,
        dividend_cut_occurred=dividend_cut_occurred,
        dividend_cut_at=cut_at,
        outcome_label=outcome_label,
        accuracy_delta=accuracy_delta,
    )
    db.add(log_entry)
    db.flush()

    # Update analyst accuracy
    analyst = db.query(Analyst).filter(Analyst.id == rec.analyst_id).first()
    if analyst:
        old_sector_alpha = analyst.sector_alpha
        old_overall = analyst.overall_accuracy

        # Store sector_accuracy_before on the log entry
        sector_before = None
        if old_sector_alpha and rec.sector:
            sector_before = old_sector_alpha.get(rec.sector)
        log_entry.sector_accuracy_before = sector_before

        # Update analyst
        analyst.overall_accuracy = _update_overall_accuracy(old_overall, accuracy_delta)
        analyst.sector_alpha = _update_sector_alpha(old_sector_alpha, rec.sector, outcome_label)
        analyst.last_backtest_at = datetime.now(timezone.utc)

        # Store sector_accuracy_after
        if rec.sector:
            log_entry.sector_accuracy_after = analyst.sector_alpha.get(rec.sector)

    return log_entry


def backtest_analyst(
    db: Session,
    analyst_id: int,
) -> dict:
    """
    Run backtests for all eligible recommendations of one analyst.

    Eligible: published > 30 days ago AND no existing accuracy log entry.

    Returns summary: {backtested, skipped, outcomes}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=_MIN_DAYS_FOR_BACKTEST)

    # Recommendations old enough but not yet backtested
    already_tested_ids = (
        db.query(AnalystAccuracyLog.recommendation_id)
        .filter(AnalystAccuracyLog.analyst_id == analyst_id)
        .subquery()
    )

    eligible_recs = (
        db.query(AnalystRecommendation)
        .filter(
            AnalystRecommendation.analyst_id == analyst_id,
            AnalystRecommendation.published_at <= cutoff,
            ~AnalystRecommendation.id.in_(already_tested_ids),
        )
        .all()
    )

    backtested = 0
    outcomes: dict[str, int] = {}

    for rec in eligible_recs:
        try:
            log_entry = backtest_recommendation(db, rec)
            if log_entry:
                backtested += 1
                outcomes[log_entry.outcome_label] = outcomes.get(log_entry.outcome_label, 0) + 1
        except Exception as e:
            logger.error(f"Backtest error for rec {rec.id} ({rec.ticker}): {e}")
            continue

    logger.info(
        f"Backtest analyst {analyst_id}: "
        f"{backtested}/{len(eligible_recs)} backtested, outcomes={outcomes}"
    )
    return {
        "backtested": backtested,
        "skipped": len(eligible_recs) - backtested,
        "outcomes": outcomes,
    }
