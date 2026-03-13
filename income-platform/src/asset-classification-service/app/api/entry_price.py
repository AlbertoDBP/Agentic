"""Agent 04 — Entry Price API Router

POST /entry-price/{ticker}

Computes a buy-zone entry price using asset-class-specific logic:
  - CommonStock / REIT / MLP / Preferred  → yield_based
  - BDC                                   → nav_discount (3 % / 8 % discounts)
  - CEF                                   → nav_discount (8 % / 15 % discounts)
  - ETF                                   → etf_entry_score (4-signal composite)

All data is sourced exclusively from platform_shared DB tables.
No external HTTP calls are made from this module.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.classification.engine import ClassificationEngine

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class EntryPriceRequest(BaseModel):
    target_yield_pct: Optional[float] = None
    max_position_pct: Optional[float] = None


class EntryPriceResponse(BaseModel):
    ticker: str
    asset_class: str
    entry_price_low: Optional[float]
    entry_price_high: Optional[float]
    position_size_pct: float
    entry_method: str
    target_yield_used: Optional[float]
    nav_delta_pct: Optional[float]
    etf_entry_score: Optional[float]
    etf_entry_zone: Optional[str]
    annual_income_estimate: Optional[float]
    notes: str


# ---------------------------------------------------------------------------
# Asset-class group helpers
# ---------------------------------------------------------------------------

_YIELD_BASED_CLASSES = {
    "CommonStock", "REIT", "MLP", "Preferred",
    # common sub-labels Agent 04 may emit
    "REIT_EQUITY", "REIT_MORTGAGE", "MLP_PIPELINE", "MLP_UPSTREAM",
    "PREFERRED_STOCK", "PREFERRED_ETF",
}

_BDC_CLASSES = {"BDC"}

_CEF_CLASSES = {"CEF", "CLOSED_END_FUND"}

_ETF_CLASSES = {
    "ETF", "COVERED_CALL_ETF", "BOND_ETF", "EQUITY_INCOME_ETF",
    "HIGH_YIELD_BOND_ETF", "PREFERRED_ETF", "INTERNATIONAL_INCOME_ETF",
    "REIT_ETF",
}


def _group(asset_class: str) -> str:
    """Map an asset_class string to a calculation group."""
    ac = asset_class.upper()
    for cls in _BDC_CLASSES:
        if cls.upper() in ac:
            return "BDC"
    for cls in _CEF_CLASSES:
        if cls.upper() in ac:
            return "CEF"
    for cls in _ETF_CLASSES:
        if cls.upper() in ac:
            return "ETF"
    # Preferred can also be ETF — already handled above; yield-based second
    for cls in _YIELD_BASED_CLASSES:
        if cls.upper() in ac:
            return "YIELD_BASED"
    # Fallback
    return "YIELD_BASED"


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------

def _query_features(db: Session, ticker: str) -> dict:
    row = db.execute(
        text(
            "SELECT yield_forward, yield_5yr_avg, yield_trailing_12m, div_cagr_3y"
            " FROM platform_shared.features_historical"
            " WHERE symbol = :ticker ORDER BY as_of_date DESC LIMIT 1"
        ),
        {"ticker": ticker},
    ).fetchone()
    if row is None:
        return {}
    return dict(row._mapping)


def _query_security(db: Session, ticker: str) -> Optional[float]:
    row = db.execute(
        text(
            "SELECT last_price FROM platform_shared.securities WHERE ticker = :ticker"
        ),
        {"ticker": ticker},
    ).fetchone()
    return float(row._mapping["last_price"]) if row else None


def _query_nav(db: Session, ticker: str) -> Optional[dict]:
    row = db.execute(
        text(
            "SELECT nav, market_price, premium_discount"
            " FROM platform_shared.nav_snapshots"
            " WHERE symbol = :ticker ORDER BY snapshot_date DESC LIMIT 1"
        ),
        {"ticker": ticker},
    ).fetchone()
    if row is None:
        return None
    return dict(row._mapping)


def _query_income_scores(db: Session, ticker: str) -> dict:
    row = db.execute(
        text(
            "SELECT factor_details, total_score"
            " FROM platform_shared.income_scores"
            " WHERE ticker = :ticker ORDER BY scored_at DESC LIMIT 1"
        ),
        {"ticker": ticker},
    ).fetchone()
    if row is None:
        return {}
    return dict(row._mapping)


def _query_portfolio_constraints(db: Session, portfolio_id: UUID) -> Optional[dict]:
    row = db.execute(
        text(
            "SELECT target_income_yield_pct, max_position_pct"
            " FROM platform_shared.portfolio_constraints"
            " WHERE portfolio_id = :portfolio_id"
        ),
        {"portfolio_id": str(portfolio_id)},
    ).fetchone()
    if row is None:
        return None
    return dict(row._mapping)


# ---------------------------------------------------------------------------
# Signal scoring helpers (ETF)
# ---------------------------------------------------------------------------

def _score_52w_range(features: dict, factor_details: dict) -> float:
    """Signal 1: 52-week range position (weight 0.25).

    Prefer pre-computed score from income_scores; fall back to
    price_range_position from features_historical.
    """
    # Attempt 1 — income_scores factor_details
    if factor_details:
        prs = factor_details.get("price_range_position")
        if prs and isinstance(prs, dict):
            raw = prs.get("score")
            if raw is not None:
                # Agent 03 scale: 0-8 → 1-10 linear (8→10, 0→1)
                return max(1.0, min(10.0, float(raw) / 8.0 * 9.0 + 1.0))

    # Attempt 2 — range_ratio from features_historical
    rr = features.get("price_range_position")
    if rr is None:
        rr = features.get("range_ratio")
    if rr is not None:
        rr = float(rr)
        if rr < 0.25:
            return 10.0
        if rr < 0.40:
            return 8.0
        if rr < 0.55:
            return 6.0
        if rr < 0.70:
            return 4.0
        return 2.0

    return 6.0  # neutral fallback


def _score_yield_vs_avg(features: dict) -> float:
    """Signal 2: yield spread vs 5-yr average (weight 0.30)."""
    yf = features.get("yield_forward")
    ya = features.get("yield_5yr_avg")
    if not yf or not ya:
        return 6.0  # neutral
    spread = (float(yf) - float(ya)) / float(ya)
    if spread > 0.15:
        return 10.0
    if spread > 0.05:
        return 8.0
    if spread >= -0.05:
        return 6.0
    if spread >= -0.15:
        return 4.0
    return 2.0


def _score_sma_deviation(
    current_price: float, features: dict, factor_details: dict
) -> float:
    """Signal 3: SMA-50 deviation (weight 0.25)."""
    sma50 = None

    # Attempt 1 — factor_details
    if factor_details:
        sma_fd = factor_details.get("sma_50")
        if sma_fd is not None:
            sma50 = float(sma_fd)
        else:
            sma_block = factor_details.get("price_momentum")
            if isinstance(sma_block, dict):
                sma50 = sma_block.get("sma_50")
                if sma50 is not None:
                    sma50 = float(sma50)

    # Attempt 2 — features_historical
    if sma50 is None:
        sma50 = features.get("sma_50")
        if sma50 is not None:
            sma50 = float(sma50)

    if sma50 is None or sma50 == 0:
        # Fallback: use price_momentum factor score (already 1-10) if available
        if factor_details:
            pm = factor_details.get("price_momentum")
            if isinstance(pm, dict):
                s = pm.get("score")
                if s is not None:
                    return max(1.0, min(10.0, float(s)))
            if isinstance(pm, (int, float)):
                return max(1.0, min(10.0, float(pm)))
        return 6.0  # neutral

    dev = (current_price - sma50) / sma50
    if dev < -0.08:
        return 10.0
    if dev < -0.03:
        return 8.0
    if dev <= 0.03:
        return 6.0
    if dev <= 0.08:
        return 4.0
    return 2.0


def _score_price_momentum(features: dict, factor_details: dict) -> float:
    """Signal 4: price momentum / change pct (weight 0.20)."""
    change = None

    if factor_details:
        pm = factor_details.get("price_momentum")
        if isinstance(pm, dict):
            change = pm.get("price_change_pct")
            if change is None:
                s = pm.get("score")
                if s is not None:
                    return max(1.0, min(10.0, float(s)))
        elif isinstance(pm, (int, float)):
            return max(1.0, min(10.0, float(pm)))

    if change is None:
        change = features.get("price_change_pct")

    if change is None:
        return 6.0  # neutral

    change = float(change)
    if change < -0.10:
        return 10.0
    if change < -0.05:
        return 8.0
    if change <= 0.05:
        return 6.0
    if change <= 0.10:
        return 4.0
    return 2.0


def _etf_composite_score(
    current_price: float, features: dict, factor_details: dict
) -> tuple[float, str]:
    """Return (composite_score 1-10, zone label)."""
    s1 = _score_52w_range(features, factor_details)
    s2 = _score_yield_vs_avg(features)
    s3 = _score_sma_deviation(current_price, features, factor_details)
    s4 = _score_price_momentum(features, factor_details)
    score = round(s1 * 0.25 + s2 * 0.30 + s3 * 0.25 + s4 * 0.20, 2)
    if score >= 7.5:
        zone = "Attractive"
    elif score >= 5.0:
        zone = "Neutral"
    else:
        zone = "Expensive"
    return score, zone


# ---------------------------------------------------------------------------
# Per-group calculation functions
# ---------------------------------------------------------------------------

def _calc_yield_based(
    ticker: str,
    asset_class: str,
    current_price: Optional[float],
    features: dict,
    target_yield_pct: float,
    position_size_pct: float,
) -> EntryPriceResponse:
    """Yield-based entry price for CommonStock / REIT / MLP / Preferred."""
    is_preferred = "PREFERRED" in asset_class.upper()

    if current_price is None or not features.get("yield_forward"):
        return EntryPriceResponse(
            ticker=ticker,
            asset_class=asset_class,
            entry_price_low=None,
            entry_price_high=None,
            position_size_pct=position_size_pct,
            entry_method="yield_based",
            target_yield_used=target_yield_pct,
            nav_delta_pct=None,
            etf_entry_score=None,
            etf_entry_zone=None,
            annual_income_estimate=None,
            notes="Insufficient data — yield_forward or current price unavailable",
        )

    yf = float(features["yield_forward"])   # decimal, e.g. 0.055
    annual_div = yf * float(current_price)
    target_decimal = target_yield_pct / 100.0
    entry_high = round(annual_div / target_decimal, 2)
    entry_low = round(entry_high * 0.95, 2)

    if is_preferred:
        # Par value cap at $25
        entry_high = round(min(entry_high, 25.0), 2)
        entry_low = round(min(entry_low, 25.0 * 0.95), 2)

    annual_income = round(annual_div, 4)

    return EntryPriceResponse(
        ticker=ticker,
        asset_class=asset_class,
        entry_price_low=entry_low,
        entry_price_high=entry_high,
        position_size_pct=position_size_pct,
        entry_method="yield_based",
        target_yield_used=target_yield_pct,
        nav_delta_pct=None,
        etf_entry_score=None,
        etf_entry_zone=None,
        annual_income_estimate=annual_income,
        notes=(
            f"Buy {ticker} at or below ${entry_high:.2f} "
            f"to lock in \u2265{target_yield_pct}% yield"
        ),
    )


def _calc_bdc(
    ticker: str,
    asset_class: str,
    current_price: Optional[float],
    nav_data: Optional[dict],
    position_size_pct: float,
) -> EntryPriceResponse:
    """NAV-discount entry price for BDC (3% / 8% discounts)."""
    if nav_data is None:
        return EntryPriceResponse(
            ticker=ticker,
            asset_class=asset_class,
            entry_price_low=None,
            entry_price_high=None,
            position_size_pct=position_size_pct,
            entry_method="nav_discount",
            target_yield_used=None,
            nav_delta_pct=None,
            etf_entry_score=None,
            etf_entry_zone=None,
            annual_income_estimate=None,
            notes="NAV data unavailable — cannot compute entry price",
        )

    nav = float(nav_data["nav"])
    entry_high = round(nav * 0.97, 2)
    entry_low = round(nav * 0.92, 2)
    nav_delta = None
    if current_price is not None:
        nav_delta = round((float(current_price) - nav) / nav * 100, 2)

    return EntryPriceResponse(
        ticker=ticker,
        asset_class=asset_class,
        entry_price_low=entry_low,
        entry_price_high=entry_high,
        position_size_pct=position_size_pct,
        entry_method="nav_discount",
        target_yield_used=None,
        nav_delta_pct=nav_delta,
        etf_entry_score=None,
        etf_entry_zone=None,
        annual_income_estimate=None,
        notes=(
            f"Buy {ticker} at 3%-8% discount to NAV (${nav:.2f}): "
            f"${entry_low:.2f}–${entry_high:.2f}"
        ),
    )


def _calc_cef(
    ticker: str,
    asset_class: str,
    current_price: Optional[float],
    nav_data: Optional[dict],
    position_size_pct: float,
) -> EntryPriceResponse:
    """NAV-discount entry price for CEF (8% / 15% discounts)."""
    if nav_data is None:
        return EntryPriceResponse(
            ticker=ticker,
            asset_class=asset_class,
            entry_price_low=None,
            entry_price_high=None,
            position_size_pct=position_size_pct,
            entry_method="nav_discount",
            target_yield_used=None,
            nav_delta_pct=None,
            etf_entry_score=None,
            etf_entry_zone=None,
            annual_income_estimate=None,
            notes="NAV data unavailable — cannot compute entry price",
        )

    nav = float(nav_data["nav"])
    entry_high = round(nav * 0.92, 2)
    entry_low = round(nav * 0.85, 2)
    nav_delta = None
    if current_price is not None:
        nav_delta = round((float(current_price) - nav) / nav * 100, 2)

    return EntryPriceResponse(
        ticker=ticker,
        asset_class=asset_class,
        entry_price_low=entry_low,
        entry_price_high=entry_high,
        position_size_pct=position_size_pct,
        entry_method="nav_discount",
        target_yield_used=None,
        nav_delta_pct=nav_delta,
        etf_entry_score=None,
        etf_entry_zone=None,
        annual_income_estimate=None,
        notes=(
            f"Buy {ticker} at 8%-15% discount to NAV (${nav:.2f}): "
            f"${entry_low:.2f}–${entry_high:.2f}"
        ),
    )


def _calc_etf(
    ticker: str,
    asset_class: str,
    current_price: Optional[float],
    nav_data: Optional[dict],
    features: dict,
    factor_details: dict,
    position_size_pct: float,
) -> EntryPriceResponse:
    """4-signal composite ETF entry score."""
    if current_price is None:
        return EntryPriceResponse(
            ticker=ticker,
            asset_class=asset_class,
            entry_price_low=None,
            entry_price_high=None,
            position_size_pct=position_size_pct,
            entry_method="etf_entry_score",
            target_yield_used=None,
            nav_delta_pct=None,
            etf_entry_score=None,
            etf_entry_zone=None,
            annual_income_estimate=None,
            notes="Current price unavailable — cannot compute ETF entry score",
        )

    etf_score, zone = _etf_composite_score(current_price, features, factor_details)

    if zone == "Attractive":
        discount = 0.05
    elif zone == "Neutral":
        discount = 0.02
    else:
        discount = 0.0

    entry_low = round(current_price * (1.0 - discount), 2)

    # entry_price_high = NAV ceiling (fallback to current_price if no NAV)
    nav = None
    nav_delta = None
    if nav_data is not None:
        nav = float(nav_data["nav"])
        nav_delta = round((current_price - nav) / nav * 100, 2)
        entry_high = round(nav, 2)
    else:
        entry_high = round(current_price, 2)

    if zone == "Expensive":
        entry_low = None
        entry_high = None
        note = f"{ticker} ETF entry score {etf_score}/10 — Expensive; no entry recommended"
    else:
        note = (
            f"{ticker} ETF entry score {etf_score}/10 ({zone}); "
            f"buy at ${entry_low:.2f}–${entry_high:.2f}"
        )

    return EntryPriceResponse(
        ticker=ticker,
        asset_class=asset_class,
        entry_price_low=entry_low,
        entry_price_high=entry_high,
        position_size_pct=position_size_pct,
        entry_method="etf_entry_score",
        target_yield_used=None,
        nav_delta_pct=nav_delta,
        etf_entry_score=etf_score,
        etf_entry_zone=zone,
        annual_income_estimate=None,
        notes=note,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/entry-price/{ticker}", response_model=EntryPriceResponse)
async def get_entry_price(
    ticker: str,
    body: EntryPriceRequest = None,
    portfolio_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
) -> EntryPriceResponse:
    """Compute buy-zone entry price for a ticker using asset-class-specific logic."""
    ticker = ticker.upper().strip()
    if body is None:
        body = EntryPriceRequest()

    # 1. Classify
    engine = ClassificationEngine(db)
    try:
        classification = await engine.classify(ticker)
    except Exception as exc:
        logger.error(f"Classification failed for {ticker}: {exc}")
        raise HTTPException(status_code=502, detail=f"Classification error: {exc}")

    asset_class: str = classification.get("asset_class", "CommonStock")

    # 2. Resolve target_yield_pct and max_position_pct
    target_yield_pct = settings.default_target_yield_pct
    max_position_pct = settings.default_max_position_pct

    if portfolio_id is not None:
        try:
            constraints = _query_portfolio_constraints(db, portfolio_id)
            if constraints:
                if constraints.get("target_income_yield_pct") is not None:
                    target_yield_pct = float(constraints["target_income_yield_pct"])
                if constraints.get("max_position_pct") is not None:
                    max_position_pct = float(constraints["max_position_pct"])
        except Exception as exc:
            logger.warning(f"Could not fetch portfolio_constraints for {portfolio_id}: {exc}")

    # Request body overrides portfolio constraints
    if body.target_yield_pct is not None:
        target_yield_pct = body.target_yield_pct
    if body.max_position_pct is not None:
        max_position_pct = body.max_position_pct

    # 3. Fetch market data from DB
    try:
        features = _query_features(db, ticker)
    except Exception as exc:
        logger.warning(f"features_historical query failed for {ticker}: {exc}")
        features = {}

    try:
        current_price = _query_security(db, ticker)
    except Exception as exc:
        logger.warning(f"securities query failed for {ticker}: {exc}")
        current_price = None

    # 4. Route to asset-class calculation
    group = _group(asset_class)

    if group in ("BDC", "CEF", "ETF"):
        try:
            nav_data = _query_nav(db, ticker)
        except Exception as exc:
            logger.warning(f"nav_snapshots query failed for {ticker}: {exc}")
            nav_data = None

    if group == "BDC":
        return _calc_bdc(ticker, asset_class, current_price, nav_data, max_position_pct)

    if group == "CEF":
        return _calc_cef(ticker, asset_class, current_price, nav_data, max_position_pct)

    if group == "ETF":
        try:
            scores_row = _query_income_scores(db, ticker)
            factor_details = scores_row.get("factor_details") or {}
        except Exception as exc:
            logger.warning(f"income_scores query failed for {ticker}: {exc}")
            factor_details = {}
        return _calc_etf(
            ticker, asset_class, current_price, nav_data,
            features, factor_details, max_position_pct,
        )

    # Default: YIELD_BASED
    return _calc_yield_based(
        ticker, asset_class, current_price, features,
        target_yield_pct, max_position_pct,
    )
