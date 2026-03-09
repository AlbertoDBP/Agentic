# Architecture Decision Records — Income Fortress Platform

**Version:** 1.3.0
**Last Updated:** 2026-03-09

---

## ADR-P01 — Monte Carlo NAV Erosion in Agent 03

**Status:** Accepted | **Date:** 2025-12-XX

### Context
Covered call ETFs (JEPI, XYLD, QYLD) pay high distributions but can exhibit NAV
erosion that destroys capital over time. Standard yield metrics miss this.

### Decision
Agent 03 runs Monte Carlo simulation (1,000 paths) projecting NAV trajectory over
3 years. Portfolios with >70% probability of >10% NAV decline receive a veto flag
regardless of yield score.

### Consequences
- Income score can be high while NAV veto blocks recommendation
- Requires 3yr price history for simulation inputs
- Adds ~300ms to scoring latency (acceptable at p95 ≤ 2s budget)

---

## ADR-P02 — Asset Classification Shared Detector

**Status:** Accepted | **Date:** 2026-01-XX

### Context
Multiple agents need to know asset class (dividend growth stock, covered call ETF,
BDC, REIT, bond CEF, etc.) to apply correct scoring rules.

### Decision
Shared detector at `src/shared/asset_class_detector/`. Agent 04 is primary owner.
Agent 03 auto-calls Agent 04 if `asset_class` is absent in payload.

### Consequences
- Single source of truth for asset classification logic
- Agent 03 latency increases when classification is missing and auto-call required

---

## ADR-P03 — Tax Efficiency as Parallel Output (0% Score Weight)

**Status:** Accepted | **Date:** 2026-01-XX

### Context
Tax treatment (qualified dividends, ROC, ordinary income) significantly affects
after-tax yield. Including it in the income score would conflate pre-tax income
quality with tax situation (which varies by investor).

### Decision
Agent 05 tax analysis runs in parallel. Output appears alongside income score but
contributes 0% to score calculation. Users see both; platform scores on pre-tax
income quality only.

### Consequences
- Income score is comparable across investors (tax-agnostic)
- User must consider tax output manually when making decisions

---

## ADR-P04 — Proposal-Only Architecture (No Auto-Execution)

**Status:** Accepted | **Date:** 2025-12-XX

### Context
Financial platforms that auto-execute trades create legal, compliance, and trust
risks. Income investors also prefer deliberate entry timing.

### Decision
No agent auto-executes any transaction. All agent outputs are proposals requiring
explicit user approval. The platform is a decision support system, not a trading bot.

### Consequences
- Platform cannot be registered as a robo-advisor
- User is always in the execution loop
- Transaction table is written only after user confirms

---

## ADR-P05 — Analyst Signal Storage Schema

**Status:** Accepted | **Date:** 2026-01-XX

### Context
Agent 02 ingests Seeking Alpha analyst recommendations. The platform must never
silently block analyst signals — if platform assessment conflicts with analyst
signal, user sees both with explicit override acknowledgment required.

### Decision
`analysts`, `analyst_articles`, `analyst_recommendations`, `analyst_accuracy_log`
tables store full signal provenance. Agent 12 dual-lens model presents both
analyst signal and platform assessment side-by-side.

### Consequences
- Analyst signal accuracy tracked over time via `analyst_accuracy_log`
- No silent recommendation filtering

---

## ADR-P06 — Portfolio Health Score TTL Strategy

**Status:** Accepted | **Date:** 2026-03-09

### Context
Health scores are expensive to compute (requires portfolio rollup + all position
rescoring). Recomputing on every request is infeasible.

### Decision
Health score TTL defaults to 24 hours, user-configurable via `user_preferences`.
Price cache TTL is linked to the same TTL. Both expire together. Agent 01 price
refresh triggers health score staleness flag.

### Consequences
- Health score may be up to 24h stale between refreshes
- Same TTL for price and health score simplifies cache invalidation logic

---

## ADR-P07 — Finnhub as 4th Credit Rating Provider

**Status:** Accepted | **Date:** 2026-03-09

### Context
`credit_rating` returned NULL from all three existing providers (Polygon.io, FMP,
yfinance). The Agent 03 BBB- quality gate was blocked by this gap.

