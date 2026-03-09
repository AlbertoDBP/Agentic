# Implementation Specification — Portfolio & Positions Schema

**Version:** 1.3.0
**Date:** 2026-03-09
**Status:** Migration Ready — Run before any portfolio-layer agent deployment

---

## Technical Design

### Migration Strategy
- Tool: asyncpg (consistent with all deployed agents)
- Pattern: phased execution, `IF NOT EXISTS` guards, full rollback on error
- Run from service root: `python3 scripts/migrate.py`
- DB SSL: strip `?sslmode=require`, pass `connect_args={"ssl": "require"}`

### Phase Execution Order
```
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4
```
Each phase depends on the previous. Failure at any phase rolls back entire
transaction.

### FK Convention
Symbol TEXT FK throughout (ADR-P09). No seeding required — `securities` rows
inserted on-demand via `ON CONFLICT DO NOTHING` upsert.

---

## File Location

```
src/portfolio-positions-schema/
├── app/
│   └── __init__.py
└── scripts/
    └── migrate.py
```

Migration script path: `src/portfolio-positions-schema/scripts/migrate.py`

---

## Migration Script Details

```python
# Run from service root
import sys
sys.path.insert(0, "..")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if "?sslmode=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?sslmode=require")[0]

conn = await asyncpg.connect(DATABASE_URL, ssl="require")
```

### Phase 0 Tables

**`securities`**
- PK: `symbol TEXT`
- Auto-populated by Agent 01 on ticker discovery via ON CONFLICT upsert
- Contains ETF-specific fields: `expense_ratio`, `aum_millions`, `inception_date`

**`features_historical`**
- PK: `UUID`, UNIQUE `(symbol, as_of_date)`
- FK: `symbol REFERENCES securities(symbol)`
- Includes Amendment A1 columns: `yield_5yr_avg`, `chowder_number`
- `raw_features JSONB` stores full 50+ feature vector

**`user_preferences`**
- PK: `UUID`, UNIQUE `(tenant_id, preference_key)`
- Default keys (inserted on tenant creation, not in migration):
  - `data_freshness_hours` → `'24'` (integer)
  - `income_gap_trigger_pct` → `'5.0'` (decimal)
  - `min_score_grade` → `'B'` (string)
  - `dca_threshold_usd` → `'2000'` (integer)

### Phase 3 Critical Pattern

`positions` UNIQUE constraint: `(portfolio_id, symbol, status)`

Status transition implementation:
```python
# PROPOSED → ACTIVE: update existing row
await conn.execute("""
    UPDATE platform_shared.positions
    SET status = 'ACTIVE', updated_at = NOW()
    WHERE portfolio_id = $1 AND symbol = $2 AND status = 'PROPOSED'
""", portfolio_id, symbol)

# ACTIVE → CLOSED: update + set closed_date
await conn.execute("""
    UPDATE platform_shared.positions
    SET status = 'CLOSED', closed_date = CURRENT_DATE, updated_at = NOW()
    WHERE portfolio_id = $1 AND symbol = $2 AND status = 'ACTIVE'
""", portfolio_id, symbol)
```

### Phase 4 Income Gap Index

Critical partial index for Agent 07 trigger:
```sql
CREATE INDEX IF NOT EXISTS idx_income_gap_shortfall
    ON platform_shared.portfolio_income_metrics (portfolio_id, income_gap_annual)
    WHERE income_gap_annual < 0;
```

---

## Production Run Command

```bash
ssh -i ~/.ssh/id_ed25519 root@legatoinvest.com \
  "cd /opt/Agentic/income-platform/src/portfolio-positions-schema && \
   DATABASE_URL=\$DATABASE_URL python3 scripts/migrate.py"
```

---

## Verification Query (post-migration)

```python
# Run via any deployed agent container
tables = await conn.fetch("""
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'platform_shared'
    ORDER BY tablename
""")
# Expected: 22+ tables including all 12 new ones
```

---

## Testing & Acceptance

### Unit Tests

| Test | Expected |
|------|----------|
| `securities` INSERT + upsert | ON CONFLICT updates name, asset_type |
| `positions` UNIQUE constraint | Second ACTIVE row for same (portfolio, symbol) raises |
| `portfolio_constraints` UNIQUE | Second constraint for same portfolio raises |
| Status transition PROPOSED→ACTIVE | Row updated, no duplicate created |
| FK enforcement | Position with unknown symbol raises FK violation |

### Integration Tests

| Test | Expected |
|------|----------|
| Full migration run on clean schema | All 12 tables created, all indexes present |
| Re-run migration (idempotent) | IF NOT EXISTS guards — no error, no data loss |
| Rollback on phase failure | No partial state committed |
| Agent 01 securities upsert | New tickers inserted; known tickers updated |

### Acceptance Criteria (Testable)

- [ ] Migration completes in < 30 seconds on production DB
- [ ] All 12 tables exist in `platform_shared` after migration
- [ ] All partial indexes visible in `pg_indexes`
- [ ] `UNIQUE (portfolio_id, symbol, status)` enforced on `positions`
- [ ] `UNIQUE (portfolio_id)` enforced on `portfolio_constraints`
- [ ] Agent 01 can upsert to `securities` without error
- [ ] Agent 03 can write to `features_historical` without error
- [ ] `income_gap_annual < 0` partial index used by Agent 07 query (EXPLAIN ANALYZE)

### Known Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Migration run twice | IF NOT EXISTS guards make it idempotent |
| securities row missing when position inserted | FK violation — Agent 01 must upsert securities first |
| portfolio in DRAFT status queried by Agent 09 | Agent 09 should filter `status = 'ACTIVE'` only |
| Two ACTIVE positions for same (portfolio, symbol) | UNIQUE constraint prevents this |
| features_historical with NULL chowder (< 5yr history) | chowder_signal = 'INSUFFICIENT_DATA' |

---

## Implementation Notes

- The `platform_shared` schema already exists — migration does NOT create it
- `gen_random_uuid()` requires pg 13+ or pgcrypto extension — both available on DO
- All DECIMAL types use sufficient precision for financial data (no FLOAT)
- `TEXT[]` used for `flags` on `portfolio_health_scores` — simple array, no join table
- `JSONB` used for `monthly_income_schedule`, `sector_limits`, `raw_features` —
  flexible enough for future schema changes without migration
