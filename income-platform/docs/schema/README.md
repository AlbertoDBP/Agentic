# Income Platform — Data Model & Schema Reference

## Overview

The Income Fortress platform uses a single **PostgreSQL database** with a shared schema (`platform_shared`) to coordinate data between multiple microservices. All persistent data is stored here; services communicate asynchronously via this database rather than direct API calls.

**Schema name:** `platform_shared`

**Extensions required:**
- `uuid-ossp` — for UUID generation
- `pgvector` — for semantic embeddings (Agent 02 Newsletter Ingestion)

---

## Data Architecture

The platform is organized into **logical domains**:

1. **Market Data** — Historical price bars, daily OHLCV data
2. **Income Scoring** — Quality gates, income scores, and scoring runs
3. **Asset Classification** — Ticker → asset class rules and classifications
4. **Analyst Intelligence** — Analyst profiles, recommendations, accuracy tracking
5. **NAV Erosion Analysis** — Covered call ETF metrics and risk modeling
6. **Scenario Simulation** — Portfolio scenario results
7. **Portfolio Management** — Holdings, transactions, snapshots (in V3.0 schema)

---

## Service Ownership Model

### Write Access (Owns & Manages Tables)

| Service | Tables | Purpose |
|---------|--------|---------|
| **Agent 01 — Market Data Service** | `market_data_daily`, `price_history` | Historical price data, OHLCV bars from external providers |
| **Agent 02 — Newsletter Ingestion** | `analysts`, `analyst_articles`, `analyst_recommendations`, `analyst_accuracy_log`, `credit_overrides` | Analyst intelligence, recommendations, accuracy scoring |
| **Agent 03 — Income Scoring** | `income_scores`, `quality_gate_results`, `scoring_runs` | Income scores, quality gates, audit logs |
| **Agent 04 — Asset Classification** | `asset_classifications`, `asset_class_rules`, `classification_overrides` | Asset class detection, rule engine results |
| **Agent 05 — Tax Optimization** | None (stateless service) | Computes tax strategies from existing data |
| **Agent 06 — Scenario Simulation** | `scenario_results` | Portfolio scenario simulation outcomes |
| **NAV Erosion Analysis** | `covered_call_etf_metrics`, `nav_erosion_analysis_cache`, `nav_erosion_data_collection_log` | Covered call ETF NAV degradation metrics |

### Read Access (Consumes Data)

| Service | Reads From | Purpose |
|---------|-----------|---------|
| **Agent 03 — Income Scoring** | `market_data_daily`, `price_history`, `asset_classifications` | Fetch fundamentals, historical prices, asset class for quality gates |
| **Agent 04 — Asset Classification** | `market_data_daily` | Fetch sector, market cap, fundamentals for classification |
| **Agent 05 — Tax Optimization** | `asset_classifications`, `income_scores` | Lookup tax treatment, yields for optimization |
| **Agent 06 — Scenario Simulation** | `income_scores`, `asset_classifications` | Fetch income projections for scenario modeling |
| **UI / Dashboards** | All tables | Display scores, recommendations, portfolios, intelligence |

---

## Table Inventory

### Market Data Domain

| Table | Schema | Owner | Purpose | Rows |
|-------|--------|-------|---------|------|
| `price_history` | `platform_shared` | Agent 01 | Historical OHLCV bars (per day, per symbol) | 100K–1M |
| `market_data_daily` | `platform_shared` | Agent 01 | Daily price snapshots (legacy/platform-wide) | 10K–100K |
| `covered_call_etf_metrics` | `public` | NAV Analysis | Historical metrics for covered call ETFs | 10K–50K |

### Income Scoring Domain

| Table | Schema | Owner | Purpose | Rows |
|-------|--------|-------|---------|------|
| `income_scores` | `platform_shared` | Agent 03 | Income scores (0–100, per ticker, per run) | 1K–10K |
| `quality_gate_results` | `platform_shared` | Agent 03 | Pass/fail quality gate evaluations per ticker | 500–5K |
| `scoring_runs` | `platform_shared` | Agent 03 | Audit log of scoring batches/runs | 100–1K |

