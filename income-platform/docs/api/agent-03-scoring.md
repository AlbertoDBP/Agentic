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

---

## Weight Profiles (v2.0)

### GET /weights/

List all weight profiles.

**Auth:** Required
**Method:** GET

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| asset_class | string | null | Filter by asset class (e.g., DIVIDEND_STOCK) |
| active_only | boolean | false | Return only active profiles |

**Response 200:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "asset_class": "DIVIDEND_STOCK",
    "version": 1,
    "is_active": true,
    "weight_yield": 25,
    "weight_durability": 45,
    "weight_technical": 30,
    "yield_sub_weights": {
      "yield_vs_market": 6,
      "dividend_growth_cagr": 9,
      "payout_sustainability": 10
    },
    "durability_sub_weights": {
      "fcf_margin": 15,
      "roe": 15,
      "debt_safety": 15
    },
    "technical_sub_weights": {
      "volatility": 10,
      "price_momentum": 10,
      "price_range_position": 10
    },
    "source": "seed_profile",
    "created_at": "2026-03-12T10:00:00Z"
  }
]
```

**Errors:**
- 401: Not authenticated
- 404: No profiles found (empty asset class with filter)

---

### GET /weights/{asset_class}

Returns the active weight profile for a given asset class.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| asset_class | string | Asset class (e.g., DIVIDEND_STOCK, MORTGAGE_REIT, BDC, COVERED_CALL_ETF, EQUITY_REIT, BOND, PREFERRED_STOCK) |

**Response 200:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_class": "MORTGAGE_REIT",
  "version": 1,
  "is_active": true,
  "weight_yield": 30,
  "weight_durability": 45,
  "weight_technical": 25,
  "yield_sub_weights": {},
  "durability_sub_weights": {},
  "technical_sub_weights": {},
  "source": "seed_profile",
  "created_at": "2026-03-12T10:00:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 404: No active profile found for asset class

---

### POST /weights/{asset_class}

Create a new weight profile for an asset class. This supersedes the currently active profile.

**Auth:** Required
**Method:** POST

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| asset_class | string | Asset class |

**Request body:**
```json
{
  "weight_yield": 25,
  "weight_durability": 45,
  "weight_technical": 30,
  "yield_sub_weights": {
    "yield_vs_market": 6,
    "dividend_growth_cagr": 9,
    "payout_sustainability": 10
  },
  "durability_sub_weights": {
    "fcf_margin": 15,
    "roe": 15,
    "debt_safety": 15
  },
  "technical_sub_weights": {
    "volatility": 10,
    "price_momentum": 10,
    "price_range_position": 10
  },
  "source": "quarterly_review",
  "change_reason": "Q1 2026 learning loop adjustment",
  "created_by": "agent-03-tuner"
}
```

**Field validation:**
- weight_yield + weight_durability + weight_technical must equal 100
- Each sub_weights group must sum to the corresponding main weight
- All values must be non-negative

**Response 201:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "asset_class": "DIVIDEND_STOCK",
  "version": 2,
  "is_active": true,
  "weight_yield": 25,
  "weight_durability": 45,
  "weight_technical": 30,
  "yield_sub_weights": {},
  "durability_sub_weights": {},
  "technical_sub_weights": {},
  "source": "quarterly_review",
  "created_at": "2026-03-12T11:00:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 404: Asset class not supported
- 422: Weights do not sum to 100 or sub-weights invalid

---

## Signal Penalty Configuration (v2.0)

### GET /signal-config/

Returns the active signal penalty configuration. This defines how Agent 02 newsletter signals influence income scores.

**Auth:** Required
**Method:** GET

**Response 200:**
```json
{
  "id": "650e8400-e29b-41d4-a716-446655440000",
  "version": 1,
  "is_active": true,
  "bearish_strong_penalty": 8.0,
  "bearish_moderate_penalty": 5.0,
  "bearish_weak_penalty": 2.0,
  "bullish_strong_bonus_cap": 0.0,
  "min_n_analysts": 3,
  "min_decay_weight": 0.5,
  "consensus_bearish_threshold": -0.20,
  "consensus_bullish_threshold": 0.20,
  "created_at": "2026-03-12T10:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| bearish_strong_penalty | float | Points deducted for strong bearish signal (default 8.0) |
| bearish_moderate_penalty | float | Points deducted for moderate bearish signal (default 5.0) |
| bearish_weak_penalty | float | Points deducted for weak bearish signal (default 2.0) |
| bullish_strong_bonus_cap | float | Max points added for bullish signal (always 0.0 in v2.0) |
| min_n_analysts | integer | Minimum number of analysts required to apply penalty |
| min_decay_weight | float | Minimum signal decay weight (recency) required |
| consensus_bearish_threshold | float | Consensus score threshold for bearish classification (default -0.20) |
| consensus_bullish_threshold | float | Consensus score threshold for bullish classification (default 0.20) |

**Architecture note:** `bullish_strong_bonus_cap` is always 0.0 in v2.0. This is a deliberate capital preservation constraint: signals can only reduce scores, never inflate them. Even strong bullish analyst consensus will not increase income scores — only reduce them when bearish.

Signal penalty is applied automatically in `POST /scores/evaluate`. The `signal_penalty` field in ScoreResponse shows how many points were deducted, and `signal_penalty_details` contains the full Agent 02 signal context.

**Errors:**
- 401: Not authenticated
- 404: No active configuration found (should not occur in production)

---

## Learning Loop (v2.0)

### GET /learning-loop/shadow-portfolio/

List recent shadow portfolio entries. AGGRESSIVE_BUY and ACCUMULATE recommendations are tracked forward for 90 days to measure actual income outcomes.

**Auth:** Required
**Method:** GET

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| asset_class | string | null | Filter by asset class |
| outcome | string | null | Filter by outcome (PENDING, CORRECT, INCORRECT, NEUTRAL) |
| limit | integer | 50 | Max results (1-500) |

**Response 200:**
```json
[
  {
    "id": "750e8400-e29b-41d4-a716-446655440000",
    "ticker": "JNJ",
    "asset_class": "DIVIDEND_STOCK",
    "entry_score": 85.5,
    "entry_grade": "A",
    "entry_recommendation": "AGGRESSIVE_BUY",
    "entry_price": 150.25,
    "entry_date": "2025-12-12T10:00:00Z",
    "hold_period_days": 90,
    "exit_price": 157.80,
    "exit_date": "2026-03-12T10:00:00Z",
    "actual_return_pct": 5.0,
    "outcome_label": "CORRECT",
    "outcome_populated_at": "2026-03-12T11:00:00Z"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| entry_score | float | Income score at entry (0-100) |
| entry_grade | string | Grade at entry (A+, A, B+, B, C, D, F) |
| entry_recommendation | string | Recommendation at entry (AGGRESSIVE_BUY, ACCUMULATE) |
| actual_return_pct | float | Actual return percentage after hold period |
| outcome_label | string | CORRECT (return >= +5%), INCORRECT (return <= -5%), NEUTRAL, or PENDING |

**Errors:**
- 401: Not authenticated

---

### POST /learning-loop/populate-outcomes

Populate outcome labels for shadow portfolio entries past their 90-day hold period.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "exit_prices": {
    "JNJ": 157.80,
    "PEP": 82.50,
    "KO": 61.25
  },
  "triggered_by": "quarterly_review"
}
```

**Outcome rules:**
- CORRECT: actual_return >= +5%
- INCORRECT: actual_return <= -5%
- NEUTRAL: -5% < actual_return < +5%

**Response 200:**
```json
{
  "updated": 3,
  "skipped_no_price": 0,
  "skipped_no_entry_price": 1,
  "total_pending": 15
}
```

**Errors:**
- 401: Not authenticated
- 422: Invalid exit_prices structure

---

### POST /learning-loop/review/{asset_class}

Trigger a quarterly weight review for one asset class. Analyzes CORRECT vs INCORRECT shadow portfolio outcomes to propose weight adjustments.

**Auth:** Required
**Method:** POST

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| asset_class | string | One of: EQUITY_REIT, MORTGAGE_REIT, BDC, COVERED_CALL_ETF, DIVIDEND_STOCK, BOND, PREFERRED_STOCK |

**Request body:**
```json
{
  "triggered_by": "quarterly_review_job",
  "lookback_days": null
}
```

**Response 201:**
```json
{
  "id": "850e8400-e29b-41d4-a716-446655440000",
  "asset_class": "DIVIDEND_STOCK",
  "status": "COMPLETE",
  "outcomes_analyzed": 12,
  "correct_count": 10,
  "incorrect_count": 2,
  "weight_before": {
    "weight_yield": 25,
    "weight_durability": 45,
    "weight_technical": 30
  },
  "weight_after": {
    "weight_yield": 28,
    "weight_durability": 42,
    "weight_technical": 30
  },
  "delta_yield": 3,
  "delta_durability": -3,
  "delta_technical": 0,
  "skip_reason": null,
  "created_at": "2026-03-12T12:00:00Z"
}
```

**Review status values:**
- COMPLETE: Review ran, proposal generated
- SKIPPED: Insufficient data or weak signal
- FAILED: Database or analysis error

**Skip reasons (when status=SKIPPED):**
- "insufficient_samples": Fewer than 10 usable outcomes (CORRECT + INCORRECT)
- "no_signal": Outcomes too neutral to warrant weight change
- Other descriptive reason

**Weight adjustment constraints:**
- Each pillar can change by ±5 percentage points max per quarter
- Sum of weights always equals 100
- Each pillar respects floor (10) and ceiling (90) constraints

**Errors:**
- 401: Not authenticated
- 404: Asset class not found
- 422: Invalid asset_class
- 500: Review analysis failed

---

### GET /learning-loop/reviews

List weight review run history.

**Auth:** Required
**Method:** GET

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| asset_class | string | null | Filter by asset class |
| limit | integer | 20 | Max results (1-200) |

**Response 200:**
```json
[
  {
    "id": "850e8400-e29b-41d4-a716-446655440000",
    "asset_class": "DIVIDEND_STOCK",
    "status": "COMPLETE",
    "outcomes_analyzed": 12,
    "correct_count": 10,
    "incorrect_count": 2,
    "weight_before": {},
    "weight_after": {},
    "delta_yield": 3,
    "delta_durability": -3,
    "delta_technical": 0,
    "skip_reason": null,
    "created_at": "2026-03-12T12:00:00Z"
  }
]
```

**Errors:**
- 401: Not authenticated

---

## Classification Accuracy (v2.0)

### GET /classification-accuracy/feedback

List recent classification feedback entries. Every POST /scores/evaluate call records how the asset_class was determined.

**Auth:** Required
**Method:** GET

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| ticker | string | null | Filter by ticker |
| source | string | null | Filter by source (AGENT04, MANUAL_OVERRIDE) |
| limit | integer | 50 | Max results (1-500) |

**Response 200:**
```json
[
  {
    "id": "950e8400-e29b-41d4-a716-446655440000",
    "ticker": "JNJ",
    "asset_class_used": "DIVIDEND_STOCK",
    "source": "AGENT04",
    "agent04_class": "DIVIDEND_STOCK",
    "agent04_confidence": 0.95,
    "is_mismatch": false,
    "captured_at": "2026-03-12T10:00:00Z",
    "income_score_id": "550e8400-e29b-41d4-a716-446655440000"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| source | string | AGENT04 (auto-classified) or MANUAL_OVERRIDE (caller provided) |
| agent04_class | string | Asset class determined by Agent 04 |
| agent04_confidence | float | Confidence score from Agent 04 (0.0-1.0) |
| is_mismatch | boolean or null | True if Agent 04 disagrees with asset_class_used; null if CLASSIFICATION_VERIFY_OVERRIDES=False |

**Errors:**
- 401: Not authenticated

---

### GET /classification-accuracy/runs

List monthly accuracy rollup runs.

**Auth:** Required
**Method:** GET

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| period_month | string | null | Filter by month ("YYYY-MM") |
| asset_class | string | null | Filter by asset class (null = all-classes aggregate) |
| limit | integer | 20 | Max results (1-200) |

**Response 200:**
```json
[
  {
    "id": "a50e8400-e29b-41d4-a716-446655440000",
    "period_month": "2026-03",
    "asset_class": "DIVIDEND_STOCK",
    "total_calls": 150,
    "agent04_trusted": 145,
    "manual_overrides": 5,
    "mismatches": 1,
    "accuracy_rate": 0.993,
    "override_rate": 0.033,
    "mismatch_rate": 0.007,
    "computed_at": "2026-04-01T00:00:00Z",
    "computed_by": "monthly_rollup_job"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| total_calls | integer | Total POST /scores/evaluate calls in period |
| agent04_trusted | integer | Calls where source=AGENT04 and is_mismatch != True |
| manual_overrides | integer | Calls where source=MANUAL_OVERRIDE |
| mismatches | integer | Calls where is_mismatch=True |
| accuracy_rate | float | (agent04_trusted + non_mismatches) / total_calls |
| override_rate | float | manual_overrides / total_calls |
| mismatch_rate | float | mismatches / total_calls |

**Errors:**
- 401: Not authenticated

---

### POST /classification-accuracy/rollup

Trigger monthly accuracy rollup for a calendar month.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "period_month": "2026-03",
  "computed_by": "manual_rollup_request"
}
```

**Response 201:**
```json
{
  "period_month": "2026-03",
  "runs_created": 8,
  "total_feedback_entries": 1200,
  "message": "Rollup complete: 7 per-class rows + 1 all-classes aggregate"
}
```

**Rollup process:**
- Creates one row per asset class with feedback from period_month
- Creates one aggregate row with asset_class=null
- Computes accuracy_rate, override_rate, mismatch_rate
- Returns count of rows created and total feedback entries processed

**Field validation:**
- period_month must be "YYYY-MM" format

**Errors:**
- 401: Not authenticated
- 422: Invalid period_month format (e.g., "2026-13" or "invalid")
- 500: Rollup computation failed (DB error)

---

## Updated POST /scores/evaluate Response (v2.0)

The response now includes classification and signal penalty tracking:

```json
{
  "ticker": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "valuation_yield_score": 8.5,
  "financial_durability_score": 9.2,
  "technical_entry_score": 7.8,
  "total_score_raw": 25.5,
  "nav_erosion_penalty": 0.0,
  "signal_penalty": 0.0,
  "total_score": 25.5,
  "grade": "A",
  "recommendation": "STRONG_BUY",
  "factor_details": {},
  "nav_erosion_details": null,
  "signal_penalty_details": null,
  "chowder_number": 8.1,
  "chowder_signal": "ATTRACTIVE",
  "weight_profile_version": 1,
  "weight_profile_id": "550e8400-e29b-41d4-a716-446655440000",
  "data_quality_score": 0.92,
  "data_completeness_pct": 88.0,
  "scored_at": "2026-03-12T09:59:35Z"
}
```

**New fields in v2.0:**

| Field | Type | Description |
|-------|------|-------------|
| weight_profile_version | integer | Version of weight profile used for scoring |
| weight_profile_id | string | UUID FK to scoring_weight_profiles table |
| signal_penalty | float | Points deducted by Agent 02 signal penalty (default 0.0) |
| signal_penalty_details | object or null | Signal context: signal_type, signal_strength, consensus_score, penalty applied |
