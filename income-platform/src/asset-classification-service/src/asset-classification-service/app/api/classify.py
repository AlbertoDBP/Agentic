"""Agent 04 — Classification API Router"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.classification.engine import ClassificationEngine

logger = logging.getLogger(__name__)
router = APIRouter()


class ClassifyRequest(BaseModel):
    ticker: str
    security_data: Optional[dict] = None   # optional enrichment hint from caller


class BatchClassifyRequest(BaseModel):
    tickers: List[str]                     # max 100
    security_data: Optional[dict] = None  # applied to all tickers if provided


@router.post("/classify")
async def classify_ticker(request: ClassifyRequest, db: Session = Depends(get_db)):
    """Classify a single ticker. Returns full classification with benchmarks and tax profile."""
    if not request.ticker:
        raise HTTPException(status_code=422, detail="ticker is required")
    engine = ClassificationEngine(db)
    return await engine.classify(request.ticker, request.security_data)


@router.post("/classify/batch")
async def classify_batch(request: BatchClassifyRequest, db: Session = Depends(get_db)):
    """Classify up to 100 tickers. Returns list of classifications."""
    if len(request.tickers) > 100:
        raise HTTPException(status_code=422, detail="Maximum 100 tickers per batch request")

    engine = ClassificationEngine(db)
    results = []
    errors = []

    for ticker in request.tickers:
        try:
            result = await engine.classify(ticker.upper().strip(), request.security_data)
            results.append(result)
        except Exception as e:
            logger.error(f"Error classifying {ticker}: {e}")
            errors.append({"ticker": ticker, "error": str(e)})

    return {
        "total": len(request.tickers),
        "classified": len(results),
        "errors": len(errors),
        "results": results,
        "error_details": errors,
    }


@router.get("/classify/{ticker}")
async def get_classification(ticker: str, db: Session = Depends(get_db)):
    """Get latest classification for ticker. Runs fresh classification if not cached."""
    engine = ClassificationEngine(db)
    return await engine.classify(ticker.upper().strip())
