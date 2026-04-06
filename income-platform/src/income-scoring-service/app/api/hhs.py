"""HHS endpoints — POST /hhs/evaluate

Computes Holding Health Score for a ticker using the full scoring pipeline
(quality gate + income scorer + HHS wrapper). No DB persistence — on-demand only.
"""
import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.scoring.classification_client import get_asset_class as _classify_ticker
from app.scoring.data_client import MarketDataClient
from app.scoring.hhs_weights import HHSWeightDefaults, RiskProfile
from app.scoring.hhs_wrapper import HHSResult, HHSStatus, HHSWrapper
from app.scoring.income_scorer import IncomeScorer
from app.scoring.quality_gate import (
    AssetClass,
    BondGateInput,
    CoveredCallETFGateInput,
    DividendStockGateInput,
    GateStatus,
    QualityGateEngine,
)
from app.scoring.weight_profile_loader import weight_profile_loader

logger = logging.getLogger(__name__)
router = APIRouter()

_wrapper = HHSWrapper()
_scorer = IncomeScorer()
_gate = QualityGateEngine()
_client = MarketDataClient()


class HHSRequest(BaseModel):
    ticker: str
    asset_class: Optional[str] = None
    risk_profile: str = "moderate"


class HHSResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    ticker: str
    asset_class: str
    status: str
    hhs_score: Optional[float]
    income_pillar: Optional[float]
    durability_pillar: Optional[float]
    unsafe: bool
    unsafe_threshold_used: int
    income_weight_used: int
    durability_weight_used: int
    gate_fail_reasons: list[str]


async def _fetch_market_data(ticker: str, asset_class: str) -> dict:
    """Fetch market data from Agent 01 concurrently."""
    today = date.today()
    start_date = (today - timedelta(days=settings.score_history_days)).isoformat()
    end_date = today.isoformat()

    tasks: dict[str, object] = {
        "fundamentals": _client.get_fundamentals(ticker),
        "dividend_history": _client.get_dividend_history(ticker),
        "history_stats": _client.get_history_stats(ticker, start_date, end_date),
        "current_price": _client.get_current_price(ticker),
        "features": _client.get_features(ticker),
    }
    if asset_class in (AssetClass.COVERED_CALL_ETF, "COVERED_CALL_ETF"):
        tasks["etf_data"] = _client.get_etf_data(ticker)

    gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
    market_data: dict = {}
    for key, res in zip(tasks.keys(), gathered):
        if isinstance(res, Exception):
            logger.warning("Failed to fetch %s for %s: %s", key, ticker, res)
            market_data[key] = [] if key == "dividend_history" else {}
        else:
            market_data[key] = res
    return market_data


def _run_gate(ticker: str, asset_class: str, market_data: dict):
    """Run quality gate using data derived from market_data."""
    ac = asset_class.upper()
    div_history = market_data.get("dividend_history") or []
    fundamentals = market_data.get("fundamentals") or {}

    # Derive dividend history years from market data
    div_history_years: Optional[int] = None
    if div_history:
        years = {
            d["ex_date"][:4]
            for d in div_history
            if isinstance(d.get("ex_date"), str) and len(d["ex_date"]) >= 4
        }
        div_history_years = len(years) if years else None

    raw_fcf = fundamentals.get("consecutive_positive_fcf_years")
    fcf_years: Optional[int] = int(raw_fcf) if raw_fcf is not None else None

    if ac in ("DIVIDEND_STOCK", "EQUITY_STOCK"):
        gate_result = _gate.evaluate_dividend_stock(DividendStockGateInput(
            ticker=ticker,
            dividend_history_years=div_history_years,
            consecutive_positive_fcf_years=fcf_years,
            credit_rating=fundamentals.get("credit_rating"),
        ))
    elif ac == "COVERED_CALL_ETF":
        etf_data = market_data.get("etf_data") or {}
        gate_result = _gate.evaluate_covered_call_etf(CoveredCallETFGateInput(
            ticker=ticker,
            distribution_history_months=div_history_years * 12 if div_history_years is not None else None,
            aum_millions=etf_data.get("aum_millions"),
            track_record_years=etf_data.get("track_record_years"),
        ))
    elif ac == "BOND":
        gate_result = _gate.evaluate_bond(BondGateInput(
            ticker=ticker,
            credit_rating=fundamentals.get("credit_rating"),
        ))
    elif ac == "BDC":
        gate_result = _gate.evaluate_bdc(ticker, div_history_years,
                                         fundamentals.get("credit_rating"))
    elif ac in ("MREIT", "MORTGAGE_REIT"):
        gate_result = _gate.evaluate_mortgage_reit(ticker, div_history_years,
                                                   fundamentals.get("credit_rating"))
    elif ac in ("REIT", "EQUITY_REIT"):
        gate_result = _gate.evaluate_equity_reit(ticker, div_history_years,
                                                  fundamentals.get("credit_rating"))
    elif ac in ("PREFERRED", "PREFERRED_STOCK"):
        gate_result = _gate.evaluate_preferred(ticker, div_history_years,
                                                fundamentals.get("credit_rating"))
    else:
        # Conservative fallback for unknown asset classes
        gate_result = _gate.evaluate_bond(BondGateInput(ticker=ticker))

    gate_result.dividend_history_years = div_history_years
    gate_result.consecutive_positive_fcf_years = fcf_years
    return gate_result


@router.post("/hhs/evaluate", response_model=HHSResponse)
async def evaluate_hhs(request: HHSRequest, db: Session = Depends(get_db)):
    ticker = request.ticker.upper()
    risk_profile = RiskProfile(request.risk_profile)

    # Resolve asset class
    if request.asset_class:
        asset_class = request.asset_class.upper()
    else:
        resolved, _ = await _classify_ticker(ticker)
        if resolved is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"asset_class not provided and Agent 04 could not classify {ticker}. "
                    "Provide asset_class explicitly or ensure Agent 04 is running."
                ),
            )
        asset_class = resolved.upper()

    # Fetch market data
    try:
        market_data = await _fetch_market_data(ticker, asset_class)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {e}")

    # Run gate
    gate_result = _run_gate(ticker, asset_class, market_data)

    # Compute HHS
    if gate_result.status == GateStatus.FAIL:
        hhs = _wrapper.from_gate_result(gate_result, asset_class=asset_class, ticker=ticker)
    elif gate_result.status == GateStatus.INSUFFICIENT_DATA:
        hhs = _wrapper.from_gate_result(gate_result, asset_class=asset_class, ticker=ticker)
    else:
        wp = weight_profile_loader.get_active_profile(asset_class, db)
        score = _scorer.score(
            ticker=ticker,
            asset_class=asset_class,
            quality_gate_result=gate_result,
            market_data=market_data,
            weight_profile=wp,
        )
        score.ticker = ticker
        score.asset_class = asset_class
        hhs_weights = HHSWeightDefaults.get(asset_class, risk_profile)
        hhs = _wrapper.compute(score, hhs_weights)

    return HHSResponse(
        ticker=hhs.ticker,
        asset_class=hhs.asset_class,
        status=hhs.status,
        hhs_score=hhs.hhs_score,
        income_pillar=hhs.income_pillar,
        durability_pillar=hhs.durability_pillar,
        unsafe=hhs.unsafe,
        unsafe_threshold_used=hhs.unsafe_threshold_used,
        income_weight_used=hhs.income_weight_used,
        durability_weight_used=hhs.durability_weight_used,
        gate_fail_reasons=hhs.gate_fail_reasons,
    )
