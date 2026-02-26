"""
Agent 03 — Income Scoring Service
API: Scores endpoints — Phase 2 full implementation.

Endpoints:
  POST /scores/evaluate   — run quality gate + scoring, persist result
  GET  /scores/           — last 20 scores (optional ?recommendation= filter)
  GET  /scores/{ticker}   — latest score for a ticker
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import IncomeScore, QualityGateResult
from app.scoring.data_client import MarketDataClient
from app.scoring.income_scorer import IncomeScorer, ScoreResult
from app.scoring.nav_erosion import NAVErosionAnalyzer
from app.scoring.quality_gate import (
    AssetClass,
    BondGateInput,
    CoveredCallETFGateInput,
    DividendStockGateInput,
    QualityGateEngine,
)

logger = logging.getLogger(__name__)

router   = APIRouter()
_scorer   = IncomeScorer()
_analyzer = NAVErosionAnalyzer()
_gate     = QualityGateEngine()
_client   = MarketDataClient()


# ── Pydantic request / response models ────────────────────────────────────────

class ScoreRequest(BaseModel):
    ticker: str
    asset_class: str


class ScoreResponse(BaseModel):
    ticker: str
    asset_class: str
    valuation_yield_score: float
    financial_durability_score: float
    technical_entry_score: float
    total_score_raw: float
    nav_erosion_penalty: float
    total_score: float
    grade: str
    recommendation: str
    factor_details: dict
    nav_erosion_details: Optional[dict] = None
    data_quality_score: float
    data_completeness_pct: float
    scored_at: datetime


class ScoreListItem(BaseModel):
    ticker: str
    asset_class: str
    total_score: float
    grade: str
    recommendation: str
    scored_at: datetime


# ── Internal helpers ───────────────────────────────────────────────────────────

def _orm_to_response(score: IncomeScore) -> ScoreResponse:
    return ScoreResponse(
        ticker=score.ticker,
        asset_class=score.asset_class,
        valuation_yield_score=score.valuation_yield_score,
        financial_durability_score=score.financial_durability_score,
        technical_entry_score=score.technical_entry_score,
        total_score_raw=score.total_score_raw,
        nav_erosion_penalty=score.nav_erosion_penalty,
        total_score=score.total_score,
        grade=score.grade,
        recommendation=score.recommendation,
        factor_details=score.factor_details or {},
        nav_erosion_details=score.nav_erosion_details,
        data_quality_score=score.data_quality_score or 0.0,
        data_completeness_pct=score.data_completeness_pct or 0.0,
        scored_at=score.scored_at,
    )


def _result_to_response(
    result: ScoreResult,
    nav_erosion_details: Optional[dict],
    scored_at: datetime,
) -> ScoreResponse:
    return ScoreResponse(
        ticker=result.ticker,
        asset_class=result.asset_class,
        valuation_yield_score=result.valuation_yield_score,
        financial_durability_score=result.financial_durability_score,
        technical_entry_score=result.technical_entry_score,
        total_score_raw=result.total_score_raw,
        nav_erosion_penalty=result.nav_erosion_penalty,
        total_score=result.total_score,
        grade=result.grade,
        recommendation=result.recommendation,
        factor_details=result.factor_details,
        nav_erosion_details=nav_erosion_details,
        data_quality_score=result.data_quality_score,
        data_completeness_pct=result.data_completeness_pct,
        scored_at=scored_at,
    )


async def _fetch_market_data(ticker: str, asset_class: str) -> dict:
    """Fetch all required market data from Agent 01 concurrently."""
    today      = date.today()
    start_date = (today - timedelta(days=settings.score_history_days)).isoformat()
    end_date   = today.isoformat()

    tasks: dict[str, object] = {
        "fundamentals":    _client.get_fundamentals(ticker),
        "dividend_history": _client.get_dividend_history(ticker),
        "history_stats":   _client.get_history_stats(ticker, start_date, end_date),
        "current_price":   _client.get_current_price(ticker),
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


def _derive_dividend_years(dividend_history: list) -> Optional[int]:
    """Count unique calendar years in dividend history."""
    years = set()
    for d in dividend_history or []:
        ex_date = d.get("ex_date")
        if ex_date:
            try:
                years.add(str(ex_date)[:4])
            except (IndexError, TypeError):
                pass
    return len(years) if years else None


def _run_inline_gate(ticker: str, asset_class: str, market_data: dict):
    """Run quality gate inline using fetched market data.

    Returns a GateResult with a dynamically attached ``dividend_history_years``
    attribute so the scorer can read it without caring about the object type.
    """
    fundamentals     = market_data.get("fundamentals")     or {}
    dividend_history = market_data.get("dividend_history") or []
    dividend_years   = _derive_dividend_years(dividend_history)

    # Best-effort FCF year count: 1 positive year if current FCF is positive.
    fcf       = fundamentals.get("free_cash_flow")
    fcf_years = 1 if (fcf is not None and fcf > 0) else None

    ac = asset_class.upper()
    if ac in (AssetClass.DIVIDEND_STOCK, "DIVIDEND_STOCK"):
        gate_result = _gate.evaluate_dividend_stock(DividendStockGateInput(
            ticker=ticker,
            credit_rating=fundamentals.get("credit_rating"),
            consecutive_positive_fcf_years=fcf_years,
            dividend_history_years=dividend_years,
        ))

    elif ac in (AssetClass.COVERED_CALL_ETF, "COVERED_CALL_ETF"):
        etf_data    = market_data.get("etf_data") or {}
        aum_raw     = etf_data.get("aum")
        aum_millions = float(aum_raw) / 1_000_000 if aum_raw else None
        gate_result = _gate.evaluate_covered_call_etf(CoveredCallETFGateInput(
            ticker=ticker,
            aum_millions=aum_millions,
        ))

    else:  # BOND or unknown
        gate_result = _gate.evaluate_bond(BondGateInput(
            ticker=ticker,
            credit_rating=fundamentals.get("credit_rating"),
        ))

    # Attach dividend_history_years so the scorer can read it via getattr
    gate_result.dividend_history_years = dividend_years
    return gate_result


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ScoreListItem])
def list_scores(
    recommendation: Optional[str] = Query(None, description="Filter by recommendation"),
    db: Session = Depends(get_db),
):
    """Return the last 20 income scores, optionally filtered by recommendation."""
    query = db.query(IncomeScore).order_by(IncomeScore.scored_at.desc())
    if recommendation:
        query = query.filter(IncomeScore.recommendation == recommendation.upper())
    scores = query.limit(20).all()
    return [
        ScoreListItem(
            ticker=s.ticker,
            asset_class=s.asset_class,
            total_score=s.total_score,
            grade=s.grade,
            recommendation=s.recommendation,
            scored_at=s.scored_at,
        )
        for s in scores
    ]


@router.post("/evaluate", response_model=ScoreResponse)
async def evaluate_score(req: ScoreRequest, db: Session = Depends(get_db)):
    """Score a ticker using quality gate + weighted scoring engine.

    Flow:
    1. Look up the latest passing quality gate result from DB (24-h cache hit).
    2. Fetch market data from Agent 01 concurrently.
    3. If no DB gate record, run the quality gate inline from market data.
    4. Run the income scoring engine.
    5. Apply NAV erosion penalty for COVERED_CALL_ETF.
    6. Persist IncomeScore to DB.
    7. Return full score breakdown.
    """
    ticker     = req.ticker.upper()
    asset_class = req.asset_class.upper()

    # 1. Latest passing gate result from DB
    gate_db = (
        db.query(QualityGateResult)
        .filter(
            QualityGateResult.ticker == ticker,
            QualityGateResult.passed.is_(True),
        )
        .order_by(QualityGateResult.evaluated_at.desc())
        .first()
    )

    # 2. Fetch market data concurrently
    try:
        market_data = await _fetch_market_data(ticker, asset_class)
    except Exception as e:
        logger.error("Failed to fetch market data for %s: %s", ticker, e)
        market_data = {}

    # 3. Inline gate if no DB record found
    gate_proxy = gate_db
    if gate_proxy is None:
        try:
            gate_proxy = _run_inline_gate(ticker, asset_class, market_data)
        except Exception as e:
            logger.warning("Inline gate failed for %s: %s", ticker, e)
            gate_proxy = None

    # 4. Score
    try:
        result: ScoreResult = _scorer.score(ticker, asset_class, gate_proxy, market_data)
    except Exception as e:
        logger.error("Scoring engine error for %s: %s", ticker, e)
        raise HTTPException(status_code=500, detail=f"Scoring engine error: {e}")

    # 5. NAV erosion penalty (covered call ETFs only)
    nav_erosion_details: Optional[dict] = None
    if asset_class in (AssetClass.COVERED_CALL_ETF, "COVERED_CALL_ETF"):
        try:
            erosion = _analyzer.analyze(ticker, market_data.get("history_stats") or {})
            result.nav_erosion_penalty = float(erosion.penalty)
            result.total_score        = max(0.0, result.total_score_raw - result.nav_erosion_penalty)
            result.grade              = IncomeScorer._grade(result.total_score)
            result.recommendation     = IncomeScorer._recommendation(result.total_score)
            nav_erosion_details = {
                "prob_erosion_gt_5pct":      erosion.prob_erosion_gt_5pct,
                "median_annual_nav_change_pct": erosion.median_annual_nav_change_pct,
                "risk_classification":       erosion.risk_classification,
                "penalty_applied":           erosion.penalty,
            }
        except Exception as e:
            logger.warning("NAV erosion analysis failed for %s: %s", ticker, e)

    # 6. Persist to DB
    now        = datetime.utcnow()
    valid_until = now + timedelta(seconds=settings.cache_ttl_score)
    quality_gate_id = getattr(gate_db, "id", None)

    db_score = IncomeScore(
        ticker=ticker,
        asset_class=asset_class,
        valuation_yield_score=result.valuation_yield_score,
        financial_durability_score=result.financial_durability_score,
        technical_entry_score=result.technical_entry_score,
        total_score_raw=result.total_score_raw,
        nav_erosion_penalty=result.nav_erosion_penalty,
        total_score=result.total_score,
        grade=result.grade,
        recommendation=result.recommendation,
        factor_details=result.factor_details,
        nav_erosion_details=nav_erosion_details,
        data_quality_score=result.data_quality_score,
        data_completeness_pct=result.data_completeness_pct,
        scored_at=now,
        valid_until=valid_until,
        quality_gate_id=quality_gate_id,
    )
    try:
        db.add(db_score)
        db.commit()
        db.refresh(db_score)
        return _orm_to_response(db_score)
    except Exception as e:
        db.rollback()
        logger.error("Failed to persist score for %s: %s", ticker, e)
        # Return the in-memory result so the caller still gets a useful response
        return _result_to_response(result, nav_erosion_details, now)


@router.get("/{ticker}", response_model=ScoreResponse)
def get_score(ticker: str, db: Session = Depends(get_db)):
    """Return the latest income score for a ticker from the database."""
    ticker = ticker.upper()
    score = (
        db.query(IncomeScore)
        .filter(IncomeScore.ticker == ticker)
        .order_by(IncomeScore.scored_at.desc())
        .first()
    )
    if score is None:
        raise HTTPException(
            status_code=404,
            detail=f"No score found for {ticker}. Run POST /scores/evaluate first.",
        )
    return _orm_to_response(score)
