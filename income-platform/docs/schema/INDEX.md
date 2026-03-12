# Income Platform Schema Documentation Index

Complete reference guide for the Income Fortress platform data model.

---

## Documentation Files

### 1. [README.md](./README.md) — Start Here
**Overview of the entire data architecture**

- Platform architecture (single PostgreSQL database, `platform_shared` schema)
- Service ownership model (which service owns which tables)
- Read access patterns (who consumes whose data)
- Table inventory with descriptions
- Critical dependencies and data flow order
- Deployment & migration instructions
- Caching & validity strategies
- Performance considerations

**Best for:** Getting oriented, understanding the big picture

---

### 2. [core-tables.md](./core-tables.md) — Detailed Reference
**Complete column definitions for all 18+ tables**

Tables documented:
- **Market Data Domain:** `price_history`, `market_data_daily`, `covered_call_etf_metrics`
- **Income Scoring Domain:** `scoring_runs`, `quality_gate_results`, `income_scores`
- **Asset Classification Domain:** `asset_class_rules`, `asset_classifications`, `classification_overrides`
- **Analyst Intelligence Domain:** `analysts`, `analyst_articles`, `analyst_recommendations`, `analyst_accuracy_log`, `credit_overrides`
- **Scenario Simulation Domain:** `scenario_results`
- **NAV Erosion Domain:** `nav_erosion_analysis_cache`, `nav_erosion_data_collection_log`

**For each table:**
- Column names, types, nullability, defaults
- Indexes and their purposes
- Constraints (PKs, FKs, UNIQUEs, CHECKs)
- Service ownership and read access
- Typical query patterns
- Notes on usage

**Best for:** Understanding table structure, writing queries, debugging data issues

---

### 3. [relationships.md](./relationships.md) — Connections & Data Flow
**Foreign keys, data dependencies, and how tables relate**

- Foreign key relationships with diagrams
- Data flow pipeline (batch scoring, intelligence, simulation)
- Read access patterns by service
- Common query patterns (with SQL)
- Entity relationship diagram (Mermaid)
- Data freshness & cache validity
- Transactional integrity guarantees
- Performance optimization tips

**Best for:** Understanding data flow, designing new features, optimizing queries

---

### 4. [queries.md](./queries.md) — Copy-Paste SQL
**Ready-to-use SELECT queries for common tasks**

Organized by domain:
- Income scoring queries
- Asset classification queries
- Analyst intelligence queries
- Market data queries
- NAV erosion queries
- Scenario simulation queries
- Admin & maintenance queries
- Performance analysis queries

**All queries are:**
- Tested and working
- Documented with comments
- Filtering for validity (caches, expiry)
- Using proper indexes

**Best for:** Writing reports, building dashboards, quick data exploration

---

## Quick Navigation

### I want to...

**Understand the overall data structure**
→ Start with [README.md](./README.md)

**See the exact column names and types**
→ Go to [core-tables.md](./core-tables.md)

**Understand how tables connect to each other**
→ Read [relationships.md](./relationships.md)

**Write a SQL query**
→ Check [queries.md](./queries.md) for examples, adapt as needed

**Debug why data is missing**
→ Check [core-tables.md](./core-tables.md) for nullable columns and defaults
→ Check [relationships.md](./relationships.md) for dependencies
→ Use queries in [queries.md](./queries.md) to inspect tables

**Add a new table**
→ Read [README.md](./README.md) service ownership model
→ Update migration script in your service
→ Document in [core-tables.md](./core-tables.md)
→ Update relationships in [relationships.md](./relationships.md)

**Optimize a slow query**
→ Check [relationships.md](./relationships.md) performance tips
→ Look at indexed columns in [core-tables.md](./core-tables.md)
→ Run EXPLAIN ANALYZE using patterns in [queries.md](./queries.md)

---

## Table Quick Reference

### By Domain

#### Market Data (Agent 01)
| Table | Rows | Key Columns | Owner | Scope |
|-------|------|------------|-------|-------|
| `price_history` | 100K–1M | symbol, date | Agent 01 | OHLCV bars per symbol per date |
| `market_data_daily` | 10K–100K | ticker_symbol, trade_date | Agent 01 | Daily price snapshots (legacy) |
| `covered_call_etf_metrics` | 10K–50K | ticker, data_date | NAV Service | ETF metrics for erosion analysis |

