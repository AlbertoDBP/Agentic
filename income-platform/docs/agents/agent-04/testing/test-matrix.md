# Test Matrix — Agent 04 Asset Classification Service

**Total Tests:** 201
**Pass Rate:** 201/201 (100%)
**Runtime:** ~0.25s
**Last Run:** 2026-03-12

---

## Test Files

| File | Classes | Tests |
|---|---|---|
| `tests/test_detector.py` | 7 | 55 |
| `tests/test_tax_profile.py` | 4 | 48 |
| `tests/test_benchmarks.py` | 3 | 28 |
| `tests/test_classify_api.py` | 3 | 22 |
| `tests/test_rules_api.py` | 4 | 27 |
| `tests/test_engine.py` | 6 | 21 |
| **Total** | **27** | **201** |

---

## test_detector.py (55 tests)

### TestCoveredCallETF (10 tests)

| Test | Description | Expected |
|---|---|---|
| test_jepi_ticker_pattern | JEPI classifies via known ticker list | COVERED_CALL_ETF |
| test_covered_call_metadata | fund_category=Covered Call ETF | COVERED_CALL_ETF |
| test_covered_call_features | has_options_strategy + distributes_option_premium | COVERED_CALL_ETF |
| test_covered_call_characteristics | income_type=option_premium | option_premium |
| test_covered_call_tax_treatment | tax_treatment=ordinary | ordinary |
| test_covered_call_rate_sensitivity | rate_sensitivity=low | low |
| test_covered_call_valuation | valuation_method contains nav_trend | yield + nav_trend |
| test_covered_call_preferred_account | preferred_account=IRA | IRA |
| test_covered_call_nav_erosion | nav_erosion_tracking=True | True |
| test_covered_call_confidence | confidence >= 0.90 | >= 0.90 |

### TestPreferredStock (6 tests)

| Test | Description | Expected |
|---|---|---|
| test_preferred_suffix_pa | BAC-PA suffix detection | PREFERRED_STOCK |
| test_preferred_suffix_pb | BAC-PB suffix detection | PREFERRED_STOCK |
| test_preferred_metadata | security_type=preferred_stock | PREFERRED_STOCK |
| test_preferred_characteristics | income_type=fixed_dividend | fixed_dividend |
| test_preferred_tax_treatment | tax_treatment=qualified | qualified |
| test_preferred_account | preferred_account=TAXABLE | TAXABLE |

### TestMortgageREIT (6 tests)

| Test | Description | Expected |
|---|---|---|
| test_agnc_ticker | AGNC classifies as MORTGAGE_REIT | MORTGAGE_REIT |
| test_nly_ticker | NLY classifies as MORTGAGE_REIT | MORTGAGE_REIT |
| test_mreit_hybrid | MORTGAGE_REIT is_hybrid=True | True |
| test_mreit_coverage_ratio | coverage_ratio_required=True | True |
| test_mreit_valuation | valuation_method=P/BV | P/BV |
| test_mreit_rate_sensitivity | rate_sensitivity=high | high |

### TestEquityREIT (3 tests)

| Test | Description | Expected |
|---|---|---|
| test_equity_reit_sector | sector=Real Estate + is_reit=True | EQUITY_REIT |
| test_equity_reit_valuation | valuation_method=P/FFO | P/FFO |
| test_equity_reit_account | preferred_account=IRA | IRA |

### TestBDC (5 tests)

| Test | Description | Expected |
|---|---|---|
| test_arcc_ticker | ARCC classifies as BDC | BDC |
| test_main_ticker | MAIN classifies as BDC | BDC |
| test_bdc_metadata | security_type=bdc | BDC |
| test_bdc_coverage_ratio | coverage_ratio_required=True | True |
| test_bdc_valuation | valuation_method=P/NAV | P/NAV |

### TestBond (5 tests)

| Test | Description | Expected |
|---|---|---|
| test_bond_ticker_list | Known bond ETF tickers | BOND |
| test_bond_maturity_feature | has_maturity_date=True + coupon | BOND |
| test_bond_income_type | income_type=interest | interest |
| test_bond_tax_treatment | tax_treatment=ordinary | ordinary |
| test_bond_account | preferred_account=IRA | IRA |

### TestDividendStock (3 tests)

| Test | Description | Expected |
|---|---|---|
| test_dividend_stock_features | common_stock=True + pays_dividend | DIVIDEND_STOCK |
| test_dividend_stock_tax | tax_treatment=qualified | qualified |
| test_dividend_stock_account | preferred_account=TAXABLE | TAXABLE |

### TestFallbackAndEdgeCases (13 tests)

