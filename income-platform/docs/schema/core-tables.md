# Core Tables Reference

Detailed column definitions, types, constraints, and indexes for all platform_shared tables.

---

## Market Data Domain

### price_history

Historical OHLCV price bars. Managed by Agent 01 via Alembic migrations. Stores intraday/daily prices fetched from Alpha Vantage and other providers.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | `gen_random_uuid()` | Primary key |
| `symbol` | VARCHAR(10) | No | — | Ticker symbol (e.g., 'JEPI', 'VTI') |
| `date` | DATE | No | — | Date of the price bar |
| `open_price` | NUMERIC(12, 4) | Yes | NULL | Opening price |
| `high_price` | NUMERIC(12, 4) | Yes | NULL | Highest price of the day |
| `low_price` | NUMERIC(12, 4) | Yes | NULL | Lowest price of the day |
| `close_price` | NUMERIC(12, 4) | Yes | NULL | Closing price |
| `adjusted_close` | NUMERIC(12, 4) | Yes | NULL | Adjusted closing price (split/dividend-adjusted) |
| `volume` | BIGINT | Yes | NULL | Trading volume in shares |
| `data_source` | VARCHAR(50) | No | `'alpha_vantage'` | Data provider name |
| `created_at` | TIMESTAMPTZ | No | `now()` | Timestamp when record was inserted |

**Indexes:**
- `ix_price_history_symbol` — on `symbol` for ticker-based lookups

**Constraints:**
- **Unique:** `(symbol, date)` ensures one record per symbol per date
- **Primary Key:** `id`

**Owned by:** Agent 01 — Market Data Service

**Read by:** Agent 03 (income scoring), Agent 04 (classification), Agent 05 (tax optimization)

**Typical queries:**
```sql
-- Get last 30 days of price history for a ticker
SELECT * FROM price_history
WHERE symbol = 'JEPI' AND date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY date DESC;

-- Find latest close price
SELECT close_price FROM price_history
WHERE symbol = 'JEPI'
ORDER BY date DESC LIMIT 1;
```

---

### market_data_daily

Platform-wide daily price snapshots. Created by V3.0 migration. Legacy table; newer data goes to `price_history`.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `data_id` | UUID | No | `uuid_generate_v4()` | Primary key |
| `ticker_symbol` | VARCHAR(20) | No | — | Ticker (e.g., 'QYLD', 'REIT') |
| `trade_date` | DATE | No | — | Date of the trade/price |
| `open_price` | NUMERIC(10, 2) | Yes | NULL | Opening price |
| `high_price` | NUMERIC(10, 2) | Yes | NULL | High |
| `low_price` | NUMERIC(10, 2) | Yes | NULL | Low |
| `close_price` | NUMERIC(10, 2) | No | — | Closing price (required) |
| `volume` | BIGINT | Yes | NULL | Trading volume |
| `adjusted_close` | NUMERIC(10, 2) | Yes | NULL | Adjusted close |
| `created_at` | DATETIME(timezone=True) | No | `now()` | Insert timestamp |

**Constraints:**
- **Primary Key:** `data_id`

**Owned by:** Agent 01 — Market Data Service (legacy)

**Notes:** Prefer `price_history` for new code. This table exists for backward compatibility.

---

### covered_call_etf_metrics

Historical metrics for covered call ETF Monte Carlo NAV erosion analysis. Populated by data collection pipelines.

**Schema:** `public`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | SERIAL | No | auto | Primary key |
| `ticker` | VARCHAR(20) | No | — | ETF ticker (e.g., 'JEPI', 'QYLD') |
| `data_date` | DATE | No | — | Date of this metric snapshot |
| `nav` | FLOAT | No | — | Net asset value |
| `market_price` | FLOAT | No | — | Market price per share |
| `premium_discount_pct` | FLOAT | Yes | NULL | Premium/discount to NAV (%) |
| `monthly_distribution` | FLOAT | Yes | NULL | Monthly distribution amount per share |
| `distribution_yield_ttm` | FLOAT | Yes | NULL | Trailing twelve-month yield (%) |
| `roc_percentage` | FLOAT | Yes | NULL | Percentage of distribution that is return of capital (%) |
| `monthly_premium_yield` | FLOAT | Yes | NULL | Monthly option premium yield (as % of NAV) |
| `implied_volatility` | FLOAT | Yes | NULL | Implied volatility of the underlying |
| `underlying_return_1m` | FLOAT | Yes | NULL | 1-month return of underlying index (%) |
| `underlying_volatility_30d` | FLOAT | Yes | NULL | 30-day volatility of underlying (%) |
| `expense_ratio` | FLOAT | Yes | NULL | Annual expense ratio (%) |
| `leverage_ratio` | FLOAT | No | `1.0` | Leverage multiplier |
| `created_at` | TIMESTAMP | No | `NOW()` | Insert timestamp |
| `updated_at` | TIMESTAMP | No | `NOW()` | Last update timestamp |

