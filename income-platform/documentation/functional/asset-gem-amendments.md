# Functional Specification — Asset-Gem Amendments (A1–A4)

**Version:** 1.3.0
**Date:** 2026-03-09
**Status:** Specified — Implementation Pending

---

## Purpose & Scope

Four amendments to enhance the income signal quality of deployed agents 01, 03,
04, and the future Agent 12. No breaking changes to existing deployed APIs.
All changes are additive.

---

## Amendment A1 — Chowder Number & 5yr Avg Yield in features_historical

**Affects:** Agent 01 (data collection), Agent 03 (feature input)
**Schema:** `platform_shared.features_historical`

### New Columns

| Column | Type | Formula |
|--------|------|---------|
| `yield_5yr_avg` | DECIMAL(6,4) | 5-year rolling average of TTM yield |
| `chowder_number` | DECIMAL(6,2) | `yield_trailing_12m + div_cagr_5y` |

### Chowder Number Rules
- DGI stocks (non-utility): Chowder ≥ 12 = ATTRACTIVE
- Utility stocks: Chowder ≥ 8 = ATTRACTIVE
- Any: Chowder < 8 = UNATTRACTIVE
- Borderline: between thresholds

### Data Source
- `yield_trailing_12m` — already collected by Agent 01
- `div_cagr_5y` — already collected by Agent 01
- `yield_5yr_avg` — Agent 01 computes from historical yield series (5yr window)
- `chowder_number` — computed: `yield_trailing_12m + div_cagr_5y`

---

## Amendment A2 — Chowder Signal in Agent 03 Output

**Affects:** Agent 03 (scoring output)
**Weight:** 0% (informational only — does not affect income score)

### Output Addition

```json
{
  "income_score": 78.5,
  "grade": "B",
  "factor_scores": {
    "yield_quality": 82.0,
    "dividend_safety": 75.0,
    "nav_stability": 80.0,
    "chowder_number": 14.2,
    "chowder_signal": "ATTRACTIVE"
  }
}
```

### chowder_signal Values
- `ATTRACTIVE` — meets threshold for asset type
- `BORDERLINE` — below threshold, above floor
- `UNATTRACTIVE` — below floor
- `INSUFFICIENT_DATA` — < 5 years of dividend history

### Rationale
Chowder Number is a well-known DGI heuristic with strong community adoption.
At 0% weight it provides a cross-check signal for users without distorting the
platform's proprietary income score methodology.

---

## Amendment A3 — Named Entry Signal Flags in Agent 04 Output

**Affects:** Agent 04 (classification output)

### Output Addition

```json
{
  "asset_class": "dividend_growth_stock",
  "entry_signals": {
    "oversold_signal": false,
    "approaching_oversold": true,
    "near_50d_ma": true,
    "near_200d_ma": false,
    "golden_cross_active": true,
    "post_exdiv_dip_window": false,
    "near_support_level": false
  }
}
```

### Flag Definitions

| Flag | Definition |
|------|------------|
| `oversold_signal` | RSI < 30 |
| `approaching_oversold` | RSI 30–40 |
| `near_50d_ma` | Price within ±2% of 50-day MA |
| `near_200d_ma` | Price within ±2% of 200-day MA |
| `golden_cross_active` | 50d MA > 200d MA, crossover within 30 days |
| `post_exdiv_dip_window` | Within 5 days after ex-dividend date |
| `near_support_level` | Price within 3% above identified support level |

### Rationale
Named boolean flags are more readable and stable across API versions than
numeric thresholds. Consumer agents (Agent 12) can gate on specific flags
without re-implementing the detection logic.

---

## Amendment A4 — DCA Schedule in Agent 12 BUY Proposals

**Affects:** Agent 12 (proposal output)
**Trigger:** When proposed position value ≥ DCA threshold (default $2,000)

### Output Addition

```json
{
  "proposal_type": "BUY",
  "symbol": "JEPI",
  "rationale": "...",
  "dca_schedule": {
    "total_amount": 4000.00,
    "tranches": 4,
    "tranche_amount": 1000.00,
    "suggested_dates": [
      "2026-04-01",
      "2026-04-15",
      "2026-05-01",
      "2026-05-15"
    ],
    "frequency": "bi-weekly",
    "note": "DCA schedule is a suggestion only. User controls execution."
  }
}
```

### Rules
- 4 tranches, bi-weekly cadence (default)
- User-configurable: threshold, tranches, frequency
- **Never auto-executed** — user approves each tranche independently
- `dca_schedule` omitted when amount < threshold
- `dca_schedule` omitted for SELL proposals

### Rationale
Income investors benefit from cost averaging to reduce timing risk on entries.
4-tranche structure is a well-known DGI practice. Platform never executes —
user retains full control of each tranche decision.
