# Proposal Execution Panel Enrichment — Design Spec

**Date:** 2026-03-30
**Status:** Approved

---

## 1. Problem

The execution panel shows only three fields (score, recommendation, entry range) before asking the user to commit cash. Critical data needed for an informed buy decision is available in the DB but not surfaced: current price vs entry zone, score sub-components, income and safety grades, sizing rationale, portfolio cash and income context. The portfolio impact bar also computes with hardcoded zeros for `currentAnnualIncome` and `currentPortfolioValue`.

---

## 2. Goals

1. Surface all decision-relevant data for a proposal inline — no extra clicks, no separate pages.
2. Fix portfolio impact bar to use real portfolio income and value figures.
3. Keep the single-API-call design: enrich the proposal response server-side rather than adding new frontend fetches.

---

## 3. Data Sources

| New field | Source table | Column |
|---|---|---|
| `current_price` | `platform_shared.market_data_cache` | `price` |
| `week52_high` / `week52_low` | `platform_shared.market_data_cache` | `week52_high`, `week52_low` |
| `nav_value` / `nav_discount_pct` | `platform_shared.market_data_cache` | `nav_value`, `nav_discount_pct` |
| `valuation_yield_score` | `platform_shared.income_scores` | `valuation_yield_score` |
| `financial_durability_score` | `platform_shared.income_scores` | `financial_durability_score` |
| `technical_entry_score` | `platform_shared.income_scores` | `technical_entry_score` |
| `zone_status` | computed | see §4 |
| `pct_from_entry` | computed | see §4 |

Portfolio `annual_income` and `blended_yield` are already returned by `GET /api/portfolios` (broker-service) but not typed in TypeScript — fix is adding the fields to the `Portfolio` type.

---

## 4. Zone Status Computation

Computed in Python inside `_proposal_to_response` after fetching `current_price`. The `ProposalResponse` model declares `zone_status: Optional[str] = None` but the runtime value is always set by the constructor — never left as `None`. If `current_price` is absent the function produces `"UNKNOWN"`. Frontend code receiving `null` (e.g. direct model construction) must treat it as `"UNKNOWN"`.

```
if current_price is None or entry_price_low is None:
    zone_status = "UNKNOWN"
elif current_price < entry_price_low:
    zone_status = "BELOW_ENTRY"
elif current_price <= (entry_price_high or entry_price_low):
    zone_status = "IN_ZONE"
else:
    zone_status = "ABOVE_ENTRY"

pct_from_entry = (current_price - entry_price_low) / entry_price_low
                 if both are not None else None
                 # negative = below entry; positive = above entry
```

`pct_from_entry` is included in the API response for future use (sorting by proximity to entry) but is not rendered in the current execution panel UI.

**`_enrich_proposals` anchor on `market_data_cache`:** the SQL selects from `market_data_cache` with the ticker IN list. If a ticker has no row there, it is absent from the returned dict — no enrichment, no score sub-components either. This is expected; `_proposal_to_response` falls back to all-None + zone_status `"UNKNOWN"`.

**`nav_discount_pct` sign convention:** stored as a signed decimal where negative means the fund trades at a discount to NAV (e.g. `-0.08` = 8% discount). This is the favorable condition for CEF buyers. The UI renders negative values in green, positive (premium) in amber.

---

## 5. Backend Changes

### `src/proposal-service/app/api/proposals.py`

Add `_enrich_proposals(db, tickers) -> dict[str, dict]` helper:
- Single SQL query with `IN (...)` against `market_data_cache` (LEFT JOIN `income_scores` LATERAL, latest row per ticker).
- Returns dict keyed by ticker with all enrichment fields.

Extend `ProposalResponse` with new optional fields (all `Optional[float]` or `Optional[str]`):
`current_price`, `zone_status`, `pct_from_entry`, `valuation_yield_score`, `financial_durability_score`, `technical_entry_score`, `week52_high`, `week52_low`, `nav_value`, `nav_discount_pct`.

Update `list_proposals` endpoint: call `_enrich_proposals` once for all returned tickers, pass enrichment data into `_proposal_to_response`.

Update `_proposal_to_response` signature: `_proposal_to_response(p, enrichment=None)`.

---

## 6. Frontend Changes

### `src/frontend/src/lib/types.ts`

Add to `Portfolio`:
```typescript
annual_income?: number | null;
blended_yield?: number | null;
```

Add to `ProposalWithPortfolio`:
```typescript
current_price?: number | null;
zone_status?: string | null;
pct_from_entry?: number | null;
valuation_yield_score?: number | null;
financial_durability_score?: number | null;
technical_entry_score?: number | null;
week52_high?: number | null;
week52_low?: number | null;
nav_value?: number | null;
nav_discount_pct?: number | null;
```

### `src/frontend/src/components/proposals/execution-panel.tsx`

Replace the 3-cell analysis block with two labeled sections:

**STOCK section** (inline data grid, 3 columns):
- Row 1: Current Price · Entry Range · Zone Status badge
- Row 2: Platform Score · Income Grade · Safety Grade
- Row 3: Platform Yield · Analyst Yield · Analyst Rec
- Sub-row: Valuation score · Durability score · Technicals score (smaller, muted)
- Thesis block (if present)
- Sizing rationale block (if present)

**PORTFOLIO section** (inline data grid, 3 columns):
- Cash · Total Value · Annual Income
- Blended Yield · Target Yield · Monthly Income Target

Zone badge colors: BELOW_ENTRY=blue, IN_ZONE=green, ABOVE_ENTRY=amber, UNKNOWN=gray.

### `src/frontend/src/components/proposals/execution-panel.tsx` — impact fix

Change lines 85–87:
```typescript
currentAnnualIncome: portfolio.annual_income ?? 0,
currentPortfolioValue: portfolio.total_value ?? null,
```

---

## 7. Component Map

| File | Change |
|---|---|
| `src/proposal-service/app/api/proposals.py` | Add `_enrich_proposals` helper; extend `ProposalResponse`; update `list_proposals` and `_proposal_to_response` |
| `src/proposal-service/tests/test_proposal_enrichment.py` | New — tests for zone_status computation and enrichment field mapping |
| `src/frontend/src/lib/types.ts` | Add fields to `Portfolio` and `ProposalWithPortfolio` |
| `src/frontend/src/components/proposals/execution-panel.tsx` | Rebuild analysis block; fix impact calculation inputs |

---

## 8. Key Constraints

- **Single DB round-trip**: `_enrich_proposals` runs one query for all tickers in the list response, not one per ticker.
- **LEFT JOIN only**: missing market data or scores → fields return `null`; frontend shows "—". Never errors.
- **No new API endpoints**: all data flows through the existing `GET /proposals` response.
- **Existing order form unchanged**: the shares ↔ dollar linkage, TIF, draft save all stay as-is.
- **SQLite test compatibility**: `_enrich_proposals` is patched in unit tests; zone_status computation is tested as a pure function.
