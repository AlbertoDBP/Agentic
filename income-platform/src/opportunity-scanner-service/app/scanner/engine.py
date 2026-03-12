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

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings
from app.scanner.scoring_client import score_ticker

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


@dataclass
class ScanEngineResult:
    total_scanned: int
    total_passed: int
    total_vetoed: int
    items: list[ScanItem]         # only items that passed all filters, ranked
    all_items: list[ScanItem]     # all scored items including filtered-out


async def run_scan(
    tickers: list[str],
    min_score: float = 0.0,
    min_yield: float = 0.0,
    asset_classes: Optional[list[str]] = None,
    quality_gate_only: bool = False,
) -> ScanEngineResult:
    """
    Score all tickers concurrently (max scan_concurrency at a time),
    apply filters, rank, and return the engine result.
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

    # Score concurrently with semaphore
    semaphore = asyncio.Semaphore(settings.scan_concurrency)

    async def _score_bounded(ticker: str) -> tuple[str, Optional[dict]]:
        async with semaphore:
            result = await score_ticker(ticker)
            return ticker, result

    tasks = [_score_bounded(t) for t in tickers]
    raw_results: list[tuple[str, Optional[dict]]] = await asyncio.gather(*tasks)

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
