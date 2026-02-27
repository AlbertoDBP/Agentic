"""
Tax Profile Builder
Builds the tax_efficiency output field consumed by Agent 05.
0% weight in composite score — parallel output only.
"""
from dataclasses import dataclass


# Approximate tax drag by income type (Florida — no state tax)
TAX_DRAG_BY_INCOME_TYPE = {
    "qualified_dividend":  0.15,   # 15% federal for most brackets
    "option_premium":      0.37,   # ordinary income top rate
    "interest":            0.37,   # ordinary income
    "reit_distribution":   0.37,   # ordinary income (Section 199A partial deduction not modeled)
    "ordinary_dividend":   0.37,   # ordinary income
    "fixed_dividend":      0.15,   # qualified in most cases
    "roc":                 0.00,   # return of capital — tax deferred
    "unknown":             0.37,   # conservative assumption
}


@dataclass
class TaxEfficiency:
    income_type: str
    tax_treatment: str
    estimated_tax_drag_pct: float
    preferred_account: str          # TAXABLE | IRA | EITHER
    notes: str


def build_tax_profile(asset_class: str, characteristics: dict) -> dict:
    """
    Build tax_efficiency output for a classified asset.
    Always populated regardless of VETO or score.
    Consumed by Agent 05.
    """
    income_type = characteristics.get("income_type", "unknown")
    tax_treatment = characteristics.get("tax_treatment", "unknown")
    preferred_account = characteristics.get("preferred_account", "TAXABLE")

    drag = TAX_DRAG_BY_INCOME_TYPE.get(income_type, 0.37)

    notes = _tax_notes(asset_class, income_type, tax_treatment)

    return {
        "income_type": income_type,
        "tax_treatment": tax_treatment,
        "estimated_tax_drag_pct": round(drag * 100, 1),
        "preferred_account": preferred_account,
        "notes": notes,
    }


def _tax_notes(asset_class: str, income_type: str, tax_treatment: str) -> str:
    notes_map = {
        "COVERED_CALL_ETF": (
            "Option premium taxed as ordinary income. "
            "Hold in IRA/Roth to shelter high distributions."
        ),
        "MORTGAGE_REIT": (
            "Distributions taxed as ordinary income. "
            "Section 199A deduction may apply (20% deduction on qualified REIT dividends). "
            "Best held in tax-advantaged accounts."
        ),
        "EQUITY_REIT": (
            "REIT distributions typically ordinary income. "
            "Section 199A deduction may apply. "
            "IRA preferred for high-yielding REITs."
        ),
        "BDC": (
            "BDC dividends typically ordinary income (pass-through structure). "
            "IRA preferred to shelter high yields."
        ),
        "BOND": (
            "Interest income taxed as ordinary income. "
            "Hold in IRA to defer tax on coupon payments."
        ),
        "PREFERRED_STOCK": (
            "Qualified dividends receive preferential tax treatment. "
            "Taxable account is efficient for qualified preferred dividends."
        ),
        "DIVIDEND_STOCK": (
            "Qualified dividends taxed at preferential rates (0/15/20%). "
            "Taxable account is efficient for qualified dividend payers."
        ),
    }
    return notes_map.get(asset_class, "Consult Agent 05 for account placement optimization.")
