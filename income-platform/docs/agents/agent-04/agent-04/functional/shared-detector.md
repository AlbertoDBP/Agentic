# Functional Spec — Shared Asset Class Detector

**Component:** `src/shared/asset_class_detector/`  
**Importable by:** Agent 03, Agent 04, and all future agents  
**Last Updated:** 2026-02-27  
**Status:** ✅ Production

---

## Purpose & Scope

A shared Python utility that classifies income securities into one of 7 asset classes using rule-based matching. Designed to be imported by any agent without requiring an HTTP call to Agent 04. Provides a fallback path when Agent 04 is unavailable.

---

## Asset Class Taxonomy

```
Income Asset
├── Equity Income
│   ├── DIVIDEND_STOCK    — qualified dividend, P/E + yield, TAXABLE preferred
│   ├── EQUITY_REIT       — REIT distribution, P/FFO, IRA preferred
│   └── MORTGAGE_REIT     — hybrid REIT+CEF, P/BV, coverage_ratio_required
├── Fixed Income
│   └── BOND              — interest, yield_to_maturity, IRA preferred
├── Alternative Income
│   └── BDC               — ordinary dividend, P/NAV, coverage_ratio_required
└── Fund Structures
    ├── COVERED_CALL_ETF  — option premium, yield + nav_trend, nav_erosion_tracking
    └── PREFERRED_STOCK   — fixed dividend, yield_to_call, TAXABLE preferred
```

---

## Rule Types

### 1. ticker_pattern
Matches against known ticker lists, suffixes, and prefixes.
- Highest specificity — evaluated at priority 5
- Examples: `JEPI` → COVERED_CALL_ETF, `BAC-PA` suffix → PREFERRED_STOCK

### 2. metadata
Matches against string fields: `security_type`, `fund_category`, `strategy`, `sub_sector`.
- Priority 10
- Example: `fund_category=Mortgage REIT` → MORTGAGE_REIT

### 3. sector
Matches against sector classification.
- Priority 10–20
- Example: `sector=Real Estate` → EQUITY_REIT (lower confidence, needs other signals)

### 4. feature
Matches against boolean flags and numeric thresholds.
- Priority 15–50, partial credit scoring
- Example: `has_maturity_date=True AND coupon_rate_exists=True` → BOND

---

## Confidence Scoring

- Each rule match returns a `confidence_weight` (0–1)
- Multiple matches for same class: `max(matches) + 0.05 * (len-1)`, capped at 0.99
- Result ranked by `total_confidence` descending
- Top result is returned as classification
- `needs_enrichment=True` when `confidence < 0.70`

---

## Rule Priority (lower = more specific = evaluated first)

| Priority | Rule Type | Typical Weight |
|---|---|---|
| 5 | ticker_pattern (known list) | 0.90–0.95 |
| 5 | ticker_pattern (suffix) | 0.90 |
| 10 | metadata | 0.85–0.90 |
| 10–20 | sector | 0.55–0.85 |
| 15–20 | feature | 0.55–0.85 |
| 50 | DIVIDEND_STOCK fallback | 0.60 |

---

## Public Interface

```python
from shared.asset_class_detector import AssetClassDetector

detector = AssetClassDetector()                   # seed rules
detector = AssetClassDetector(rules=db_rules)     # DB rules

# Returns DetectionResult or UNKNOWN if no match
result = detector.detect("JEPI", security_data={})

# Never returns UNKNOWN — defaults to DIVIDEND_STOCK
result = detector.detect_with_fallback("ZZZZZ")
```

### DetectionResult fields
```python
ticker: str
asset_class: AssetClass          # enum
parent_class: str                # EQUITY | FIXED_INCOME | ALTERNATIVE | FUND
confidence: float                # 0.0–0.99
is_hybrid: bool                  # True for MORTGAGE_REIT
characteristics: dict            # income_type, tax_treatment, valuation_method, etc.
matched_rules: List[dict]        # rule_type, matched_on, confidence per match
source: str                      # "rule_engine_v1" | "fallback" | "override"
needs_enrichment: bool           # True if confidence < 0.70
```

---

## Seed Rules Coverage

| Asset Class | Rule Count | Primary Detection Method |
|---|---|---|
| COVERED_CALL_ETF | 3 | Ticker list + metadata strategy + feature flags |
| PREFERRED_STOCK | 3 | Ticker suffix (-PA/-PB) + metadata + feature flags |
| MORTGAGE_REIT | 3 | Ticker list + metadata + feature (leverage ratio) |
| EQUITY_REIT | 3 | Sector + metadata + feature (payout ratio) |
| BDC | 3 | Ticker list + metadata + sector |
| BOND | 3 | Ticker list + metadata + feature (maturity date) |
| DIVIDEND_STOCK | 2 | Feature (yield + common stock) + metadata |

---

## Future Evolution (v2 — Roadmap)

- ML classifier trained on shadow portfolio outcomes runs in parallel
- Rule-based v1 and ML v2 run side-by-side during validation period
- Cutover when ML confidence consistently exceeds rule-based
- New hybrid patterns detected in production promoted to rule engine via DB insert — no redeploy
- Valuation methods per class remain fixed (accounting identities, not learned)
