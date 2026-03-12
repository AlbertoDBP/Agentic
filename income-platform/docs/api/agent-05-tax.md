# Agent 05: Tax Optimization Service

Provides tax treatment profiling, after-tax yield calculation, account placement optimization, and tax-loss harvesting identification for income-generating investments.

**Port:** 8005
**Base URL:** `http://<host>:8005`

## Health Check

### GET /health

Service health check — verifies database connectivity.

**Auth:** Not required
**Method:** GET

**Response 200:**
```json
{
  "status": "healthy",
  "service": "tax-optimization-service",
  "version": "1.0.0",
  "agent_id": 5,
  "database": "connected"
}
```

---

## Tax Profile

### GET /tax/profile/{symbol}

Return the tax treatment profile for a symbol without calculating specific distributions.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Stock/ETF symbol |

**Query parameters:**
| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| asset_class | enum | No | Auto-detect (Agent 04) | DIVIDEND_STOCK, COVERED_CALL_ETF, BOND |
| filing_status | enum | No | SINGLE | SINGLE, MARRIED_FILING_JOINTLY, MARRIED_FILING_SEPARATELY, HEAD_OF_HOUSEHOLD |
| state_code | string | No | None | Two-letter state abbreviation |
| account_type | enum | No | TAXABLE | TAXABLE, TRADITIONAL_IRA, ROTH_IRA, 401K |
| annual_income | float | No | 0 | Estimated annual income (for tax bracket calculation) |

**Response 200:**
```json
{
  "symbol": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "account_type": "TAXABLE",
  "filing_status": "SINGLE",
  "state_code": "CA",
  "annual_income": 150000,
  "primary_treatment": "QUALIFIED_DIVIDEND",
  "federal_tax_rate": 0.15,
  "state_tax_rate": 0.093,
  "fica_tax_rate": 0.0,
  "effective_combined_rate": 0.243,
  "section_199a_eligible": true,
  "section_1256_eligible": false,
  "k1_required": false,
  "notes": "Qualified dividend treatment applies if held >60 days around ex-dividend"
}
```

| Field | Description |
|-------|-------------|
| primary_treatment | QUALIFIED_DIVIDEND, ORDINARY_INCOME, INTEREST, CAPITAL_GAIN, etc. |
| federal_tax_rate | Federal rate for this income bracket (15%, 20%, or 37% for qualified dividends) |
| state_tax_rate | State-level tax rate (varies by state) |
| fica_tax_rate | FICA (Social Security + Medicare) — typically 0 for dividends, may apply in RMD scenarios |
| effective_combined_rate | Total tax rate (federal + state + FICA) |
| section_199a_eligible | Eligible for Section 199A (20% pass-through deduction) — not typically applicable to dividends |
| section_1256_eligible | Subject to Section 1256 treatment (60% long-term + 40% short-term capital gains) |
| k1_required | K-1 form required for tax filing |

---

### POST /tax/profile

POST version for complex tax profile requests.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "symbol": "JEPI",
  "asset_class": "COVERED_CALL_ETF",
  "filing_status": "MARRIED_FILING_JOINTLY",
  "state_code": "TX",
  "account_type": "TAXABLE",
  "annual_income": 300000
}
```

**Response 200:** Same as GET /tax/profile/{symbol}

---

## Tax Calculation

### POST /tax/calculate

Calculate after-tax net distribution and effective tax rate for a specific distribution amount.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "symbol": "JNJ",
  "distribution_amount": 50.0,
  "annual_income": 150000,
  "filing_status": "SINGLE",
  "state_code": "CA",
  "account_type": "TAXABLE",
  "asset_class": "DIVIDEND_STOCK"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| symbol | string | Yes | Stock/ETF symbol |
| distribution_amount | float | Yes | Annual distribution per share or per unit |
| annual_income | float | Yes | Taxpayer's total annual income |
| filing_status | enum | No | Default: SINGLE |
| state_code | string | No | Two-letter state code |
| account_type | enum | No | Default: TAXABLE |
| asset_class | enum | No | Auto-detect if not provided |

**Response 200:**
```json
{
  "symbol": "JNJ",
  "distribution_amount": 50.0,
  "asset_class": "DIVIDEND_STOCK",
  "tax_treatment": "QUALIFIED_DIVIDEND",
  "federal_tax": 7.5,
  "state_tax": 4.65,
  "total_tax": 12.15,
  "after_tax_distribution": 37.85,
  "effective_tax_rate": 0.243,
  "account_type": "TAXABLE",
  "filing_status": "SINGLE",
  "state_code": "CA"
}
```

---

### GET /tax/calculate/{symbol}

GET convenience endpoint for quick single-symbol tax calculations.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Stock/ETF symbol |

**Query parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| distribution_amount | float | Yes | Annual distribution per share (>0) |
| annual_income | float | Yes | Estimated annual income (≥0) |
| filing_status | enum | No | Default: SINGLE |
| state_code | string | No | Two-letter state code |
| account_type | enum | No | Default: TAXABLE |
| asset_class | enum | No | DIVIDEND_STOCK, COVERED_CALL_ETF, BOND |

**Response 200:** Same as POST /tax/calculate

**Example:**
```bash
curl "http://localhost:8005/tax/calculate/JNJ?distribution_amount=50&annual_income=150000&state_code=CA"
```

---

## Portfolio Optimization

### POST /tax/optimize

Analyze a portfolio of holdings and recommend optimal account placement to minimize tax drag on income distributions.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "holdings": [
    {
      "symbol": "JNJ",
      "asset_class": "DIVIDEND_STOCK",
      "quantity": 100,
      "annual_income_per_share": 3.25,
      "current_price": 182.50
    },
    {
      "symbol": "JEPI",
      "asset_class": "COVERED_CALL_ETF",
      "quantity": 50,
      "annual_income_per_share": 1.80,
      "current_price": 55.00
    }
  ],
  "accounts": [
    {
      "name": "Taxable Brokerage",
      "account_type": "TAXABLE",
      "capacity": 500000
    },
    {
      "name": "Traditional IRA",
      "account_type": "TRADITIONAL_IRA",
      "capacity": 7000
    }
  ],
  "filing_status": "MARRIED_FILING_JOINTLY",
  "state_code": "CA",
  "annual_income": 300000
}
```