| Test | Description | Expected |
|---|---|---|
| test_unknown_ticker | Completely unknown ticker | UNKNOWN or DIVIDEND_STOCK |
| test_detect_with_fallback | detect_with_fallback never returns UNKNOWN | DIVIDEND_STOCK |
| test_case_insensitive | jepi == JEPI == Jepi | COVERED_CALL_ETF |
| test_whitespace_ticker | " JEPI " stripped correctly | COVERED_CALL_ETF |
| test_needs_enrichment_false | High confidence → needs_enrichment=False | False |
| test_needs_enrichment_true | Low confidence → needs_enrichment=True | True |
| test_confidence_capped | Max confidence never exceeds 0.99 | <= 0.99 |
| test_multiple_matches_boost | Multiple rule matches boost confidence | > single match |
| test_hybrid_flag | MORTGAGE_REIT is_hybrid=True | True |
| test_non_hybrid_flag | DIVIDEND_STOCK is_hybrid=False | False |
| test_parent_class_fund | COVERED_CALL_ETF parent=FUND | FUND |
| test_parent_class_equity | DIVIDEND_STOCK parent=EQUITY | EQUITY |
| test_parent_class_alternative | BDC parent=ALTERNATIVE | ALTERNATIVE |

### TestSeedRules (4 tests)

| Test | Description | Expected |
|---|---|---|
| test_all_classes_have_rules | All 7 classes have at least 1 rule | True |
| test_required_rule_fields | id, asset_class, rule_type, rule_config, priority, confidence_weight | All present |
| test_valid_confidence_weights | All weights 0.0–1.0 | True |
| test_valid_rule_types | All types in [ticker_pattern, metadata, sector, feature] | True |

---

## test_tax_profile.py (48 tests)

### TestTaxProfileStructure (35 tests)
Verifies `build_tax_profile()` returns all required fields for each asset class with correct types, values, and non-empty notes.

### TestTaxDrag (6 tests)
Verifies `estimated_tax_drag_pct` correct for qualified_dividend (15%), option_premium (37%), interest (37%), reit_distribution (37%), fixed_dividend (15%), roc (0%).

### TestTaxNotes (4 tests)
Verifies tax notes are non-empty strings for COVERED_CALL_ETF, MORTGAGE_REIT, BDC, BOND.

### TestTaxDragTable (3 tests)
Verifies TAX_DRAG_BY_INCOME_TYPE table structure: all 8 entries, values 0.0–1.0, unknown key present.

---

## test_benchmarks.py (28 tests)

### TestGetBenchmark (10 tests)
Verifies `get_benchmark()` returns non-None for all 7 asset classes; returns None for unknown class.

### TestBenchmarkToDict (10 tests)
Verifies `benchmark_to_dict()` includes all 7 required keys for each class.

### TestBenchmarkValues (8 tests)
Spot-checks benchmark data: yield thresholds, peer group membership, expense ratios.

### TestBenchmarksDict (2 tests)
Verifies BENCHMARKS dict covers all 7 MVP asset classes.

---

## test_classify_api.py (22 tests)

### TestClassifySingle (10 tests)
Tests `POST /classify` — 401 without auth, 422 on empty ticker, successful classification shape (all required fields present), `is_override=False` for rule-classified tickers.

### TestClassifyBatch (8 tests)
Tests `POST /classify/batch` — 401 without auth, 422 on batch > 100, response shape (total/classified/errors/results/error_details), partial failure handling.

### TestGetClassification (4 tests)
Tests `GET /classify/{ticker}` — 401 without auth, successful response shape.

---

## test_rules_api.py (27 tests)

### TestListRules (5 tests)
Tests `GET /rules` — 401 without auth, returns total + rules list, rules include all required fields.

### TestCreateRule (9 tests)
Tests `POST /rules` — 401 without auth, 422 on invalid rule_type, 422 on confidence_weight out of range, successful creation returns id + message, all 4 valid rule_types accepted.

### TestSetOverride (7 tests)
Tests `PUT /overrides/{ticker}` — 401 without auth, creates new override, updates existing override, stores asset_class uppercased, optional reason/created_by fields.

### TestRemoveOverride (6 tests)
Tests `DELETE /overrides/{ticker}` — 401 without auth, 404 when not found, successful removal returns message.

---

## test_engine.py (21 tests)

### TestGetDetector (2 tests)
Verifies detector is lazily instantiated and reused across calls.

### TestGetCached (3 tests)
Verifies cache hit returns existing record, cache miss returns None, expired records not returned.

### TestGetOverride (2 tests)
Verifies active override returned, expired/future override not returned.

### TestLoadDbRules (5 tests)
Verifies DB rules loaded and passed to detector; falls back to seed rules on DB error.

### TestClassifyPipeline (3 tests)
End-to-end engine test: override path (confidence=1.0), rule path (persist + return), enrichment path (needs_enrichment=True triggers data_client).

### TestSerialise (4 tests)
Verifies `_serialise()` returns all expected keys with correct types; handles None valid_until.

---

## Running Tests

```bash
cd src/asset-classification-service
python -m pytest tests/ -q
```
