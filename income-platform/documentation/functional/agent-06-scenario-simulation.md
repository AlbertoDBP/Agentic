# Functional Specification — Agent 06: Scenario Simulation Service

**Version:** 1.0.0
**Date:** 2026-03-11
**Port:** 8006
**Status:** ✅ Built — Ready for deployment

---

## Purpose & Scope

Agent 06 answers one question: **"What happens to my portfolio income and value under stress?"**

It is a **read-only analytical service** — produces stress test results, income projections,
and vulnerability rankings only. Never executes trades or modifies positions.

Primary downstream consumer: Agent 12 (Proposal Agent) for pre-proposal stress validation.

---

## Responsibilities

1. Apply named market scenario shocks to portfolio positions (asset-class aware)
2. Project forward income using Monte Carlo simulation (P10/P50/P90)
3. Rank holdings by stress sensitivity across multiple scenarios
4. Surface custom scenario support for NL/LLM-driven what-if analysis
5. Persist stress results on explicit save request (with user label)
6. Expose predefined scenario library for UI and downstream agents

---

## Predefined Scenario Library

| Scenario | Description |
|----------|-------------|
| `RATE_HIKE_200BPS` | +2% rates — REIT/BDC/bond price hit, income compression |
| `MARKET_CORRECTION_20` | -20% equity — broad income resilience test |
| `RECESSION_MILD` | Earnings decline, dividend cuts — bonds benefit |
| `INFLATION_SPIKE` | +3% CPI — pricing power separates winners from losers |
| `CREDIT_STRESS` | Spread widening — mREIT/BDC income severely impacted |
| `CUSTOM` | User-defined shock parameters (NL/LLM compatible) |

All scenarios define `price_pct` and `income_pct` shocks for 7 asset classes:
EQUITY_REIT, MORTGAGE_REIT, BDC, COVERED_CALL_ETF, DIVIDEND_STOCK, BOND, PREFERRED_STOCK.

---

## Stress Model

**v1: Asset-Class Shock Table** (ADR-P12 — GLM deferred to v2)

Per-position calculation:
```
stressed_value  = current_value  × (1 + price_pct  / 100)
stressed_income = annual_income  × (1 + income_pct / 100)
```

Asset class resolved from `platform_shared.asset_classifications`.
Fallback: DIVIDEND_STOCK shocks for unclassified symbols.

---

## Income Projection Model

Monte Carlo N=1000, log-normal GBM per position:
```
simulated_income = base_income × exp(N(0, σ) − σ²/2)
σ = DEFAULT_YIELD_VOLATILITY × √(horizon_months / 12)
DEFAULT_YIELD_VOLATILITY = 5% annual
```

Returns P10/P50/P90 income bands for portfolio and per-position.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/scenarios/stress-test` | Run scenario against portfolio |
| POST | `/scenarios/income-projection` | Monte Carlo income projection |
| POST | `/scenarios/vulnerability` | Cross-scenario worst-case ranking |
| GET | `/scenarios/library` | List predefined scenarios + shock tables |
| GET | `/health` | Service health |

---

## Key Design Principles

- **Always portfolio-scoped** — requires `portfolio_id` from `platform_shared.portfolios`
- **Explicit save only** — results persisted only when `save: true` + optional `label`
- **Custom scenarios** — uniform shock structure, identical engine path as predefined
- **Read-only** — never writes to positions, transactions, or portfolios
- **No inter-agent HTTP** — reads `platform_shared` directly via asyncpg

---

## Data Sources

| Data | Table | Access |
|------|-------|--------|
| Positions | `platform_shared.positions` | asyncpg direct |
| Asset classifications | `platform_shared.asset_classifications` | asyncpg direct |
| Saved results | `platform_shared.scenario_results` | SQLAlchemy ORM |

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| PostgreSQL `platform_shared` | Position reads + result persistence |
| Agent 01 `/sync` | Populates `positions.annual_income` (prerequisite) |

No runtime dependency on other agents — all data read from DB.

---

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Stress test latency | ≤ 500ms p95 (DB read + shock calculation) |
| Income projection latency | ≤ 1s p95 (N=1000 Monte Carlo) |
| Vulnerability report latency | ≤ 2s p95 (multi-scenario) |
| Empty portfolio response | 422, not 500 |
| Unknown scenario | 422, not 500 |
| Result persistence | Only on explicit `save: true` |
