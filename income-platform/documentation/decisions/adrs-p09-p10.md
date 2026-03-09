# ADR-P09 — Symbol TEXT as Primary Key (v1), UUID Migration Path (v2)
**Status:** Accepted
**Date:** 2026-03-09

## Context

During Review, production DB inspection revealed that `platform_shared.securities`
does not exist. All deployed agents (01–05) reference tickers as plain `TEXT`
symbols — there is no UUID master registry. The original DDL assumed a
`securities(id UUID PK)` table that was never created.

Two options were evaluated:
- **Option A:** Create `securities(id UUID PK)`, seed with known universe, migrate
  all agent tables to UUID FK
- **Option B:** Create `securities(symbol TEXT PK)`, consistent with all deployed
  agents, defer UUID migration to v2

## Decision

**Option B — symbol TEXT PK for v1.**

```sql
-- v1 entity chain:
securities(symbol TEXT PK)
    ↓
positions(symbol TEXT FK, portfolio_id UUID FK)
    ↓
portfolios(id UUID PK)
```

## Rationale

- All deployed agents use `symbol TEXT` — consistency prevents a multi-service
  refactor as a prerequisite for the portfolio layer
- No seeding step required — `securities` rows can be inserted on-demand when
  new tickers are tracked
- UUID purity is an engineering preference, not a functional requirement at this
  scale
- Delaying UUID migration until v2 allows the full agent fleet to be built first,
  then migrated in one coordinated pass

## v2 Migration Path (for ADR reference)

When UUID migration is warranted:

```sql
-- Step 1: Add UUID column to securities
ALTER TABLE platform_shared.securities
    ADD COLUMN id UUID DEFAULT gen_random_uuid();

-- Step 2: Add security_id FK columns to child tables
ALTER TABLE platform_shared.positions
    ADD COLUMN security_id UUID;
ALTER TABLE platform_shared.transactions
    ADD COLUMN security_id UUID;
-- ... repeat for all tables with symbol FK

-- Step 3: Backfill UUIDs
UPDATE platform_shared.positions p
    SET security_id = s.id
    FROM platform_shared.securities s
    WHERE p.symbol = s.symbol;
-- ... repeat for all tables

-- Step 4: Add NOT NULL constraints + FK constraints
-- Step 5: Make securities.id the PK (swap with symbol)
-- Step 6: Drop symbol FK columns from child tables
-- Step 7: Keep symbol as UNIQUE index for backward compat
```

**Trigger for v2 migration:** When multi-asset-class universe exceeds 500 tickers
OR when international securities (non-unique symbols across exchanges) are added.

## Consequences

- All agent input contracts use `symbol: str` not `security_id: UUID`
- JOIN pattern: `JOIN platform_shared.securities s ON s.symbol = p.symbol`
- No seeding required at migration time — `ON CONFLICT DO NOTHING` upsert pattern
  when agents encounter new tickers
- `securities` table auto-populated as agents discover new symbols

---

# ADR-P10 — Positions Entity: Average Cost Basis v1, Tax Lot v2

**Status:** Accepted
**Date:** 2026-03-09

## Context

Two designs for the `positions` table were considered:

**Per-tax-lot:** One row per purchase event. Enables precise tax-loss harvesting,
wash sale detection at lot level, and accurate holding period calculations.

**Average cost basis:** One row per symbol per portfolio. Simpler queries, matches
how most retail brokers display positions, sufficient for v1 income optimization.

## Decision

**Average cost basis for v1.** One row per (portfolio_id, symbol, status).

```sql
UNIQUE (portfolio_id, symbol, status)
```

## Rationale

- v1 targets income optimization — yield, income gap, portfolio health
- Tax-loss harvesting at lot level is a v2 feature (Agent 05 v2)
- `transactions` table retains full buy/sell history — lot reconstruction
  is possible retroactively from transaction log
- Simpler JOIN patterns for Agents 06, 08, 09 which query all positions
- Consistent with how Alpaca, Schwab, and most broker APIs report positions

## v2 Migration Path

```sql
-- Add tax_lots table (does not modify positions table)
CREATE TABLE platform_shared.tax_lots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id     UUID NOT NULL REFERENCES platform_shared.positions(id),
    portfolio_id    UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    symbol          TEXT NOT NULL,
    lot_date        DATE NOT NULL,           -- acquisition date for this lot
    quantity        DECIMAL(15,4) NOT NULL,
    cost_basis      DECIMAL(12,4) NOT NULL,  -- per share for this lot
    total_cost      DECIMAL(15,2) NOT NULL,
    holding_period_days INTEGER,
    is_long_term    BOOLEAN,                 -- > 365 days
    wash_sale_flag  BOOLEAN DEFAULT FALSE,
    closed_date     DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- positions table becomes the aggregate view:
-- positions.avg_cost_basis = weighted avg of open lot cost bases
-- positions.quantity = sum of open lot quantities
-- Agent 05 v2 reads tax_lots directly for harvest candidates
```

**Trigger for v2:** When Agent 05 v2 (lot-level tax optimization) is designed,
or when a user requests specific lot identification for a sell transaction.

## Consequences

- `transactions` table is the source of truth for lot reconstruction
- Wash sale detection in v1 operates at symbol + 30-day window (not lot-level)
- Agent 05 v1 tax optimization is position-level (already deployed, no change)
- `acquired_date` on positions = date of first purchase (oldest lot approximation)
- Average cost basis is accurate for income calculations (YOC, yield metrics)
