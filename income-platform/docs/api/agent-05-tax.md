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
| filing_status | enum | No | SINGLE | SINGLE, MARRIED_JOINT, MARRIED_SEPARATE, HEAD_OF_HOUSEHOLD |
| state_code | string | No | None | Two-letter state abbreviation |
| account_type | enum | No | TAXABLE | TAXABLE, TRAD_IRA, ROTH_IRA, 401K |
| annual_income | float | No | 0 | Estimated annual income (for tax bracket calculation) |

**Response 200:**
```json
{
  "symbol": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "asset_class_fallback": false,
  "primary_tax_treatment": "QUALIFIED_DIVIDEND",
  "secondary_treatments": ["ORDINARY_INCOME"],
  "qualified_dividend_eligible": true,
  "section_199a_eligible": false,
  "section_1256_eligible": false,
  "k1_required": false,
  "notes": [
    "Qualified dividends require 61-day holding period around ex-dividend date.",
    "Foreign dividends may not qualify; confirm treaty status."
  ]
}
```

| Field | Description |
|-------|-------------|
| asset_class | Resolved asset class (from request, Agent 04, or fallback) |
| asset_class_fallback | True if Agent 04 was unavailable and ORDINARY_INCOME was used |
| primary_tax_treatment | QUALIFIED_DIVIDEND, ORDINARY_INCOME, REIT_DISTRIBUTION, MLP_DISTRIBUTION, SECTION_1256_60_40, RETURN_OF_CAPITAL, or TAX_EXEMPT |
| secondary_treatments | List of possible alternative treatments for this asset class |
| qualified_dividend_eligible | True if distributions qualify for preferential tax rates |
| section_199a_eligible | True for REITs and MLPs (20% pass-through deduction) |
| section_1256_eligible | True for futures-based ETFs (60/40 blended rate) |
| k1_required | True for MLPs and some partnerships |
| notes | Plain-language tax guidance for this asset class |

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
  "filing_status": "MARRIED_JOINT",
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
  "gross_distribution": 50.0,
  "federal_tax_owed": 7.5,
  "state_tax_owed": 4.65,
  "niit_owed": 0.0,
  "total_tax_owed": 12.15,
  "net_distribution": 37.85,
  "effective_tax_rate": 0.243,
  "after_tax_yield_uplift": 0.0,
  "bracket_detail": [
    {
      "income_type": "QUALIFIED_DIVIDEND",
      "rate_federal": 0.15,
      "rate_state": 0.093,
      "rate_combined": 0.243,
      "niit_applicable": false
    }
  ],
  "notes": []
}
```

| Field | Description |
|-------|-------------|
| gross_distribution | Input distribution amount before tax |
| federal_tax_owed | Federal tax on this distribution |
| state_tax_owed | State tax (0.0 if no state_code or no-tax state) |
| niit_owed | Net Investment Income Tax (3.8% if income above threshold) |
| total_tax_owed | Sum of federal + state + NIIT |
| net_distribution | After-tax distribution (gross - total_tax_owed) |
| effective_tax_rate | total_tax_owed / gross_distribution |
| after_tax_yield_uplift | Tax savings vs treating entire distribution as ordinary income |
| bracket_detail | Per-income-type breakdown with individual rates |
| notes | Explanatory notes (e.g., "Section 1256 60/40 blended rate applied") |

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
      "symbol": "JEPI",
      "asset_class": "COVERED_CALL_ETF",
      "account_type": "TAXABLE",
      "current_value": 50000.0,
      "annual_yield": 0.09
    },
    {
      "symbol": "JNJ",
      "asset_class": "DIVIDEND_STOCK",
      "account_type": "TAXABLE",
      "current_value": 25000.0,
      "annual_yield": 0.03
    }
  ],
  "annual_income": 200000,
  "filing_status": "SINGLE",
  "state_code": "FL"
}
```

