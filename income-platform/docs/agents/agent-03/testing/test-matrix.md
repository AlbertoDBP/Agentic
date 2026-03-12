# Test Matrix — Agent 03: Income Scoring Service

**Total Tests:** 438
**Status:** ✅ 438/438 passing
**Date:** 2026-03-12

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
| `test_chowder.py` | Chowder Number computation | 14 | Field presence, default None, float/str acceptance |
| `test_weight_profiles.py` | Weight Profile API | 27 | GET returns 200, POST creates profile, auth required, 404 for unknown class, response shape |
| `test_dynamic_weights.py` | Dynamic weight integration | 47 | IncomeScorer uses profile ceilings, default profile matches v1.0, different profiles produce different scores, weight_profile_version propagated |
| `test_signal_penalty.py` | SignalPenaltyEngine | 60 | Bearish thresholds (strong/moderate/weak), bullish cap=0, eligibility gates, score floor ≥0, newsletter client scenarios (disabled/200/404/timeout/error), signal config API, evaluate endpoint with penalty |
| `test_learning_loop.py` | ShadowPortfolioManager | 74 | Record entry, skip non-qualifying, populate outcomes, CORRECT/INCORRECT/NEUTRAL labels, error handling |
| `test_learning_loop.py` | QuarterlyWeightTuner | | Insufficient samples, no signal, compute adjustment, sum=100 invariant |
| `test_learning_loop.py` | Learning Loop API | | Shadow portfolio list, populate outcomes, review trigger, review history |
| `test_classification_accuracy.py` | ClassificationFeedbackTracker | 47 | Record AGENT04/MANUAL, mismatch detection (True/False/None), monthly rollup accuracy, rollup with no data |
| `test_classification_accuracy.py` | Classification Accuracy API | | Feedback list, runs list, rollup trigger, auth guard |
| **Total** | | **438** | |

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

### Weight Profiles (v2.0)

| Test | Input | Expected |
|---|---|---|
| GET /weights/ returns active | asset_class=DIVIDEND_STOCK | 200, active profile for DIVIDEND_STOCK |
| GET /weights/{asset_class} | asset_class=MORTGAGE_REIT | 200, active MORTGAGE_REIT profile (30/45/25) |
| Unknown asset class | asset_class=UNKNOWN_CLASS | 404 |
| POST creates new profile | weight_yield=25, weight_durability=45, weight_technical=30 | 201, new profile with version incremented |
| Weights don't sum to 100 | weight_yield=25, weight_durability=45, weight_technical=29 | 422 unprocessable_entity |
| Auth required | no auth header | 401 |

### Dynamic Weights (v2.0)

| Test | Input | Expected |
|---|---|---|
| Uses active profile | asset_class=DIVIDEND_STOCK, use active profile | score computed with active weights |
| Default profile matches v1.0 | use default profile if none specified | score matches v1.0 baseline |
| Different profiles produce different scores | two profiles with different weights | same ticker produces different scores |
| weight_profile_version propagated | POST /scores/evaluate | response.weight_profile_version == active profile version |

### Signal Penalty (v2.0)

| Test | Scenario | Expected |
|---|---|---|
| BEARISH_STRONG | consensus=-0.8 | penalty=-8.0 |
| BEARISH_MODERATE | consensus=-0.5 | penalty=-5.0 |
| BEARISH_WEAK | consensus=-0.2 | penalty=-2.0 |
| BULLISH_STRONG | consensus=+0.8 | penalty=0.0 (never inflates) |
| Bullish weak | consensus=+0.1 | penalty=0.0 (cap is 0) |
| Eligibility gate — min_n_analysts | n_analysts=2, min=3 | gate skipped, penalty=0 |
| Eligibility gate — min_decay_weight | decay_weight=0.3, min=0.4 | gate skipped, penalty=0 |
| Score floor | raw_score=3.0, penalty=5.0 | final_score=0.0 (never below 0) |
| Newsletter service disabled | NEWSLETTER_SERVICE_URL=null | penalty=0 (no call to Agent 02) |
| Newsletter returns 404 | GET /signal/{ticker} → 404 | penalty=0, no error raised |
| Newsletter timeout | GET /signal/{ticker} → timeout | penalty=0, no error raised |
| Newsletter error | GET /signal/{ticker} → 500 | penalty=0, no error raised |

