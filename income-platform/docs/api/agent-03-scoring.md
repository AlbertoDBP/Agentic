# Agent 03: Income Scoring Service

Scores income-generating assets (dividend stocks, covered call ETFs, bonds) using quality gates and weighted scoring. Capital preservation is the first priority.

**Port:** 8003
**Base URL:** `http://<host>:8003`

## Health Check

### GET /health

Service health check — verifies database connectivity.

**Auth:** Not required
**Method:** GET

**Response 200:**
```json
{
  "service": "income-scoring-service",
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "checks": {
    "database": {
      "status": "healthy",
      "schema_exists": true
    }
  }
}
```

---

## Quality Gate Evaluation

### POST /quality-gate/evaluate

Evaluate a single ticker against quality gate criteria for its asset class.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "ticker": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "credit_rating": "AAA",
  "consecutive_positive_fcf_years": 15,
  "dividend_history_years": 60
}
```

**Asset class-specific fields:**

**DIVIDEND_STOCK:**
- `credit_rating` (optional): Credit rating (e.g., A-, BBB+, AAA)
- `consecutive_positive_fcf_years` (optional): Years of positive FCF
- `dividend_history_years` (optional): Years of dividend history

**COVERED_CALL_ETF:**
- `aum_millions` (optional): Assets under management in millions
- `track_record_years` (optional): Years of fund operation
- `distribution_history_months` (optional): Months of consistent distributions

**BOND:**
- `credit_rating` (optional): Bond issuer credit rating
- `duration_years` (optional): Bond duration in years
- `issuer_type` (optional): Type of issuer
- `yield_to_maturity` (optional): YTM percentage

**Response 200:**
```json
{
  "ticker": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "passed": true,
  "status": "PASS",
  "fail_reasons": [],
  "warnings": [],
  "checks": {
    "credit_rating": {
      "passed": true,
      "value": "AAA",
      "required": "BBB- or better"
    },
    "fcf": {
      "passed": true,
      "value": 15,
      "required": "≥5 consecutive positive years"
    },
    "dividend_history": {
      "passed": true,
      "value": 60,
      "required": "≥10 years"
    }
  },
  "data_quality_score": 0.95,
  "evaluated_at": "2026-03-12T09:59:35Z",
  "valid_until": "2026-03-13T09:59:35Z"
}
```

Gate results are cached for 24 hours. Subsequent calls return cached results unless the asset fails.

**Errors:**
- 400: Unsupported asset class
- 422: Invalid field values

---

### POST /quality-gate/batch

Evaluate up to 50 tickers in a single batch request.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "tickers": [
    {
      "ticker": "JNJ",
      "asset_class": "DIVIDEND_STOCK",
      "credit_rating": "AAA",
      "consecutive_positive_fcf_years": 15,
      "dividend_history_years": 60
    }
  ]
}
```

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| max_items | integer | 50 | Maximum batch size |

**Response 200:**
```json
{
  "total": 1,
  "passed": 1,
  "failed": 0,
  "insufficient_data": 0,
  "results": [
    {
      "ticker": "JNJ",
      "asset_class": "DIVIDEND_STOCK",
      "passed": true,
      "status": "PASS",
      "fail_reasons": [],
      "warnings": [],
      "checks": {},
      "data_quality_score": 0.95,
      "evaluated_at": "2026-03-12T09:59:35Z",
      "valid_until": "2026-03-13T09:59:35Z"
    }
  ],
  "evaluated_at": "2026-03-12T09:59:35Z"
}
```

**Errors:**
- 400: Batch size exceeds maximum (50)

---

## Income Scoring

### POST /scores/evaluate

