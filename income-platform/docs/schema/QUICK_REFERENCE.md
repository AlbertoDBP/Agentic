# Quick Reference Card

One-page cheat sheet for the income-platform data model.

---

## Tables by Domain

### Income Scoring (Agent 03)
```
scoring_runs → quality_gate_results → income_scores
  • One run produces many gate results
  • Gate result optionally linked to income score
  • If gate fails, no score created
```

### Analyst Intelligence (Agent 02)
```
analysts → analyst_articles → analyst_recommendations
         → analyst_accuracy_log (backtest results)
         → credit_overrides (manual grades)
  • Articles have multiple recommendations (one per ticker)
  • Recommendations expire after 90 days (auto)
  • Can be superseded when analyst changes view
```

### Asset Classification (Agent 04)
```
asset_class_rules → asset_classifications
                 → classification_overrides (manual)
  • Rules evaluated to produce classifications
  • Overrides take precedence over rule results
  • Classifications valid for 30 days
```

### Market Data (Agent 01)
```
price_history (OHLCV per symbol per date)
market_data_daily (legacy snapshots)
covered_call_etf_metrics (for NAV analysis)
```

### Scenario & NAV
```
scenario_results (Agent 06 outputs)
nav_erosion_analysis_cache (NAV service results)
```

---

## Column Cheat Sheet

### income_scores
```
ticker, asset_class, total_score, grade, recommendation
valuation_yield_score (0-40), financial_durability_score (0-40),
technical_entry_score (0-20), nav_erosion_penalty (0-30),
factor_details (JSON), nav_erosion_details (JSON),
scored_at, valid_until (24h cache)
```

### quality_gate_results
```
ticker, asset_class, passed (BOOLEAN), fail_reasons (JSON),
credit_rating, credit_rating_passed,
consecutive_fcf_years, fcf_passed,
dividend_history_years, dividend_history_passed,
etf_aum_millions, etf_aum_passed,
reit_coverage_ratio, reit_coverage_passed,
evaluated_at, valid_until (24h cache)
```

### analyst_recommendations
```
analyst_id, article_id, ticker,
recommendation (Buy/Hold/Sell), sentiment_score (-1 to 1),
yield_at_publish, payout_ratio, safety_grade,
published_at, expires_at (90d auto-expire),
decay_weight (staleness 1.0 → 0), is_active (BOOLEAN),
superseded_by (self-join), platform_alignment
```

### asset_classifications
```
ticker, asset_class, parent_class, confidence (0-1),
is_hybrid (BOOLEAN), characteristics (JSON),
tax_efficiency (JSON), matched_rules (JSON),
classified_at, valid_until (30d cache)
```

### price_history
```
symbol, date, open_price, high_price, low_price,
close_price, adjusted_close, volume,
data_source (default: 'alpha_vantage'), created_at
UNIQUE(symbol, date)
```

---

## Common Filters

| Query Type | Filter | Notes |
|-----------|--------|-------|
| Latest score | `scored_at DESC LIMIT 1` | Check `valid_until > NOW()` |
| Latest gate | `evaluated_at DESC LIMIT 1` | 24h cache validity |
| Active analyst recs | `is_active = TRUE AND expires_at > NOW()` | Auto-expire after 90d |
| Valid classifications | `valid_until > NOW() OR valid_until IS NULL` | 30d cache |
| Recent articles | `published_at >= NOW() - INTERVAL '30 days'` | Avoid full scan |

---

## Foreign Keys

| From Table | To Table | Column |
|-----------|----------|--------|
| quality_gate_results | scoring_runs | `scoring_run_id` |
| income_scores | scoring_runs | `scoring_run_id` |
| income_scores | quality_gate_results | `quality_gate_id` |
| analyst_articles | analysts | `analyst_id` |
| analyst_recommendations | analysts | `analyst_id` |
| analyst_recommendations | analyst_articles | `article_id` |
| analyst_recommendations | analyst_recommendations | `superseded_by` (self) |
| analyst_accuracy_log | analysts | `analyst_id` |
| analyst_accuracy_log | analyst_recommendations | `recommendation_id` |

---

## Indexes (By Usage Frequency)

| Index | Columns | Use Case |
|-------|---------|----------|
| `ix_income_scores_ticker_scored` | `(ticker, scored_at DESC)` | Latest score per ticker |
| `ix_qg_ticker_evaluated` | `(ticker, evaluated_at DESC)` | Latest gate per ticker |
| `ix_analyst_rec_ticker_active_weight` | `(ticker, is_active, decay_weight DESC)` | Consensus queries |
| `ix_analyst_articles_analyst_published` | `(analyst_id, published_at DESC)` | Analyst history |
| `ix_price_history_symbol` | `(symbol)` | Price lookups |
| `ix_analysts_sa_id` | `(sa_publishing_id)` | Analyst lookup |
| `ix_analytics_embedding` | `(content_embedding)` IVFFlat | Semantic search |

---

## Key Cache Durations

| Table | Cache Field | Duration | Trigger |
|-------|------------|----------|---------|
| income_scores | `valid_until` | 24h | Nightly batch |
| quality_gate_results | `valid_until` | 24h | Nightly batch |
| asset_classifications | `valid_until` | 30 days | Classification run |
| analyst_recommendations | `expires_at` | 90 days | Article publication |
| nav_erosion_analysis_cache | `valid_until` | 7 days | NAV analysis run |

