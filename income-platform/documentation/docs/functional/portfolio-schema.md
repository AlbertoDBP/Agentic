# Functional Specification — Portfolio & Positions Schema

**Version:** 1.3.0
**Date:** 2026-03-09
**Status:** Migration Ready

---

## Purpose & Scope

Defines the persistence layer for portfolio and position data in the Income Fortress
Platform. Provides the shared database foundation that enables the `Asset × Position
× Portfolio` joint context required by Agents 07, 08, 09, 11, and 12.

---

## Responsibilities

1. Persist portfolio definitions (DRAFT / ACTIVE / ARCHIVED lifecycle)
2. Persist position records with average cost basis (PROPOSED / ACTIVE / CLOSED)
3. Store per-portfolio income targets and concentration constraints
4. Record all transactions (buy, sell, dividend, DRIP, fee, transfer)
5. Store dividend events with tax treatment metadata
6. Maintain rolling income metrics per portfolio per date
7. Store portfolio health scores with component breakdown
8. Provide the master securities registry (`symbol TEXT PK`)
9. Store per-ticker historical features (50+ factors including Chowder Number)
10. Store per-tenant user preferences (TTL, thresholds, grade minimums)

---

## Entity Chain

```
securities (symbol TEXT PK)           ← master ticker registry
    ↓ FK: symbol
positions (symbol TEXT FK,            ← one row per ticker per portfolio per status
           portfolio_id UUID FK)
    ↓ FK: portfolio_id
portfolios (id UUID PK)               ← one per account strategy
```

---

## Table Inventory

### Phase 0 — Foundation

| Table | Owner | Purpose |
|-------|-------|---------|
| `securities` | Agent 01 | Master ticker registry, auto-populated on discovery |
| `features_historical` | Agent 03 | 50+ scoring features per ticker per date |
| `user_preferences` | Platform | Per-tenant settings: TTL, thresholds, grade gates |

### Phase 1 — Asset Layer

| Table | Owner | Purpose |
|-------|-------|---------|
| `nav_snapshots` | Agent 10 / 01 | NAV + erosion tracking for ETFs |

### Phase 2 — Portfolio Layer

| Table | Owner | Purpose |
|-------|-------|---------|
| `accounts` | Agent 08 | Brokerage account containers |
| `portfolios` | Agent 08 | Strategy containers (DRAFT/ACTIVE/ARCHIVED) |
| `portfolio_constraints` | Agent 08 | Yield targets, position limits, quality gates |

### Phase 3 — Position Layer

| Table | Owner | Purpose |
|-------|-------|---------|
| `positions` | Agent 08 / 05 | Holdings (PROPOSED/ACTIVE/CLOSED), avg cost basis |
| `transactions` | Agent 05 | Full transaction log (buy/sell/div/drip) |
| `dividend_events` | Agent 05 | Dividend receipts with reinvestment tracking |

### Phase 4 — Metrics Layer

| Table | Owner | Purpose |
|-------|-------|---------|
| `portfolio_income_metrics` | Agent 09 | Income rollup, income gap, monthly schedule |
| `portfolio_health_scores` | Agent 11 | Composite health score + component breakdown |

---

## Key Interfaces

### securities — upsert on discovery (Agent 01)
```python
INSERT INTO platform_shared.securities (symbol, name, asset_type, ...)
VALUES ($1, $2, $3, ...)
ON CONFLICT (symbol) DO UPDATE SET
    name = EXCLUDED.name,
    updated_at = NOW()
```

### positions — UNIQUE constraint
```sql
UNIQUE (portfolio_id, symbol, status)
```
One ACTIVE row per ticker per portfolio. Status transitions:
- `PROPOSED` → `ACTIVE` on user approval
- `ACTIVE` → `CLOSED` on full sell

### income gap trigger (Agent 07 input)
```sql
SELECT * FROM platform_shared.portfolio_income_metrics
WHERE income_gap_annual < 0
  AND as_of_date = CURRENT_DATE
```

---

## Lifecycle Rules

### Portfolio Status
| Status | Description | Who transitions |
|--------|-------------|-----------------|
| DRAFT | Greenfield construction, positions PROPOSED | Agent 08 creates |
| ACTIVE | Live portfolio, positions ACTIVE | User approves |
| ARCHIVED | No longer managed | User or Agent 08 |

### Position Status
| Status | Description |
|--------|-------------|
| PROPOSED | Agent 08 / 12 proposal, awaiting user approval |
| ACTIVE | User-approved, tracked live |
| CLOSED | Fully sold, historical record retained |

---

## Constraints Design

`portfolio_constraints` has `UNIQUE (portfolio_id)` — one active constraint set per
portfolio. Version history kept in `previous_constraints JSONB` column.

Constraint hierarchy (all gates, most restrictive wins):
1. `exclude_nav_erosion_risk` — hard veto on NAV-eroding assets
2. `exclude_junk_bond_risk` — hard veto on speculative grade
3. `min_income_score_grade` — quality floor (A/B/C/D)
4. `max_position_pct` — concentration cap per ticker
5. `max_sector_pct` / `sector_limits` JSONB — sector concentration
6. `min_chowder_signal` — Chowder Number quality gate

---

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Position query latency | ≤ 100ms for single portfolio read |
| Income metrics freshness | Computed daily minimum; triggered by Agent 01 refresh |
| Health score freshness | TTL 24h default; user-configurable |
| Transaction integrity | All position updates atomic with transaction insert |
| Constraint versioning | Prior version preserved before any constraint update |

---

## Dependencies

- `platform_shared` schema must exist (owned by existing agents)
- PostgreSQL `gen_random_uuid()` function must be available (pgcrypto or pg 13+)
- Migration must run before any portfolio-layer agent deployment