Score a ticker using quality gate + weighted scoring engine.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "ticker": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "gate_data": {
    "credit_rating": "AAA",
    "consecutive_positive_fcf_years": 15,
    "dividend_history_years": 60
  }
}
```

**Gate data is optional** if a passing quality gate result exists in the DB from the last 24 hours. If no DB record and no `gate_data` provided, returns 422.

**Response 200:**
```json
{
  "ticker": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "valuation_yield_score": 8.5,
  "financial_durability_score": 9.2,
  "technical_entry_score": 7.8,
  "total_score_raw": 25.5,
  "nav_erosion_penalty": 0.0,
  "total_score": 25.5,
  "grade": "A",
  "recommendation": "STRONG_BUY",
  "factor_details": {
    "yield_pct": 2.85,
    "yield_spread": 0.95,
    "dividend_growth_cagr": 0.085,
    "payout_ratio": 0.62,
    "fcf_margin": 0.28,
    "roe": 0.45,
    "debt_to_equity": 0.62,
    "volatility": 0.18,
    "price_momentum": 0.05,
    "chowder_number": 8.1,
    "chowder_signal": "ATTRACTIVE"
  },
  "nav_erosion_details": null,
  "chowder_number": 8.1,
  "chowder_signal": "ATTRACTIVE",
  "data_quality_score": 0.92,
  "data_completeness_pct": 88.0,
  "scored_at": "2026-03-12T09:59:35Z"
}
```

| Field | Description |
|-------|-------------|
| total_score_raw | Score before NAV erosion penalty |
| nav_erosion_penalty | Penalty applied for covered call ETFs (0 for other asset classes) |
| total_score | Final score (raw - penalty) |
| grade | Letter grade: A, B, C, D, F |
| recommendation | STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL |
| chowder_number | For dividend stocks: yield + 5yr div growth rate + payout ratio |
| chowder_signal | ATTRACTIVE (>8), FAIR (5-8), POOR (<5), or null |
| data_quality_score | Percentage of required data points available |

**NAV Erosion (Covered Call ETFs Only):**
- Analyzes historical NAV changes
- Returns `prob_erosion_gt_5pct` (probability NAV declines >5% annually)
- Returns `risk_classification` (LOW, MODERATE, HIGH)
- Applies penalty if risk is HIGH

**Errors:**
- 422: No passing quality gate + no gate_data provided, or gate fails
- 500: Market data fetch failure or scoring engine error

---

### GET /scores/

List the last 20 income scores.

**Auth:** Required
**Method:** GET

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| recommendation | string | null | Filter by recommendation (e.g., STRONG_BUY) |

**Response 200:**
```json
[
  {
    "ticker": "JNJ",
    "asset_class": "DIVIDEND_STOCK",
    "total_score": 25.5,
    "grade": "A",
    "recommendation": "STRONG_BUY",
    "scored_at": "2026-03-12T09:59:35Z"
  }
]
```

---

### GET /scores/{ticker}

Retrieve the latest income score for a ticker.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| ticker | string | Stock symbol |

**Response 200:**
```json
{
  "ticker": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "valuation_yield_score": 8.5,
  "financial_durability_score": 9.2,
  "technical_entry_score": 7.8,
  "total_score_raw": 25.5,
  "nav_erosion_penalty": 0.0,
  "total_score": 25.5,
  "grade": "A",
  "recommendation": "STRONG_BUY",
  "factor_details": {},
  "nav_erosion_details": null,
  "chowder_number": 8.1,
  "chowder_signal": "ATTRACTIVE",
  "data_quality_score": 0.92,
  "data_completeness_pct": 88.0,
  "scored_at": "2026-03-12T09:59:35Z"
}
```

**Errors:**
- 404: No score found for ticker; run POST /scores/evaluate first

---

## Scoring Methodology

### Valuation & Yield Score (0-10)
- Current yield vs. historical average
- Yield spread relative to Treasury
- Dividend growth CAGR
- Payout ratio sustainability

### Financial Durability Score (0-10)
- Free cash flow margin
- Return on equity (ROE)
- Debt-to-equity ratio
- Interest coverage ratio

### Technical Entry Score (0-10)
- Price momentum (3-month)
- Volatility (1-year standard deviation)
- Relative strength index (RSI)
- Moving average alignment

### Total Score
- Weighted combination of three factors
- Scaled to 0-30 range
- Grade: A (27-30), B (23-27), C (19-23), D (15-19), F (<15)

### Chowder Number (Dividend Stocks Only)
Formula: Current Yield (%) + 5-Year Dividend Growth CAGR (%) + Payout Ratio (%)

- **ATTRACTIVE:** ≥8.0
- **FAIR:** 5.0-8.0
- **POOR:** <5.0

### NAV Erosion Penalty (Covered Call ETFs)
- Examines 1, 3, 5-year price changes
- Calculates probability of >5% annual NAV erosion
- Applies 0-3 point penalty if HIGH risk
- Helps prevent overpaying for options income
