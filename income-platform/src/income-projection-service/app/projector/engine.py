"""
Agent 09 — Projection Engine
Produces a position-level 12-month forward income forecast.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.projector import portfolio_reader

logger = logging.getLogger(__name__)

VALID_YIELD_SOURCES = ("forward", "trailing", "position_record")


@dataclass
class PositionProjection:
    symbol: str
    current_value: float
    yield_used_pct: float
    projected_annual: float
    div_cagr_3y: Optional[float]
    data_source: str  # "features_historical" | "position_record" | "missing"


@dataclass
class ProjectionResult:
    portfolio_id: str
    horizon_months: int
    yield_source: str
    total_projected_annual: float
    total_projected_monthly_avg: float
    monthly_cashflow: list[dict]          # [{"month": 1, "projected_income": X}, ...]
    positions: list[dict]                 # serialised PositionProjection dicts
    positions_included: int
    positions_missing_data: int
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _pick_yield(
    pos: dict,
    feat: Optional[dict],
    yield_source: str,
) -> tuple[float, str]:
    """
    Return (yield_pct, data_source) following the fallback chain:
      forward -> trailing -> position_record -> 0 / "missing"
    """
    if feat is not None:
        if yield_source == "forward":
            fwd = feat.get("yield_forward")
            if fwd is not None:
                return float(fwd), "features_historical"
            trailing = feat.get("yield_trailing_12m")
            if trailing is not None:
                return float(trailing), "features_historical"
        elif yield_source == "trailing":
            trailing = feat.get("yield_trailing_12m")
            if trailing is not None:
                return float(trailing), "features_historical"
            fwd = feat.get("yield_forward")
            if fwd is not None:
                return float(fwd), "features_historical"

    # Both forward and trailing paths fall through to position_record.
    # Prefer annual_income (already a dollar figure) over yield_on_value,
    # which is frequently stored as 0 even when annual_income is populated.
    annual_income = pos.get("annual_income")
    current_value = float(pos.get("current_value") or 0.0)
    if annual_income is not None and float(annual_income) > 0 and current_value > 0:
        yield_pct = float(annual_income) / current_value * 100.0
        return yield_pct, "position_record"

    pos_yield = pos.get("yield_on_value")
    if pos_yield is not None and float(pos_yield) > 0:
        return float(pos_yield), "position_record"

    return 0.0, "missing"


async def run_projection(
    portfolio_id: str,
    horizon_months: int = 12,
    yield_source: str = "forward",
) -> ProjectionResult:
    """
    Core projection engine.  Reads live data via asyncpg and computes
    position-level and portfolio-level income forecasts.
    """
    if yield_source not in VALID_YIELD_SOURCES:
        yield_source = "forward"

    # --- 1. Fetch active positions -------------------------------------------
    positions = await portfolio_reader.get_positions(portfolio_id)

    # --- 2. Fetch latest features_historical per symbol ----------------------
    symbols = [p["symbol"] for p in positions]
    features_by_symbol = await portfolio_reader.get_features(symbols)

    # --- 3. Project each position --------------------------------------------
    position_projections: list[PositionProjection] = []
    positions_missing = 0

    for pos in positions:
        symbol = pos["symbol"]
        current_value = float(pos.get("current_value") or 0.0)
        feat = features_by_symbol.get(symbol)

        # Honour position_record source directly without feature lookup.
        # Use annual_income as the primary source since yield_on_value may be 0.
        if yield_source == "position_record":
            annual_income = pos.get("annual_income")
            if annual_income is not None and float(annual_income) > 0 and current_value > 0:
                yield_pct = float(annual_income) / current_value * 100.0
                data_source = "position_record"
            else:
                pos_yield = pos.get("yield_on_value")
                if pos_yield is not None and float(pos_yield) > 0:
                    yield_pct, data_source = float(pos_yield), "position_record"
                else:
                    yield_pct, data_source = 0.0, "missing"
        else:
            yield_pct, data_source = _pick_yield(pos, feat, yield_source)

        if data_source == "missing":
            positions_missing += 1

        projected_annual = round(current_value * yield_pct / 100.0, 2)

        div_cagr_3y: Optional[float] = None
        if feat is not None and feat.get("div_cagr_3y") is not None:
            div_cagr_3y = float(feat["div_cagr_3y"])

        position_projections.append(
            PositionProjection(
                symbol=symbol,
                current_value=current_value,
                yield_used_pct=yield_pct,
                projected_annual=projected_annual,
                div_cagr_3y=div_cagr_3y,
                data_source=data_source,
            )
        )

    # --- 4. Aggregate totals -------------------------------------------------
    total_annual = round(sum(p.projected_annual for p in position_projections), 2)
    monthly_avg = round(total_annual / 12.0, 2) if horizon_months > 0 else 0.0

    # --- 5. Monthly cashflow (uniform distribution) --------------------------
    monthly_cashflow = [
        {"month": m, "projected_income": monthly_avg}
        for m in range(1, horizon_months + 1)
    ]

    positions_included = len(position_projections) - positions_missing

    positions_out = [
        {
            "symbol": p.symbol,
            "current_value": p.current_value,
            "yield_used_pct": p.yield_used_pct,
            "projected_annual": p.projected_annual,
            "div_cagr_3y": p.div_cagr_3y,
            "data_source": p.data_source,
        }
        for p in position_projections
    ]

    return ProjectionResult(
        portfolio_id=portfolio_id,
        horizon_months=horizon_months,
        yield_source=yield_source,
        total_projected_annual=total_annual,
        total_projected_monthly_avg=monthly_avg,
        monthly_cashflow=monthly_cashflow,
        positions=positions_out,
        positions_included=positions_included,
        positions_missing_data=positions_missing,
    )
