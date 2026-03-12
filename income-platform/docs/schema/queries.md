# Common Query Patterns & Examples

Copy-paste ready SQL queries for common developer tasks.

---

## Income Scoring Queries

### Get Latest Score for a Ticker

```sql
SELECT
  id, ticker, asset_class,
  total_score, grade, recommendation,
  valuation_yield_score,
  financial_durability_score,
  technical_entry_score,
  nav_erosion_penalty,
  scored_at
FROM income_scores
WHERE ticker = 'JEPI'
  AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY scored_at DESC
LIMIT 1;
```

### Get All ACCUMULATE Recommendations

```sql
SELECT
  ticker, total_score, grade, recommendation,
  data_quality_score, scored_at
FROM income_scores
WHERE recommendation = 'ACCUMULATE'
  AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY total_score DESC;
```

### Check if Ticker Passed Quality Gate

```sql
SELECT
  ticker, asset_class,
  passed, fail_reasons,
  credit_rating, credit_rating_passed,
  consecutive_fcf_years, fcf_passed,
  dividend_history_years, dividend_history_passed,
  evaluated_at
FROM quality_gate_results
WHERE ticker = 'JEPI'
  AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY evaluated_at DESC
LIMIT 1;
```

### Get Quality Gate & Score Together

```sql
SELECT
  qg.ticker,
  qg.passed,
  qg.fail_reasons,
  is.total_score,
  is.grade,
  is.recommendation,
  qg.evaluated_at,
  is.scored_at
FROM quality_gate_results qg
LEFT JOIN income_scores is
  ON qg.id = is.quality_gate_id
WHERE qg.ticker = 'JEPI'
ORDER BY qg.evaluated_at DESC
LIMIT 1;
```

### Get Scoring Run Statistics

```sql
SELECT
  id, run_type, triggered_by,
  tickers_requested, tickers_gate_passed,
  tickers_scored, tickers_errored,
  started_at, completed_at, duration_seconds,
  status
FROM scoring_runs
WHERE status = 'COMPLETE'
ORDER BY completed_at DESC
LIMIT 10;
```

### Find All Failed Quality Gates from Last 7 Days

```sql
SELECT
  ticker, asset_class,
  fail_reasons, evaluated_at
FROM quality_gate_results
WHERE passed = FALSE
  AND evaluated_at >= NOW() - INTERVAL '7 days'
ORDER BY evaluated_at DESC;
```

### Score Breakdown with Component Details

```sql
SELECT
  ticker,
  total_score,
  grade,
  valuation_yield_score,
  financial_durability_score,
  technical_entry_score,
  nav_erosion_penalty,
  factor_details->>'yield_vs_5yr_avg' as yield_factor,
  nav_erosion_details->>'risk_classification' as nav_risk,
  data_quality_score,
  scored_at
FROM income_scores
WHERE ticker = 'JEPI'
ORDER BY scored_at DESC
LIMIT 1;
```

### Compare Scores Over Time (Trend)

```sql
SELECT
  DATE(scored_at) as date,
  total_score,
  grade,
  recommendation
FROM income_scores
WHERE ticker = 'JEPI'
ORDER BY scored_at DESC
LIMIT 30;
```

---

## Asset Classification Queries

### Get Asset Class for a Ticker

```sql
SELECT
  ticker,
  asset_class,
  parent_class,
  confidence,
  characteristics,
  tax_efficiency,
  classified_at
FROM asset_classifications
WHERE ticker = 'JEPI'
  AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY classified_at DESC
LIMIT 1;
```

### Check if Classification Has Manual Override

```sql
SELECT
  ac.ticker,
  ac.asset_class as auto_class,
  COALESCE(co.asset_class, ac.asset_class) as final_class,
  CASE WHEN co.id IS NOT NULL THEN 'OVERRIDE' ELSE 'AUTO' END as source,
  co.reason as override_reason
FROM asset_classifications ac
LEFT JOIN classification_overrides co ON ac.ticker = co.ticker
WHERE ac.ticker = 'JEPI'
ORDER BY ac.classified_at DESC
LIMIT 1;
```

### Find All REITs

```sql
SELECT
  ticker,
  asset_class,
  confidence,
  characteristics->>'payout_ratio' as payout_ratio,
  classified_at
FROM asset_classifications
WHERE asset_class = 'REIT'
  AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY confidence DESC;
```

### Find All Covered Call ETFs

```sql
SELECT
  ticker,
  asset_class,
  confidence,
  tax_efficiency
FROM asset_classifications
WHERE asset_class = 'COVERED_CALL_ETF'
  AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY classified_at DESC;
```

### Find All Hybrid Assets

