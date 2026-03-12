# Agent 06: Scenario Simulation Service

Stress testing, income projection, and vulnerability analysis for income portfolios. Evaluates portfolio resilience under various market scenarios.

**Port:** 8006
**Base URL:** `http://<host>:8006`

## Health Check

### GET /health

Service health check.

**Auth:** Not required
**Method:** GET

**Response 200:**
```json
{
  "service": "scenario-simulation-service",
  "version": "1.0.0",
  "status": "healthy"
}
```

---

## Stress Testing

### POST /scenarios/stress-test

Run a stress test on a portfolio under a predefined or custom market scenario.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "scenario_type": "RATE_HIKE_200BPS",
  "as_of_date": "2026-03-12",
  "save": true,
  "label": "March 2026 Interest Rate Shock"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| portfolio_id | UUID | Yes | Portfolio identifier |
| scenario_type | string | Yes | Predefined scenario name or "CUSTOM" |
| scenario_params | object | No | Required if scenario_type is CUSTOM |
| as_of_date | date | No | Valuation date; defaults to today |
| save | boolean | No | Persist result to database |
| label | string | No | Human-readable label for saved result |

**Predefined Scenarios:**
- `RATE_HIKE_200BPS`: Federal funds rate increases 200 basis points
- `MARKET_CORRECTION_20`: Stock market declines 20%
- `RECESSION_SCENARIO`: Moderate recession with yield curve inversion
- `INFLATION_SPIKE`: 2% increase in inflation expectations
- `DURATION_SHOCK`: Long-duration bonds decline sharply

**Custom Scenario Example:**
```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "scenario_type": "CUSTOM",
  "scenario_params": {
    "equity_shock_pct": -15.0,
    "bond_shock_pct": -8.5,
    "dividend_cut_pct": 10.0,
    "yield_shock_bps": 125
  },
  "save": false
}
```

**Response 200:**
```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "scenario_name": "RATE_HIKE_200BPS",
  "portfolio_value_before": 500000,
  "portfolio_value_after": 475000,
  "value_change_pct": -5.0,
  "annual_income_before": 15000,
  "annual_income_after": 13200,
  "income_change_pct": -12.0,
  "position_impacts": [
    {
      "symbol": "JNJ",
      "asset_class": "DIVIDEND_STOCK",
      "current_value": 150000,
      "stressed_value": 142500,
      "current_income": 4500,
      "stressed_income": 4050,
      "value_change_pct": -5.0,
      "income_change_pct": -10.0,
      "vulnerability_rank": 2
    },
    {
      "symbol": "JEPI",
      "asset_class": "COVERED_CALL_ETF",
      "current_value": 175000,
      "stressed_value": 158750,
      "current_income": 6125,
      "stressed_income": 5313,
      "value_change_pct": -9.3,
      "income_change_pct": -13.3,
      "vulnerability_rank": 1
    }
  ],
  "computed_at": "2026-03-12T09:59:35Z",
  "saved": true,
  "result_id": "result-xyz-123"
}
```

| Field | Description |
|-------|-------------|
| value_change_pct | Portfolio value change (%, negative = decline) |
| income_change_pct | Annual income change (%) |
| position_impacts | Per-position impact details, ranked by vulnerability |
| vulnerability_rank | 1 = most vulnerable, N = least vulnerable |
| saved | True if result was persisted to database |
| result_id | Database UUID for saved result (if saved=true) |

**Errors:**
- 422: Portfolio not found, no open positions, or invalid scenario
- 500: Stress engine failure

---

## Income Projection

### POST /scenarios/income-projection

