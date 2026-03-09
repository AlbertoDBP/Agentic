"""
Agent 05 — Tax Optimization Service
Pydantic models / schemas
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Enumerations ────────────────────────────────────────────────────────────

class AssetClass(str, Enum):
    COVERED_CALL_ETF   = "COVERED_CALL_ETF"
    DIVIDEND_STOCK     = "DIVIDEND_STOCK"
    REIT               = "REIT"
    BOND_ETF           = "BOND_ETF"
    PREFERRED_STOCK    = "PREFERRED_STOCK"
    MLP                = "MLP"
    BDC                = "BDC"
    CLOSED_END_FUND    = "CLOSED_END_FUND"
    ORDINARY_INCOME    = "ORDINARY_INCOME"   # Agent-04 fallback
    UNKNOWN            = "UNKNOWN"


class TaxTreatment(str, Enum):
    QUALIFIED_DIVIDEND       = "QUALIFIED_DIVIDEND"
    ORDINARY_INCOME          = "ORDINARY_INCOME"
    RETURN_OF_CAPITAL        = "RETURN_OF_CAPITAL"
    CAPITAL_GAIN_SHORT       = "CAPITAL_GAIN_SHORT"
    CAPITAL_GAIN_LONG        = "CAPITAL_GAIN_LONG"
    TAX_EXEMPT               = "TAX_EXEMPT"
    REIT_DISTRIBUTION        = "REIT_DISTRIBUTION"
    MLP_DISTRIBUTION         = "MLP_DISTRIBUTION"
    SECTION_1256_60_40       = "SECTION_1256_60_40"   # futures / options ETFs


class AccountType(str, Enum):
    TAXABLE   = "TAXABLE"
    TRAD_IRA  = "TRAD_IRA"
    ROTH_IRA  = "ROTH_IRA"
    HSA       = "HSA"
    FOUR01K   = "401K"


class FilingStatus(str, Enum):
    SINGLE            = "SINGLE"
    MARRIED_JOINT     = "MARRIED_JOINT"
    MARRIED_SEPARATE  = "MARRIED_SEPARATE"
    HEAD_OF_HOUSEHOLD = "HEAD_OF_HOUSEHOLD"


# ─── Tax Profile schemas ──────────────────────────────────────────────────────

class TaxProfileRequest(BaseModel):
    symbol: str = Field(..., description="Ticker symbol")
    asset_class: Optional[AssetClass] = None
    annual_income: Optional[float] = Field(None, ge=0)
    filing_status: FilingStatus = FilingStatus.SINGLE
    state_code: Optional[str] = Field(None, max_length=2)
    account_type: AccountType = AccountType.TAXABLE


class TaxProfileResponse(BaseModel):
    symbol: str
    asset_class: AssetClass
    asset_class_fallback: bool = False          # True when Agent-04 unavailable
    primary_tax_treatment: TaxTreatment
    secondary_treatments: List[TaxTreatment] = []
    qualified_dividend_eligible: bool
    section_199a_eligible: bool                 # REITs
    section_1256_eligible: bool                 # futures-based ETFs
    k1_required: bool                           # MLPs, some CEFs
    notes: List[str] = []


# ─── Tax Calculator schemas ───────────────────────────────────────────────────

class TaxCalculationRequest(BaseModel):
    symbol: str
    annual_income: float = Field(..., ge=0)
    filing_status: FilingStatus = FilingStatus.SINGLE
    state_code: Optional[str] = None
    account_type: AccountType = AccountType.TAXABLE
    distribution_amount: float = Field(..., ge=0,
        description="Annual distribution per share (gross)")
    asset_class: Optional[AssetClass] = None


class TaxBracketDetail(BaseModel):
    income_type: str
    rate_federal: float
    rate_state: Optional[float] = None
    rate_combined: float
    niit_applicable: bool = False          # 3.8 % Net Investment Income Tax


class TaxCalculationResponse(BaseModel):
    symbol: str
    gross_distribution: float
    federal_tax_owed: float
    state_tax_owed: float
    niit_owed: float
    total_tax_owed: float
    net_distribution: float
    effective_tax_rate: float              # 0-1
    after_tax_yield_uplift: float          # vs treating as ordinary income
    bracket_detail: List[TaxBracketDetail]
    notes: List[str] = []


# ─── Tax Optimizer schemas ────────────────────────────────────────────────────

class HoldingInput(BaseModel):
    symbol: str
    asset_class: Optional[AssetClass] = None
    account_type: AccountType = AccountType.TAXABLE
    current_value: float = Field(..., ge=0)
    annual_yield: float = Field(..., ge=0, le=5.0)   # decimal, e.g. 0.08


class OptimizationRequest(BaseModel):
    holdings: List[HoldingInput]
    annual_income: float = Field(..., ge=0)
    filing_status: FilingStatus = FilingStatus.SINGLE
    state_code: Optional[str] = None


class PlacementRecommendation(BaseModel):
    symbol: str
    current_account: AccountType
    recommended_account: AccountType
    reason: str
    estimated_annual_tax_savings: float


class OptimizationResponse(BaseModel):
    total_portfolio_value: float
    current_annual_tax_burden: float
    optimized_annual_tax_burden: float
    estimated_annual_savings: float
    placement_recommendations: List[PlacementRecommendation]
    summary: str
    notes: List[str] = []


# ─── Tax Harvester schemas ────────────────────────────────────────────────────

class HarvestingCandidate(BaseModel):
    symbol: str
    current_value: float = Field(..., ge=0)
    cost_basis: float = Field(..., ge=0)
    holding_period_days: int = Field(..., ge=0)
    account_type: AccountType = AccountType.TAXABLE


class HarvestingRequest(BaseModel):
    candidates: List[HarvestingCandidate]
    annual_income: float = Field(..., ge=0)
    filing_status: FilingStatus = FilingStatus.SINGLE
    state_code: Optional[str] = None
    wash_sale_check: bool = True


class HarvestingOpportunity(BaseModel):
    symbol: str
    unrealized_loss: float
    tax_savings_estimated: float
    holding_period_days: int
    long_term: bool
    wash_sale_risk: bool
    action: str                   # e.g. "HARVEST_NOW", "HOLD", "MONITOR"
    rationale: str


class HarvestingResponse(BaseModel):
    total_harvestable_losses: float
    total_estimated_tax_savings: float
    opportunities: List[HarvestingOpportunity]
    wash_sale_warnings: List[str] = []
    notes: List[str] = []


# ─── Generic health / error ───────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    agent_id: int


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
