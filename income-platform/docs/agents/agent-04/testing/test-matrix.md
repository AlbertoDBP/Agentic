# Test Matrix — Agent 04 Asset Classification Service

**Total Tests:** 55  
**Pass Rate:** 55/55 (100%)  
**Runtime:** ~0.30s  
**Last Run:** 2026-02-27  
**File:** `tests/test_detector.py`

---

## Test Coverage by Asset Class

### COVERED_CALL_ETF (10 tests)

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

### PREFERRED_STOCK (6 tests)

| Test | Description | Expected |
|---|---|---|
| test_preferred_suffix_pa | BAC-PA suffix detection | PREFERRED_STOCK |
| test_preferred_suffix_pb | BAC-PB suffix detection | PREFERRED_STOCK |
| test_preferred_metadata | security_type=preferred_stock | PREFERRED_STOCK |
| test_preferred_characteristics | income_type=fixed_dividend | fixed_dividend |
| test_preferred_tax_treatment | tax_treatment=qualified | qualified |
| test_preferred_account | preferred_account=TAXABLE | TAXABLE |

### MORTGAGE_REIT (6 tests)

| Test | Description | Expected |
|---|---|---|
| test_agnc_ticker | AGNC classifies as MORTGAGE_REIT | MORTGAGE_REIT |
| test_nly_ticker | NLY classifies as MORTGAGE_REIT | MORTGAGE_REIT |
| test_mreit_hybrid | MORTGAGE_REIT is_hybrid=True | True |
| test_mreit_coverage_ratio | coverage_ratio_required=True | True |
| test_mreit_valuation | valuation_method=P/BV | P/BV |
| test_mreit_rate_sensitivity | rate_sensitivity=high | high |

### EQUITY_REIT (3 tests)

| Test | Description | Expected |
|---|---|---|
| test_equity_reit_sector | sector=Real Estate + is_reit=True | EQUITY_REIT |
| test_equity_reit_valuation | valuation_method=P/FFO | P/FFO |
| test_equity_reit_account | preferred_account=IRA | IRA |

### BDC (5 tests)

| Test | Description | Expected |
|---|---|---|
| test_arcc_ticker | ARCC classifies as BDC | BDC |
| test_main_ticker | MAIN classifies as BDC | BDC |
| test_bdc_metadata | security_type=bdc | BDC |
| test_bdc_coverage_ratio | coverage_ratio_required=True | True |
| test_bdc_valuation | valuation_method=P/NAV | P/NAV |

### BOND (5 tests)

| Test | Description | Expected |
|---|---|---|
| test_bond_ticker_list | Known bond ETF tickers | BOND |
| test_bond_maturity_feature | has_maturity_date=True + coupon | BOND |
| test_bond_income_type | income_type=interest | interest |
| test_bond_tax_treatment | tax_treatment=ordinary | ordinary |
| test_bond_account | preferred_account=IRA | IRA |

### DIVIDEND_STOCK (3 tests)

| Test | Description | Expected |
|---|---|---|
| test_dividend_stock_features | common_stock=True + pays_dividend | DIVIDEND_STOCK |
| test_dividend_stock_tax | tax_treatment=qualified | qualified |
| test_dividend_stock_account | preferred_account=TAXABLE | TAXABLE |

---

## Fallback & Edge Cases (13 tests)

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

---

## Seed Rule Completeness (4 tests)

| Test | Description | Expected |
|---|---|---|
| test_all_classes_have_rules | All 7 classes have at least 1 rule | True |
| test_required_rule_fields | id, asset_class, rule_type, rule_config, priority, confidence_weight | All present |
| test_valid_confidence_weights | All weights 0.0–1.0 | True |
| test_valid_rule_types | All types in [ticker_pattern, metadata, sector, feature] | True |

---

## Running Tests

```bash
cd src/asset-classification-service

PYTHONPATH=/path/to/income-platform/src:/path/to/income-platform/src/asset-classification-service \
python3 -m pytest tests/test_detector.py -v

# Quick pass/fail
python3 -m pytest tests/test_detector.py -q
```

---

## Integration Test Scenarios (Manual)

| Scenario | Command | Expected |
|---|---|---|
| Health check | `GET /health` | `{"status":"healthy","database":"connected"}` |
| JEPI classify | `POST /classify {"ticker":"JEPI"}` | `COVERED_CALL_ETF, confidence=0.95` |
| AGNC classify | `POST /classify {"ticker":"AGNC"}` | `MORTGAGE_REIT, is_hybrid=true` |
| ARCC classify | `POST /classify {"ticker":"ARCC"}` | `BDC, coverage_ratio_required=true` |
| Cache hit | Second call for same ticker | `classified_at` same timestamp |
| Batch classify | `POST /classify/batch {"tickers":["JEPI","AGNC","ARCC"]}` | 3 results |
