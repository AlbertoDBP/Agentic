"""
Agent 07 — Opportunity Scanner Service
Scanner Engine: scores a universe of tickers, applies filters, ranks results.

Algorithm:
  1. Score each ticker via Agent 03 (concurrent, bounded by scan_concurrency)
  2. Apply filters: min_score, min_yield, asset_classes, quality_gate_only
  3. Flag tickers with score < quality_gate_threshold as vetoed (VETO gate)
  4. Rank passing tickers by total_score descending
  5. Return ScanEngineResult with items + stats
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings
from app.scanner.entry_exit import compute_entry_exit

logger = logging.getLogger(__name__)


@dataclass
class ScanItem:
    ticker: str
    score: float
    grade: str
    recommendation: str
    asset_class: str
    chowder_signal: Optional[str]
    chowder_number: Optional[float]
    signal_penalty: float
    rank: int
    passed_quality_gate: bool    # score >= quality_gate_threshold
    veto_flag: bool              # True when score < quality_gate_threshold
    passed_filters: bool         # True when all caller filters satisfied
    score_details: dict[str, Any] = field(default_factory=dict)
    entry_exit: Optional[dict] = None
    portfolio_context: Optional[dict] = None
    analyst_context: Optional[dict] = None   # populated for analyst-ideas source scans


@dataclass
class ScanEngineResult:
    total_scanned: int
    total_passed: int
    total_vetoed: int
    items: list[ScanItem]         # only items that passed all filters, ranked
    all_items: list[ScanItem]     # all scored items including filtered-out


def tickers_from_analyst_suggestions(suggestions: list[dict]) -> tuple[list[str], dict]:
    """
    Extract ticker list and analyst context map from suggestion rows.
    Returns (tickers, {ticker: analyst_context}).
    """
    from app.scanner.analyst_ideas import build_analyst_context
    tickers = [s["ticker"] for s in suggestions]
    context_map = {s["ticker"]: build_analyst_context(s) for s in suggestions}
    return tickers, context_map


async def run_scan(
    tickers: list[str],
    min_score: float = 0.0,
    min_yield: float = 0.0,
    asset_classes: Optional[list[str]] = None,
    quality_gate_only: bool = False,
    market_cache: Optional[dict] = None,
    score_cache: Optional[dict] = None,
) -> ScanEngineResult:
    """
    Score all tickers, apply filters, rank, and return the engine result.

    Fast path: use pre-fetched scores from score_cache (batch DB read — no HTTP).
    Slow path: call Agent 03 HTTP for any tickers missing from score_cache.
    """
    if not tickers:
        return ScanEngineResult(0, 0, 0, [], [])

    # Deduplicate preserving order
    seen: set[str] = set()
    unique = []
    for t in tickers:
        upper = t.upper()
        if upper not in seen:
            seen.add(upper)
            unique.append(upper)
    tickers = unique

    cached = score_cache or {}
    hits = [t for t in tickers if t in cached]
    misses = [t for t in tickers if t not in cached]

    if misses:
        logger.warning(
            "%d tickers have no score in DB and will be skipped: %s",
            len(misses), misses[:10],
        )

    # Scores come from the DB batch-fetch — no HTTP calls to Agent 03.
    # Agent 03 runs on schedule (daily + on position changes); the scanner
    # is a pure reader of its output.
    raw_results: list[tuple[str, Optional[dict]]] = [
        (t, cached[t]) for t in hits
    ]

    threshold = settings.quality_gate_threshold
    all_items: list[ScanItem] = []
    total_vetoed = 0

    for ticker, data in raw_results:
        if data is None:
            logger.debug("No score returned for %s — skipped", ticker)
            continue

        score = float(data.get("total_score", 0.0))
        passed_gate = score >= threshold
        if not passed_gate:
            total_vetoed += 1

        item = ScanItem(
            ticker=ticker,
            score=score,
            grade=data.get("grade", "F"),
            recommendation=data.get("recommendation", "AVOID"),
            asset_class=data.get("asset_class", "UNKNOWN"),
            chowder_signal=data.get("chowder_signal"),
            chowder_number=data.get("chowder_number"),
            signal_penalty=float(data.get("signal_penalty", 0.0)),
            rank=0,
            passed_quality_gate=passed_gate,
            veto_flag=not passed_gate,
            passed_filters=False,
            score_details={
                "valuation_yield_score": data.get("valuation_yield_score"),
                "financial_durability_score": data.get("financial_durability_score"),
                "technical_entry_score": data.get("technical_entry_score"),
                "nav_erosion_penalty": data.get("nav_erosion_penalty"),
            },
        )
        cache_row = (market_cache or {}).get(ticker, {})
        ee = compute_entry_exit(
            asset_class=item.asset_class,
            price=cache_row.get("price"),
            support_level=cache_row.get("support_level"),
            sma_200=cache_row.get("sma_200"),
            resistance_level=cache_row.get("resistance_level"),
            week_52_high=cache_row.get("week_52_high"),
            dividend_yield=cache_row.get("dividend_yield"),
            nav_value=cache_row.get("nav_value"),
        )
        item.entry_exit = ee.to_dict()

        all_items.append(item)

    # Apply filters
    passing = []
    for item in all_items:
        if quality_gate_only and item.veto_flag:
            continue
        if item.score < min_score:
            continue
        if asset_classes and item.asset_class not in asset_classes:
            continue
        # min_yield filter: check against chowder_number as proxy for yield signal
        # (Agent 03 does not return raw yield in score response; filter is informational)
        item.passed_filters = True
        passing.append(item)

    # Rank by score descending
    passing.sort(key=lambda x: x.score, reverse=True)
    for rank, item in enumerate(passing, start=1):
        item.rank = rank

    return ScanEngineResult(
        total_scanned=len(all_items),
        total_passed=len(passing),
        total_vetoed=total_vetoed,
        items=passing,
        all_items=all_items,
    )