```sql
SELECT
  ticker,
  asset_class,
  parent_class,
  characteristics
FROM asset_classifications
WHERE is_hybrid = TRUE
  AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY classified_at DESC;
```

### Get Active Classification Rules

```sql
SELECT
  id,
  asset_class,
  rule_type,
  priority,
  confidence_weight,
  rule_config
FROM asset_class_rules
WHERE active = TRUE
ORDER BY priority ASC, confidence_weight DESC;
```

### Apply Overrides for Specific Tickers

```sql
-- Create override
INSERT INTO classification_overrides
  (ticker, asset_class, reason, created_by, effective_from)
VALUES
  ('XYZ', 'DIVIDEND_STOCK', 'Manual adjustment for special case', 'admin', NOW())
ON CONFLICT (ticker) DO UPDATE SET
  asset_class = EXCLUDED.asset_class,
  reason = EXCLUDED.reason;
```

---

## Analyst Intelligence Queries

### Get Analyst Consensus for a Ticker (Weighted by Decay)

```sql
SELECT
  ar.analyst_id,
  a.display_name,
  ar.recommendation,
  ar.sentiment_score,
  ar.yield_at_publish,
  ar.payout_ratio,
  ar.safety_grade,
  ar.decay_weight,
  ar.published_at,
  ar.expires_at,
  ar.platform_alignment
FROM analyst_recommendations ar
JOIN analysts a ON ar.analyst_id = a.id
WHERE ar.ticker = 'JEPI'
  AND ar.is_active = TRUE
  AND ar.expires_at > NOW()
ORDER BY ar.decay_weight DESC, ar.published_at DESC;
```

### Consensus Summary (Average Sentiment & Weighted Votes)

```sql
SELECT
  ticker,
  COUNT(DISTINCT ar.analyst_id) as analyst_count,
  AVG(CAST(ar.sentiment_score AS FLOAT)) as avg_sentiment,
  AVG(ar.decay_weight) as avg_decay_weight,
  MAX(ar.published_at) as most_recent_rec,
  COUNT(CASE WHEN ar.recommendation = 'Buy' THEN 1 END) as buy_count,
  COUNT(CASE WHEN ar.recommendation = 'Hold' THEN 1 END) as hold_count,
  COUNT(CASE WHEN ar.recommendation = 'Sell' THEN 1 END) as sell_count
FROM analyst_recommendations ar
WHERE ar.ticker = 'JEPI'
  AND ar.is_active = TRUE
  AND ar.expires_at > NOW()
GROUP BY ticker;
```

### Get Articles from a Specific Analyst

```sql
SELECT
  id,
  title,
  published_at,
  tickers_mentioned,
  metadata->>'word_count' as word_count
FROM analyst_articles
WHERE analyst_id = <analyst_id>
ORDER BY published_at DESC
LIMIT 50;
```

### Find Articles Mentioning a Ticker

```sql
SELECT
  aa.id,
  a.display_name,
  aa.title,
  aa.published_at,
  COUNT(ar.id) as recommendation_count
FROM analyst_articles aa
JOIN analysts a ON aa.analyst_id = a.id
LEFT JOIN analyst_recommendations ar
  ON aa.id = ar.article_id AND ar.ticker = 'JEPI'
WHERE 'JEPI' = ANY(aa.tickers_mentioned)
GROUP BY aa.id, a.display_name, aa.title, aa.published_at
ORDER BY aa.published_at DESC;
```

### Analyst Accuracy by Sector (Last 6 Months)

```sql
SELECT
  a.display_name,
  aal.sector,
  COUNT(*) as total_calls,
  SUM(CASE WHEN aal.outcome_label = 'Correct' THEN 1 ELSE 0 END)::FLOAT
    / COUNT(*) as accuracy_rate,
  AVG(CAST(aal.accuracy_delta AS FLOAT)) as avg_delta
FROM analyst_accuracy_log aal
JOIN analysts a ON aal.analyst_id = a.id
WHERE aal.backtest_run_at >= NOW() - INTERVAL '6 months'
GROUP BY a.display_name, aal.sector
HAVING COUNT(*) >= 5  -- Min 5 calls to be meaningful
ORDER BY a.display_name, accuracy_rate DESC;
```

### Find Analysts with Highest Overall Accuracy

```sql
SELECT
  id,
  display_name,
  overall_accuracy,
  article_count,
  last_backtest_at,
  sector_alpha
FROM analysts
WHERE is_active = TRUE
  AND overall_accuracy IS NOT NULL
ORDER BY overall_accuracy DESC
LIMIT 20;
```

### Get Recent Incorrect Predictions

