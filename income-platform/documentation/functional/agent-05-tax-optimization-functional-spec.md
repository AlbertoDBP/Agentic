# Agent 05 — Tax Optimization Service: Functional Specification

**Version:** 1.0.0
**Date:** 2026-03-09
**Status:** Complete — Tested
**Port:** 8005
**Service Path:** `src/tax-optimization-service/`

---

## 1. Purpose & Scope

Agent 05 provides tax intelligence for income-generating investments within the Income Fortress Platform. It determines how distributions from different asset classes are taxed, calculates after-tax yield, recommends optimal account placement to minimize tax drag, and identifies tax-loss harvesting opportunities.

This service is **read-only** with respect to the platform database and has **no dependency on Agent 01 (Market Data)**. All tax logic is rule-based using annually-maintained IRS bracket tables and state rate constants.

---

## 2. Responsibilities

- **Tax Profiling** — Map each asset class to its expected tax treatment (qualified dividend, ordinary income, return of capital, REIT distribution, MLP distribution, Section 1256 60/40, tax-exempt)
- **Tax Calculation** — Compute federal tax, state tax, and Net Investment Income Tax (NIIT) on a given distribution amount for a specific investor profile
- **Account Placement Optimization** — Recommend which account type (taxable, TRAD_IRA, ROTH_IRA, HSA, 401k) best suits each holding to minimize annual tax drag
- **Tax-Loss Harvesting Identification** — Scan positions for unrealized losses that qualify for harvesting, with wash-sale risk flagging
- **Asset Class Fallback** — When asset class is unknown, call Agent 04; if Agent 04 is unavailable, default to `ORDINARY_INCOME` with a degradation flag

---

## 3. Supported Asset Classes

| Asset Class | Primary Treatment | Section 199A | Section 1256 | K-1 Required |
|---|---|---|---|---|
| COVERED_CALL_ETF | ORDINARY_INCOME | No | Yes | No |
| DIVIDEND_STOCK | QUALIFIED_DIVIDEND | No | No | No |
| REIT | REIT_DISTRIBUTION | Yes | No | No |
| BOND_ETF | ORDINARY_INCOME | No | No | No |
| PREFERRED_STOCK | QUALIFIED_DIVIDEND | No | No | No |
| MLP | MLP_DISTRIBUTION | Yes | No | Yes |
| BDC | ORDINARY_INCOME | No | No | No |
| CLOSED_END_FUND | ORDINARY_INCOME | No | No | No |
| ORDINARY_INCOME | ORDINARY_INCOME | No | No | No |
| UNKNOWN | ORDINARY_INCOME | No | No | No |

---

## 4. Interfaces

### 4.1 Inputs

| Endpoint | Method | Key Inputs |
|---|---|---|
| `/health` | GET | — |
| `/tax/asset-classes` | GET | — |
| `/tax/profile/{symbol}` | GET/POST | symbol, asset_class (optional), filing_status, state_code, account_type, annual_income |
| `/tax/calculate/{symbol}` | GET/POST | symbol, distribution_amount, annual_income, filing_status, state_code, account_type, asset_class |
| `/tax/optimize` | POST | holdings[], annual_income, filing_status, state_code |
| `/tax/harvest` | POST | candidates[], annual_income, filing_status, state_code, wash_sale_check |

### 4.2 Outputs

All responses are JSON. Key response fields:

- **Tax Profile**: `asset_class`, `primary_tax_treatment`, `asset_class_fallback`, `qualified_dividend_eligible`, `section_199a_eligible`, `k1_required`, `notes[]`
- **Tax Calculation**: `gross_distribution`, `federal_tax_owed`, `state_tax_owed`, `niit_owed`, `net_distribution`, `effective_tax_rate`, `after_tax_yield_uplift`
- **Optimization**: `estimated_annual_savings`, `placement_recommendations[]`, each with `recommended_account`, `reason`, `estimated_annual_tax_savings`
- **Harvesting**: `total_harvestable_losses`, `total_estimated_tax_savings`, `opportunities[]` with `action` (HARVEST_NOW / MONITOR / HOLD / REVIEW_WASH_SALE)

---

## 5. Dependencies