**Indexes:**
- `idx_cc_etf_ticker_date` — on `(ticker, data_date DESC)` for most recent data per ticker
- `idx_cc_etf_date` — on `data_date DESC` for time-based queries

**Constraints:**
- **Unique:** `(ticker, data_date)`
- **Check:** `nav > 0`, `market_price > 0`, `expense_ratio BETWEEN 0 AND 0.10`

**Triggers:**
- `update_cc_etf_metrics_updated_at` — automatically updates `updated_at` on record modification

**Owned by:** NAV Erosion Analysis Service

**Read by:** Agent 03 (NAV penalty scoring)

**Typical queries:**
```sql
-- Get latest metrics for JEPI
SELECT * FROM covered_call_etf_metrics
WHERE ticker = 'JEPI'
ORDER BY data_date DESC LIMIT 1;

-- Check if ETF is at premium or discount
SELECT ticker, data_date, market_price, nav, premium_discount_pct
FROM covered_call_etf_metrics
WHERE data_date = CURRENT_DATE
  AND premium_discount_pct > 2;  -- trading at >2% premium
```

---

## Income Scoring Domain

### scoring_runs

Audit log of each scoring batch or individual scoring request. Provides traceability and statistics.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | `gen_random_uuid()` | Primary key |
| `run_type` | VARCHAR(20) | No | — | Type: `SINGLE`, `BATCH`, or `SCHEDULED` |
| `triggered_by` | VARCHAR(50) | Yes | NULL | Who/what triggered run (e.g., `user_id`, `scheduler`, `api`) |
| `tickers_requested` | INTEGER | No | `0` | Count of tickers requested for scoring |
| `tickers_gate_passed` | INTEGER | No | `0` | Count that passed quality gate |
| `tickers_gate_failed` | INTEGER | No | `0` | Count that failed quality gate |
| `tickers_scored` | INTEGER | No | `0` | Count successfully scored |
| `tickers_errored` | INTEGER | No | `0` | Count that errored out |
| `started_at` | TIMESTAMPTZ | No | `NOW()` | Run start time |
| `completed_at` | TIMESTAMPTZ | Yes | NULL | Run completion time (null if still running) |
| `duration_seconds` | FLOAT | Yes | NULL | Total runtime in seconds |
| `status` | VARCHAR(20) | No | `'RUNNING'` | `RUNNING`, `COMPLETE`, or `FAILED` |
| `error_summary` | TEXT | Yes | NULL | Summary of errors if status = FAILED |
| `config_snapshot` | JSONB | Yes | NULL | Configuration used for this run (for reproducibility) |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | Insert timestamp |

**Indexes:**
- `ix_scoring_runs_started` — on `started_at` for time-range queries
- `ix_scoring_runs_status` — on `status` for finding incomplete runs

**Constraints:**
- **Primary Key:** `id`

**Owned by:** Agent 03 — Income Scoring Service

**Read by:** Dashboard, API, Agent 03 (self-reference for linking scores)

**Typical queries:**
```sql
-- Find most recent completed scoring run
SELECT * FROM scoring_runs
WHERE status = 'COMPLETE'
ORDER BY completed_at DESC LIMIT 1;

-- Get statistics from last batch run
SELECT tickers_requested, tickers_gate_passed, tickers_scored, tickers_errored
FROM scoring_runs
WHERE run_type = 'BATCH'
  AND completed_at >= NOW() - INTERVAL '7 days'
ORDER BY completed_at DESC LIMIT 10;
```

---

### quality_gate_results

Pass/fail quality gate evaluation per ticker. Acts as a VETO: if failed, ticker is excluded from scoring.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | `gen_random_uuid()` | Primary key |
| `ticker` | VARCHAR(20) | No | — | Ticker symbol (indexed) |
| `asset_class` | VARCHAR(30) | No | — | Asset class (e.g., `DIVIDEND_STOCK`, `COVERED_CALL_ETF`, `BOND`) |
| `passed` | BOOLEAN | No | — | Whether quality gate passed (true) or failed (false) |
| `fail_reasons` | JSONB | Yes | NULL | List of failure reasons if `passed = false` |
| `credit_rating` | VARCHAR(10) | Yes | NULL | Credit rating evaluated (e.g., 'A+', 'B-') |
| `credit_rating_passed` | BOOLEAN | Yes | NULL | Whether credit rating gate passed |
| `consecutive_fcf_years` | INTEGER | Yes | NULL | Years of consecutive positive free cash flow |
| `fcf_passed` | BOOLEAN | Yes | NULL | Whether FCF gate passed |
| `dividend_history_years` | INTEGER | Yes | NULL | Years of consecutive dividend payments |
| `dividend_history_passed` | BOOLEAN | Yes | NULL | Whether dividend history gate passed |
| `etf_aum_millions` | FLOAT | Yes | NULL | ETF assets under management (millions) |
| `etf_aum_passed` | BOOLEAN | Yes | NULL | Whether AUM gate passed |
| `etf_track_record_years` | FLOAT | Yes | NULL | Years of ETF track record |
| `etf_track_record_passed` | BOOLEAN | Yes | NULL | Whether track record gate passed |
| `reit_coverage_ratio` | FLOAT | Yes | NULL | REIT interest coverage ratio |
| `reit_coverage_passed` | BOOLEAN | Yes | NULL | Whether REIT coverage gate passed |
| `data_quality_score` | FLOAT | Yes | NULL | Data quality confidence (0–100) |
| `evaluated_at` | TIMESTAMPTZ | No | `NOW()` | When evaluation occurred |
| `valid_until` | TIMESTAMPTZ | Yes | NULL | Cache expiry (usually evaluated_at + 24h) |
| `scoring_run_id` | UUID | Yes | NULL | FK to `scoring_runs(id)` — which run generated this result |

