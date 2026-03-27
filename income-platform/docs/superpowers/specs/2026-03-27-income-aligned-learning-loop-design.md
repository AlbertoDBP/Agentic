# Income-Aligned Learning Loop Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the existing price-return-based learning loop with a per-pillar, income-aligned outcome measurement system that correctly evaluates Income, Durability, and Technical scoring accuracy against the signals each pillar is actually predicting.

**Architecture:** Each shadow portfolio entry records three independent outcome measurements with pillar-appropriate hold periods (Technical=60d, Income=365d, Durability=365d derived from Income). The weight tuner draws per-pillar signal from per-pillar outcomes. A backtest endpoint bootstraps calibrated weights from historical data on first run. A threshold trigger fires early reviews when evidence of systematic miss is unambiguous.

**Tech Stack:** Python/FastAPI (income-scoring-service), SQLAlchemy/PostgreSQL (`platform_shared` schema), asyncpg, existing `data_client.py` dividend history API.

---

## Context: What Exists Today

The current learning loop in `src/income-scoring-service/`:

- `app/scoring/shadow_portfolio.py` — `ShadowPortfolioManager`: records ACCUMULATE/AGGRESSIVE_BUY entries; populates outcomes after 90-day hold using price return (CORRECT ≥+5%, INCORRECT ≤−5%)
- `app/scoring/weight_tuner.py` — `QuarterlyWeightTuner`: uses the single `outcome_label` to compute per-pillar signal and adjust top-level weights quarterly
- `app/api/learning_loop.py` — REST endpoints for shadow portfolio and review management
- `app/models.py` — `ShadowPortfolioEntry`, `ScoringWeightProfile`, `WeightChangeAudit`, `WeightReviewRun` in `platform_shared` schema

**The flaw:** All three pillars (Income, Durability, Technical) are evaluated against the same 90-day price return outcome. Price is the right signal for the Technical pillar but the wrong signal for Income and Durability. A dividend stock can drop in price while maintaining strong dividends — the current loop would label that as INCORRECT and penalize the pillars that correctly evaluated income sustainability.

---

## Migration Strategy: Full Replacement (Option A)

Old columns (`exit_price`, `actual_return_pct`, `outcome_label`, `outcome_populated_at`) are kept as nullable and ignored by new code. Old entries remain inert — they are not backfilled with per-pillar outcomes. The new populate jobs only process entries where per-pillar outcome columns exist (i.e., entries created after this migration).

The backtest endpoint retroactively computes per-pillar outcomes for all historical entries that have sufficient data, then immediately triggers `apply_review()` to produce calibrated weights on day one.

---

## Section 1: Data Model

### `scoring_weight_profiles` — add one column

```sql
ALTER TABLE platform_shared.scoring_weight_profiles
  ADD COLUMN benchmark_ticker VARCHAR(20) NULL;
```

**Default benchmark tickers seeded on migration:**

| Asset Class | Benchmark |
|---|---|
| EQUITY_REIT | VNQ |
| MORTGAGE_REIT | REM |
| BDC | BIZD |
| COVERED_CALL_ETF | JEPI |
| DIVIDEND_STOCK | DVY |
| BOND | AGG |
| PREFERRED_STOCK | PFF |

The benchmark ticker is fetched and price-updated by the same market data refresh cycle that updates all other tickers. No special scheduling needed.

### `shadow_portfolio_entries` — add per-pillar outcome blocks

All new columns are nullable. Old entries remain valid with nulls in new columns.

**Entry-time capture (new parameters to `maybe_record_entry()`):**

```sql
benchmark_ticker          VARCHAR(20)   -- snapshot from weight profile at entry time
benchmark_entry_price     FLOAT         -- benchmark price at entry (fetched once per asset class per scoring batch)
durability_score_at_entry FLOAT         -- financial_durability_score at time of entry
income_ttm_at_entry       FLOAT         -- TTM dividend sum at time of entry (from dividend_history)
```