#### Income Scoring (Agent 03)
| Table | Rows | Key Columns | Owner | Scope |
|-------|------|------------|-------|-------|
| `scoring_runs` | 100–1K | run_type, status | Agent 03 | Audit log of scoring batches |
| `quality_gate_results` | 500–5K | ticker, evaluated_at | Agent 03 | Pass/fail gate evaluations |
| `income_scores` | 1K–10K | ticker, scored_at | Agent 03 | Income scores 0–100 |

#### Asset Classification (Agent 04)
| Table | Rows | Key Columns | Owner | Scope |
|-------|------|------------|-------|-------|
| `asset_class_rules` | 20–100 | asset_class, rule_type | Agent 04 | Rule engine definitions |
| `asset_classifications` | 1K–5K | ticker, classified_at | Agent 04 | Classification results |
| `classification_overrides` | 10–100 | ticker | Agent 04 | Manual overrides |

#### Analyst Intelligence (Agent 02)
| Table | Rows | Key Columns | Owner | Scope |
|-------|------|------------|-------|-------|
| `analysts` | 50–500 | sa_publishing_id | Agent 02 | Analyst profiles |
| `analyst_articles` | 10K–100K | analyst_id, published_at | Agent 02 | Ingested articles |
| `analyst_recommendations` | 50K–500K | ticker, is_active, decay_weight | Agent 02 | Extracted recommendations |
| `analyst_accuracy_log` | 50K–500K | analyst_id, ticker | Agent 02 | Backtest outcomes |
| `credit_overrides` | 10–100 | ticker | Agent 02 | Manual credit grades |

#### Scenario Simulation (Agent 06)
| Table | Rows | Key Columns | Owner | Scope |
|-------|------|------------|-------|-------|
| `scenario_results` | 100–10K | portfolio_id, created_at | Agent 06 | Scenario projections |

#### NAV Erosion
| Table | Rows | Key Columns | Owner | Scope |
|-------|------|------------|-------|-------|
| `nav_erosion_analysis_cache` | 100–1K | ticker, valid_until | NAV Service | Cached Monte Carlo results |
| `nav_erosion_data_collection_log` | 1K–10K | ticker, collection_date | NAV Service | Data collection audit |

### By Schema

**`platform_shared`** (main application schema)
- scoring_runs
- quality_gate_results
- income_scores
- asset_class_rules
- asset_classifications
- classification_overrides
- analysts
- analyst_articles
- analyst_recommendations
- analyst_accuracy_log
- credit_overrides
- scenario_results

**`public`** (NAV erosion analysis)
- covered_call_etf_metrics
- nav_erosion_analysis_cache
- nav_erosion_data_collection_log

---

## Data Relationships at a Glance

```
BATCH SCORING FLOW:
  scoring_runs (parent)
    ├→ quality_gate_results (one per ticker)
    │   └→ income_scores (if gate passed)
    └→ metadata + stats

ANALYST INTELLIGENCE FLOW:
  analysts (profiles)
    ├→ analyst_articles (publications)
    │   └→ analyst_recommendations (ticker-level)
    └→ analyst_accuracy_log (backtest results)

CLASSIFICATION FLOW:
  asset_class_rules (definitions)
    └→ asset_classifications (results)
    └→ classification_overrides (manual)

SCENARIO SIMULATION:
  income_scores + asset_classifications (input)
    └→ scenario_results (output)
```

---

## Service Data Ownership

```
Agent 01 (Market Data)      → price_history, market_data_daily
Agent 02 (Newsletter)       → analysts, analyst_articles, analyst_recommendations,
                               analyst_accuracy_log, credit_overrides
Agent 03 (Income Scoring)   → scoring_runs, quality_gate_results, income_scores
Agent 04 (Classification)   → asset_class_rules, asset_classifications,
                               classification_overrides
Agent 05 (Tax Optimization) → (stateless, no writes)
Agent 06 (Scenario Sim)     → scenario_results
NAV Erosion Service         → covered_call_etf_metrics, nav_erosion_analysis_cache,
                               nav_erosion_data_collection_log
```

---

## Key Concepts

### Quality Gate
A VETO-level check. If a ticker **fails** the quality gate, it is excluded from scoring entirely, regardless of other factors. Checked before income score computation.

