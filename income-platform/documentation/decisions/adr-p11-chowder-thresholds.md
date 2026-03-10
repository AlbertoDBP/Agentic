# ADR-P11 — Chowder Number Threshold Management (Deferred)

**Status:** Deferred — Review Before Agent 12 Implementation
**Date:** 2026-03-09

## Context

Amendment A2 added Chowder Number scoring to Agent 03 with a simple
asset-class-based threshold table:

```python
CHOWDER_THRESHOLDS = {
    "DIVIDEND_STOCK":   {"attractive": 12.0, "floor": 8.0},
    "COVERED_CALL_ETF": {"attractive": 8.0,  "floor": 5.0},
    "BOND":             {"attractive": 8.0,  "floor": 5.0},
}
```

This is a known simplification. The Chowder Rule in DGI practice uses
different thresholds by **industry/sector**, not just asset class:

- Utilities: ≥ 8% (lower growth expected)
- REITs: ≥ 8% (high yield, lower growth)
- Financials: ≥ 12%
- Technology: ≥ 15% (lower yield, higher growth expected)
- Consumer Staples: ≥ 12%

A DIVIDEND_STOCK classified ticker could be a utility (threshold 8%) or
a tech company (threshold 15%) — the current flat 12% is a compromise
that will misclassify edge cases.

## Problem

1. `platform_shared.securities.sector` is currently NULL for most tickers
   (FMP paid plan required to populate it)
2. Agent 04 classifies asset class but not industry/sector
3. No threshold configuration system exists — thresholds are hardcoded
   in `income_scorer.py`

## Options to Evaluate

**Option A — Sector-aware threshold table**
Extend `CHOWDER_THRESHOLDS` to include sector keys alongside asset class.
Read `sector` from `market_data["fundamentals"]` with asset_class fallback.

**Option B — Database-driven thresholds**
Store thresholds in `platform_shared.user_preferences` or a new
`platform_shared.scoring_thresholds` table. Admin-configurable without
code deploy.

**Option C — ML-derived thresholds**
Use historical Chowder Number distributions per sector/asset_class to
derive thresholds statistically. Revisit in v3 adaptive scoring roadmap.

**Option D — Industry classification layer**
Add a dedicated industry classifier (sub-layer of Agent 04) that maps
tickers to GICS sectors. Use GICS sector as primary threshold key.

## Trigger for Resolution

Review this ADR when:
1. FMP paid plan is active (sector data available for most tickers)
2. Agent 12 (Proposal Agent) is being designed — threshold accuracy
   directly affects proposal quality
3. Universe exceeds 50 unique tickers with known sector data

## Current Behavior (Accepted Interim)

- DIVIDEND_STOCK → 12% threshold (may over-penalize utilities/REITs)
- COVERED_CALL_ETF → 8% threshold (reasonable)
- BOND → 8% threshold (reasonable)
- `INSUFFICIENT_DATA` when yield or cagr is None

## Consequences of Deferral

- Utility and REIT dividend stocks may show `UNATTRACTIVE` chowder signal
  when they should show `BORDERLINE` (conservative bias — acceptable)
- No user-visible impact until Agent 12 uses chowder_signal in proposals
- Chowder is 0% score weight — no scoring impact, only signal label