**Indexes:**
- `ix_qg_ticker_evaluated` — on `(ticker, evaluated_at DESC)` for latest evaluation per ticker

**Constraints:**
- **Primary Key:** `id`
- **Foreign Key:** `scoring_run_id` → `scoring_runs(id)`

**Owned by:** Agent 03 — Income Scoring Service

**Read by:** Agent 03 (linking to income_scores), Dashboard

**Typical queries:**
```sql
-- Get latest quality gate result for a ticker
SELECT * FROM quality_gate_results
WHERE ticker = 'JEPI'
ORDER BY evaluated_at DESC LIMIT 1;

-- Find all tickers that failed quality gate
SELECT ticker, fail_reasons
FROM quality_gate_results
WHERE passed = false
  AND evaluated_at >= NOW() - INTERVAL '7 days'
ORDER BY evaluated_at DESC;

-- Get valid (non-expired) gates
SELECT * FROM quality_gate_results
WHERE valid_until > NOW() OR valid_until IS NULL
ORDER BY evaluated_at DESC;
```

---

### income_scores

Full income score for a ticker. Only created if quality gate passed.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | `gen_random_uuid()` | Primary key |
| `ticker` | VARCHAR(20) | No | — | Ticker symbol (indexed) |
| `asset_class` | VARCHAR(30) | No | — | Asset class classification |
| `valuation_yield_score` | FLOAT | No | — | Component score (0–40): yield attractiveness |
| `financial_durability_score` | FLOAT | No | — | Component score (0–40): payout safety, debt, volatility |
| `technical_entry_score` | FLOAT | No | — | Component score (0–20): RSI, support proximity |
| `total_score_raw` | FLOAT | No | — | Sum of components before penalty (0–100) |
| `nav_erosion_penalty` | FLOAT | No | `0.0` | Points deducted for covered call ETFs (0–30) |
| `total_score` | FLOAT | No | — | Final adjusted score = `total_score_raw - nav_erosion_penalty` (floor 0) |
| `grade` | VARCHAR(5) | No | — | Letter grade: `A+`, `A`, `B+`, `B`, `C`, `D`, `F` |
| `recommendation` | VARCHAR(20) | No | — | Recommendation: `AGGRESSIVE_BUY`, `ACCUMULATE`, `WATCH`, `SELL`, `AVOID` |
| `factor_details` | JSONB | Yes | NULL | Detailed factor breakdowns for explainability (SHAP-style) |
| `nav_erosion_details` | JSONB | Yes | NULL | NAV erosion analysis (probability, penalty, risk category) |
| `data_quality_score` | FLOAT | Yes | NULL | Confidence in score (0–100) |
| `data_completeness_pct` | FLOAT | Yes | NULL | Percentage of features populated |
| `scored_at` | TIMESTAMPTZ | No | `NOW()` | When score was generated |
| `valid_until` | TIMESTAMPTZ | Yes | NULL | Cache expiry (usually scored_at + 24h) |
| `scoring_run_id` | UUID | Yes | NULL | FK to `scoring_runs(id)` |
| `quality_gate_id` | UUID | Yes | NULL | FK to `quality_gate_results(id)` |

**Indexes:**
- `ix_income_scores_ticker_scored` — on `(ticker, scored_at DESC)` for latest score per ticker
- `ix_income_scores_recommendation` — on `recommendation` for filtering by recommendation

**Constraints:**
- **Primary Key:** `id`
- **Foreign Keys:**
  - `scoring_run_id` → `scoring_runs(id)`
  - `quality_gate_id` → `quality_gate_results(id)`

**Owned by:** Agent 03 — Income Scoring Service

**Read by:** Dashboard, Agent 05 (tax optimization), Agent 06 (scenario simulation), API

**Typical queries:**
```sql
-- Get latest income score for JEPI
SELECT * FROM income_scores
WHERE ticker = 'JEPI'
ORDER BY scored_at DESC LIMIT 1;

-- Find all ACCUMULATE recommendations
SELECT ticker, total_score, grade, recommendation
FROM income_scores
WHERE recommendation = 'ACCUMULATE'
  AND valid_until > NOW()
ORDER BY total_score DESC;

-- Get scores from specific scoring run
SELECT ticker, total_score, grade
FROM income_scores
WHERE scoring_run_id = '<run-id>'
ORDER BY total_score DESC;
```

---

## Asset Classification Domain