**Always check cache validity in WHERE clause!**

---

## Most Important Queries

### Latest Income Score
```sql
SELECT * FROM income_scores WHERE ticker = 'JEPI'
  AND (valid_until IS NULL OR valid_until > NOW())
  ORDER BY scored_at DESC LIMIT 1;
```

### Quality Gate + Score Together
```sql
SELECT qg.*, is.* FROM quality_gate_results qg
  LEFT JOIN income_scores is ON qg.id = is.quality_gate_id
  WHERE qg.ticker = 'JEPI' ORDER BY qg.evaluated_at DESC LIMIT 1;
```

### Analyst Consensus
```sql
SELECT analyst_id, recommendation, sentiment_score, decay_weight
  FROM analyst_recommendations
  WHERE ticker = 'JEPI' AND is_active AND expires_at > NOW()
  ORDER BY decay_weight DESC;
```

### Asset Classification Lookup
```sql
SELECT * FROM asset_classifications
  WHERE ticker = 'JEPI' AND (valid_until IS NULL OR valid_until > NOW())
  ORDER BY classified_at DESC LIMIT 1;
```

### Did Service Write Data?
```sql
-- Agent 01: price_history updated today?
SELECT COUNT(*) FROM price_history
  WHERE symbol = 'JEPI' AND date = CURRENT_DATE;

-- Agent 03: scoring run completed today?
SELECT status, duration_seconds FROM scoring_runs
  WHERE run_type = 'BATCH' ORDER BY completed_at DESC LIMIT 1;

-- Agent 02: articles fetched today?
SELECT COUNT(*) FROM analyst_articles
  WHERE fetched_at >= CURRENT_DATE;
```

---

## Service Ownership

| Service | Writes To | Reads From |
|---------|-----------|-----------|
| Agent 01 | price_history, market_data_daily | (external APIs) |
| Agent 02 | analysts, analyst_articles, analyst_recommendations, analyst_accuracy_log, credit_overrides | market_data_daily |
| Agent 03 | scoring_runs, quality_gate_results, income_scores | market_data_daily, price_history, asset_classifications, credit_overrides, nav_erosion_analysis_cache |
| Agent 04 | asset_classifications, asset_class_rules, classification_overrides | market_data_daily |
| Agent 05 | (none) | asset_classifications, income_scores |
| Agent 06 | scenario_results | income_scores, asset_classifications |
| NAV Service | covered_call_etf_metrics, nav_erosion_analysis_cache | (data collection pipeline) |

---

## Schema Name

All application tables in: **`platform_shared`**

NAV erosion tables in: **`public`**

---

## Extensions Required

- `uuid-ossp` — UUID functions
- `pgvector` — Vector embeddings (Agent 02)

---

## Deployment

```bash
# All migrations are in service directories
src/<service>/scripts/migrate.py    # Most services
src/market-data-service/migrations # Agent 01 (Alembic)

# All migrations are IDEMPOTENT (safe to re-run)
```

---

## Typical Data Flow (Nightly)

```
1. Agent 01: Fetch market data → price_history, market_data_daily
2. Agent 04: Classify tickers → asset_classifications
3. Agent 03: Quality gate + score → quality_gate_results, income_scores
4. Agent 02: (Continuous) Ingest articles → analyst_articles, recommendations
5. Agent 06: (On-demand) Simulate scenarios → scenario_results
```

---

## Debugging Checklist

| Issue | Check |
|-------|-------|
| No data in table | Does migration exist? Did service write? Check ownership. |
| Stale data | Check `scored_at`, `classified_at`, `published_at` timestamps |
| Cache expired | `valid_until < NOW()` or `expires_at < NOW()` |
| Query slow | Using indexed columns? Filtering by date range? |
| Missing foreign key | FK constraints listed above — verify source table has data |
| Vector search not working | pgvector extension installed? Data in embedding column? |

---

## Common Mistakes

❌ **Querying all rows without filter**
```sql
SELECT * FROM income_scores;  -- Bad!
```
✅ **Filter by indexed column**
```sql
SELECT * FROM income_scores WHERE ticker = 'JEPI';
```

---

❌ **Ignoring cache validity**
```sql
SELECT * FROM income_scores WHERE ticker = 'JEPI' LIMIT 1;  -- May be stale!
```
✅ **Check cache**
```sql
SELECT * FROM income_scores WHERE ticker = 'JEPI'
  AND (valid_until IS NULL OR valid_until > NOW()) LIMIT 1;
```

---

❌ **N+1 queries**
```sql
SELECT * FROM analysts;
-- Then loop: SELECT * FROM analyst_articles WHERE analyst_id = ...
```
✅ **Join instead**
```sql
SELECT a.*, ar.* FROM analysts a
  JOIN analyst_articles ar ON a.id = ar.analyst_id;
```

---

## Document Links

- **Architecture Overview:** README.md
- **All Columns & Types:** core-tables.md
- **Foreign Keys & Flow:** relationships.md
- **Copy-Paste Queries:** queries.md
- **Navigation:** INDEX.md

---

**Updated:** 2026-03-12 | **Schema:** v3.0 | **DB:** PostgreSQL 13+
