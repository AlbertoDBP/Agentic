"""
Agent 03 — Income Scoring Service
API: Quality Gate endpoints.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from app.config import settings
from app.database import get_db
from app.models import QualityGateResult, ScoringRun
from app.scoring.quality_gate import (
    AssetClass, QualityGateEngine,
    DividendStockGateInput, CoveredCallETFGateInput, BondGateInput,
    GateResult, GateStatus,
)

router = APIRouter()
engine = QualityGateEngine()


class QualityGateRequest(BaseModel):
    ticker: str
    asset_class: AssetClass
    credit_rating: Optional[str] = None
    consecutive_positive_fcf_years: Optional[int] = None
    dividend_history_years: Optional[int] = None
    aum_millions: Optional[float] = None
    track_record_years: Optional[float] = None
    distribution_history_months: Optional[int] = None
    duration_years: Optional[float] = None
    issuer_type: Optional[str] = None
    yield_to_maturity: Optional[float] = None
    class Config:
        use_enum_values = True


class QualityGateResponse(BaseModel):
    ticker: str
    asset_class: str
    passed: bool
    status: str
    fail_reasons: list[str]
    warnings: list[str]
    checks: dict
    data_quality_score: float
    evaluated_at: datetime
    valid_until: datetime


class BatchQualityGateRequest(BaseModel):
    tickers: list[QualityGateRequest] = Field(..., max_length=50)


class BatchQualityGateResponse(BaseModel):
    total: int
    passed: int
    failed: int
    insufficient_data: int
    results: list[QualityGateResponse]
    evaluated_at: datetime


def _run_gate(req: QualityGateRequest) -> GateResult:
    if req.asset_class == AssetClass.DIVIDEND_STOCK:
        return engine.evaluate_dividend_stock(DividendStockGateInput(
            ticker=req.ticker,
            credit_rating=req.credit_rating,
            consecutive_positive_fcf_years=req.consecutive_positive_fcf_years,
            dividend_history_years=req.dividend_history_years,
        ))
    elif req.asset_class == AssetClass.COVERED_CALL_ETF:
        return engine.evaluate_covered_call_etf(CoveredCallETFGateInput(
            ticker=req.ticker,
            aum_millions=req.aum_millions,
            track_record_years=req.track_record_years,
            distribution_history_months=req.distribution_history_months,
        ))
    elif req.asset_class == AssetClass.BOND:
        return engine.evaluate_bond(BondGateInput(
            ticker=req.ticker,
            credit_rating=req.credit_rating,
            duration_years=req.duration_years,
            issuer_type=req.issuer_type,
            yield_to_maturity=req.yield_to_maturity,
        ))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported asset class: {req.asset_class}")


def _to_response(result: GateResult) -> QualityGateResponse:
    return QualityGateResponse(
        ticker=result.ticker,
        asset_class=result.asset_class.value,
        passed=result.passed,
        status=result.status.value,
        fail_reasons=result.fail_reasons,
        warnings=result.warnings,
        checks=result.checks,
        data_quality_score=result.data_quality_score,
        evaluated_at=result.evaluated_at,
        valid_until=result.valid_until,
    )


@router.post("/evaluate", response_model=QualityGateResponse)
def evaluate_single(req: QualityGateRequest, db: Session = Depends(get_db)):
    result = _run_gate(req)
    return _to_response(result)


@router.post("/batch", response_model=BatchQualityGateResponse)
def evaluate_batch(req: BatchQualityGateRequest, db: Session = Depends(get_db)):
    if len(req.tickers) > settings.max_batch_size:
        raise HTTPException(status_code=400, detail=f"Batch size exceeds maximum {settings.max_batch_size}")

    passed = failed = insufficient = 0
    results = []

    for ticker_req in req.tickers:
        result = _run_gate(ticker_req)
        if result.status == GateStatus.PASS:
            passed += 1
        elif result.status == GateStatus.FAIL:
            failed += 1
        else:
            insufficient += 1
        results.append(_to_response(result))

    return BatchQualityGateResponse(
        total=len(req.tickers),
        passed=passed,
        failed=failed,
        insufficient_data=insufficient,
        results=results,
        evaluated_at=datetime.utcnow(),
    )