### asset_class_rules

Rule engine definitions for asset classification. Seeded at startup; can be modified at runtime.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | `gen_random_uuid()` | Primary key |
| `asset_class` | VARCHAR(50) | No | — | Target asset class (e.g., `DIVIDEND_STOCK`, `REIT`, `BDC`) |
| `rule_type` | VARCHAR(20) | No | — | Type of rule: `FINANCIAL_METRIC`, `SECTOR`, `TICKER_LIST`, `SECTOR_MAPPING`, etc. |
| `rule_config` | JSONB | No | — | Rule configuration (varies by rule_type) |
| `priority` | INTEGER | No | `100` | Rule priority (lower = higher priority, 0–1000) |
| `confidence_weight` | FLOAT | No | `1.0` | Confidence multiplier for this rule (0.5–2.0) |
| `active` | BOOLEAN | No | `TRUE` | Whether rule is enabled |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | Insert timestamp |

**Constraints:**
- **Primary Key:** `id`
- **Index:** `asset_class` for rule lookup by target classification

**Owned by:** Agent 04 — Asset Classification Service

**Read by:** Agent 04 (rule engine evaluation)

**Notes:**
- Rules are seeded from `shared/asset_class_detector/seed_rules.py`
- `rule_config` structure depends on `rule_type`:
  - `FINANCIAL_METRIC`: `{metric: 'debt_to_equity', operator: '<=', threshold: 2.0}`
  - `SECTOR_MAPPING`: `{gics_sector: 'Real Estate', target_class: 'REIT'}`
  - `TICKER_LIST`: `{tickers: ['JNJ', 'PG'], target_class: 'DIVIDEND_STOCK'}`

---

### asset_classifications

Classification results. One row per ticker per classification run.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | `gen_random_uuid()` | Primary key |
| `ticker` | VARCHAR(20) | No | — | Ticker symbol (indexed) |
| `asset_class` | VARCHAR(50) | No | — | Primary asset class (e.g., `DIVIDEND_STOCK`) |
| `parent_class` | VARCHAR(50) | No | — | Parent classification (e.g., `EQUITY`, `FIXED_INCOME`, `ALTERNATIVE`) |
| `confidence` | FLOAT | No | — | Confidence in classification (0.0–1.0) |
| `is_hybrid` | BOOLEAN | No | `FALSE` | Whether ticker has characteristics of multiple classes |
| `characteristics` | JSONB | Yes | NULL | Detected characteristics (e.g., `{dividend_payer: true, yield: 0.045}`) |
| `benchmarks` | JSONB | Yes | NULL | Applicable benchmarks for comparison |
| `sub_scores` | JSONB | Yes | NULL | Scores from individual classification rules |
| `tax_efficiency` | JSONB | Yes | NULL | Tax treatment profile (qualified div, ordinary income, etc.) |
| `matched_rules` | JSONB | Yes | NULL | Rules that matched (for explainability) |
| `source` | VARCHAR(50) | No | `'rule_engine_v1'` | Classification source |
| `is_override` | BOOLEAN | No | `FALSE` | Whether this is a manual override |
| `classified_at` | TIMESTAMPTZ | No | `NOW()` | Classification timestamp |
| `valid_until` | TIMESTAMPTZ | Yes | NULL | Cache expiry (usually classified_at + 30d) |

**Indexes:**
- `ix_asset_classifications_ticker` — on `ticker` for lookup by symbol
- `ix_asset_classifications_classified_at` — on `classified_at DESC` for recent classifications

**Constraints:**
- **Primary Key:** `id`

**Owned by:** Agent 04 — Asset Classification Service

**Read by:** Agent 03 (quality gate checks), Agent 05 (tax treatment lookup), Agent 06 (scenario filtering)

**Typical queries:**
```sql
-- Get classification for JEPI
SELECT * FROM asset_classifications
WHERE ticker = 'JEPI'
  AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY classified_at DESC LIMIT 1;

-- Find all REITs
SELECT ticker, confidence, characteristics
FROM asset_classifications
WHERE asset_class = 'REIT'
ORDER BY confidence DESC;

-- Find hybrid assets
SELECT ticker, asset_class, confidence
FROM asset_classifications
WHERE is_hybrid = true
ORDER BY classified_at DESC;
```

---

### classification_overrides

Manual overrides for edge cases or special rules.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | `gen_random_uuid()` | Primary key |
| `ticker` | VARCHAR(20) | No | — | Ticker (unique constraint) |
| `asset_class` | VARCHAR(50) | No | — | Overridden asset class |
| `reason` | TEXT | Yes | NULL | Explanation for override |
| `created_by` | VARCHAR(100) | Yes | NULL | User who created override |
| `effective_from` | TIMESTAMPTZ | No | `NOW()` | When override becomes effective |
| `effective_until` | TIMESTAMPTZ | Yes | NULL | When override expires (null = permanent) |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | Insert timestamp |

**Constraints:**
- **Primary Key:** `id`
- **Unique:** `ticker` — one override per ticker
- **Index:** `ticker` for lookup

