"""
Agent 05 — Tax Optimization Service
API Routes
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, check_db_health
from app.models import (
    AccountType,
    AssetClass,
    FilingStatus,
    HarvestingRequest,
    OptimizationRequest,
    TaxCalculationRequest,
    TaxProfileRequest,
)
from app.tax.profiler import build_tax_profile
from app.tax.calculator import calculate_tax_burden
from app.tax.optimizer import optimize_portfolio
from app.tax.harvester import identify_harvesting_opportunities

logger = logging.getLogger(__name__)

router = APIRouter()
health_router = APIRouter()


# ─── Health ──────────────────────────────────────────────────────────────────

@health_router.get("/health")
async def health_check():
    db_ok = await check_db_health()
    return {
        "status": "healthy",
        "service": "tax-optimization-service",
        "version": "1.0.0",
        "agent_id": 5,
        "database": "connected" if db_ok else "unavailable",
    }


# ─── Tax Profile ──────────────────────────────────────────────────────────────

@router.get("/tax/profile/{symbol}")
async def get_tax_profile(
    symbol: str,
    asset_class: Optional[AssetClass] = Query(None),
    filing_status: FilingStatus = Query(FilingStatus.SINGLE),
    state_code: Optional[str] = Query(None, max_length=2),
    account_type: AccountType = Query(AccountType.TAXABLE),
    annual_income: Optional[float] = Query(None, ge=0),
):
    """
    Return the tax treatment profile for a symbol.
    If asset_class is not provided, Agent 04 is called; falls back to ORDINARY_INCOME.
    """
    try:
        result = await build_tax_profile(
            TaxProfileRequest(
                symbol=symbol.upper(),
                asset_class=asset_class,
                filing_status=filing_status,
                state_code=state_code,
                account_type=account_type,
                annual_income=annual_income,
            )
        )
        return result
    except Exception as exc:
        logger.error("Tax profile error for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/tax/profile")
async def post_tax_profile(request: TaxProfileRequest):
    """POST version of tax profile for complex requests."""
    try:
        return await build_tax_profile(request)
    except Exception as exc:
        logger.error("Tax profile POST error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Tax Calculation ──────────────────────────────────────────────────────────

@router.post("/tax/calculate")
async def calculate_tax(request: TaxCalculationRequest):
    """
    Calculate the after-tax net distribution and effective tax rate
    for a given symbol and distribution amount.
    """
    try:
        return await calculate_tax_burden(request)
    except Exception as exc:
        logger.error("Tax calculation error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tax/calculate/{symbol}")
async def calculate_tax_get(
    symbol: str,
    distribution_amount: float = Query(..., gt=0,
        description="Annual distribution per share"),
    annual_income: float = Query(..., ge=0),
    filing_status: FilingStatus = Query(FilingStatus.SINGLE),
    state_code: Optional[str] = Query(None, max_length=2),
    account_type: AccountType = Query(AccountType.TAXABLE),
    asset_class: Optional[AssetClass] = Query(None),
):
    """GET convenience endpoint for quick single-symbol tax calculations."""
    try:
        return await calculate_tax_burden(
            TaxCalculationRequest(
                symbol=symbol.upper(),
                annual_income=annual_income,
                filing_status=filing_status,
                state_code=state_code,
                account_type=account_type,
                distribution_amount=distribution_amount,
                asset_class=asset_class,
            )
        )
    except Exception as exc:
        logger.error("Tax calc GET error %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Portfolio Optimization ───────────────────────────────────────────────────

@router.post("/tax/optimize")
async def optimize_tax(request: OptimizationRequest):
    """
    Analyze a portfolio of holdings and recommend optimal account placement
    to minimize tax drag on income distributions.
    """
    if not request.holdings:
        raise HTTPException(status_code=422, detail="At least one holding is required.")
    try:
        return await optimize_portfolio(request)
    except Exception as exc:
        logger.error("Portfolio optimization error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Tax-Loss Harvesting ──────────────────────────────────────────────────────

@router.post("/tax/harvest")
async def harvest_losses(request: HarvestingRequest):
    """
    Identify tax-loss harvesting opportunities across a set of positions.
    Proposals only — no trades are executed.
    """
    if not request.candidates:
        raise HTTPException(status_code=422, detail="At least one candidate position is required.")
    try:
        return await identify_harvesting_opportunities(request)
    except Exception as exc:
        logger.error("Harvesting analysis error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Convenience: Asset-class tax summary ────────────────────────────────────

@router.get("/tax/asset-classes")
async def list_asset_class_profiles():
    """
    Return a reference summary of expected tax treatment for each supported asset class.
    """
    from app.tax.profiler import _PROFILE_MAP
    return {
        ac.value: {
            "primary_treatment": profile["primary"].value,
            "qualified_dividend_eligible": profile["qualified"],
            "section_199a_eligible": profile["s199a"],
            "section_1256_eligible": profile["s1256"],
            "k1_required": profile["k1"],
        }
        for ac, profile in _PROFILE_MAP.items()
    }