**Response 200:**
```json
{
  "total_portfolio_value": 75000.0,
  "current_annual_tax_burden": 1350.0,
  "optimized_annual_tax_burden": 675.0,
  "estimated_annual_savings": 675.0,
  "placement_recommendations": [
    {
      "symbol": "JEPI",
      "current_account": "TAXABLE",
      "recommended_account": "TRAD_IRA",
      "reason": "Ordinary income taxed at 32%; shelter in IRA to defer tax.",
      "estimated_annual_tax_savings": 675.0
    }
  ],
  "summary": "Moving 1 holding to tax-advantaged accounts saves ~$675/year.",
  "notes": []
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
      "current_value": 16500.0,
      "cost_basis": 18500.0,
      "holding_period_days": 270,
      "account_type": "TAXABLE"
    },
    {
      "symbol": "JNJ",
      "current_value": 28000.0,
      "cost_basis": 25000.0,
      "holding_period_days": 400,
      "account_type": "TAXABLE"
    }
  ],
  "annual_income": 150000,
  "filing_status": "SINGLE",
  "state_code": "FL",
  "wash_sale_check": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| candidates | array | Yes | Positions to analyze |
| candidates[].symbol | string | Yes | Ticker symbol |
| candidates[].current_value | float | Yes | Current market value of position (≥0) |
| candidates[].cost_basis | float | Yes | Total cost basis of position (≥0) |
| candidates[].holding_period_days | int | Yes | Days position has been held (≥0) |
| candidates[].account_type | enum | No | Default: TAXABLE |
| annual_income | float | Yes | Taxpayer's annual income (≥0) |
| filing_status | enum | No | Default: SINGLE |
| state_code | string | No | Two-letter state code |
| wash_sale_check | bool | No | Default: true — flag wash-sale risks |

**Response 200:**
```json
{
  "total_harvestable_losses": 2000.0,
  "total_estimated_tax_savings": 300.0,
  "opportunities": [
    {
      "symbol": "AAPL",
      "unrealized_loss": 2000.0,
      "tax_savings_estimated": 300.0,
      "holding_period_days": 270,
      "long_term": false,
      "wash_sale_risk": false,
      "action": "HARVEST_NOW",
      "rationale": "Short-term loss; harvest before 365-day mark to offset gains."
    }
  ],
  "wash_sale_warnings": [],
  "notes": []
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
  "COVERED_CALL_ETF": {
    "primary_treatment": "ORDINARY_INCOME",
    "qualified_dividend_eligible": false,
    "section_199a_eligible": false,
    "section_1256_eligible": true,
    "k1_required": false
  },
  "DIVIDEND_STOCK": {
    "primary_treatment": "QUALIFIED_DIVIDEND",
    "qualified_dividend_eligible": true,
    "section_199a_eligible": false,
    "section_1256_eligible": false,
    "k1_required": false
  },
  "REIT": {
    "primary_treatment": "REIT_DISTRIBUTION",
    "qualified_dividend_eligible": false,
    "section_199a_eligible": true,
    "section_1256_eligible": false,
    "k1_required": false
  },
  "BOND_ETF": {
    "primary_treatment": "ORDINARY_INCOME",
    "qualified_dividend_eligible": false,
    "section_199a_eligible": false,
    "section_1256_eligible": false,
    "k1_required": false
  },
  "PREFERRED_STOCK": {
    "primary_treatment": "QUALIFIED_DIVIDEND",
    "qualified_dividend_eligible": true,
    "section_199a_eligible": false,
    "section_1256_eligible": false,
    "k1_required": false
  },
  "MLP": {
    "primary_treatment": "MLP_DISTRIBUTION",
    "qualified_dividend_eligible": false,
    "section_199a_eligible": true,
    "section_1256_eligible": false,
    "k1_required": true
  },
  "BDC": {
    "primary_treatment": "ORDINARY_INCOME",
    "qualified_dividend_eligible": false,
    "section_199a_eligible": false,
    "section_1256_eligible": false,
    "k1_required": false
  },
  "CLOSED_END_FUND": {
    "primary_treatment": "ORDINARY_INCOME",
    "qualified_dividend_eligible": false,
    "section_199a_eligible": false,
    "section_1256_eligible": false,
    "k1_required": false
  }
}
```

---

## Tax Rates (2024)

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
| TRAD_IRA | Deferred (RMD at 73) | Tax-deferred | Income deferral |
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