**Owned by:** Agent 04 — Asset Classification Service

**Read by:** Asset classification queries (checked before rule engine results)

**Notes:** Overrides take precedence over rule-engine results.

---

## Analyst Intelligence Domain

### analysts

Analyst registry. One row per tracked analyst from Seeking Alpha.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | SERIAL | No | auto | Primary key |
| `sa_publishing_id` | VARCHAR(100) | No | — | Seeking Alpha internal ID (unique) |
| `display_name` | VARCHAR(200) | No | — | Display name of analyst |
| `is_active` | BOOLEAN | No | `TRUE` | Whether analyst is actively tracked |
| `philosophy_cluster` | INTEGER | Yes | NULL | K-Means cluster ID (Intelligence Flow grouping) |
| `philosophy_summary` | TEXT | Yes | NULL | LLM-generated summary of analyst philosophy |
| `philosophy_source` | VARCHAR(10) | No | `'llm'` | Source of philosophy: `llm` or `kmeans` |
| `philosophy_vector` | Vector(1536) | Yes | NULL | Embedding of philosophy (pgvector) |
| `philosophy_tags` | JSONB | Yes | NULL | Tags extracted from philosophy (style, sectors, etc.) |
| `overall_accuracy` | NUMERIC(5, 4) | Yes | NULL | Overall accuracy (0.0–1.0) |
| `sector_alpha` | JSONB | Yes | NULL | Accuracy by sector (e.g., `{REIT: 0.81, TECH: 0.62}`) |
| `article_count` | INTEGER | No | `0` | Number of articles ingested |
| `last_article_fetched_at` | TIMESTAMPTZ | Yes | NULL | Last time articles were fetched for this analyst |
| `last_backtest_at` | TIMESTAMPTZ | Yes | NULL | Last time accuracy was backtested |
| `config` | JSONB | Yes | NULL | Per-analyst config overrides (null = use user defaults) |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | Insert timestamp |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | Last update timestamp |

**Indexes:**
- `ix_analysts_sa_id` — on `sa_publishing_id` for lookup
- `ix_analysts_active` — on `is_active` for finding active analysts

**Constraints:**
- **Primary Key:** `id`
- **Unique:** `sa_publishing_id`

**Owned by:** Agent 02 — Newsletter Ingestion Service

**Read by:** Dashboard, Intelligence Flow (accuracy backtesting)

**Typical queries:**
```sql
-- Get analyst by Seeking Alpha ID
SELECT * FROM analysts WHERE sa_publishing_id = '<sa-id>';

-- Find top analysts by accuracy
SELECT display_name, overall_accuracy, sector_alpha
FROM analysts
WHERE is_active = true
  AND overall_accuracy IS NOT NULL
ORDER BY overall_accuracy DESC LIMIT 10;

-- Get sector specialists
SELECT display_name, sector_alpha
FROM analysts
WHERE is_active = true
  AND sector_alpha->>'REIT' IS NOT NULL
ORDER BY (sector_alpha->>'REIT')::NUMERIC DESC;
```

---

### analyst_articles

Raw ingested articles from analysts. One row per unique article.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | SERIAL | No | auto | Primary key |
| `analyst_id` | INTEGER | No | — | FK to `analysts(id)` |
| `sa_article_id` | VARCHAR(100) | No | — | Seeking Alpha internal article ID (unique) |
| `url_hash` | VARCHAR(64) | Yes | NULL | SHA-256 hash of URL |
| `content_hash` | VARCHAR(64) | Yes | NULL | SHA-256 hash of full text (for dedup) |
| `title` | TEXT | No | — | Article title |
| `full_text` | TEXT | Yes | NULL | Full article text |
| `published_at` | TIMESTAMPTZ | No | — | Publication timestamp |
| `fetched_at` | TIMESTAMPTZ | No | `NOW()` | When article was fetched |
| `content_embedding` | Vector(1536) | Yes | NULL | Semantic embedding of article (pgvector) |
| `tickers_mentioned` | TEXT[] | Yes | NULL | Array of tickers mentioned |
| `metadata` | JSONB | Yes | NULL | Article metadata (word_count, source, etc.) |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | Insert timestamp |

**Indexes:**
- `ix_analyst_articles_analyst_published` — on `(analyst_id, published_at DESC)` for analyst's articles
- `ix_analyst_articles_url_hash` — on `url_hash` for deduplication
- `ix_analyst_articles_content_hash` — on `content_hash` for content dedup
- `ix_articles_embedding` — IVFFlat vector index on `content_embedding` for semantic search

**Constraints:**
- **Primary Key:** `id`
- **Unique:** `sa_article_id`
- **Foreign Key:** `analyst_id` → `analysts(id)`

**Owned by:** Agent 02 — Newsletter Ingestion Service

**Read by:** Semantic search, Intelligence Flow (feature extraction)