```sql
SELECT
  a.display_name,
  aal.ticker,
  aal.sector,
  aal.original_recommendation,
  aal.price_at_publish,
  aal.price_at_t90,
  ((aal.price_at_t90 - aal.price_at_publish) / aal.price_at_publish * 100)::NUMERIC(5,2) as return_pct,
  aal.outcome_label,
  aal.backtest_run_at
FROM analyst_accuracy_log aal
JOIN analysts a ON aal.analyst_id = a.id
WHERE aal.outcome_label = 'Incorrect'
  AND aal.backtest_run_at >= NOW() - INTERVAL '30 days'
ORDER BY aal.backtest_run_at DESC;
```

### Check Recommendation Alignment with Platform

```sql
SELECT
  analyst_id, ticker, recommendation,
  platform_alignment, platform_scored_at
FROM analyst_recommendations
WHERE platform_alignment IS NULL
  AND is_active = TRUE
ORDER BY published_at DESC
LIMIT 50;
```

### Apply Credit Grade Override

```sql
INSERT INTO credit_overrides
  (ticker, override_grade, reason, set_by, reviewed_at)
VALUES
  ('CORP', 'BB+', 'CRE exposure concerns', 'analyst@example.com', NOW())
ON CONFLICT (ticker) DO UPDATE SET
  override_grade = EXCLUDED.override_grade,
  reason = EXCLUDED.reason,
  set_by = EXCLUDED.set_by;
```

---

## Market Data Queries

### Get Latest Price for a Ticker

```sql
SELECT
  symbol,
  date,
  close_price,
  adjusted_close,
  volume,
  created_at
FROM price_history
WHERE symbol = 'JEPI'
ORDER BY date DESC
LIMIT 1;
```

### Get Price History (Last N Days)

```sql
SELECT
  symbol,
  date,
  open_price,
  high_price,
  low_price,
  close_price,
  adjusted_close,
  volume
FROM price_history
WHERE symbol = 'JEPI'
  AND date >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY date DESC;
```

### Calculate Returns and Volatility

```sql
WITH prices AS (
  SELECT
    date,
    close_price,
    LAG(close_price) OVER (ORDER BY date) as prev_close
  FROM price_history
  WHERE symbol = 'JEPI'
    AND date >= CURRENT_DATE - INTERVAL '30 days'
)
SELECT
  STDDEV((close_price - prev_close) / prev_close) * SQRT(252) as annualized_volatility,
  ((SELECT close_price FROM price_history
    WHERE symbol = 'JEPI'
    ORDER BY date DESC LIMIT 1)
   / (SELECT close_price FROM price_history
    WHERE symbol = 'JEPI'
    ORDER BY date ASC LIMIT 1) - 1) * 100 as return_pct
FROM prices
WHERE prev_close IS NOT NULL;
```

---

## NAV Erosion Queries

### Get Latest NAV Erosion Analysis

```sql
SELECT
  ticker,
  analysis_type,
  median_annualized_nav_change_pct,
  probability_erosion_gt_5pct,
  probability_erosion_gt_10pct,
  sustainability_penalty,
  analysis_date,
  valid_until
FROM nav_erosion_analysis_cache
WHERE ticker = 'JEPI'
  AND valid_until >= CURRENT_DATE
ORDER BY analysis_date DESC
LIMIT 1;
```

### Find High-Risk Covered Call ETFs

```sql
SELECT
  ticker,
  probability_erosion_gt_5pct,
  probability_erosion_gt_10pct,
  sustainability_penalty,
  CASE
    WHEN probability_erosion_gt_5pct <= 0.2 THEN 'MINIMAL'
    WHEN probability_erosion_gt_5pct <= 0.4 THEN 'LOW'
    WHEN probability_erosion_gt_5pct <= 0.6 THEN 'MODERATE'
    WHEN probability_erosion_gt_5pct <= 0.8 THEN 'HIGH'
    ELSE 'SEVERE'
  END as risk_category,
  analysis_date
FROM nav_erosion_analysis_cache
WHERE valid_until >= CURRENT_DATE
  AND probability_erosion_gt_5pct > 0.4
ORDER BY probability_erosion_gt_5pct DESC;
```

### Covered Call ETF Historical Metrics

```sql
SELECT
  ticker,
  data_date,
  nav,
  market_price,
  premium_discount_pct,
  monthly_premium_yield,
  monthly_distribution,
  distribution_yield_ttm
FROM covered_call_etf_metrics
WHERE ticker = 'JEPI'
ORDER BY data_date DESC
LIMIT 30;
```

### NAV Erosion Impact on Income Score