Project income distribution over a forward time horizon with confidence intervals.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "horizon_months": 12
}
```

| Field | Type | Required | Range | Description |
|-------|------|----------|-------|-------------|
| portfolio_id | UUID | Yes | - | Portfolio identifier |
| horizon_months | integer | No | 1-60 | Forward projection period; defaults to 12 |

**Response 200:**
```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "horizon_months": 12,
  "projected_income_p10": 12000,
  "projected_income_p50": 15000,
  "projected_income_p90": 18500,
  "by_position": [
    {
      "symbol": "JNJ",
      "asset_class": "DIVIDEND_STOCK",
      "quantity": 100,
      "current_annual_income": 4500,
      "projected_income_p10": 4350,
      "projected_income_p50": 4500,
      "projected_income_p90": 4725,
      "growth_assumption_pct": 5.5,
      "dividend_cut_risk_pct": 2.0
    }
  ],
  "computed_at": "2026-03-12T09:59:35Z"
}
```

| Field | Description |
|-------|-------------|
| p10, p50, p90 | 10th, 50th (median), 90th percentile of income distribution |
| growth_assumption_pct | Historical dividend growth rate used in projection |
| dividend_cut_risk_pct | Probability of dividend cut based on position fundamentals |

**Modeling Assumptions:**
- Dividend growth follows historical CAGR
- Dividend cuts are modeled as low-probability tail events
- Covered call premiums decline as volatility declines
- Bond distributions remain stable

---

## Vulnerability Ranking

### POST /scenarios/vulnerability

Run multiple stress scenarios and rank positions by worst-case loss.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "scenario_types": ["RATE_HIKE_200BPS", "MARKET_CORRECTION_20", "RECESSION_SCENARIO"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| portfolio_id | UUID | Yes | Portfolio identifier |
| scenario_types | array[string] | No | Scenarios to test; defaults to [RATE_HIKE_200BPS, MARKET_CORRECTION_20] |

**Response 200:**
```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "rankings": [
    {
      "rank": 1,
      "symbol": "JEPI",
      "worst_scenario": "RATE_HIKE_200BPS",
      "max_value_loss_pct": -9.3
    },
    {
      "rank": 2,
      "symbol": "JNJ",
      "worst_scenario": "MARKET_CORRECTION_20",
      "max_value_loss_pct": -8.5
    }
  ]
}
```

Positions are ranked from most to least vulnerable (worst case first).

**Errors:**
- 422: Portfolio not found, no open positions

---

## Scenario Library

### GET /scenarios/library

Retrieve available predefined scenarios with their parameters.

**Auth:** Required
**Method:** GET

**Response 200:**
```json
{
  "scenarios": [
    {
      "name": "RATE_HIKE_200BPS",
      "label": "200 Basis Point Rate Hike",
      "description": "Federal Reserve raises rates aggressively",
      "parameters": {
        "rate_shock_bps": 200,
        "equity_shock_pct": -8.0,
        "bond_shock_pct": -12.0,
        "dividend_cut_pct": 5.0,
        "yield_shock_bps": 200
      }
    },
    {
      "name": "MARKET_CORRECTION_20",
      "label": "20% Stock Market Decline",
      "description": "Broad equity selloff without credit crisis",
      "parameters": {
        "equity_shock_pct": -20.0,
        "bond_shock_pct": -2.0,
        "dividend_cut_pct": 8.0
      }
    },
    {
      "name": "RECESSION_SCENARIO",
      "label": "Mild Recession",
      "description": "Economic downturn with yield curve inversion",
      "parameters": {
        "equity_shock_pct": -15.0,
        "bond_shock_pct": -5.0,
        "dividend_cut_pct": 15.0,
        "unemployment_increase_pct": 2.5
      }
    },
    {
      "name": "INFLATION_SPIKE",
      "label": "Inflation Surge",
      "description": "CPI increases 2% YoY, expectations repriced",
      "parameters": {
        "inflation_shock_pct": 2.0,
        "equity_shock_pct": -5.0,
        "bond_shock_pct": -8.0,
        "dividend_growth_boost_pct": 2.0
      }
    },
    {
      "name": "DURATION_SHOCK",
      "label": "Long Duration Bond Shock",
      "description": "Unexpected spike in long-term yields",
      "parameters": {
        "bond_shock_pct": -15.0,
        "equity_shock_pct": -3.0,
        "yield_shock_bps": 150
      }
    }
  ]
}
```

---

## Portfolio Data Requirements

To run simulations, portfolios must have:

1. **Positions Data**
   - Symbol (e.g., JNJ, JEPI)
   - Quantity (shares owned)
   - Current price (as of valuation date)
   - Annual income per share

2. **Asset Classifications**
   - Asset class mapping for each symbol
   - Pulled from Agent 04 Classification Service

3. **Historical Data** (for projections)
   - Price history (1-3 years)
   - Dividend history
   - Volatility estimates

---

## Stress Engine Mechanics

### Per-Position Impact Calculation

For each position under a scenario:

```
stressed_price = current_price × (1 + asset_class_shock_pct)
stressed_income = annual_income × (1 - dividend_cut_pct)
value_change_pct = (stressed_price - current_price) / current_price × 100
income_change_pct = (stressed_income - annual_income) / annual_income × 100
```

### Vulnerability Ranking

Positions are ranked by worst case across all scenarios:

```
vulnerability_rank = rank by minimum value_change_pct across all scenarios
```

---

## Common Use Cases

### 1. Stress Test Portfolio

```bash
curl -X POST http://localhost:8006/scenarios/stress-test \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
    "scenario_type": "RATE_HIKE_200BPS",
    "save": true
  }'
```

### 2. Project Income Distribution

```bash
curl -X POST http://localhost:8006/scenarios/income-projection \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
    "horizon_months": 24
  }'
```

### 3. Rank Vulnerabilities

```bash
curl -X POST http://localhost:8006/scenarios/vulnerability \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
    "scenario_types": ["RATE_HIKE_200BPS", "MARKET_CORRECTION_20"]
  }'
```

### 4. View Scenario Library

```bash
curl http://localhost:8006/scenarios/library \
  -H "Authorization: Bearer $TOKEN"
```