**Typical queries:**
```sql
-- Get latest articles from an analyst
SELECT title, published_at FROM analyst_articles
WHERE analyst_id = <id>
ORDER BY published_at DESC LIMIT 20;

-- Find articles mentioning a ticker
SELECT analyst_id, title, published_at
FROM analyst_articles
WHERE 'JEPI' = ANY(tickers_mentioned)
ORDER BY published_at DESC;

-- Semantic search (approximate NN)
SELECT id, title, published_at
FROM analyst_articles
WHERE content_embedding <-> (SELECT content_embedding FROM analyst_articles WHERE id = <query_id>) < 0.5
LIMIT 10;
```

---

### analyst_recommendations

Extracted structured recommendations. One row per ticker per article.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | SERIAL | No | auto | Primary key |
| `analyst_id` | INTEGER | No | — | FK to `analysts(id)` |
| `article_id` | INTEGER | No | — | FK to `analyst_articles(id)` |
| `ticker` | VARCHAR(20) | No | — | Ticker recommended |
| `sector` | VARCHAR(50) | Yes | NULL | GICS sector |
| `asset_class` | VARCHAR(20) | Yes | NULL | Asset class (CommonStock, REIT, MLP, BDC, etc.) |
| `recommendation` | VARCHAR(20) | Yes | NULL | Recommendation: StrongBuy, Buy, Hold, Sell, StrongSell |
| `sentiment_score` | NUMERIC(4, 3) | Yes | NULL | Sentiment (-1.0 to 1.0) |
| `yield_at_publish` | NUMERIC(6, 4) | Yes | NULL | Yield at publication date |
| `payout_ratio` | NUMERIC(6, 4) | Yes | NULL | Payout ratio |
| `dividend_cagr_3yr` | NUMERIC(6, 4) | Yes | NULL | 3-year dividend CAGR |
| `dividend_cagr_5yr` | NUMERIC(6, 4) | Yes | NULL | 5-year dividend CAGR |
| `safety_grade` | VARCHAR(5) | Yes | NULL | Seeking Alpha Dividend Safety Grade |
| `source_reliability` | VARCHAR(20) | Yes | NULL | Source: EarningsCall, 10K, 10Q, Press Release, etc. |
| `content_embedding` | Vector(1536) | Yes | NULL | Semantic embedding of recommendation text |
| `metadata` | JSONB | Yes | NULL | Metadata (price_target, risks[], thesis, etc.) |
| `published_at` | TIMESTAMPTZ | No | — | Publication date |
| `expires_at` | TIMESTAMPTZ | No | — | Expiry date (published_at + aging_days, typically 90d) |
| `decay_weight` | NUMERIC(5, 4) | No | `1.0` | Staleness decay weight (1.0 = fresh, →0 as expires_at approaches) |
| `is_active` | BOOLEAN | No | `TRUE` | Whether recommendation is still valid |
| `superseded_by` | INTEGER | Yes | NULL | FK to newer recommendation if analyst changed view |
| `platform_alignment` | VARCHAR(20) | Yes | NULL | Agent 12 alignment: Aligned, Partial, Divergent, Vetoed |
| `platform_scored_at` | TIMESTAMPTZ | Yes | NULL | When platform evaluated alignment |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | Insert timestamp |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | Last update timestamp |

**Indexes:**
- `ix_analyst_rec_ticker_active_weight` — on `(ticker, is_active, decay_weight DESC)` for consensus queries
- `ix_analyst_rec_analyst_ticker_published` — on `(analyst_id, ticker, published_at DESC)` for analyst history
- `ix_recs_expires_at` — on `expires_at` for staleness queries
- `ix_recs_embedding` — IVFFlat vector index on `content_embedding`

**Constraints:**
- **Primary Key:** `id`
- **Foreign Keys:**
  - `analyst_id` → `analysts(id)`
  - `article_id` → `analyst_articles(id)`
  - `superseded_by` → `analyst_recommendations(id)`

**Owned by:** Agent 02 — Newsletter Ingestion Service (read/write by Agent 12 for alignment scoring)

**Read by:** Consensus queries, Agent 06 (scenario filtering), Dashboard

**Typical queries:**
```sql
-- Get active recommendations for JEPI by weight
SELECT analyst_id, recommendation, decay_weight, published_at
FROM analyst_recommendations
WHERE ticker = 'JEPI'
  AND is_active = true
  AND expires_at > NOW()
ORDER BY decay_weight DESC, published_at DESC;

-- Consensus: average sentiment for a ticker
SELECT ticker, AVG(CAST(sentiment_score AS FLOAT)) as avg_sentiment
FROM analyst_recommendations
WHERE ticker = 'JEPI'
  AND is_active = true
  AND expires_at > NOW()
GROUP BY ticker;

-- Find recommendations not yet aligned with platform
SELECT analyst_id, ticker, recommendation
FROM analyst_recommendations
WHERE platform_alignment IS NULL
  AND is_active = true
ORDER BY published_at DESC LIMIT 50;
```

---

### analyst_accuracy_log