```sql
SELECT
  is.ticker,
  is.total_score_raw,
  neac.sustainability_penalty,
  is.total_score as final_score,
  neac.probability_erosion_gt_5pct,
  neac.analysis_date
FROM income_scores is
JOIN nav_erosion_analysis_cache neac
  ON is.ticker = neac.ticker
WHERE neac.valid_until >= CURRENT_DATE
  AND is.valid_until >= NOW()
  AND neac.sustainability_penalty > 0
ORDER BY neac.sustainability_penalty DESC;
```

---

## Scenario Simulation Queries

### Get Scenario Results for a Portfolio

```sql
SELECT
  scenario_name,
  scenario_type,
  projected_income_p10,
  projected_income_p50,
  projected_income_p90,
  label,
  created_at
FROM scenario_results
WHERE portfolio_id = '<portfolio_uuid>'
ORDER BY created_at DESC
LIMIT 20;
```

### Compare Income Projections Across Scenarios

```sql
SELECT
  scenario_name,
  projected_income_p10,
  projected_income_p50,
  projected_income_p90,
  (projected_income_p90 - projected_income_p10) as range_width
FROM scenario_results
WHERE portfolio_id = '<portfolio_uuid>'
ORDER BY projected_income_p50 DESC;
```

### Get Most Recent Scenario Results

```sql
WITH latest_scenarios AS (
  SELECT DISTINCT ON (scenario_name)
    scenario_name, scenario_type, projected_income_p50,
    vulnerability_ranking, created_at
  FROM scenario_results
  WHERE portfolio_id = '<portfolio_uuid>'
  ORDER BY scenario_name, created_at DESC
)
SELECT * FROM latest_scenarios
ORDER BY projected_income_p50 DESC;
```

---

## Admin & Maintenance Queries

### Check Data Freshness

```sql
SELECT
  'income_scores' as table_name,
  MAX(scored_at) as last_update,
  NOW() - MAX(scored_at) as age,
  COUNT(*) as row_count
FROM income_scores
UNION ALL
SELECT
  'quality_gate_results',
  MAX(evaluated_at),
  NOW() - MAX(evaluated_at),
  COUNT(*)
FROM quality_gate_results
UNION ALL
SELECT
  'analyst_recommendations',
  MAX(published_at),
  NOW() - MAX(published_at),
  COUNT(*)
FROM analyst_recommendations
UNION ALL
SELECT
  'analyst_articles',
  MAX(published_at),
  NOW() - MAX(published_at),
  COUNT(*)
FROM analyst_articles;
```

### Count Expired Cache Entries

```sql
SELECT
  COUNT(*) as expired_income_scores
FROM income_scores
WHERE valid_until < NOW();

SELECT
  COUNT(*) as expired_quality_gates
FROM quality_gate_results
WHERE valid_until < NOW();

SELECT
  COUNT(*) as expired_classifications
FROM asset_classifications
WHERE valid_until < NOW();

SELECT
  COUNT(*) as stale_analyst_recs
FROM analyst_recommendations
WHERE expires_at < NOW();
```

### Find Missing Data Quality Scores

```sql
SELECT
  ticker, COUNT(*) as count
FROM income_scores
WHERE data_quality_score IS NULL
  AND scored_at >= NOW() - INTERVAL '7 days'
GROUP BY ticker
ORDER BY count DESC;
```

### Cleanup Expired Recommendations

```sql
UPDATE analyst_recommendations
SET is_active = FALSE
WHERE expires_at < NOW()
  AND is_active = TRUE;
```

### Recompute Latest Cache for a Ticker

```sql
DELETE FROM quality_gate_results
WHERE ticker = 'JEPI'
  AND evaluated_at < NOW() - INTERVAL '24 hours';

DELETE FROM income_scores
WHERE ticker = 'JEPI'
  AND scored_at < NOW() - INTERVAL '24 hours';
```

### Get Database Statistics

```sql
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as size,
  n_live_tup as row_count,
  last_vacuum,
  last_analyze
FROM pg_stat_user_tables
WHERE schemaname = 'platform_shared'
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;
```

---

## Performance Tips

### Slow Query Analysis

```sql
-- Find slow queries in log
SELECT query, calls, mean_time, max_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%'
ORDER BY mean_time DESC
LIMIT 20;
```

### Check Index Usage

```sql
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan as scans,
  idx_tup_read as tuples_read,
  idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'platform_shared'
ORDER BY idx_scan DESC;
```

### Analyze Query Plan

```sql
EXPLAIN ANALYZE
SELECT * FROM income_scores
WHERE ticker = 'JEPI'
ORDER BY scored_at DESC LIMIT 1;
```

---

**Last Updated:** 2026-03-12
**All queries tested on PostgreSQL 13+**
