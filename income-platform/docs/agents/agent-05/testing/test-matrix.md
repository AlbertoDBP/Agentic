# Test Matrix — Agent 05 Tax Optimization Service

**Total Tests:** 135
**Pass Rate:** 135/135 (100%)
**Runtime:** ~2.0s
**Last Run:** 2026-03-12

---

## Test Files

| File | Classes | Tests |
|---|---|---|
| `tests/test_tax_optimization.py` | 5 | 30 |
| `tests/test_tax_extended.py` | 10 | 105 |
| **Total** | **15** | **135** |

---

## test_tax_optimization.py (30 tests)

### TestAPIRoutes (8 tests)
Tests all API endpoints for auth guards (401 without token), correct routing, and HTTP method enforcement.

### TestTaxProfiler (7 tests)
Tests `build_tax_profile()` for each supported asset class — correct `primary_tax_treatment`, `qualified_dividend_eligible`, `section_199a_eligible`, `k1_required`, and non-empty notes.

### TestTaxCalculator (7 tests)
Tests `calculate_tax_burden()` — qualified vs ordinary rates, tax-sheltered short-circuit, NIIT application, after-tax yield uplift calculation.

### TestTaxHarvester (5 tests)
Tests `identify_harvesting_opportunities()` — loss detection, wash-sale flagging, gains-only positions skipped, empty candidate list, HARVEST_NOW vs HOLD actions.

### TestTaxOptimizer (3 tests)
Tests `optimize_portfolio()` — high-tax assets moved to IRA, low-tax assets kept in TAXABLE, savings estimate positive.

---

## test_tax_extended.py (105 tests)

### TestProfilerAllClasses (22 tests)
Exhaustive verification that every asset class in `_PROFILE_MAP` returns a valid `TaxProfileResponse` with correct types, non-None treatments, and proper boolean fields.

### TestOptimizerHeuristics (13 tests)
Tests placement logic: MLP in TAXABLE (UBTI concern), REIT in IRA, qualified dividend stocks in TAXABLE, mixed portfolios, portfolio summary fields.

### TestAPIAuthAndRoutes (13 tests)
Tests 401 enforcement on all 7 protected endpoints; health endpoint accessible without token; correct 422 on empty holdings/candidates.

### TestHarvesterBoundaries (12 tests)
Edge cases: zero loss (no opportunity), exactly-at-cost (borderline), large loss, `wash_sale_check=False` bypasses flagging, action strings match spec (HARVEST_NOW/HOLD/MONITOR).

### TestCalculateTaxBurdenEdgeCases (10 tests)
Edge cases: zero distribution, very high income (20% qualified rate + NIIT), ROC treatment (zero tax), TAX_EXEMPT treatment, MLP 70/30 split, Section 1256 blended rate, married vs single bracket differences.

### TestStateRate (7 tests)
Verifies state rate lookup: FL=0.0, CA=0.133, TX=0.0, NY=0.109, unknown state defaults to 0.05, None returns 0.0.

### TestQualifiedRate (7 tests)
Verifies 0%, 15%, 20% qualified dividend brackets for SINGLE filing at boundary income levels.

### TestOrdinaryRate (7 tests)
Verifies all 7 ordinary income brackets for SINGLE filing at boundary income levels.

### TestNIIT (5 tests)
Verifies NIIT (3.8%) applies above threshold for each filing status; does not apply below; excluded for ROC and MLP.

### TestIsTaxSheltered (5 tests)
Verifies TRAD_IRA, ROTH_IRA, HSA, 401K all return True; TAXABLE returns False.

### TestMarginalRate (4 tests)
Unit tests for `_marginal_rate()` helper — boundary conditions, top bracket, single-bracket list.

---

## Running Tests

```bash
cd src/tax-optimization-service
.venv/bin/python -m pytest tests/ -q
```