Backtest outcome records. One row per recommendation outcome evaluation.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | SERIAL | No | auto | Primary key |
| `analyst_id` | INTEGER | No | — | FK to `analysts(id)` |
| `recommendation_id` | INTEGER | No | — | FK to `analyst_recommendations(id)` |
| `ticker` | VARCHAR(20) | No | — | Ticker of recommendation |
| `sector` | VARCHAR(50) | Yes | NULL | GICS sector |
| `asset_class` | VARCHAR(20) | Yes | NULL | Asset class |
| `original_recommendation` | VARCHAR(20) | Yes | NULL | Original recommendation at publish |
| `price_at_publish` | NUMERIC(12, 4) | Yes | NULL | Stock price at publication |
| `price_at_t30` | NUMERIC(12, 4) | Yes | NULL | Price 30 days later |
| `price_at_t90` | NUMERIC(12, 4) | Yes | NULL | Price 90 days later |
| `dividend_cut_occurred` | BOOLEAN | Yes | NULL | Whether dividend was cut during eval period |
| `dividend_cut_at` | TIMESTAMPTZ | Yes | NULL | When cut occurred (if applicable) |
| `outcome_label` | VARCHAR(20) | Yes | NULL | Outcome: Correct, Incorrect, Partial, Inconclusive |
| `accuracy_delta` | NUMERIC(5, 4) | Yes | NULL | +/- applied to analyst's accuracy score |
| `sector_accuracy_before` | NUMERIC(5, 4) | Yes | NULL | Sector accuracy before this backtest |
| `sector_accuracy_after` | NUMERIC(5, 4) | Yes | NULL | Sector accuracy after this backtest |
| `user_override_occurred` | BOOLEAN | No | `FALSE` | Whether user overrode platform decision |
| `override_outcome_label` | VARCHAR(20) | Yes | NULL | Outcome if user overrode platform |
| `backtest_run_at` | TIMESTAMPTZ | No | `NOW()` | When backtest was run |
| `notes` | TEXT | Yes | NULL | Additional notes |

**Indexes:**
- `ix_accuracy_analyst` — on `analyst_id` for analyst performance tracking
- `ix_accuracy_ticker` — on `ticker` for ticker outcome analysis

**Constraints:**
- **Primary Key:** `id`
- **Foreign Keys:**
  - `analyst_id` → `analysts(id)`
  - `recommendation_id` → `analyst_recommendations(id)`

**Owned by:** Agent 02 — Newsletter Ingestion Service (Intelligence Flow backtest)

**Read by:** Accuracy scoring, Dashboard

**Typical queries:**
```sql
-- Get analyst accuracy breakdown by sector
SELECT analyst_id, sector,
       COUNT(*) as total_recs,
       SUM(CASE WHEN outcome_label = 'Correct' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as accuracy
FROM analyst_accuracy_log
WHERE backtest_run_at >= NOW() - INTERVAL '1 year'
GROUP BY analyst_id, sector
ORDER BY analyst_id, accuracy DESC;

-- Find recent incorrect predictions
SELECT analyst_id, ticker, outcome_label
FROM analyst_accuracy_log
WHERE outcome_label = 'Incorrect'
  AND backtest_run_at >= NOW() - INTERVAL '30 days'
ORDER BY backtest_run_at DESC;
```

---

### credit_overrides

Manual credit grade overrides for edge cases.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | SERIAL | No | auto | Primary key |
| `ticker` | VARCHAR(20) | No | — | Ticker (unique) |
| `override_grade` | VARCHAR(5) | No | — | Credit grade (e.g., 'B', 'C+', 'BB-') |
| `reason` | TEXT | Yes | NULL | Explanation |
| `set_by` | VARCHAR(100) | Yes | NULL | User who set override |
| `reviewed_at` | TIMESTAMPTZ | Yes | NULL | When override was reviewed |
| `expires_at` | TIMESTAMPTZ | Yes | NULL | Expiry date (null = permanent) |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | Insert timestamp |

**Constraints:**
- **Primary Key:** `id`
- **Unique:** `ticker`
- **Index:** `ticker`

**Owned by:** Agent 02 — Newsletter Ingestion Service

**Read by:** Agent 03 (credit rating priority chain)

**Notes:** Used as fallback when SA grade and FMP proxy are unavailable. Agent 03 checks this before scoring.

---

## Scenario Simulation Domain

### scenario_results

Portfolio scenario simulation outcomes.

**Schema:** `platform_shared`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | `gen_random_uuid()` | Primary key |
| `portfolio_id` | UUID | No | — | Portfolio being simulated |
| `scenario_name` | VARCHAR(50) | No | — | Name of scenario (e.g., "Fed Hike", "Recession 2025") |
| `scenario_type` | VARCHAR(20) | No | — | Type: `PREDEFINED` or `CUSTOM` |
| `scenario_params` | JSONB | Yes | NULL | Parameters used in simulation |
| `result_summary` | JSONB | No | — | Summary results (income projections, metrics) |
| `vulnerability_ranking` | JSONB | Yes | NULL | Ranked list of vulnerabilities to scenario |
| `projected_income_p10` | NUMERIC(12, 2) | Yes | NULL | 10th percentile projected annual income |
| `projected_income_p50` | NUMERIC(12, 2) | Yes | NULL | 50th percentile (median) projected income |
| `projected_income_p90` | NUMERIC(12, 2) | Yes | NULL | 90th percentile projected income |
| `label` | VARCHAR(200) | Yes | NULL | Custom label for scenario |
| `created_at` | TIMESTAMPTZ | No | `now()` | Timestamp |

