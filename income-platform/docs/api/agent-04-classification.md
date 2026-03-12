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
  "confidence": 0.98,
  "matching_rules": [
    {
      "rule_type": "ticker_pattern",
      "rule_config": {"pattern": "JPMorgan.*Premium.*Income"},
      "confidence_weight": 0.95,
      "priority": 50
    }
  ],
  "benchmark": "NASDAQ-100",
  "tax_profile": {
    "primary_treatment": "QUALIFIED_DIVIDEND",
    "section_199a_eligible": true,
    "qualified_dividend_eligible": true,
    "k1_required": false
  },
  "classified_at": "2026-03-12T09:59:35Z"
}
```

| Field | Description |
|-------|-------------|
| asset_class | DIVIDEND_STOCK, COVERED_CALL_ETF, BOND, or NULL_CLASS |
| confidence | 0.0-1.0, combines all matching rule weights |
| matching_rules | Rules that matched, ordered by match strength |
| benchmark | Relevant index for performance comparison |
| tax_profile | Tax treatment summary for the asset class |

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

| Class | Description | Tax Treatment |
|-------|-------------|---|
| DIVIDEND_STOCK | Equity with regular dividends | Qualified dividend (if held >60 days) |
| COVERED_CALL_ETF | Option-writing ETF | Qualified dividend + Section 1256 |
| BOND | Fixed income | Interest (ordinary income) |
| NULL_CLASS | Unknown/non-classifiable | Ordinary income (default) |

### Tax Treatment by Asset Class

**DIVIDEND_STOCK:**
- Primary: Qualified dividend
- Section 199A eligible: Yes
- Section 1256 eligible: No
- K-1 required: No

**COVERED_CALL_ETF:**
- Primary: Qualified dividend
- Section 199A eligible: Yes
- Section 1256 eligible: Yes (options portion)
- K-1 required: No

**BOND:**
- Primary: Ordinary interest
- Section 199A eligible: No (except municipal bond interest)
- Section 1256 eligible: No
- K-1 required: Depends on bond structure

### Benchmarks

Each classification is mapped to a relevant market benchmark:
- DIVIDEND_STOCK → S&P 500 or sector index
- COVERED_CALL_ETF → S&P 500 or Russell 2000
- BOND → Bloomberg Aggregate Bond Index
- NULL_CLASS → No benchmark

### Confidence Scoring

Confidence is the weighted average of all matching rule confidences:

```
confidence = sum(rule.confidence_weight for each matching rule) / count(matching rules)
```

- ≥0.90: High confidence
- 0.70-0.90: Moderate confidence
- <0.70: Low confidence