**Response 200:**
```json
{
  "portfolio_value": 27275,
  "annual_tax_burden_current": 3140,
  "annual_tax_burden_optimized": 2680,
  "tax_savings": 460,
  "recommendations": [
    {
      "symbol": "JNJ",
      "asset_class": "DIVIDEND_STOCK",
      "quantity": 100,
      "current_location": "TAXABLE",
      "recommended_location": "TRADITIONAL_IRA",
      "tax_impact": "Defer income tax; subject to RMD rules",
      "priority": 1
    }
  ],
  "account_placement_plan": [
    {
      "account_name": "Taxable Brokerage",
      "holdings": [
        {"symbol": "JEPI", "quantity": 50}
      ]
    }
  ]
}
```

Optimization considers:
- Tax treatment of each security
- Marginal tax bracket of investor
- Available account space
- RMD implications
- Asset location efficiency

---

## Tax-Loss Harvesting

### POST /tax/harvest

Identify tax-loss harvesting opportunities across a set of positions. Returns proposals only; no trades are executed.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "candidates": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "purchase_price": 185.00,
      "current_price": 165.00,
      "purchase_date": "2024-06-15"
    },
    {
      "symbol": "JNJ",
      "quantity": 50,
      "purchase_price": 160.00,
      "current_price": 182.50,
      "purchase_date": "2025-01-10"
    }
  ],
  "realized_gains_ytd": 25000,
  "filing_status": "MARRIED_FILING_JOINTLY",
  "state_code": "CA"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| candidates | array | Yes | List of positions to analyze |
| realized_gains_ytd | float | No | Capital gains already realized this tax year |
| filing_status | enum | No | Default: SINGLE |
| state_code | string | No | Two-letter state code |

**Response 200:**
```json
{
  "total_unrealized_losses": 2000,
  "opportunities": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "unrealized_loss": 2000,
      "tax_savings": 520,
      "wash_sale_risk": {
        "risky": false,
        "reason": null,
        "recovery_date": null
      },
      "replacement_suggestions": [
        {
          "symbol": "MSFT",
          "correlation": 0.92,
          "reason": "Similar tech exposure, low wash-sale risk"
        }
      ]
    }
  ],
  "total_potential_tax_savings": 520,
  "wash_sale_warnings": []
}
```

**Wash Sale Rules:**
- Cannot claim loss if you buy the same or substantially identical security within 30 days before/after sale
- Wash sale period extends 30 days after sale
- Service flags positions at risk and suggests replacement securities

---

## Asset Class Reference

### GET /tax/asset-classes

Return a reference summary of tax treatment for each supported asset class.

**Auth:** Required
**Method:** GET

**Response 200:**
```json
{
  "DIVIDEND_STOCK": {
    "primary_treatment": "QUALIFIED_DIVIDEND",
    "qualified_dividend_eligible": true,
    "section_199a_eligible": false,
    "section_1256_eligible": false,
    "k1_required": false
  },
  "COVERED_CALL_ETF": {
    "primary_treatment": "QUALIFIED_DIVIDEND",
    "qualified_dividend_eligible": true,
    "section_199a_eligible": false,
    "section_1256_eligible": true,
    "k1_required": false
  },
  "BOND": {
    "primary_treatment": "ORDINARY_INTEREST",
    "qualified_dividend_eligible": false,
    "section_199a_eligible": false,
    "section_1256_eligible": false,
    "k1_required": false
  }
}
```

---

## Tax Rates (2026)

### Federal Qualified Dividend Rates
- 0% rate: ~$47,000 (single) / ~$94,000 (MFJ)
- 15% rate: ~$47,000-$518,000 (single) / ~$94,000-$583,750 (MFJ)
- 20% rate: >$518,000 (single) / >$583,750 (MFJ)

### State Tax Rates
Vary by state from 0% (Alaska, Florida, Texas, Wyoming) to 13.3% (California)

### Account Types

| Type | Tax on Distributions | Tax on Growth | Best For |
|------|---|---|---|
| TAXABLE | Immediate | Annual | Maximum flexibility |
| TRADITIONAL_IRA | Deferred (RMD at 73) | Tax-deferred | Income deferral |
| ROTH_IRA | None | Tax-free | Long-term growth |
| 401K | Deferred (RMD at 73) | Tax-deferred | Employer match |

### Filing Status Impact

The `filing_status` parameter affects:
- Tax brackets for income
- Standard deduction amount
- Capital gains rate thresholds
- Deduction phase-outs

---

## Common Use Cases

### 1. Calculate After-Tax Yield

```bash
curl -X POST http://localhost:8005/tax/calculate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"symbol": "JNJ", "distribution_amount": 3.25, "annual_income": 150000}'
```

### 2. Optimize Account Placement

```bash
curl -X POST http://localhost:8005/tax/optimize \
  -H "Authorization: Bearer $TOKEN" \
  -d @portfolio.json
```

### 3. Identify Harvesting Opportunities

```bash
curl -X POST http://localhost:8005/tax/harvest \
  -H "Authorization: Bearer $TOKEN" \
  -d @positions.json
```