**Technical outcome block (populated at T+60):**

```sql
technical_exit_price           FLOAT
benchmark_exit_price           FLOAT
technical_return_pct           FLOAT    -- (exit - entry) / entry * 100
technical_benchmark_return_pct FLOAT    -- (bm_exit - bm_entry) / bm_entry * 100
technical_alpha_pct            FLOAT    -- technical_return_pct - technical_benchmark_return_pct
technical_outcome_label        VARCHAR(20)  -- PENDING | CORRECT | INCORRECT | NEUTRAL
technical_outcome_at           TIMESTAMP
```

**Income outcome block (populated at T+365):**

```sql
income_ttm_at_exit     FLOAT
income_change_pct      FLOAT    -- (ttm_at_exit - ttm_at_entry) / ttm_at_entry * 100
income_outcome_label   VARCHAR(20)  -- PENDING | CORRECT | INCORRECT | NEUTRAL
income_outcome_at      TIMESTAMP
```

**Durability outcome block (populated after Income, at T+365):**

```sql
durability_score_at_exit   FLOAT
durability_outcome_label   VARCHAR(20)  -- PENDING | CORRECT | INCORRECT | NEUTRAL
durability_outcome_at      TIMESTAMP
```

Note: `durability_score_delta` is derivable as `durability_score_at_exit - durability_score_at_entry` and does not need a stored column.

---

## Section 2: Outcome Measurement

### Technical — T+60 days

**Input:** `{ticker: current_price}` + `{benchmark_ticker: current_price}` (one benchmark price per asset class, not per entry row).

**Computation:**
```python
technical_return_pct = (exit_price - entry_price) / entry_price * 100
benchmark_return_pct = (bm_exit - bm_entry) / bm_entry * 100
alpha = technical_return_pct - benchmark_return_pct

CORRECT   if alpha >= +3.0
INCORRECT if alpha <= -3.0
NEUTRAL   otherwise
```

±3% band filters noise. The entry timing call must meaningfully outperform the asset class to count as CORRECT.

**Edge cases:**
- No entry price → set NEUTRAL, skip alpha computation
- Benchmark entry price missing → set NEUTRAL
- Ticker delisted (exit price unavailable) → set INCORRECT (forced — a delisting is a failed call)

### Income — T+365 days

**Input:** `{ticker: ttm_dividend_sum}` — computed from `data_client.get_dividend_history()`, summing payment amounts with `ex_date` in the 12 months preceding the exit date.

**Computation:**
```python
change_pct = (ttm_at_exit - ttm_at_entry) / ttm_at_entry * 100

CORRECT   if change_pct >= +2.0   (income grew)
INCORRECT if change_pct <= -5.0   (income meaningfully cut)
NEUTRAL   otherwise               (-5% to +2%: held steady, inconclusive)
```

**Edge cases:**
- `ttm_at_exit == 0` (dividend suspended) → force INCORRECT regardless of entry TTM
- `ttm_at_entry == 0` → set NEUTRAL (cannot compute change; should not have been recorded, but guard exists)
- Dividend history unavailable → set NEUTRAL, log warning

### Durability — derived from Income, at T+365

**Computed after Income outcome is finalized for the same entry.** Both share the T+365 hold period; populate Income first, then Durability in the same job.

**Input:** `{ticker: current_durability_score}` — fetched from the most recent `income_scores` row.

**Confidence threshold:**
```python
confidence_threshold = 0.60 * weight_durability  # e.g. weight=40 → threshold=24 pts
entry_confidence = "HIGH" if durability_score_at_entry >= confidence_threshold else "LOW"
```

**Outcome matrix:**