**Checks:** Credit rating, FCF history, dividend history, ETF AUM, REIT coverage

### Income Score Components
Three components sum to 0–100, then adjusted by NAV erosion penalty:
- **Valuation Yield Score (0–40):** Yield attractiveness
- **Financial Durability Score (0–40):** Payout safety, debt, volatility
- **Technical Entry Score (0–20):** RSI, support proximity
- **NAV Erosion Penalty (0–30):** Applied only to covered call ETFs

**Final Score = Total - Penalty** (floor 0)

### Asset Classification
Determines tax treatment and characteristics. Can be automatic (rule engine) or manual (override). Includes confidence score.

### Analyst Recommendations
Tagged with decay_weight (staleness) and platform_alignment (agreement with platform scores). Automatically expire after 90 days. Can be superseded when analyst changes view.

### Cache Validity
Many tables cache results to avoid expensive recomputation:
- Quality gates: 24h
- Income scores: 24h
- Classifications: 30 days
- Analyst recs: 90 days (auto-expire)
- NAV erosion: 7 days

Always check `valid_until` or `expires_at` in queries.

---

## Common Patterns

### Consensus Query (Multiple Analysts)
```sql
SELECT ticker,
  AVG(sentiment_score) as avg_sentiment,
  COUNT(*) as analyst_count
FROM analyst_recommendations
WHERE ticker = 'JEPI' AND is_active AND expires_at > NOW()
GROUP BY ticker;
```

### Latest Valid Result
```sql
SELECT * FROM income_scores
WHERE ticker = 'JEPI'
  AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY scored_at DESC LIMIT 1;
```

### Explainability Breakdown
```sql
SELECT
  total_score,
  valuation_yield_score,
  financial_durability_score,
  technical_entry_score,
  nav_erosion_penalty,
  factor_details,  -- JSON with breakdown
  nav_erosion_details  -- JSON with erosion analysis
FROM income_scores WHERE ticker = 'JEPI';
```

---

## Migration Commands

```bash
# Agent 01 — Market Data (Alembic)
cd src/market-data-service
alembic upgrade head

# Agent 02 — Newsletter (Python script)
cd src/agent-02-newsletter-ingestion
python scripts/migrate.py

# Agent 03 — Income Scoring (Python script)
cd src/income-scoring-service
python scripts/migrate.py

# Agent 04 — Classification (Python script)
cd src/asset-classification-service
python scripts/migrate.py

# Agent 06 — Scenario Simulation (Python script)
cd src/scenario-simulation-service
python scripts/migrate.py
```

All migrations are **idempotent** and safe to re-run.

---

## Support & Troubleshooting

### Missing Data?
1. Check table exists: `SELECT COUNT(*) FROM platform_shared.<table>;`
2. Verify cache validity: Check `valid_until` / `expires_at` columns
3. Verify service ownership: Did the right agent write the data?
4. Check dependencies: Was upstream data generated first?

### Slow Queries?
1. Check indexes in [core-tables.md](./core-tables.md)
2. Use EXPLAIN ANALYZE: See [queries.md](./queries.md) examples
3. Filter by indexed columns (ticker, date, is_active, etc.)
4. Avoid full table scans without time ranges

### Data Quality Issues?
1. Check `data_quality_score` in tables that have it
2. Look at completeness metrics: `data_completeness_pct`
3. Review `fail_reasons` for quality gates
4. Check `metadata` JSONB for additional context

---

## Contributing

When adding new documentation:
1. Update [core-tables.md](./core-tables.md) for new tables
2. Update [relationships.md](./relationships.md) for new FKs
3. Add example queries to [queries.md](./queries.md)
4. Keep this INDEX.md in sync

---

## Version Info

- **Platform Schema Version:** 3.0
- **Database:** PostgreSQL 13+
- **Extensions Required:** uuid-ossp, pgvector (optional), pg_trgm (optional)
- **Last Updated:** 2026-03-12
- **Maintainer:** Documentation Team

---

## File Directory

```
income-platform/docs/schema/
├── INDEX.md ........................ This file (navigation & overview)
├── README.md ....................... Architecture & ownership
├── core-tables.md .................. Detailed column reference
├── relationships.md ................ FKs & data flow
└── queries.md ...................... SQL examples
```

---

**Start reading:** [README.md](./README.md)
