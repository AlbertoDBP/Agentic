"""
Asset Class Taxonomy
Defines the 7 MVP asset classes, hierarchy, and characteristics.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict


class AssetClass(str, Enum):
    DIVIDEND_STOCK = "DIVIDEND_STOCK"
    COVERED_CALL_ETF = "COVERED_CALL_ETF"
    BOND = "BOND"
    EQUITY_REIT = "EQUITY_REIT"
    MORTGAGE_REIT = "MORTGAGE_REIT"
    BDC = "BDC"
    PREFERRED_STOCK = "PREFERRED_STOCK"
    UNKNOWN = "UNKNOWN"


class ParentClass(str, Enum):
    EQUITY = "EQUITY"
    FIXED_INCOME = "FIXED_INCOME"
    ALTERNATIVE = "ALTERNATIVE"
    FUND = "FUND"


@dataclass
class AssetClassInfo:
    asset_class: AssetClass
    parent_class: ParentClass
    income_type: str
    tax_treatment: str          # qualified | ordinary | interest | roc
    valuation_method: str
    rate_sensitivity: str       # high | medium | low
    principal_at_risk: bool
    nav_erosion_tracking: bool = False
    coverage_ratio_required: bool = False
    is_hybrid: bool = False
    hybrid_parents: List[str] = field(default_factory=list)
    preferred_account: str = "TAXABLE"   # TAXABLE | IRA | EITHER


ASSET_CLASS_HIERARCHY: Dict[AssetClass, AssetClassInfo] = {
    AssetClass.DIVIDEND_STOCK: AssetClassInfo(
        asset_class=AssetClass.DIVIDEND_STOCK,
        parent_class=ParentClass.EQUITY,
        income_type="qualified_dividend",
        tax_treatment="qualified",
        valuation_method="P/E + yield",
        rate_sensitivity="medium",
        principal_at_risk=True,
        preferred_account="TAXABLE",
    ),
    AssetClass.COVERED_CALL_ETF: AssetClassInfo(
        asset_class=AssetClass.COVERED_CALL_ETF,
        parent_class=ParentClass.FUND,
        income_type="option_premium",
        tax_treatment="ordinary",
        valuation_method="yield + nav_trend",
        rate_sensitivity="low",
        principal_at_risk=True,
        nav_erosion_tracking=True,
        preferred_account="IRA",
    ),
    AssetClass.BOND: AssetClassInfo(
        asset_class=AssetClass.BOND,
        parent_class=ParentClass.FIXED_INCOME,
        income_type="interest",
        tax_treatment="ordinary",
        valuation_method="yield_to_maturity",
        rate_sensitivity="high",
        principal_at_risk=False,
        preferred_account="IRA",
    ),
    AssetClass.EQUITY_REIT: AssetClassInfo(
        asset_class=AssetClass.EQUITY_REIT,
        parent_class=ParentClass.EQUITY,
        income_type="reit_distribution",
        tax_treatment="ordinary",
        valuation_method="P/FFO",
        rate_sensitivity="high",
        principal_at_risk=True,
        preferred_account="IRA",
    ),
    AssetClass.MORTGAGE_REIT: AssetClassInfo(
        asset_class=AssetClass.MORTGAGE_REIT,
        parent_class=ParentClass.EQUITY,
        income_type="reit_distribution",
        tax_treatment="ordinary",
        valuation_method="P/BV",
        rate_sensitivity="high",
        principal_at_risk=True,
        is_hybrid=True,
        hybrid_parents=["EQUITY_REIT", "FUND"],
        coverage_ratio_required=True,
        preferred_account="IRA",
    ),
    AssetClass.BDC: AssetClassInfo(
        asset_class=AssetClass.BDC,
        parent_class=ParentClass.ALTERNATIVE,
        income_type="ordinary_dividend",
        tax_treatment="ordinary",
        valuation_method="P/NAV",
        rate_sensitivity="medium",
        principal_at_risk=True,
        coverage_ratio_required=True,
        preferred_account="IRA",
    ),
    AssetClass.PREFERRED_STOCK: AssetClassInfo(
        asset_class=AssetClass.PREFERRED_STOCK,
        parent_class=ParentClass.EQUITY,
        income_type="fixed_dividend",
        tax_treatment="qualified",
        valuation_method="yield_to_call",
        rate_sensitivity="high",
        principal_at_risk=False,
        preferred_account="TAXABLE",
    ),
    AssetClass.UNKNOWN: AssetClassInfo(
        asset_class=AssetClass.UNKNOWN,
        parent_class=ParentClass.EQUITY,
        income_type="unknown",
        tax_treatment="unknown",
        valuation_method="unknown",
        rate_sensitivity="unknown",
        principal_at_risk=True,
        preferred_account="TAXABLE",
    ),
}