| Entry Confidence | Income Outcome | Durability Outcome | Rationale |
|---|---|---|---|
| HIGH | CORRECT | CORRECT | Strong durability predicted → income held → validated |
| HIGH | INCORRECT | INCORRECT | Strong durability predicted → income cut → false confidence |
| LOW | INCORRECT | NEUTRAL | We flagged the risk; outcome doesn't tell us weight was wrong |
| LOW | CORRECT | NEUTRAL | Overly pessimistic but not harmful |
| ANY | NEUTRAL | NEUTRAL | Income inconclusive; no durability signal |

**Edge cases:**
- `durability_score_at_exit` unavailable (ticker no longer in scoring system) → set NEUTRAL
- `income_outcome_label` still PENDING → skip; cannot compute durability outcome yet

---

## Section 3: Weight Tuner

### Algorithm

The core signal computation stays structurally identical to `QuarterlyWeightTuner.compute_adjustment()`, but each pillar now draws from its own per-pillar outcome label.

```python
# Income signal — uses income_outcome_label
income_correct   = [e for e in outcomes if e.income_outcome_label == "CORRECT"]
income_incorrect = [e for e in outcomes if e.income_outcome_label == "INCORRECT"]
signal_y = mean(e.valuation_yield_score / wy for e in income_correct)
         - mean(e.valuation_yield_score / wy for e in income_incorrect)

# Durability signal — uses durability_outcome_label
dur_correct   = [e for e in outcomes if e.durability_outcome_label == "CORRECT"]
dur_incorrect = [e for e in outcomes if e.durability_outcome_label == "INCORRECT"]
signal_d = mean(e.financial_durability_score / wd for e in dur_correct)
         - mean(e.financial_durability_score / wd for e in dur_incorrect)

# Technical signal — uses technical_outcome_label
tech_correct   = [e for e in outcomes if e.technical_outcome_label == "CORRECT"]
tech_incorrect = [e for e in outcomes if e.technical_outcome_label == "INCORRECT"]
signal_t = mean(e.technical_entry_score / wt for e in tech_correct)
         - mean(e.technical_entry_score / wt for e in tech_incorrect)
```

### Review cadence — two separate schedules

**Technical review — quarterly (every 90 days)**
- Adjusts only `weight_technical`
- Uses `technical_outcome_label`; Income/Durability outcomes ignored
- After adjustment: normalize all three weights to sum=100 (absorb rounding in the largest pillar)

**Income/Durability review — annual (every 365 days)**
- Adjusts `weight_yield` and `weight_durability` together
- Uses `income_outcome_label` and `durability_outcome_label` independently
- After adjustment: normalize all three to sum=100

### MIN_SAMPLES per pillar

`MIN_SAMPLES = 10` applies independently per pillar. A review run logs `SKIPPED: insufficient_samples` for any pillar that hasn't accumulated 10 usable (CORRECT + INCORRECT) outcomes, even if other pillars have enough.

### Unchanged constraints

- `MAX_DELTA_PER_REVIEW = 5` pts per pillar per run
- `MIN_PILLAR_WEIGHT = 5`, `MAX_PILLAR_WEIGHT = 90`
- Sub-weights within each pillar are never touched

### Signal threshold (early trigger)

After any outcome population run, a threshold check fires per pillar per asset class:

```python
THRESHOLD_INCORRECT_RATE = 0.60   # 60% of recent outcomes are INCORRECT
THRESHOLD_MIN_OUTCOMES   = 20     # must have at least 20 outcomes to trigger
MIN_REVIEW_GAP_DAYS      = 30     # minimum days between reviews for same class+pillar
```

If `incorrect_count / (correct_count + incorrect_count) > 0.60` AND total usable ≥ 20, and it has been ≥ 30 days since the last review for that asset class + pillar combination → trigger `apply_review()` immediately.

Logged in `WeightReviewRun` with `triggered_by = "SIGNAL_THRESHOLD"`.

---

## Section 4: API Surface

### New / replaced endpoints in `/learning-loop`

**Replace `POST /learning-loop/populate-outcomes`** with:

```
POST /learning-loop/populate-technical-outcomes
Body: {
  exit_prices: {ticker: float},
  benchmark_exit_prices: {benchmark_ticker: float}
}
Response: { updated, skipped_no_price, skipped_no_entry_price, total_pending }
```

```
POST /learning-loop/populate-income-durability-outcomes
Body: {
  ttm_dividends: {ticker: float},
  current_durability_scores: {ticker: float}
}
Response: {
  income: { updated, skipped, total_pending },
  durability: { updated, skipped_awaiting_income, total_pending }
}
```

Income is computed first within this single call; Durability is derived immediately after using the freshly computed Income outcome labels.

**New:**

```
POST /learning-loop/backtest/{asset_class}
Body: { triggered_by: str }
Response: WeightReviewRunResponse
```

Retroactively populates per-pillar outcomes for all historical entries with sufficient data, then immediately triggers `apply_review()`. Returns the resulting `WeightReviewRun`.

**Extended:**

```
POST /learning-loop/review/{asset_class}
Body: {
  triggered_by: str,
  pillar: "technical" | "income_durability" | "all",   # new field, default "all"
  lookback_days: int | null
}
```

### Updated weight profile endpoints

`GET /weights/{asset_class}` — response now includes `benchmark_ticker`.

`PATCH /weights/{asset_class}` — accepts `benchmark_ticker` in body.

### `WeightReviewRun` model — add one column

```sql
pillar_reviewed  VARCHAR(30)   -- "technical" | "income_durability" | "all"
```

Allows the audit trail to show which pillar(s) were adjusted in each run.

---

## Section 5: Backtest Strategy

The backtest endpoint runs the following pipeline for a given asset class:

1. **Fetch all historical shadow entries** for the asset class (any `outcome_label`, including old `PENDING` entries from pre-migration)
2. **For each entry with `income_ttm_at_entry` populated:**
   - Fetch dividend history from `data_client.get_dividend_history(ticker)` → compute `income_ttm_at_exit` (TTM sum 365 days after `entry_date`)
   - If dividend data available → populate `income_outcome_label`
   - Fetch most recent `income_scores.financial_durability_score` near `entry_date + 365d` → populate `durability_outcome_label`
3. **For each entry with `benchmark_entry_price` populated:**
   - Fetch price at `entry_date + 60d` from market data cache → populate `technical_outcome_label`
4. **Trigger `apply_review()`** with the full populated outcome set → immediately produces calibrated weights
5. Return `WeightReviewRun` with `triggered_by = "BACKTEST"`

The backtest is idempotent: entries already having a non-PENDING per-pillar outcome are not overwritten.

---

## Files Changed

| File | Change |
|---|---|
| `app/models.py` | Add columns to `ShadowPortfolioEntry`; add `benchmark_ticker` + `pillar_reviewed` columns |
| `app/scoring/shadow_portfolio.py` | New `maybe_record_entry()` signature; replace `populate_outcomes()` with `populate_technical_outcomes()` and `populate_income_durability_outcomes()` |
| `app/scoring/weight_tuner.py` | Replace `compute_adjustment()` with per-pillar signal logic; add threshold trigger check; add pillar selector to `apply_review()` |
| `app/api/learning_loop.py` | Replace populate endpoint; add backtest endpoint; extend review endpoint with pillar param |
| `app/api/weights.py` | Add `benchmark_ticker` to weight profile read/update |
| `scripts/migrate.py` | Add migration for new columns + seed benchmark tickers |

---

## Outcome Thresholds Summary

| Pillar | Hold Period | CORRECT | INCORRECT | NEUTRAL |
|---|---|---|---|---|
| Technical | 60 days | alpha ≥ +3% | alpha ≤ −3% | −3% to +3% |
| Income | 365 days | TTM change ≥ +2% | TTM change ≤ −5% (or suspended) | −5% to +2% |
| Durability | 365 days (derived) | HIGH confidence + income CORRECT | HIGH confidence + income INCORRECT | LOW confidence (either income outcome) |
