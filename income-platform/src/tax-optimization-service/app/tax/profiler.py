"""
Agent 05 — Tax Optimization Service
Tax Profiler — maps AssetClass → tax treatment profile.
Pure rule-based logic; no external API calls.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.models import (
    AssetClass,
    TaxProfileRequest,
    TaxProfileResponse,
    TaxTreatment,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── Asset-class → treatment mapping ─────────────────────────────────────────

_PROFILE_MAP: dict[AssetClass, dict] = {
    AssetClass.COVERED_CALL_ETF: {
        "primary": TaxTreatment.ORDINARY_INCOME,
        "secondary": [TaxTreatment.RETURN_OF_CAPITAL, TaxTreatment.SECTION_1256_60_40],
        "qualified": False,
        "s199a": False,
        "s1256": True,   # depends on underlying; default True for awareness
        "k1": False,
        "notes": [
            "Option premiums are treated as ordinary income in most covered call ETFs.",
            "Some futures-based structures qualify for 60/40 Section 1256 treatment—verify with fund prospectus.",
        ],
    },
    AssetClass.DIVIDEND_STOCK: {
        "primary": TaxTreatment.QUALIFIED_DIVIDEND,
        "secondary": [TaxTreatment.ORDINARY_INCOME],
        "qualified": True,
        "s199a": False,
        "s1256": False,
        "k1": False,
        "notes": [
            "Qualified dividends require 61-day holding period around ex-dividend date.",
            "Foreign dividends may not qualify; confirm treaty status.",
        ],
    },
    AssetClass.REIT: {
        "primary": TaxTreatment.REIT_DISTRIBUTION,
        "secondary": [TaxTreatment.RETURN_OF_CAPITAL, TaxTreatment.CAPITAL_GAIN_LONG],
        "qualified": False,
        "s199a": True,   # 20% Section 199A deduction for individuals
        "s1256": False,
        "k1": False,
        "notes": [
            "REIT distributions generally treated as ordinary income.",
            "Up to 20% Section 199A deduction available for qualifying taxpayers.",
            "Return-of-capital portion reduces cost basis—track carefully.",
        ],
    },
    AssetClass.BOND_ETF: {
        "primary": TaxTreatment.ORDINARY_INCOME,
        "secondary": [TaxTreatment.TAX_EXEMPT],
        "qualified": False,
        "s199a": False,
        "s1256": False,
        "k1": False,
        "notes": [
            "Interest income is ordinary; municipal bond ETFs may be tax-exempt at federal level.",
            "Check whether state taxes exempt in-state municipal bonds.",
        ],
    },
    AssetClass.PREFERRED_STOCK: {
        "primary": TaxTreatment.QUALIFIED_DIVIDEND,
        "secondary": [TaxTreatment.ORDINARY_INCOME],
        "qualified": True,
        "s199a": False,
        "s1256": False,
        "k1": False,
        "notes": [
            "Bank-issued trust preferred may produce ordinary income—verify issuer structure.",
        ],
    },
    AssetClass.MLP: {
        "primary": TaxTreatment.MLP_DISTRIBUTION,
        "secondary": [TaxTreatment.RETURN_OF_CAPITAL, TaxTreatment.ORDINARY_INCOME],
        "qualified": False,
        "s199a": True,
        "s1256": False,
        "k1": True,
        "notes": [
            "MLP distributions are mostly return of capital, reducing cost basis.",
            "K-1 required; file by partnership tax deadline (March 15).",
            "Unrelated Business Taxable Income (UBTI) generated in IRA accounts.",
        ],
    },
    AssetClass.BDC: {
        "primary": TaxTreatment.ORDINARY_INCOME,
        "secondary": [TaxTreatment.CAPITAL_GAIN_LONG, TaxTreatment.RETURN_OF_CAPITAL],
        "qualified": False,
        "s199a": False,
        "s1256": False,
        "k1": False,
        "notes": [
            "BDC dividends are usually ordinary income; some capital gain distributions possible.",
            "Pass-through of portfolio interest income retains ordinary character.",
        ],
    },
    AssetClass.CLOSED_END_FUND: {
        "primary": TaxTreatment.ORDINARY_INCOME,
        "secondary": [
            TaxTreatment.QUALIFIED_DIVIDEND,
            TaxTreatment.RETURN_OF_CAPITAL,
            TaxTreatment.CAPITAL_GAIN_LONG,
        ],
        "qualified": False,   # varies by fund composition
        "s199a": False,
        "s1256": False,
        "k1": False,
        "notes": [
            "CEF tax character depends on portfolio holdings—review annual 1099-DIV.",
            "Return of capital from CEFs can be destructive (NAV erosion) or non-destructive.",
        ],
    },
    AssetClass.ORDINARY_INCOME: {
        "primary": TaxTreatment.ORDINARY_INCOME,
        "secondary": [],
        "qualified": False,
        "s199a": False,
        "s1256": False,
        "k1": False,
        "notes": ["Asset class defaulted to ORDINARY_INCOME; Agent 04 classification unavailable."],
    },
    AssetClass.UNKNOWN: {
        "primary": TaxTreatment.ORDINARY_INCOME,
        "secondary": [],
        "qualified": False,
        "s199a": False,
        "s1256": False,
        "k1": False,
        "notes": ["Unknown asset class; conservative treatment applied."],
    },
}


async def _classify_via_agent04(symbol: str) -> Optional[AssetClass]:
    """Call Agent 04 to classify the symbol. Returns None on any failure."""
    try:
        async with httpx.AsyncClient(timeout=settings.agent04_timeout_seconds) as client:
            resp = await client.get(
                f"{settings.asset_classification_url}/classify/{symbol}"
            )
            if resp.status_code == 200:
                data = resp.json()
                return AssetClass(data.get("asset_class", "UNKNOWN"))
    except Exception as exc:
        logger.warning("Agent 04 classification failed for %s: %s", symbol, exc)
    return None


async def build_tax_profile(request: TaxProfileRequest) -> TaxProfileResponse:
    """
    Determine tax treatment profile for a symbol.
    Uses provided asset_class; falls back to Agent 04; then to ORDINARY_INCOME.
    """
    asset_class = request.asset_class
    fallback = False

    if asset_class is None:
        classified = await _classify_via_agent04(request.symbol)
        if classified:
            asset_class = classified
        else:
            asset_class = AssetClass.ORDINARY_INCOME
            fallback = True
            logger.info(
                "Defaulting %s to ORDINARY_INCOME — Agent 04 unavailable",
                request.symbol,
            )

    profile = _PROFILE_MAP.get(asset_class, _PROFILE_MAP[AssetClass.UNKNOWN])

    return TaxProfileResponse(
        symbol=request.symbol,
        asset_class=asset_class,
        asset_class_fallback=fallback,
        primary_tax_treatment=profile["primary"],
        secondary_treatments=profile["secondary"],
        qualified_dividend_eligible=profile["qualified"],
        section_199a_eligible=profile["s199a"],
        section_1256_eligible=profile["s1256"],
        k1_required=profile["k1"],
        notes=profile["notes"],
    )
