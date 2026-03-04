# Agent 05 — Tax Optimization Service
## Functional Specification

**Version:** 1.0.0
**Status:** Design Complete — Develop Pending
**Port:** 8005
**Monorepo Path:** `/Agentic/income-platform/src/tax-optimization-service/`
**Last Updated:** 2026-03-04
**Authors:** Alberto De Bernardi Pérez + Claude (Anthropic)

---

## 1. Purpose

Agent 05 accepts a portfolio payload containing income holdings across account types
and returns a complete tax optimization analysis. It calculates after-tax yield impact
per holding, recommends optimal account placement, identifies tax harvesting candidates,
and produces a portfolio-level tax efficiency score (0–100).

---

## 2. Scope (v1.1)

**In scope:**
- After-tax yield calculation per holding (TAXABLE / TRAD_IRA / ROTH / 401K)
- Account placement recommendations with estimated annual $ savings
- Tax harvesting candidate identification + wash-sale flag
- Portfolio tax efficiency score (0–100)
- Federal tax model only (Florida = 0% state tax)
- Read-only `user_preferences` DB access for tax profile defaults

**Out of scope (v1.1):**
- Portfolio DB reads/writes — payload-based per ADR-007
- State tax calculations
- Wash-sale rule enforcement (flag only, no blocking)
- Real-time harvesting triggers
- Tax form generation
- Agent 01 dependency — `current_price` supplied by caller in payload

---

## 3. API

### POST /analyze

Single endpoint returning all outputs.

**Request:**
```json
{
  "user_id": "uuid-optional",
  "holdings": [
    {
      "ticker": "JEPI",
      "account_type": "TAXABLE",
      "current_value": 25000.00,
      "annual_income": 1750.00,
      "current_price": 55.20,
      "cost_basis": 23000.00,
      "tax_efficiency": {
        "income_type": "ORDINARY",
        "tax_drag_pct": 0.22,
        "preferred_account": "ROTH"
      }
    }
  ],
  "tax_profile": {
    "ordinary_rate": 0.22,
    "qualified_rate": 0.15,
    "state_rate": 0.0
  }
}
```

Notes:
- `tax_efficiency` is optional — fetched from Agent 04 if absent
- `tax_profile` is optional — resolved from `user_preferences` then platform defaults
- `cost_basis` and `current_price` are optional — required only for harvesting analysis
- `user_id` is optional — used only to look up `user_preferences`

**Response:**
```json
{
  "portfolio_tax_score": 68,
  "annual_tax_drag_current": 3240.00,
  "annual_tax_drag_optimized": 1820.00,
  "annual_savings_potential": 1420.00,
  "after_tax_yield_table": [
    {
      "ticker": "JEPI",
      "gross_yield_pct": 7.0,
      "income_type": "ORDINARY",
      "tax_profile_source": "payload",
      "after_tax_yield_taxable": 5.46,
      "after_tax_yield_trad_ira": 7.0,
      "after_tax_yield_roth": 7.0,
      "current_account": "TAXABLE",
      "optimal_account": "ROTH"
    }
  ],
  "placement_recommendations": [
    {
      "ticker": "JEPI",
      "current_account": "TAXABLE",
      "recommended_account": "ROTH",
      "annual_savings_estimate": 385.00,
      "priority": "HIGH",
      "rationale": "ORDINARY income in taxable account eliminates 22% drag when moved to Roth"
    }
  ],
  "harvesting_candidates": [
    {
      "ticker": "VNQ",
      "current_price": 82.50,
      "cost_basis": 91.00,
      "unrealized_loss": -850.00,
      "estimated_tax_savings": 187.00,
      "wash_sale_warning": false
    }
  ],
  "service": "agent-05-tax-optimization",
  "version": "1.0.0",
  "timestamp": "2026-03-04T22:00:00Z"
}
```

### GET /health

```json
{
  "status": "healthy",
  "service": "agent-05-tax-optimization",
  "database": "connected",
  "port": 8005
}
```

---

## 4. Tax Model

### Income Type → Account Placement Priority

| Income Type | Taxable Drag | Preferred Account |
|---|---|---|
| ORDINARY_INCOME | 22%+ | ROTH > TRAD_IRA > TAXABLE |
| QUALIFIED_DIVIDEND | 15% | TAXABLE > ROTH > TRAD_IRA |
| RETURN_OF_CAPITAL | 0% (deferred) | TAXABLE |
| SHORT_TERM_GAIN | 22%+ | ROTH > TRAD_IRA > TAXABLE |

### Tax Profile Resolution Order
1. `tax_profile` block in request payload
2. `user_preferences` table (read by `user_id`)
3. Platform defaults: `ordinary=0.22, qualified=0.15, state=0.0`

### Agent 04 Fallback
If `tax_efficiency` absent from holding AND Agent 04 unavailable:
- Treat income as `ORDINARY_INCOME`
- Set `"tax_profile_source": "conservative_default"`
- Flag all affected holdings in response

---

## 5. Portfolio Tax Score

```
score = 100 - ((annual_tax_drag_current / total_annual_income) * 100)
Capped: 0–100
```

| Score | Interpretation |
|---|---|
| 80–100 | Well optimized |
| 60–79 | Moderate opportunity |
| 0–59 | High priority — significant tax drag |

---

## 6. Upstream Dependencies

| Service | Port | Usage | Fallback |
|---|---|---|---|
| Agent 04 — Asset Classification | 8004 | Fetch `tax_efficiency` if absent | Conservative ORDINARY_INCOME + flag |
| PostgreSQL | — | Read `user_preferences` by `user_id` | Platform defaults (22/15/0) |

**No Agent 01 dependency.** `current_price` supplied by caller in payload.
When portfolio DB is live (pre-Agent 08), price will come from daily batch-updated
portfolio positions (ADR-007 amendment).

---

## 7. Integration Points

| Direction | Agent | Data |
|---|---|---|
| Upstream consumer | Agent 04 (8004) | `tax_efficiency` enrichment |
| Future downstream | Agent 08 Rebalancing | After-tax yield table per holding |
| Future downstream | Agent 12 Proposal | Tax impact per recommended action |

---

## 8. Platform Alignment

| Principle | How Agent 05 Satisfies It |
|---|---|
| Capital preservation | Tax optimization preserves yield, not chases it |
| Proposal-based workflow | Returns recommendations only — never executes moves |
| User control | All placement changes are suggestions with $ savings shown |
| No silent blocking | Conservative fallback is explicitly flagged in response |
| Graceful degradation | Agent 04 down → result still returned with flags |