### Learning Loop (v2.0)

| Test | Scenario | Expected |
|---|---|---|
| Record entry | POST /scores/evaluate recommendation=AGGRESSIVE_BUY | shadow entry recorded with entry_price, entry_date |
| Skip non-qualifying | POST with recommendation=WATCH | no shadow entry recorded |
| Populate outcomes — correct | entry_price=100, current_price=105 (+5%) | outcome_label=CORRECT |
| Populate outcomes — incorrect | entry_price=100, current_price=94 (-6%) | outcome_label=INCORRECT |
| Populate outcomes — neutral | entry_price=100, current_price=102 (+2%) | outcome_label=NEUTRAL |
| Populate outcomes — no entry price | entry_price=null | skipped with skip count |
| Weight review — insufficient samples | 5 outcomes (CORRECT + INCORRECT) | status=SKIPPED, skip_reason="insufficient_samples" |
| Weight review — no signal | all outcomes NEUTRAL | status=SKIPPED, skip_reason="no_signal" |
| Weight review — adjustment proposed | 10 CORRECT, 2 INCORRECT → strong durability signal | status=COMPLETE, delta_durability=+5 (max) |
| Weight review — sum=100 invariant | proposed adjustment | all_weights sum exactly 100 |
| Shadow portfolio list | filter by asset_class, outcome | returns matching entries |
| Review history | filter by asset_class | returns review runs |

### Classification Accuracy (v2.0)

| Test | Scenario | Expected |
|---|---|---|
| Record AGENT04 source | no asset_class override | source=AGENT04, is_mismatch=None |
| Record MANUAL_OVERRIDE source | caller provided asset_class | source=MANUAL_OVERRIDE |
| Mismatch detection — disabled | CLASSIFICATION_VERIFY_OVERRIDES=False | is_mismatch=None (no Agent 04 call) |
| Mismatch detection — match | CLASSIFICATION_VERIFY_OVERRIDES=True, Agent 04 agrees | is_mismatch=False |
| Mismatch detection — mismatch | CLASSIFICATION_VERIFY_OVERRIDES=True, Agent 04 disagrees | is_mismatch=True |
| Monthly rollup — no data | period_month with no feedback | rollup_created with total_calls=0 |
| Monthly rollup — mixed sources | 10 AGENT04, 5 MANUAL, 1 mismatch | accuracy_rate = 9/15, override_rate = 1/3, mismatch_rate = 1/15 |
| Feedback list | filter by ticker, source, limit | returns matching feedback entries |
| Runs list | filter by asset_class, period_month | returns matching rollup runs |
| Rollup trigger — invalid format | period_month="invalid" | 422 unprocessable_entity |

---

## Edge Cases Covered

- All fields None → partial credit (not zero, not error)
- Agent 01 returns empty dict → degraded scoring, no crash
- Covered call ETF with no volatility data → penalty=0, risk=UNKNOWN
- Batch quality gate with 50 tickers → processes all, returns correct counts
- data_completeness_pct = 100.0 when all fields present
- data_completeness_pct drops proportionally per missing field
- valid_until always exactly 24h from evaluated_at
- Credit rating comparison is case-insensitive and whitespace-stripped
- Signal penalty never reduces score below 0.0
- Weight profile sum must equal 100 (enforcement at API boundary)
- Shadow portfolio entries without entry_price are gracefully skipped
- Classification feedback with is_mismatch=None when verify_overrides=False

---

## Running Tests

```bash
cd income-platform/src/income-scoring-service
PYTHONPATH=. python -m pytest tests/ -v
PYTHONPATH=. python -m pytest tests/ --cov=app/scoring --cov-report=term-missing
PYTHONPATH=. python -m pytest tests/test_signal_penalty.py -v  # Run one v2.0 test suite
```
