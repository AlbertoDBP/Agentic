"""
Portfolio aggregator — fetches HHS/IES scores from Agent 03 and computes
portfolio-level aggregates: Agg HHS, NAA Yield, HHI, concentration, etc.
"""
from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


async def fetch_score(ticker: str, scoring_service_url: str, service_token: str) -> Optional[dict]:
    """GET /scores/{ticker} from Agent 03. Returns None on error."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{scoring_service_url}/scores/{ticker}",
                headers={"Authorization": f"Bearer {service_token}"},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning("Score fetch failed for %s: %s", ticker, e)
    return None


def _is_stale(score: dict) -> bool:
    """True if valid_until is in the past."""
    vu = score.get("valid_until")
    if not vu:
        return False
    try:
        exp = datetime.fromisoformat(vu.replace("Z", "+00:00"))
        return exp < datetime.now(timezone.utc)
    except Exception as e:
        logger.warning("Unparseable valid_until value %r: %s", vu, e)
        return False


def compute_hhi(weights: list[float]) -> float:
    """Herfindahl-Hirschman Index = sum of squared position weights."""
    return round(sum(w ** 2 for w in weights), 4)


async def _fetch_tax_nay(
    portfolio_id: str,
    tax_prefs: dict | None,
) -> float | None:
    """Call tax service /tax/optimize/portfolio and return portfolio_nay.

    Returns None if tax service is unavailable or user has no preferences.
    All yield values from the tax service are decimal fractions (e.g. 0.071).
    """
    if not tax_prefs:
        return None
    tax_url = os.environ.get("TAX_OPTIMIZATION_URL", "http://tax-optimization-service:8005")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{tax_url}/tax/optimize/portfolio",
                json={
                    "portfolio_id": portfolio_id,
                    "annual_income": tax_prefs.get("annual_income", 100000),
                    "filing_status": tax_prefs.get("filing_status", "SINGLE"),
                    "state_code": tax_prefs.get("state_code"),
                },
            )
            if resp.status_code == 200:
                return resp.json().get("portfolio_nay")
    except Exception as exc:
        logger.warning("Tax service NAA fetch failed for %s: %s", portfolio_id, exc)
    return None


async def aggregate_portfolio(
    portfolio_id: str,
    positions: list[dict],
    scores: dict[str, dict],
    tax_prefs: dict | None = None,
) -> dict:
    """Compute portfolio-level aggregates from positions + score map.

    positions: list of dicts with keys: symbol, current_value, annual_income,
               cost_basis (optional), total_dividends_received (optional)
    scores: ticker → ScoreResponse dict (no valid_until = always treated as fresh)
    """
    if not positions:
        return _empty_aggregate()

    total_value = sum(p.get("current_value") or 0 for p in positions)
    total_income = sum(p.get("annual_income") or 0 for p in positions)
    total_cost = sum(p.get("cost_basis") or 0 for p in positions)
    total_dividends = sum(p.get("total_dividends_received") or 0 for p in positions)

    hhs_values, hhs_weights = [], []
    unsafe_count = 0
    gate_fail_count = 0
    asset_class_totals: dict[str, float] = {}
    sector_totals: dict[str, float] = {}

    for p in positions:
        ticker = p.get("symbol", "")
        val = p.get("current_value") or 0
        score = scores.get(ticker)

        # Asset class concentration — prefer asset_type from securities (canonical)
        ac = p.get("asset_type") or (score or {}).get("asset_class") or "UNKNOWN"
        asset_class_totals[ac] = asset_class_totals.get(ac, 0) + val

        # Sector concentration (from position data)
        sector = p.get("sector") or "Other"
        sector_totals[sector] = sector_totals.get(sector, 0) + val

        if score:
            if score.get("unsafe_flag") is True:
                unsafe_count += 1
            if score.get("quality_gate_status") in ("FAIL", "INSUFFICIENT_DATA"):
                gate_fail_count += 1

        if not score or _is_stale(score):
            continue

        hhs = score.get("hhs_score")
        gate_status = score.get("quality_gate_status", "PASS")
        if hhs is not None and gate_status in ("PASS", "INSUFFICIENT_DATA"):
            weight = float(val) / float(total_value) if total_value > 0 else 0
            hhs_values.append(float(hhs) * weight)
            hhs_weights.append(weight)

    # Weighted average HHS
    agg_hhs = round(sum(hhs_values), 2) if hhs_values else None

    # Total Return: (current_value - cost_basis + dividends_received) / cost_basis
    total_return = None
    if total_cost > 0:
        total_return = round(((total_value - total_cost + total_dividends) / total_cost) * 100, 2)

    # NAA Yield — Strategy A: read from tax service (real, post-tax + post-fee)
    # Strategy B fallback: gross yield when tax service unavailable
    _tax_nay = await _fetch_tax_nay(portfolio_id, tax_prefs)
    if _tax_nay is not None:
        naa_yield = round(_tax_nay, 4)
        naa_yield_pre_tax = False
    else:
        naa_yield = round(total_income / total_value, 4) if total_value > 0 else None
        naa_yield_pre_tax = True

    # Aggregate Yield on Cost = annual income / total cost basis
    agg_yoc = round(total_income / total_cost, 4) if total_cost > 0 else None

    # HHI on position weights
    weights = [p.get("current_value", 0) / total_value for p in positions if total_value > 0]
    hhi = compute_hhi(weights)

    # Concentration breakdowns
    concentration_by_class = [
        {"class": k, "value": round(v, 2), "pct": round(v / total_value * 100, 1) if total_value > 0 else 0}
        for k, v in sorted(asset_class_totals.items(), key=lambda x: -x[1])
    ]
    concentration_by_sector = [
        {"sector": k, "value": round(v, 2), "pct": round(v / total_value * 100, 1) if total_value > 0 else 0}
        for k, v in sorted(sector_totals.items(), key=lambda x: -x[1])
    ]

    # Top 5 income holders
    positions_with_income = sorted(
        [p for p in positions if (p.get("annual_income") or 0) > 0],
        key=lambda p: p.get("annual_income", 0),
        reverse=True,
    )[:5]
    top_income = [
        {
            "ticker": p.get("symbol"),
            "asset_class": p.get("asset_type") or (scores.get(p.get("symbol") or "") or {}).get("asset_class"),
            "annual_income": round(p.get("annual_income", 0), 2),
            "income_pct": round(p.get("annual_income", 0) / total_income * 100, 1) if total_income > 0 else 0,
            "unsafe": (scores.get(p.get("symbol") or "") or {}).get("unsafe_flag") is True,
        }
        for p in positions_with_income
    ]

    return {
        "agg_hhs": agg_hhs,
        "naa_yield": naa_yield,
        "naa_yield_pre_tax": naa_yield_pre_tax,
        "agg_yoc": agg_yoc,
        "total_value": round(total_value, 2),
        "annual_income": round(total_income, 2),
        "total_return": total_return,
        "hhi": hhi,
        "unsafe_count": unsafe_count,
        "gate_fail_count": gate_fail_count,
        "holding_count": len(positions),
        "concentration_by_class": concentration_by_class,
        "concentration_by_sector": concentration_by_sector,
        "top_income_holdings": top_income,
    }


def _empty_aggregate() -> dict:
    return {
        "agg_hhs": None, "naa_yield": None, "naa_yield_pre_tax": True, "agg_yoc": None,
        "total_value": 0.0, "annual_income": 0.0, "total_return": None, "hhi": 0.0,
        "unsafe_count": 0, "gate_fail_count": 0, "holding_count": 0,
        "concentration_by_class": [], "concentration_by_sector": [],
        "top_income_holdings": [],
    }
