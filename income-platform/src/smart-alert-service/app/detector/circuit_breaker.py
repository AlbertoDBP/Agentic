"""
Agent 11 — Smart Alert Service
Circuit breaker detection: reads income_scores and features_historical.

Three alert types:
  SCORE_DETERIORATION  — score dropped significantly between two consecutive scans
  YIELD_SUSTAINABILITY — payout ratio dangerously high with negative chowder number
  GROWTH_STALL         — dividend CAGR flipped from positive to zero-or-negative
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AlertData:
    """A single detected alert ready to be routed."""
    symbol: str
    source_agent: int
    alert_type: str
    severity: str
    details: dict = field(default_factory=dict)


def _detect_score_deterioration(db: Session) -> list[AlertData]:
    """Return SCORE_DETERIORATION alerts for tickers whose score dropped."""
    sql = text(
        """
        SELECT ticker, total_score, scored_at
        FROM (
            SELECT ticker, total_score, scored_at,
                   ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY scored_at DESC) AS rn
            FROM platform_shared.income_scores
        ) ranked
        WHERE rn <= 2
        ORDER BY ticker, scored_at DESC
        """
    )
    rows = db.execute(sql).fetchall()

    # Group into {ticker: [newest, older]}
    by_ticker: dict[str, list] = {}
    for row in rows:
        ticker = row.ticker
        if ticker not in by_ticker:
            by_ticker[ticker] = []
        by_ticker[ticker].append(row)

    alerts: list[AlertData] = []
    for ticker, ticker_rows in by_ticker.items():
        if len(ticker_rows) < 2:
            continue
        # rows are ordered newest first
        newest = ticker_rows[0]
        older = ticker_rows[1]
        score_delta = float(older.total_score) - float(newest.total_score)
        if score_delta >= settings.score_delta_critical:
            severity = "CRITICAL"
        elif score_delta >= settings.score_delta_warning:
            severity = "WARNING"
        else:
            continue
        alerts.append(
            AlertData(
                symbol=ticker,
                source_agent=11,
                alert_type="SCORE_DETERIORATION",
                severity=severity,
                details={
                    "score_before": float(older.total_score),
                    "score_after": float(newest.total_score),
                    "delta": score_delta,
                },
            )
        )
        logger.debug("SCORE_DETERIORATION for %s: delta=%.2f severity=%s", ticker, score_delta, severity)

    return alerts


def _detect_yield_sustainability(db: Session) -> list[AlertData]:
    """Return YIELD_SUSTAINABILITY alerts for symbols with payout > 90% and chowder < 0."""
    sql = text(
        """
        SELECT symbol, payout_ratio, chowder_number
        FROM (
            SELECT symbol, payout_ratio, chowder_number,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY as_of_date DESC) AS rn
            FROM platform_shared.features_historical
        ) ranked
        WHERE rn = 1
        """
    )
    rows = db.execute(sql).fetchall()

    alerts: list[AlertData] = []
    for row in rows:
        payout = row.payout_ratio
        chowder = row.chowder_number
        if payout is None or chowder is None:
            continue
        payout = float(payout)
        chowder = float(chowder)
        if payout > 0.90 and chowder < 0:
            alerts.append(
                AlertData(
                    symbol=row.symbol,
                    source_agent=11,
                    alert_type="YIELD_SUSTAINABILITY",
                    severity="WARNING",
                    details={
                        "payout_ratio": payout,
                        "chowder_number": chowder,
                    },
                )
            )
            logger.debug("YIELD_SUSTAINABILITY for %s: payout=%.4f chowder=%.4f", row.symbol, payout, chowder)

    return alerts


def _detect_growth_stall(db: Session) -> list[AlertData]:
    """Return GROWTH_STALL alerts for symbols where div_cagr_3y flipped positive → <=0."""
    sql = text(
        """
        SELECT symbol, div_cagr_3y, as_of_date
        FROM (
            SELECT symbol, div_cagr_3y, as_of_date,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY as_of_date DESC) AS rn
            FROM platform_shared.features_historical
        ) ranked
        WHERE rn <= 2
        ORDER BY symbol, as_of_date DESC
        """
    )
    rows = db.execute(sql).fetchall()

    by_symbol: dict[str, list] = {}
    for row in rows:
        sym = row.symbol
        if sym not in by_symbol:
            by_symbol[sym] = []
        by_symbol[sym].append(row)

    alerts: list[AlertData] = []
    for sym, sym_rows in by_symbol.items():
        if len(sym_rows) < 2:
            continue
        newest = sym_rows[0]
        older = sym_rows[1]
        if newest.div_cagr_3y is None:
            continue
        if older.div_cagr_3y is None:
            continue
        now_cagr = float(newest.div_cagr_3y)
        before_cagr = float(older.div_cagr_3y)
        # Trigger: was positive, now <= 0
        if before_cagr > 0 and now_cagr <= 0:
            alerts.append(
                AlertData(
                    symbol=sym,
                    source_agent=11,
                    alert_type="GROWTH_STALL",
                    severity="WARNING",
                    details={
                        "div_cagr_3y_before": before_cagr,
                        "div_cagr_3y_now": now_cagr,
                    },
                )
            )
            logger.debug("GROWTH_STALL for %s: before=%.4f now=%.4f", sym, before_cagr, now_cagr)

    return alerts


def detect_circuit_breaker_alerts(db: Session) -> list[AlertData]:
    """Run all three circuit-breaker detectors and return combined alert list."""
    alerts: list[AlertData] = []
    alerts.extend(_detect_score_deterioration(db))
    alerts.extend(_detect_yield_sustainability(db))
    alerts.extend(_detect_growth_stall(db))
    return alerts