### Asset Classification Domain

| Table | Schema | Owner | Purpose | Rows |
|-------|--------|-------|---------|------|
| `asset_classifications` | `platform_shared` | Agent 04 | Classification results (ticker → asset class) | 1K–5K |
| `asset_class_rules` | `platform_shared` | Agent 04 | Rule engine rules for classification | 20–100 |
| `classification_overrides` | `platform_shared` | Agent 04 | Manual overrides for edge cases | 10–100 |

### Analyst Intelligence Domain

| Table | Schema | Owner | Purpose | Rows |
|-------|--------|-------|---------|------|
| `analysts` | `platform_shared` | Agent 02 | Analyst profiles (one per SA analyst) | 50–500 |
| `analyst_articles` | `platform_shared` | Agent 02 | Ingested articles with embeddings | 10K–100K |
| `analyst_recommendations` | `platform_shared` | Agent 02 | Extracted recommendations (ticker per article) | 50K–500K |
| `analyst_accuracy_log` | `platform_shared` | Agent 02 | Backtest outcomes for accuracy scoring | 50K–500K |
| `credit_overrides` | `platform_shared` | Agent 02 | Manual credit grade overrides | 10–100 |

### NAV Erosion Analysis Domain

| Table | Schema | Owner | Purpose | Rows |
|-------|--------|-------|---------|------|
| `nav_erosion_analysis_cache` | `public` | NAV Analysis | Cached Monte Carlo simulation results | 100–1K |
| `nav_erosion_data_collection_log` | `public` | NAV Analysis | Audit trail of data collection | 1K–10K |

### Scenario Simulation Domain

| Table | Schema | Owner | Purpose | Rows |
|-------|--------|-------|---------|------|
| `scenario_results` | `platform_shared` | Agent 06 | Portfolio scenario outcomes (income projections) | 100–10K |

---

## Critical Dependencies

**Data flow order (when running batch scoring):**

1. **Agent 01** → Fetches latest market data, populates `market_data_daily` and `price_history`
2. **Agent 04** → Classifies tickers, populates `asset_classifications`
3. **Agent 03** → Runs quality gates + income scores, populates `income_scores`, `quality_gate_results`, `scoring_runs`
4. **Agent 02** → (Continuous) Ingests analyst articles, updates `analysts`, `analyst_articles`, `analyst_recommendations`
5. **Agent 05** → On-demand tax optimization queries (no DB writes)
6. **Agent 06** → On-demand scenario simulation queries (writes `scenario_results`)

---

## Schema Access Patterns

### By Ticker

Most queries filter by `ticker` or `ticker_symbol`. All core tables have indexes on this column.

**Example:** Find latest income score for JEPI:
```sql
SELECT * FROM platform_shared.income_scores
WHERE ticker = 'JEPI'
ORDER BY scored_at DESC
LIMIT 1;
```

### By Time Range

Many tables have `created_at`, `scored_at`, `published_at` timestamps for time-range queries.

**Example:** Get quality gate results from last 7 days:
```sql
SELECT * FROM platform_shared.quality_gate_results
WHERE evaluated_at >= NOW() - INTERVAL '7 days'
ORDER BY evaluated_at DESC;
```

### By Asset Class

Asset classification and income scoring tables are often queried by asset class.

**Example:** Find all covered call ETFs that passed the quality gate:
```sql
SELECT qg.ticker, qg.passed, is.total_score
FROM platform_shared.quality_gate_results qg
JOIN platform_shared.income_scores is ON qg.id = is.quality_gate_id
WHERE qg.asset_class = 'COVERED_CALL_ETF'
  AND qg.passed = TRUE
ORDER BY is.total_score DESC;
```

---

