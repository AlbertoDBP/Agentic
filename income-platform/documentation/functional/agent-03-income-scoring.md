# Functional Specification — Agent 03: Income Scoring Service

**Version:** 1.1.0
**Date:** 2026-03-09
**Port:** 8003
**Status:** ✅ Deployed — v1.1.0 update ready for deployment

---

## Purpose & Scope

Agent 03 scores income-generating assets using a quality gate + weighted scoring
engine. Capital preservation first — a 70% safety threshold with veto power over
yield-chasing strategies.

**v1.1.0 additions (Amendment A2):**
- Chowder Number computed and surfaced in score output (0% weight, informational)
- Chowder signal classification (ATTRACTIVE / BORDERLINE / UNATTRACTIVE / INSUFFICIENT_DATA)
- Direct read from `platform_shared.features_historical` for yield metrics

---

## Responsibilities

1. Run quality gate checks (credit rating, FCF, dividend history, AUM, track record)
2. Score tickers across three dimensions: valuation/yield, financial durability, technical entry
3. Apply NAV erosion penalty for covered call ETFs (Monte Carlo simulation)
4. Persist scores to `platform_shared.income_scores`
5. Cache quality gate results (24h TTL)
6. **[v1.1.0]** Compute and surface Chowder Number + signal from `features_historical`

---

## Scoring Dimensions (unchanged)

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Valuation / Yield | 40% | Yield attractiveness vs historical avg |
| Financial Durability | 35% | FCF, payout ratio, debt coverage |
| Technical Entry | 25% | RSI, MA proximity, support levels |
| NAV Erosion Penalty | — | Applied after scoring (ETFs only) |
| **Chowder Number** | **0%** | **Informational signal only** |

---

## Chowder Number (Amendment A2)

### Definition
`chowder_number = yield_trailing_12m + div_cagr_5y`

Both inputs sourced from `platform_shared.features_historical` (written by Agent 01 `/sync`).

### Thresholds (asset-class aware)

| Asset Class | ATTRACTIVE | BORDERLINE | UNATTRACTIVE |
|-------------|-----------|------------|--------------|
| DIVIDEND_STOCK | ≥ 12.0 | 8.0–11.99 | < 8.0 |
| COVERED_CALL_ETF | ≥ 8.0 | 5.0–7.99 | < 5.0 |
| BOND | ≥ 8.0 | 5.0–7.99 | < 5.0 |

**Note:** Sector-aware thresholds (utilities, REITs) deferred to ADR-P11 —
review before Agent 12 implementation.

### Signal values
- `ATTRACTIVE` — meets threshold for asset type
- `BORDERLINE` — below threshold, above floor
- `UNATTRACTIVE` — below floor
- `INSUFFICIENT_DATA` — yield or cagr missing from features_historical

### Fallback path
If `yield_trailing_12m` absent but `chowder_number` pre-computed in
`features_historical`, use the stored value directly.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/scores/evaluate` | Run quality gate + scoring, persist result |
| GET | `/scores/` | Last 20 scores (optional `?recommendation=` filter) |
| GET | `/scores/{ticker}` | Latest score for a ticker |
| GET | `/quality-gate/evaluate` | Run quality gate only |
| GET | `/health` | Service health |

---

## ScoreResponse (v1.1.0)

```json
{
  "ticker": "O",
  "asset_class": "DIVIDEND_STOCK",
  "valuation_yield_score": 82.0,
  "financial_durability_score": 75.0,
  "technical_entry_score": 68.0,
  "total_score_raw": 76.1,
  "nav_erosion_penalty": 0.0,
  "total_score": 76.1,
  "grade": "B",
  "recommendation": "BUY",
  "chowder_number": 14.2,
  "chowder_signal": "ATTRACTIVE",
  "factor_details": {
    "chowder_number": 14.2,
    "chowder_signal": "ATTRACTIVE",
    "...other factors...": {}
  },
  "data_quality_score": 0.88,
  "data_completeness_pct": 0.92,
  "scored_at": "2026-03-09T23:00:00"
}
```

---

## Data Sources

| Data | Source | Method |
|------|--------|--------|
| Price, fundamentals, dividends | Agent 01 HTTP | `MarketDataClient` |
| ETF metadata | Agent 01 HTTP | `MarketDataClient` |
| yield_trailing_12m, div_cagr_5y, chowder_number | `features_historical` DB | asyncpg direct read |

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| Agent 01 (port 8001) | Market data fetch |
| PostgreSQL `platform_shared` | Score persistence + features read |
| `platform_shared.features_historical` | Chowder inputs (written by Agent 01 /sync) |

---

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Score endpoint latency | ≤ 2s p95 |
| Quality gate cache | 24h TTL |
| Chowder read | asyncpg direct, ≤ 50ms |
| Chowder weight | 0% — no score impact |
