"""Portfolio Health endpoints — POST /portfolio/health

Two-output portfolio health panel:
  Output A: position-weighted aggregate HHS + exclusion counts
  Output B: NAA yield, total return, HHI

Callers provide cost basis, current value, income received, fee/tax drag
in the request — portfolio accounting data not available from market data.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.scoring.hhs_weights import HHSWeightDefaults, RiskProfile
from app.scoring.hhs_wrapper import HHSResult, HHSStatus, HHSWrapper
from app.scoring.income_scorer import IncomeScorer
from app.scoring.naa_yield import NAAYieldCalculator, NAAYieldResult
from app.scoring.portfolio_health import HoldingInput, PortfolioHealthCalculator
from app.scoring.quality_gate import GateStatus
from app.scoring.weight_profile_loader import weight_profile_loader
from app.api.hhs import _fetch_market_data, _run_gate

logger = logging.getLogger(__name__)
router = APIRouter()

_wrapper = HHSWrapper()
_scorer = IncomeScorer()
_naa_calc = NAAYieldCalculator()


class HoldingRequest(BaseModel):
    ticker: str
    asset_class: Optional[str] = None
    position_value: float
    original_cost: float          # total cost basis — portfolio accounting data
    current_value: float
    income_received: float = 0.0  # annualised dividends received
    annual_fee_drag: float = 0.0
    annual_tax_drag: Optional[float] = None  # None → pre_tax_flag=True


class PortfolioHealthRequest(BaseModel):
    holdings: list[HoldingRequest]
    risk_profile: str = "moderate"
    hhi_flag_threshold: Optional[float] = None


class PortfolioHealthResponse(BaseModel):
    aggregate_hhs: Optional[float]
    scored_holding_count: int
    excluded_holding_count: int
    unsafe_count: int
    unsafe_tickers: list[str]
    gate_fail_count: int
    insufficient_data_count: int
    stale_count: int
    portfolio_naa_yield_pct: float
    portfolio_naa_pre_tax_flag: bool
    total_return_pct: float
    hhi: float
    concentration_flags: list[str]
    sharpe: Optional[float]
    sortino: Optional[float]
    var_95: Optional[float]


@router.post("/portfolio/health", response_model=PortfolioHealthResponse)
async def portfolio_health(
    request: PortfolioHealthRequest, db: Session = Depends(get_db)
):
    risk_profile = RiskProfile(request.risk_profile)
    threshold = request.hhi_flag_threshold or 0.10
    inputs: list[HoldingInput] = []

    for h in request.holdings:
        ticker = h.ticker.upper()
        asset_class = (h.asset_class or "DIVIDEND_STOCK").upper()

        try:
            market_data = await _fetch_market_data(ticker, asset_class)
            gate = _run_gate(ticker, asset_class, market_data)

            if gate.status in (GateStatus.FAIL, GateStatus.INSUFFICIENT_DATA):
                hhs = _wrapper.from_gate_result(
                    gate, asset_class=asset_class, ticker=ticker
                )
            else:
                wp = weight_profile_loader.load(asset_class, db)
                score = _scorer.score(
                    ticker=ticker,
                    asset_class=asset_class,
                    quality_gate_result=gate,
                    market_data=market_data,
                    weight_profile=wp,
                )
                score.ticker = ticker
                score.asset_class = asset_class
                hhs = _wrapper.compute(
                    score, HHSWeightDefaults.get(asset_class, risk_profile)
                )
        except Exception as e:
            logger.warning("Could not score %s: %s — marking STALE", ticker, e)
            hhs = HHSResult(
                ticker=ticker, asset_class=asset_class, status=HHSStatus.STALE
            )

        naa = _naa_calc.compute(
            gross_annual_dividends=h.income_received,
            annual_fee_drag=h.annual_fee_drag,
            annual_tax_drag=h.annual_tax_drag,
            total_invested=h.original_cost,
        )
        inputs.append(
            HoldingInput(
                ticker=ticker,
                hhs=hhs,
                naa=naa,
                position_value=h.position_value,
                original_cost=h.original_cost,
                current_value=h.current_value,
                income_received=h.income_received,
                tax_drag=h.annual_tax_drag or 0.0,
            )
        )

    result = PortfolioHealthCalculator(hhi_flag_threshold=threshold).compute(inputs)
    return PortfolioHealthResponse(
        aggregate_hhs=result.aggregate_hhs,
        scored_holding_count=result.scored_holding_count,
        excluded_holding_count=result.excluded_holding_count,
        unsafe_count=result.unsafe_count,
        unsafe_tickers=result.unsafe_tickers,
        gate_fail_count=result.gate_fail_count,
        insufficient_data_count=result.insufficient_data_count,
        stale_count=result.stale_count,
        portfolio_naa_yield_pct=result.portfolio_naa_yield_pct,
        portfolio_naa_pre_tax_flag=result.portfolio_naa_pre_tax_flag,
        total_return_pct=result.total_return_pct,
        hhi=result.hhi,
        concentration_flags=result.concentration_flags,
        sharpe=result.sharpe,
        sortino=result.sortino,
        var_95=result.var_95,
    )
