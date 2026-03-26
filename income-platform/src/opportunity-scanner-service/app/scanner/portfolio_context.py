# src/opportunity-scanner-service/app/scanner/portfolio_context.py
"""
Agent 07 — Portfolio Context Annotator

Pure Python module — no DB calls. Receives pre-fetched positions and scan items,
computes market-value weights, annotates each item, and applies lens filtering.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

UNDERPERFORMER_SCORE_THRESHOLD = 28.0  # below 70% of max 40 pillar score


@dataclass
class PortfolioPosition:
    symbol: str
    asset_class: str
    sector: str
    shares: float
    price: Optional[float]             # from market_data_cache; None = excluded from denominator
    valuation_yield_score: Optional[float] = None
    financial_durability_score: Optional[float] = None


# PortfolioContext is a TypedDict-style alias for documentation; actual data is a plain dict
PortfolioContext = dict


def _market_value(pos: PortfolioPosition) -> Optional[float]:
    if pos.price is None or pos.shares is None:
        return None
    mv = pos.shares * pos.price
    return mv if mv > 0 else None


def annotate_with_portfolio(
    items: list[dict[str, Any]],
    positions: list[PortfolioPosition],
    class_overweight_pct: float = 20.0,
    sector_overweight_pct: float = 30.0,
) -> list[dict[str, Any]]:
    """Annotate each scan item with portfolio context."""
    # Build lookup: symbol → position
    pos_by_symbol = {p.symbol.upper(): p for p in positions}

    # Compute portfolio total market value (exclude positions with no price)
    total_mv = sum(mv for p in positions if (mv := _market_value(p)) is not None)

    # Compute asset-class and sector weights from portfolio
    class_mv: dict[str, float] = {}
    sector_mv: dict[str, float] = {}
    for p in positions:
        mv = _market_value(p)
        if mv is None:
            continue
        class_mv[p.asset_class] = class_mv.get(p.asset_class, 0.0) + mv
        sector_mv[p.sector] = sector_mv.get(p.sector, 0.0) + mv

    def _weight_pct(mv_dict: dict, key: str) -> float:
        if total_mv == 0:
            return 0.0
        return round(mv_dict.get(key, 0.0) / total_mv * 100.0, 1)

    # Identify underperformers: held positions failing income or durability pillar
    underperformers: dict[str, str] = {}   # symbol → reason
    for p in positions:
        if p.valuation_yield_score is not None and p.valuation_yield_score < UNDERPERFORMER_SCORE_THRESHOLD:
            underperformers[p.symbol.upper()] = "income_pillar"
        elif p.financial_durability_score is not None and p.financial_durability_score < UNDERPERFORMER_SCORE_THRESHOLD:
            underperformers[p.symbol.upper()] = "durability_pillar"

    result = []
    for item in items:
        ticker = item["ticker"].upper()
        held_pos = pos_by_symbol.get(ticker)
        asset_class = item.get("asset_class", "")

        already_held = held_pos is not None
        class_weight = _weight_pct(class_mv, asset_class)
        sector = held_pos.sector if held_pos else ""
        sector_weight = _weight_pct(sector_mv, sector) if sector else 0.0

        held_mv = _market_value(held_pos) if held_pos else None
        held_weight_pct = round(held_mv / total_mv * 100.0, 1) if held_mv is not None and total_mv > 0 else None

        is_underperformer = ticker in underperformers
        underperformer_reason = underperformers.get(ticker)

        ctx = {
            "already_held": already_held,
            "held_shares": held_pos.shares if held_pos else None,
            "held_weight_pct": held_weight_pct,
            "asset_class_weight_pct": class_weight,
            "sector_weight_pct": sector_weight,
            "class_overweight": class_weight > class_overweight_pct,
            "sector_overweight": sector_weight > sector_overweight_pct,
            "is_underperformer": is_underperformer,
            "underperformer_reason": underperformer_reason,
            "replacing_ticker": None,  # set by apply_lens for replacement lens
        }

        annotated = dict(item)
        annotated["portfolio_context"] = ctx
        result.append(annotated)

    return result


def apply_lens(
    items: list[dict[str, Any]],
    lens: Optional[str],
) -> list[dict[str, Any]]:
    """Filter and re-rank items according to the selected lens."""
    if lens is None:
        return items

    if lens == "gap":
        return sorted(
            (i for i in items if not i["portfolio_context"]["already_held"]),
            key=lambda i: i["score"],
            reverse=True,
        )

    if lens == "replacement":
        # Find underperforming held tickers per asset class (lowest score wins as "replacing_ticker")
        underperformer_by_class: dict[str, tuple[str, float]] = {}  # ac → (ticker, score)
        for item in items:
            ctx = item["portfolio_context"]
            if ctx["already_held"] and ctx["is_underperformer"]:
                ac = item["asset_class"]
                existing = underperformer_by_class.get(ac)
                if existing is None or item["score"] < existing[1]:
                    underperformer_by_class[ac] = (item["ticker"], item["score"])

        result = []
        for item in items:
            if item["portfolio_context"]["already_held"]:
                continue
            ac = item["asset_class"]
            replacing_entry = underperformer_by_class.get(ac)
            if replacing_entry is None:
                continue
            replacing_ticker, replacing_score = replacing_entry
            annotated = dict(item)
            annotated["portfolio_context"] = dict(item["portfolio_context"])
            annotated["portfolio_context"]["replacing_ticker"] = replacing_ticker

            result.append((annotated, replacing_score))

        # Rank by score delta vs replacing_ticker score
        result.sort(key=lambda x: x[0]["score"] - x[1], reverse=True)
        return [r[0] for r in result]

    if lens == "concentration":
        # Rank: score × (1 - class_weight_pct/100) to reward diversifying picks
        def _conc_score(i: dict) -> float:
            w = i["portfolio_context"].get("asset_class_weight_pct", 0.0)
            return i["score"] * (1 - w / 100.0)
        return sorted(items, key=_conc_score, reverse=True)

    return items
