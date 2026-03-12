# Agent 04: Asset Classification Service

Infers and classifies the asset type of securities (dividend stock, covered call ETF, bond, etc.) using rules engine and optional overrides.

**Port:** 8004
**Base URL:** `http://<host>:8004`

## Health Check

### GET /health

Service health check — verifies database connectivity.

**Auth:** Not required
**Method:** GET

**Response 200:**
```json
{
  "status": "healthy",
  "service": "asset-classification-service",
  "database": "connected",
  "port": 8004
}
```

---

## Single Classification

### POST /classify

Classify a single ticker to determine its asset class.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "ticker": "JEPI",
  "security_data": {
    "name": "JPMorgan Equity Premium Income ETF",
    "asset_type": "ETF",
    "sector": "Technology",
    "expense_ratio": 0.0035,
    "aum_millions": 18500,
    "covered_call": true
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ticker | string | Yes | Stock/ETF symbol |
| security_data | object | No | Optional enrichment hints (overrides DB lookup) |

**Response 200:**
```json
{
  "ticker": "JEPI",
  "asset_class": "COVERED_CALL_ETF",
  "parent_class": "FUND",
  "confidence": 0.95,
  "is_hybrid": false,
  "characteristics": {
    "income_type": "option_premium",
    "tax_treatment": "ordinary",
    "valuation_method": "yield + nav_trend",
    "rate_sensitivity": "low",
    "principal_at_risk": true,
    "nav_erosion_tracking": true,
    "coverage_ratio_required": false,
    "preferred_account": "IRA"
  },
  "benchmarks": {
    "peer_group": ["JEPI", "JEPQ", "QYLD", "XYLD", "DIVO"],
    "yield_benchmark_pct": 8.0,
    "expense_ratio_benchmark_pct": 0.45,
    "nav_stability_benchmark": "moderate",
    "pe_benchmark": null,
    "debt_equity_benchmark": null,
    "payout_ratio_benchmark": null
  },
  "sub_scores": null,
  "tax_efficiency": {
    "income_type": "option_premium",
    "tax_treatment": "ordinary",
    "estimated_tax_drag_pct": 37.0,
    "preferred_account": "IRA",
    "notes": "Option premium taxed as ordinary income. Hold in IRA/Roth to shelter high distributions."
  },
  "source": "rule_engine_v1",
  "is_override": false,
  "classified_at": "2026-03-12T10:00:00+00:00",
  "valid_until": "2026-03-13T10:00:00+00:00"
}
```

| Field | Description |
|-------|-------------|
| asset_class | DIVIDEND_STOCK, COVERED_CALL_ETF, BOND, EQUITY_REIT, MORTGAGE_REIT, BDC, PREFERRED_STOCK, or UNKNOWN |
| parent_class | EQUITY, FIXED_INCOME, ALTERNATIVE, FUND, or OVERRIDE |
| confidence | 0.0–1.0 — aggregated confidence from matched rules |
| is_hybrid | True for MORTGAGE_REIT and other hybrid classes |
| characteristics | Class-specific traits: income_type, tax_treatment, valuation_method, rate_sensitivity, preferred_account, etc. |
| benchmarks | Peer group and benchmark values for the asset class; null if class not in benchmarks table |
| sub_scores | Reserved for future sub-scorer phase; always null in v1.0 |
| tax_efficiency | Tax drag estimate (% of income), preferred account, and plain-language notes for Agent 05 |
| source | `rule_engine_v1` for auto-classified; `override` for manual overrides |
| is_override | True when result came from a manual ClassificationOverride record |
| classified_at | UTC timestamp of classification |
| valid_until | Cache expiry (classified_at + 24h); null for overrides (never expire) |

**Errors:**
- 422: Ticker is required

---

### GET /classify/{ticker}

Retrieve latest classification for a ticker. Runs fresh classification if not cached.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| ticker | string | Stock/ETF symbol |

**Response 200:**
```json
{
  "ticker": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "confidence": 0.92,
  "matching_rules": [
    {
      "rule_type": "sector",
      "rule_config": {"sector": "Healthcare", "dividend_threshold": 1.5},
      "confidence_weight": 0.85,
      "priority": 40
    }
  ],
  "benchmark": "S&P 500 Healthcare Index",
  "tax_profile": {
    "primary_treatment": "QUALIFIED_DIVIDEND",
    "section_199a_eligible": true,
    "qualified_dividend_eligible": true,
    "k1_required": false
  },
  "classified_at": "2026-03-12T09:59:35Z"
}
```

---

## Batch Classification

### POST /classify/batch

Classify up to 100 tickers in a single batch request.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "tickers": ["AAPL", "JNJ", "JEPI", "SPY"],
  "security_data": null
}
```

| Field | Type | Required | Max | Description |
|-------|------|----------|-----|-------------|
| tickers | array[string] | Yes | 100 | List of symbols to classify |
| security_data | object | No | - | Applied to all tickers if provided |

**Response 200:**
```json
{
  "total": 4,
  "classified": 4,
  "errors": 0,
  "results": [
    {
      "ticker": "AAPL",
      "asset_class": "DIVIDEND_STOCK",
      "confidence": 0.88,
      "benchmark": "S&P 500",
      "classified_at": "2026-03-12T09:59:35Z"
    }
  ],
  "error_details": []
}
```

**Errors:**
- 422: Batch size exceeds 100

---

## Rules Management

### GET /rules

List all active classification rules.

**Auth:** Required
**Method:** GET

**Response 200:**
```json
{
  "total": 5,
  "rules": [
    {
      "id": "rule-001",
      "asset_class": "COVERED_CALL_ETF",
      "rule_type": "ticker_pattern",
      "rule_config": {
        "pattern": "JPM.*Premium.*Income|JEPQ|JEPI|SCHW.*Covered|BXM"
      },
      "priority": 50,
      "confidence_weight": 0.95,
      "active": true,
      "created_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

**Rule types:**
- `ticker_pattern`: Regex match on symbol
- `sector`: Industry/sector-based classification
- `feature`: Attribute-based (expense ratio, yield, AUM)
- `metadata`: Custom field matching

---

### POST /rules

Add a new classification rule. Takes effect immediately — no redeployment needed.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "asset_class": "BOND",
  "rule_type": "ticker_pattern",
  "rule_config": {
    "pattern": "^[A-Z]{3}\\d{2}$"
  },
  "priority": 100,
  "confidence_weight": 0.85
}
```

| Field | Type | Required | Range | Description |
|-------|------|----------|-------|-------------|
| asset_class | string | Yes | - | Target asset class |
| rule_type | string | Yes | ticker_pattern, sector, feature, metadata | Type of rule |
| rule_config | object | Yes | - | Rule parameters (type-specific) |
| priority | integer | No | - | Lower values = higher priority (default 100) |
| confidence_weight | float | No | 0-1 | Weight in confidence calculation (default 0.80) |

**Response 200:**
```json
{
  "id": "rule-006",
  "message": "Rule created successfully"
}
```

**Errors:**
- 422: Invalid rule_type or confidence_weight

---

## Manual Overrides

### PUT /overrides/{ticker}

Set a manual override for a ticker. Overrides have confidence=1.0 and bypass all rules.

**Auth:** Required
**Method:** PUT

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| ticker | string | Stock/ETF symbol |

**Request body:**
```json
{
  "asset_class": "DIVIDEND_STOCK",
  "reason": "Manually verified as dividend-focused via 10-K",
  "created_by": "alice@example.com"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| asset_class | string | Yes | Override asset class |
| reason | string | No | Justification for override |
| created_by | string | No | Creator identifier |

**Response 200:**
```json
{
  "ticker": "XYZ",
  "message": "Override created"
}
```

If an override already exists for the ticker, it is replaced.

---

### DELETE /overrides/{ticker}

Remove manual override. Ticker will be re-classified by rules on next request.

**Auth:** Required
**Method:** DELETE

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| ticker | string | Stock/ETF symbol |

**Response 200:**
```json
{
  "ticker": "XYZ",
  "message": "Override removed"
}
```

**Errors:**
- 404: No override found for ticker

---

## Classification Details

### Asset Classes

| Class | Parent | Income Type | Tax Treatment | Account |
|-------|--------|-------------|---------------|---------|
| DIVIDEND_STOCK | EQUITY | qualified_dividend | qualified | TAXABLE |
| COVERED_CALL_ETF | FUND | option_premium | ordinary | IRA |
| BOND | FIXED_INCOME | interest | ordinary | IRA |
| EQUITY_REIT | EQUITY | reit_distribution | ordinary | IRA |
| MORTGAGE_REIT | EQUITY | reit_distribution | ordinary | IRA |
| BDC | ALTERNATIVE | ordinary_dividend | ordinary | IRA |
| PREFERRED_STOCK | EQUITY | fixed_dividend | qualified | TAXABLE |
| UNKNOWN | EQUITY | unknown | unknown | TAXABLE |

### Tax Treatment by Asset Class

Tax efficiency details are computed by `app/classification/tax_profile.py` and returned in the `tax_efficiency` field of every classification response. Each class has:

- `income_type` — primary income category
- `estimated_tax_drag_pct` — approximate federal tax drag (Florida — no state tax)
- `preferred_account` — TAXABLE or IRA
- `notes` — plain-language guidance for account placement

See [Tax Profile spec](../agents/agent-04/functional/tax-profile.md) for full details.

### Benchmarks

Each asset class has a benchmark profile in `app/classification/benchmarks.py` with peer group, yield benchmark, and valuation reference values. Returned as the `benchmarks` object in the classification response. Classes without a matching profile return `null`.

| Class | Peer Group | Yield Benchmark |
|-------|-----------|-----------------|
| COVERED_CALL_ETF | JEPI, JEPQ, QYLD, XYLD, DIVO | 8.0% |
| DIVIDEND_STOCK | JNJ, PG, KO, MMM, T | 3.0% |
| EQUITY_REIT | O, VICI, AMT, CCI, SPG | 4.5% |
| MORTGAGE_REIT | AGNC, NLY, RITM, MFA, PMT | 10.0% |
| BDC | ARCC, MAIN, BXSL, OBDC, HTGC | 9.0% |
| BOND | AGG, BND, LQD, TLT, IEF | 4.0% |
| PREFERRED_STOCK | *(no peer group)* | 6.0% |

### Confidence Scoring

Confidence is the weighted average of all matching rule confidences:

```
confidence = sum(rule.confidence_weight for each matching rule) / count(matching rules)
```

- ≥0.90: High confidence
- 0.70-0.90: Moderate confidence
- <0.70: Low confidence
