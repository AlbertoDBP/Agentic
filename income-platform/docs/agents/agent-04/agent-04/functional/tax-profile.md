# Functional Spec — Tax Profile

**Component:** `app/classification/tax_profile.py`  
**Output field:** `tax_efficiency` in every ClassificationResponse  
**Last Updated:** 2026-02-27  
**Status:** ✅ Production

---

## Purpose & Scope

Builds the `tax_efficiency` output field for every classified security. This field is a parallel output — it has 0% weight in the composite income score and is consumed exclusively by Agent 05 (Tax Optimizer) for account placement decisions.

Always populated regardless of VETO status, NAV erosion flags, or score outcome.

---

## Output Structure

```json
{
  "tax_efficiency": {
    "income_type": "option_premium",
    "tax_treatment": "ordinary",
    "estimated_tax_drag_pct": 37.0,
    "preferred_account": "IRA",
    "notes": "Option premium taxed as ordinary income. Hold in IRA/Roth to shelter high distributions."
  }
}
```

---

## Tax Drag Estimates (Florida — No State Tax)

| Income Type | Tax Rate | Notes |
|---|---|---|
| qualified_dividend | 15% | Federal preferential rate (most brackets) |
| fixed_dividend | 15% | Qualified preferred dividends |
| roc | 0% | Return of capital — tax deferred |
| option_premium | 37% | Ordinary income top rate |
| interest | 37% | Ordinary income |
| reit_distribution | 37% | Ordinary income (Section 199A partial deduction not modeled) |
| ordinary_dividend | 37% | BDC pass-through income |
| unknown | 37% | Conservative assumption |

---

## Account Placement by Class

| Asset Class | Preferred Account | Rationale |
|---|---|---|
| COVERED_CALL_ETF | IRA | Option premium = ordinary income, high yield benefits from sheltering |
| MORTGAGE_REIT | IRA | Ordinary income distributions, high yield |
| EQUITY_REIT | IRA | Ordinary income, Section 199A deduction not guaranteed |
| BDC | IRA | Pass-through ordinary income, typically high yield |
| BOND | IRA | Interest = ordinary income |
| PREFERRED_STOCK | TAXABLE | Qualified dividends = preferential rate, no benefit from sheltering |
| DIVIDEND_STOCK | TAXABLE | Qualified dividends = preferential rate, tax drag minimal |

---

## Design Decisions

- **0% composite weight** — tax efficiency is informational only, never influences income score
- **Florida-specific** — no state income tax calculations
- **Conservative estimates** — uses top marginal rate for ordinary income (37%) as worst-case
- **Section 199A not modeled** — 20% REIT deduction excluded for simplicity; Agent 05 handles nuanced calculations
- **Always populated** — even when score=0 (VETO), tax_efficiency is returned for Agent 05

---

## Downstream Consumer

Agent 05 (Tax Optimizer — v1.1 roadmap) consumes `tax_efficiency` to:
- Optimize account placement across taxable + IRA + Roth accounts
- Calculate after-tax yield scenarios
- Generate tax harvesting recommendations
