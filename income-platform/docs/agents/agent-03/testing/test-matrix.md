# Test Matrix — Agent 03: Income Scoring Service

**Total Tests:** 134  
**Status:** ✅ 134/134 passing  
**Date:** 2026-02-26

---

## Coverage Summary

| Test File | Class/Group | Tests | Coverage Area |
|---|---|---|---|
| `test_quality_gate.py` | `TestCreditRatingHelper` | 12 | Credit rating comparison, boundaries, edge cases |
| `test_quality_gate.py` | `TestDividendStockGate` | 13 | Dividend stock pass/fail, missing data, boundaries |
| `test_quality_gate.py` | `TestCoveredCallETFGate` | 7 | ETF AUM, track record, distribution history |
| `test_quality_gate.py` | `TestBondGate` | 6 | Bond credit rating, duration, issuer warnings |
| `test_quality_gate.py` | `TestGateResultContract` | 4 | Result structure, types, consistency |
| `test_income_scorer.py` | Sub-component boundaries | 38 | Each scoring rule at every threshold |
| `test_income_scorer.py` | Grade/Recommendation | 12 | Grade thresholds A+→F, all recommendations |
| `test_income_scorer.py` | Null data handling | 10 | 50% partial credit, data_completeness_pct |
| `test_income_scorer.py` | Result structure | 6 | ScoreResult fields, types |
| `test_nav_erosion.py` | Risk tiers | 8 | LOW/MODERATE/HIGH/SEVERE classification |
| `test_nav_erosion.py` | Determinism | 4 | Fixed seed reproducibility |
| `test_nav_erosion.py` | Edge cases | 8 | None volatility, zero volatility, n_simulations |
| `test_nav_erosion.py` | Result structure | 6 | NAVErosionResult fields |
| **Total** | | **134** | |

---

## Key Test Scenarios

### Quality Gate — Credit Rating

| Test | Input | Expected |
|---|---|---|
| AAA passes | credit_rating="AAA" | passed=True |
| BBB- passes (floor) | credit_rating="BBB-" | passed=True |
| BB+ fails (just below) | credit_rating="BB+" | passed=False |
| D fails | credit_rating="D" | passed=False |
| Case insensitive | credit_rating="bbb-" | passed=True |
| Unknown rating | credit_rating="ZZZ" | passed=False |
| None skipped | credit_rating=None | check skipped, no fail |

### Quality Gate — Dividend Stock

| Test | Input | Expected |
|---|---|---|
| Perfect ticker | AAA, 20yr FCF, 60yr div | passed=True |
| Junk rating | BB, 20yr FCF, 60yr div | passed=False |
| Insufficient FCF | AA, 2yr FCF, 60yr div | passed=False |
| Short dividend history | AA, 20yr FCF, 5yr div | passed=False |
| Multiple failures | BB, 1yr FCF, 5yr div | passed=False, 3 fail_reasons |
| All fields missing | None, None, None | INSUFFICIENT_DATA |
| Exact FCF boundary | 3yr FCF | passed=True |
| Exact div boundary | 10yr div | passed=True |

### Scoring Engine — Boundaries

| Sub-component | Threshold | Expected Score |
|---|---|---|
| payout_sustainability | ratio=0.399 | 16 |
| payout_sustainability | ratio=0.400 | 12 |
| payout_sustainability | ratio=0.900 | 0 |
| yield_vs_market | yield=4.01% | 14 |
| yield_vs_market | yield=1.00% | 2 |
| debt_safety | D/E=0.499 | 16 |
| debt_safety | D/E=2.000 | 0 |
| price_momentum | change=-15.1% | 12 |
| price_momentum | change=+15.0% | 0 |
| price_range_position | ratio=0.299 | 8 |
| price_range_position | ratio=0.700 | 1 |

### Scoring Engine — Grades

| Total Score | Expected Grade | Expected Recommendation |
|---|---|---|
| 95 | A+ | AGGRESSIVE_BUY |
| 85 | A | AGGRESSIVE_BUY |
| 84 | B+ | ACCUMULATE |
| 75 | B+ | ACCUMULATE |
| 70 | B | ACCUMULATE |
| 69 | C | WATCH |
| 60 | C | WATCH |
| 50 | D | WATCH |
| 49 | F | WATCH |

### NAV Erosion — Risk Tiers

| P(loss>5%) | Expected Risk | Expected Penalty |
|---|---|---|
| 0.10 | LOW | 0 |
| 0.29 | LOW | 0 |
| 0.30 | MODERATE | 10 |
| 0.49 | MODERATE | 10 |
| 0.50 | HIGH | 20 |
| 0.69 | HIGH | 20 |
| 0.70 | SEVERE | 30 |
| 0.95 | SEVERE | 30 |

---

## Edge Cases Covered

- All fields None → partial credit (not zero, not error)
- Agent 01 returns empty dict → degraded scoring, no crash
- Covered call ETF with no volatility data → penalty=0, risk=UNKNOWN
- Batch quality gate with 50 tickers → processes all, returns correct counts
- `data_completeness_pct` = 100.0 when all fields present
- `data_completeness_pct` drops proportionally per missing field
- `valid_until` always exactly 24h from `evaluated_at`
- Credit rating comparison is case-insensitive and whitespace-stripped

---

## Running Tests

```bash
cd income-platform/src/income-scoring-service
PYTHONPATH=. python -m pytest tests/ -v
PYTHONPATH=. python -m pytest tests/ --cov=app/scoring --cov-report=term-missing
```