### Decision
Finnhub (free API key obtained) added as 4th provider in Agent 01 provider cascade.
SEC EDGAR interest coverage ratio added as proxy fallback when credit rating
unavailable from all 4 providers.

Credit quality proxy mapping:
- interest_coverage ≥ 3.0 → INVESTMENT_GRADE
- interest_coverage 1.5–2.9 → BORDERLINE
- interest_coverage < 1.5 → SPECULATIVE_GRADE

### Consequences
- `credit_rating` field now populated for most investment-grade issuers
- SEC EDGAR proxy is a lagging indicator (annual filings, 90-day delay)
- BBB- gate in Agent 03 unblocked

---

## ADR-P08 — Income Gap as Autonomous Agent 07 Trigger

**Status:** Accepted | **Date:** 2026-03-09

### Context
Agent 07 (Income Gap Detector) needs a reliable, low-latency trigger. Options:
polling, event-based (Postgres NOTIFY), or query-based.

### Decision
Agent 07 reads `portfolio_income_metrics` via partial index on `income_gap_annual < 0`.
Triggered by Agent 09 after each income metrics computation. No polling required.

Partial index:
```sql
CREATE INDEX idx_income_gap_shortfall
    ON platform_shared.portfolio_income_metrics (portfolio_id, income_gap_annual)
    WHERE income_gap_annual < 0;
```

### Consequences
- Agent 07 fires only when there is an actual shortfall (no false triggers)
- Index keeps gap detection query O(shortfall count) not O(portfolio count)

---

## ADR-P09 — Symbol TEXT as Primary Key (v1), UUID Migration Path (v2)

**Status:** Accepted | **Date:** 2026-03-09

### Context
Production DB inspection revealed `platform_shared.securities` does not exist.
All deployed agents (01–05) use `symbol TEXT` — no UUID master registry.
Two options: (A) UUID PK with seeding, (B) TEXT PK consistent with deployed agents.

### Decision
**Option B — symbol TEXT PK for v1.**

```sql
securities(symbol TEXT PK)
    → positions(symbol TEXT FK, portfolio_id UUID FK)
    → portfolios(id UUID PK)
```

No seeding step required. `securities` rows inserted on-demand by Agent 01.

### v2 Migration Path
Triggered when: universe > 500 tickers OR international securities (non-unique
symbols across exchanges) required.

Steps:
1. Add `id UUID DEFAULT gen_random_uuid()` to securities
2. Add `security_id UUID` FK columns to child tables
3. Backfill UUIDs from symbol join
4. Add NOT NULL + FK constraints
5. Swap PK from symbol to id
6. Keep symbol as UNIQUE index for backward compat
7. Drop symbol FK columns from child tables

### Consequences
- All agent contracts use `symbol: str`, not `security_id: UUID`
- JOIN pattern: `JOIN platform_shared.securities s ON s.symbol = p.symbol`
- ON CONFLICT DO NOTHING upsert for auto-discovery

---

## ADR-P10 — Positions: Average Cost Basis v1, Tax Lot v2

**Status:** Accepted | **Date:** 2026-03-09

### Context
Two position granularity options: per-tax-lot (precise TLH) vs average cost basis
(simpler, matches broker display). v1 targets income optimization, not TLH.

### Decision
**Average cost basis for v1.**

```sql
UNIQUE (portfolio_id, symbol, status)
```
One row per symbol per portfolio per status. Full transaction history retained in
`transactions` table for retroactive lot reconstruction.

### v2 Migration Path
Triggered when Agent 05 v2 lot-level tax optimization is designed.

```sql
CREATE TABLE platform_shared.tax_lots (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES platform_shared.positions(id),
    portfolio_id UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    symbol      TEXT NOT NULL,
    lot_date    DATE NOT NULL,
    quantity    DECIMAL(15,4) NOT NULL,
    cost_basis  DECIMAL(12,4) NOT NULL,
    is_long_term BOOLEAN,
    wash_sale_flag BOOLEAN DEFAULT FALSE,
    closed_date DATE
);
```

`positions` table becomes aggregate view; `tax_lots` table owns lot-level detail.

### Consequences
- `transactions` is source of truth for lot reconstruction
- Wash sale detection in v1 operates at symbol + 30-day window
- `acquired_date` on positions = date of first purchase (oldest lot approximation)
