# Functional Specification: Income Scoring Engine

**Components:** `app/scoring/income_scorer.py`, `app/scoring/nav_erosion.py`, `app/scoring/data_client.py`  
**Version:** 1.0.0  
**Date:** 2026-02-26  
**Status:** Production

---

## Purpose & Scope

The Income Scoring Engine is Phase 2 of Agent 03's evaluation pipeline. It consumes market data from Agent 01 and produces a 0–100 score with grade (A+→F) and recommendation (AGGRESSIVE_BUY/ACCUMULATE/WATCH) for tickers that have passed the Quality Gate.

---

## Responsibilities

- Fetch required market data from Agent 01 via HTTP (async)
- Calculate weighted score across 3 pillars and 8 sub-components
- Apply Monte Carlo NAV erosion penalty for covered call ETFs
- Handle missing data gracefully (50% partial credit per missing field)
- Persist scores to `platform_shared.income_scores`
- Return full factor breakdown for transparency

---

## Data Client (`data_client.py`)

Async httpx client wrapping Agent 01's API. All methods degrade gracefully.

| Method | Agent 01 Endpoint | Returns |
|---|---|---|
| `get_fundamentals(ticker)` | `GET /stocks/{ticker}/fundamentals` | pe_ratio, debt_to_equity, payout_ratio, free_cash_flow, market_cap, sector |
| `get_dividend_history(ticker)` | `GET /stocks/{ticker}/dividends` | list of dividend records |
| `get_history_stats(ticker, start, end)` | `GET /stocks/{ticker}/history/stats` | volatility, min_price, max_price, avg_price, price_change_pct |
| `get_etf_data(ticker)` | `GET /stocks/{ticker}/etf` | aum, expense_ratio, covered_call |
| `get_current_price(ticker)` | `GET /stocks/{ticker}/price` | price |

On connection error or non-200 response: logs warning, returns `{}` or `[]`.

---

## Scoring Engine (`income_scorer.py`)

### Pillar 1 — Valuation & Yield (max 40 pts)

**payout_sustainability (0–16):** Measures dividend payment safety.
- payout_ratio < 0.40 → 16 pts (very safe)
- payout_ratio < 0.60 → 12 pts (safe)
- payout_ratio < 0.75 → 8 pts (moderate)
- payout_ratio < 0.90 → 4 pts (stretched)
- payout_ratio ≥ 0.90 → 0 pts (unsustainable)

**yield_vs_market (0–14):** Rewards attractive income generation.
- Annual yield > 4% → 14 pts
- Annual yield > 3% → 10 pts
- Annual yield > 2% → 6 pts
- Annual yield > 1% → 2 pts
- Annual yield ≤ 1% → 0 pts

**fcf_coverage (0–10):** Validates free cash flow supports dividends.
- FCF > 0 → 10 pts
- FCF = 0 or None → 5 pts (partial credit)
- FCF < 0 → 0 pts

### Pillar 2 — Financial Durability (max 40 pts)

**debt_safety (0–16):** Rewards low leverage.
- D/E < 0.50 → 16 pts
- D/E < 1.00 → 12 pts
- D/E < 1.50 → 8 pts
- D/E < 2.00 → 4 pts
- D/E ≥ 2.00 → 0 pts

**dividend_consistency (0–14):** Rewards long dividend track record.
- > 25 years → 14 pts (Dividend Aristocrat level)
- > 15 years → 10 pts
- > 10 years → 7 pts
- ≤ 10 years → 4 pts (minimum — gate already requires ≥10)

**volatility_score (0–10):** Rewards price stability.
- std dev < 2 → 10 pts
- std dev < 5 → 7 pts
- std dev < 10 → 4 pts
- std dev < 20 → 2 pts
- std dev ≥ 20 → 0 pts

### Pillar 3 — Technical Entry (max 20 pts)

**price_momentum (0–12):** Rewards oversold conditions (better entry).
- 90-day change < -15% → 12 pts (deeply oversold)
- 90-day change < -5% → 8 pts (oversold)
- 90-day change < +5% → 6 pts (neutral)
- 90-day change < +15% → 3 pts (slightly overbought)
- 90-day change ≥ +15% → 0 pts (overbought)

**price_range_position (0–8):** Rewards buying near 52-week lows.
- Position in range < 0.30 → 8 pts (near bottom)
- Position in range < 0.50 → 5 pts (lower half)
- Position in range < 0.70 → 3 pts (upper half)
- Position in range ≥ 0.70 → 1 pt (near top)

### Missing Data Handling

When a field is None, the sub-component receives **50% of its maximum**. This prevents tickers with incomplete data from being artificially penalized to zero while still rewarding complete data submissions.

`data_completeness_pct` = (fields present / total fields) × 100

---

## NAV Erosion Analyzer (`nav_erosion.py`)

Applied only to `COVERED_CALL_ETF` asset class after base scoring.

### Monte Carlo Simulation

```
n_simulations = settings.nav_erosion_simulations (default: 10,000)
mu = -0.03  (covered call drag assumption: 3% annual NAV headwind)
sigma = volatility / 100  (annualized from price std dev)

paths = np.random.normal(mu, sigma, n_simulations)
prob_erosion_gt_5pct = fraction where path < -0.05
```

### Risk Classification & Penalty

| P(loss > 5%) | Risk | Penalty |
|---|---|---|
| < 0.30 | LOW | 0 pts |
| < 0.50 | MODERATE | 10 pts |
| < 0.70 | HIGH | 20 pts |
| ≥ 0.70 | SEVERE | 30 pts |

If volatility is None or 0: penalty = 0, risk = UNKNOWN.

---

## Grade & Recommendation Assignment

| Final Score | Grade | Recommendation |
|---|---|---|
| ≥ 95 | A+ | AGGRESSIVE_BUY |
| ≥ 85 | A | AGGRESSIVE_BUY |
| ≥ 75 | B+ | ACCUMULATE |
| ≥ 70 | B | ACCUMULATE |
| ≥ 60 | C | WATCH |
| ≥ 50 | D | WATCH |
| < 50 | F | WATCH |

---

## API Endpoints

```
POST /scores/evaluate
    Body: ScoreRequest { ticker, asset_class, gate_data? }
    - Looks up latest passing gate result from DB
    - If not found + gate_data provided: runs inline gate
    - If not found + no gate_data: returns 422
    Returns: Full ScoreResponse with factor_details

GET /scores/
    Query: ?recommendation=AGGRESSIVE_BUY (optional filter)
    Returns: Last 20 scores ordered by scored_at desc

GET /scores/{ticker}
    Returns: Latest score for ticker
```

---

## Dependencies

- `app/scoring/quality_gate.py` — gate result for credit_rating and dividend_history_years
- `app/scoring/data_client.py` → Agent 01 `:8001`
- `numpy` — Monte Carlo simulation
- `httpx` — async HTTP client
- `platform_shared.income_scores` — persistence

---

## Success Criteria

- Scores fall within 0–100 range for all inputs
- Missing data produces partial credit (not zero, not error)
- NAV erosion penalty only applied to COVERED_CALL_ETF
- Factor details JSON contains all 8 sub-components with `score`, `max`, `value`
- `data_completeness_pct` accurately reflects missing fields
- 92 unit tests passing (66 scorer + 26 NAV erosion)

---

## Non-Functional Requirements

- **Latency:** < 500ms per evaluation (dominated by Agent 01 HTTP calls)
- **Monte Carlo:** < 100ms for 10,000 simulations (numpy vectorized)
- **Graceful degradation:** Returns partial score when Agent 01 unavailable
- **Test coverage:** 92 tests, all edge cases covered