## Deployment & Migrations

Each service manages its own tables via idempotent migration scripts:

```bash
# Agent 01 — Market Data Service
cd src/market-data-service
alembic upgrade head

# Agent 02 — Newsletter Ingestion
cd src/agent-02-newsletter-ingestion
python scripts/migrate.py

# Agent 03 — Income Scoring
cd src/income-scoring-service
python scripts/migrate.py

# Agent 04 — Asset Classification
cd src/asset-classification-service
python scripts/migrate.py

# Agent 06 — Scenario Simulation
cd src/scenario-simulation-service
python scripts/migrate.py

# NAV Erosion Analysis (manual SQL)
psql -f documentation/implementation/V2.0__nav_erosion_analysis.sql

# Portfolio Management (manual SQL or v3.0 schema)
psql -f documentation/deployment/V3.0__complete_platform_schema.sql
```

All migration scripts are **idempotent** (safe to re-run). They use `CREATE TABLE IF NOT EXISTS` and skip existing data.

---

## Caching & Validity

Several tables track **data validity** to implement intelligent caching:

| Table | Validity Field | Purpose |
|-------|----------------|---------|
| `quality_gate_results` | `valid_until` | Cache quality gate results for 24h |
| `income_scores` | `valid_until` | Cache income scores for 24h |
| `analyst_recommendations` | `expires_at` | Automatic staleness decay (e.g., 90 days) |
| `nav_erosion_analysis_cache` | `valid_until` | Cache Monte Carlo results for 7 days |
| `asset_classifications` | `valid_until` | Cache classifications for 30 days |

**Example:** Query valid (non-expired) income scores:
```sql
SELECT * FROM platform_shared.income_scores
WHERE valid_until > NOW()
  OR valid_until IS NULL
ORDER BY scored_at DESC;
```

---

## Data Quality & Audit Trails

All critical operations are logged for auditability:

- **Scoring runs:** `scoring_runs` table tracks every batch score execution
- **Accuracy tracking:** `analyst_accuracy_log` backtests recommendations vs. market outcomes
- **Data collection:** `nav_erosion_data_collection_log` tracks data quality for NAV analysis
- **Overrides:** `classification_overrides`, `credit_overrides` track manual interventions

---

## Performance Considerations

### Large Tables
- `analyst_articles` (~100K rows) — indexed on `analyst_id`, `published_at`, content hash
- `analyst_recommendations` (~500K rows) — composite index on `(ticker, is_active, decay_weight)`
- `price_history` (~1M rows) — indexed on `symbol`, `date`

### Slow Query Patterns to Avoid
1. **No ticker filter:** Scanning all income scores without filtering by ticker
2. **No date range:** Fetching all articles without a time window
3. **Vector similarity search:** Use IVFFlat indexes on `content_embedding` for approximate NN

### Recommended Indexes

Already created by migrations. If adding custom tables:
- Single-column indexes: `ticker`, `ticker_symbol`, `created_at`, `analyst_id`
- Composite indexes: `(ticker, scored_at DESC)`, `(analyst_id, ticker, published_at DESC)`
- Vector indexes: IVFFlat on embedding columns with `lists=100`

---

## Backups & Recovery

All tables in `platform_shared` schema are critical. Recommended backup strategy:

```bash
# Full schema backup
pg_dump --schema=platform_shared <database> > platform_shared_backup.sql

# Table-level backup
pg_dump --schema=platform_shared --table=income_scores <database> > income_scores_backup.sql
```

---

## Next Steps

- **Core Tables Reference:** See [`core-tables.md`](./core-tables.md) for detailed column definitions
- **Relationships:** See [`relationships.md`](./relationships.md) for foreign keys and data flows
- **Queries:** See [`queries.md`](./queries.md) for common SELECT patterns

---

**Last Updated:** 2026-03-12
**Database Version:** PostgreSQL 13+
**Platform Schema Version:** 3.0