**Indexes:**
- `ix_scenario_results_portfolio_created` — on `(portfolio_id, created_at)` for portfolio history

**Constraints:**
- **Primary Key:** `id`

**Owned by:** Agent 06 — Scenario Simulation Service

**Read by:** Dashboard, Portfolio analysis

**Typical queries:**
```sql
-- Get scenario results for a portfolio
SELECT scenario_name, projected_income_p50, created_at
FROM scenario_results
WHERE portfolio_id = '<portfolio-id>'
ORDER BY created_at DESC;

-- Compare income projections across scenarios
SELECT scenario_name, projected_income_p10, projected_income_p50, projected_income_p90
FROM scenario_results
WHERE portfolio_id = '<portfolio-id>'
ORDER BY projected_income_p50 DESC;
```

---

## NAV Erosion Analysis Domain

### nav_erosion_analysis_cache

Cached Monte Carlo simulation results for covered call ETF NAV degradation.

**Schema:** `public`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | SERIAL | No | auto | Primary key |
| `ticker` | VARCHAR(20) | No | — | ETF ticker |
| `analysis_date` | DATE | No | `CURRENT_DATE` | Date of analysis |
| `analysis_type` | VARCHAR(20) | No | — | Type: `quick` or `deep` |
| `simulation_results` | JSONB | No | — | Full Monte Carlo results |
| `median_annualized_nav_change_pct` | FLOAT | Yes | NULL | Median annual NAV change (%) |
| `probability_erosion_gt_5pct` | FLOAT | Yes | NULL | Probability of >5% annual erosion |
| `probability_erosion_gt_10pct` | FLOAT | Yes | NULL | Probability of >10% annual erosion |
| `sustainability_penalty` | FLOAT | Yes | NULL | Points to deduct from sustainability score (0–30) |
| `valid_until` | DATE | No | — | Cache expiry date |
| `created_at` | TIMESTAMP | No | `NOW()` | Insert timestamp |

**Indexes:**
- `idx_nav_cache_ticker` — on `(ticker, valid_until DESC)` for latest valid cache per ticker
- `idx_nav_cache_valid` — on `valid_until DESC` for expiry checks
- `idx_nav_cache_analysis_date` — on `analysis_date DESC` for historical analysis

**Constraints:**
- **Primary Key:** `id`
- **Unique:** `(ticker, analysis_date, analysis_type)`
- **Check:** `analysis_type IN ('quick', 'deep')`, `sustainability_penalty BETWEEN 0 AND 30`

**Owned by:** NAV Erosion Analysis Service

**Read by:** Agent 03 (NAV penalty scoring)

**Typical queries:**
```sql
-- Get latest valid NAV erosion analysis for JEPI
SELECT * FROM nav_erosion_analysis_cache
WHERE ticker = 'JEPI'
  AND valid_until >= CURRENT_DATE
ORDER BY analysis_date DESC LIMIT 1;

-- Find high-risk covered call ETFs
SELECT ticker, probability_erosion_gt_5pct, sustainability_penalty
FROM nav_erosion_analysis_cache
WHERE valid_until >= CURRENT_DATE
  AND probability_erosion_gt_5pct > 0.5
ORDER BY probability_erosion_gt_5pct DESC;
```

---

### nav_erosion_data_collection_log

Audit trail for NAV erosion data collection.

**Schema:** `public`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | SERIAL | No | auto | Primary key |
| `ticker` | VARCHAR(20) | No | — | ETF ticker |
| `collection_date` | TIMESTAMP | No | `NOW()` | When data was collected |
| `params_json` | JSONB | No | — | Parameters used in collection |
| `completeness_score` | FLOAT | Yes | NULL | Data quality score (0–100) |
| `created_at` | TIMESTAMP | No | `NOW()` | Insert timestamp |

**Indexes:**
- `idx_nav_collection_ticker` — on `(ticker, collection_date DESC)`

**Constraints:**
- **Primary Key:** `id`
- **Check:** `completeness_score BETWEEN 0 AND 100`

**Owned by:** NAV Erosion Analysis Service

**Read by:** Data quality monitoring

**Notes:** Used for audit trail and monitoring data collection health.

---

## Summary

- **Total tables documented:** 18 core tables in `platform_shared` schema + 3 NAV tables in `public`
- **Total indexed columns:** 50+ index definitions across all tables
- **Total constraints:** 30+ PKs, FKs, UNIQUEs, CHECKs
- **Vector indexes:** 2 (IVFFlat on `analyst_articles.content_embedding` and `analyst_recommendations.content_embedding`)
- **Next step:** See [`relationships.md`](./relationships.md) for foreign key relationships and data flow diagrams

---

**Last Updated:** 2026-03-12