| Dependency | Type | Required | Behavior if Unavailable |
|---|---|---|---|
| Agent 04 (Asset Classification, port 8004) | Soft | No | Defaults to ORDINARY_INCOME + `asset_class_fallback: true` flag |
| Platform PostgreSQL DB | Soft | No | `user_preferences` read skipped; service continues |
| External tax APIs | None | N/A | No external tax API calls — all rule-based |

---

## 6. Agent 04 Fallback Behavior

When `asset_class` is not provided in a request:

1. Agent 05 calls `GET {ASSET_CLASSIFICATION_URL}/classify/{symbol}` with a 3-second timeout
2. On success: uses the returned asset class, `asset_class_fallback: false`
3. On any failure (timeout, 4xx, 5xx, network error): defaults to `ORDINARY_INCOME`, sets `asset_class_fallback: true`
4. The fallback flag is always surfaced in the response — the platform never silently degrades

---

## 7. User Preferences Integration

Agent 05 reads the shared `user_preferences` table (read-only SELECT) to optionally pre-populate `filing_status`, `state_code`, `annual_income`, and `account_types` for a given `user_id`. This is an enhancement path — all endpoints function correctly without a DB connection.

---

## 8. Tax Logic Rules

### Federal Brackets (2024 IRS)
- 4 filing statuses: SINGLE, MARRIED_JOINT, MARRIED_SEPARATE, HEAD_OF_HOUSEHOLD
- Ordinary income: 10% / 12% / 22% / 24% / 32% / 35% / 37%
- Qualified dividends / LTCG: 0% / 15% / 20%

### NIIT (Net Investment Income Tax)
- 3.8% surcharge on investment income above threshold
- Thresholds: $200k (single), $250k (married joint), $125k (married separate)
- Does not apply to tax-exempt, return of capital, or MLP distributions

### State Rates
- 51 jurisdictions (50 states + DC) with flat approximation of top marginal rate
- 9 states with 0% income tax: AK, FL, NV, NH, SD, TN, TX, WA, WY

### Special Treatment Rules
- **Section 1256 (futures-based ETFs)**: 60% LTCG + 40% short-term blended rate
- **REIT/MLP distributions**: ~70% assumed return of capital, 30% ordinary income
- **Return of Capital**: $0 tax at distribution; reduces cost basis
- **Tax-exempt (muni bond ETFs)**: $0 federal tax

### Account Sheltering Rules
- Tax-sheltered accounts (TRAD_IRA, ROTH_IRA, HSA, 401k): $0 tax at distribution
- MLPs: **never** placed in IRAs (UBTI — Unrelated Business Taxable Income)
- High-ordinary-income assets (REITs, BDCs, Bond ETFs, Covered Call ETFs): shelter priority
- Tax-efficient assets (qualified dividend stocks, preferred stock): taxable account preferred

### Harvesting Rules
- Minimum loss threshold: $100 (below this: MONITOR action)
- Sheltered accounts: no benefit (HOLD action)
- Wash-sale window: 30 days — flags risk if holding period < 30 days
- All outputs are proposals only — no trades executed

---

## 9. Success Criteria

- All 8 endpoints return correct responses within 200ms for rule-based calls
- Agent 04 fallback activates within 3 seconds of timeout
- Tax calculations produce results consistent with 2024 IRS bracket tables
- Optimizer never recommends MLPs for IRA placement
- Harvester never recommends harvesting in sheltered accounts
- `asset_class_fallback: true` always present in response when fallback was used
- Service starts and serves all endpoints even when DB is unavailable

---

## 10. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Response time (rule-based endpoints) | < 200ms p99 |
| Response time (with Agent 04 callout) | < 3.5s p99 |
| Availability | 99.5% |
| Memory footprint | < 256MB |
| Concurrent requests | 10+ without degradation |
| Python version | 3.11 (Docker) / 3.13 (local dev) |

---

## 11. Out of Scope

- Actual trade execution
- Real-time tax rate updates (tables updated annually)
- Full state bracket schedules (uses top marginal rate approximation)
- UBTI quantification for MLPs in IRAs
- Foreign tax credit calculations
- AMT (Alternative Minimum Tax) calculations
- Cost basis lot tracking
