# Opportunity Scanner v2 — Design Spec

**Date:** 2026-03-26
**Status:** Approved
**Replaces:** Agent 07 v1.0.0 (basic scan UI + POST /scan)

---

## 1. Overview

Scanner v2 replaces the existing standalone scanner page and extends Agent 07 (port 8007) with three new capability layers delivered as four vertical feature slices:

| Slice | Capability | Touches |
| --- | --- | --- |
| 1 | Scanner UI — input modes, filter panel, results table | Frontend only |
| 2 | Portfolio-aware scan — gap/replacement/concentration lenses | Agent 07 backend + Frontend |
| 3 | Entry/exit price engine — limit order prices, zone status | Agent 07 backend + Frontend |
| 4 | Proposal handoff — select tickers → Agent 12 draft | Agent 07 stub + Frontend |

No new agent is introduced. No Agent 01 changes are required — all technical indicator data (`sma_50`, `sma_200`, `rsi_14d`, `support_level`, `resistance_level`) is already fetched from FMP and cached in `platform_shared.market_data_cache` by Agent 07's existing `market_cache.py`.

---

## 2. Architecture

```text
Next.js /scanner page
  └── ScannerPage
        ├── InputPanel       — mode: manual | portfolio | universe
        ├── FilterPanel      — collapsible, all Group 1 + Group 2 filters
        ├── LensPicker       — gap | replacement | concentration (Slice 2)
        ├── ResultsTable
        │     ├── ScoreBadge         — traffic-light A/B/C/D/F + grade
        │     ├── EntryExitColumns   — entry $, current $, exit $ (Slice 3)
        │     ├── ZoneStatusBadge    — BELOW / IN ZONE / NEAR / ABOVE (Slice 3)
        │     ├── PortfolioBadges    — Held / Class ⚠ / Sector ⚠ / Replacing (Slice 2)
        │     ├── HealthBadges       — Income ✓/⚠  Durable ✓/⚠ (Slice 2)
        │     ├── ExpandedRow        — signal breakdown, sub-scores (Slice 3)
        │     └── SelectionCheckbox
        └── GenerateProposalButton   — enabled when ≥1 selected (Slice 4)

Agent 07 (port 8007) — extended endpoints
  POST /scan                     ← adds portfolio_id, portfolio_lens; returns entry_exit block
  GET  /scan/{scan_id}           ← existing endpoint, unchanged
  GET  /universe                 ← existing endpoint, unchanged
  GET  /quote/{symbol}           ← existing endpoint, unchanged
  POST /scan/{scan_id}/propose   ← Slice 4 handoff stub (new)
```

Frontend communicates with Agent 07 via the existing broker route handler (service auth injected server-side).

---

## 3. Slice 1 — Scanner UI

### 3.1 Input Modes

Three mutually exclusive modes selected by a tab control:

| Mode | Behaviour |
| --- | --- |
| **Manual** | Textarea: comma- or newline-separated ticker symbols. Supports up to 200 tickers (hard limit enforced by Agent 07). |
| **Portfolio** | Dropdown listing the user's portfolios (read from `platform_shared.portfolios`). Selecting a portfolio scans all its current positions. |
| **Universe** | Toggle. Sets `use_universe: true` in the scan request. Scans all active securities in `platform_shared.securities`. |

### 3.2 Filter Panel

Collapsible. Two filter groups matching existing Agent 07 API:

**Group 1 — Scoring filters:**

- Min Score (0–100 slider, default 0)
- Quality Gate Only toggle (default off)
- Asset Class multi-select (DIVIDEND_STOCK, COVERED_CALL_ETF, BOND, EQUITY_REIT, MORTGAGE_REIT, BDC, PREFERRED_STOCK)

**Group 2 — Market data filters (applied via SQL against market_data_cache):**

- Min Yield %
- Max Payout Ratio %
- Min / Max Price $
- Min / Max Market Cap $M
- Max P/E
- Min NAV Discount % (negative = discount; e.g. -5 means ≥5% discount)
- Min Average Daily Volume

### 3.3 Results Table

Columns (Slice 1):

| Column | Content |
| --- | --- |
| ☐ | Selection checkbox |
| Rank | Integer, ascending from 1 |
| Ticker | Symbol |
| Name | From `platform_shared.securities` |
| Class | Asset class |
| Score | Numeric + letter grade badge (traffic-light colour) |
| Rec | AGGRESSIVE_BUY / ACCUMULATE / HOLD / REDUCE / AVOID |
| Yield % | Dividend yield from market_data_cache |
| Price $ | Current price |
| Veto | Flag icon when `veto_flag: true` |

Stats bar above table: `N scanned · N passed · N vetoed`

Vetoed tickers collapsed by default behind "Show vetoed (N)" toggle.

### 3.4 Run Scan

"Run Scan" button triggers `POST /scan` via broker route handler. Loading state shown in table. Errors surfaced as inline alert.

---

## 4. Slice 2 — Portfolio-Aware Scan

### 4.1 API Extension

`POST /scan` gains two new optional parameters:

```json
{
  "portfolio_id": "uuid | null",
  "portfolio_lens": "gap | replacement | concentration | null"
}
```

When `portfolio_id` is provided, Agent 07 reads `platform_shared.positions` for that portfolio and annotates each result item with a `portfolio_context` block:

```json
{
  "portfolio_context": {
    "already_held": true,
    "held_shares": 150,
    "held_weight_pct": 4.2,
    "asset_class_weight_pct": 18.5,
    "sector_weight_pct": 32.1,
    "class_overweight": false,
    "sector_overweight": true,
    "is_underperformer": false,
    "underperformer_reason": null,
    "replacing_ticker": null
  }
}
```

**Overweight thresholds** (configurable via env vars, defaults):

- `CLASS_OVERWEIGHT_PCT` = 20 — asset class weight above this triggers `class_overweight: true`
- `SECTOR_OVERWEIGHT_PCT` = 30 — sector weight above this triggers `sector_overweight: true`

**Weight computation** — `asset_class_weight_pct` and `sector_weight_pct` are computed as:
`(held_shares × current_price) / sum(held_shares × current_price across all positions in portfolio)`.
`current_price` comes from `market_data_cache.price` for each held ticker. If a position's price is missing from cache, that position is excluded from the denominator.

**Underperformer definition** — a held position is flagged when either:

- `valuation_yield_score < 28` (income pillar below 70% of max 40), OR
- `financial_durability_score < 28` (durability pillar below 70% of max 40)

Sub-scores come from the most recent Agent 03 score for that ticker (fetched during scan).

### 4.2 Lens Logic

| Lens | Filter applied | Rank modifier |
| --- | --- | --- |
| `gap` | Exclude `already_held: true` | Score descending |
| `replacement` | Include only tickers in same asset class as ≥1 underperformer; `replacing_ticker` set to the lowest-scoring underperformer in that class. If multiple candidates map to the same underperformer, each gets its own row with the same `replacing_ticker`. | Score delta vs. `replacing_ticker` score, descending |
| `concentration` | All results included | Score × (1 - class_weight_pct/100) — rewards diversifying picks |
| `null` | No filter — annotate only | Score descending |

### 4.3 Frontend Changes

- Portfolio selector active when Portfolio input mode chosen
- Lens switcher tabs appear when a portfolio is selected: [Gap Finder] [Replacement] [Concentration]
- New result row badges (inline, after ticker name):
  - `[Already Held]` — grey pill
  - `[Class ⚠ 22%]` — amber, when `class_overweight: true`
  - `[Sector ⚠ 35%]` — amber, when `sector_overweight: true`
  - `[Replacing: TICKER]` — blue pill, in Replacement lens
- Sub-score health badges per row:
  - `[Income ✓]` green / `[Income ⚠]` amber
  - `[Durable ✓]` green / `[Durable ⚠]` amber

---

## 5. Slice 3 — Entry/Exit Price Engine

### 5.1 Data Sources

All inputs read from `platform_shared.market_data_cache` — no new FMP calls during scan:

| Field | Used for |
| --- | --- |
| `price` | Current price, zone status calculation |
| `week_52_high` | Technical exit signal |
| `week_52_low` | Technical entry signal |
| `sma_50` | Near-term support reference |
| `sma_200` | Long-term support (entry anchor) |
| `rsi_14d` | Momentum confirmation |
| `support_level` | Technical entry floor |
| `resistance_level` | Technical exit ceiling |
| `dividend_yield` | Yield-based entry/exit (percent, e.g. 6.5 = 6.5%) |
| `nav_value` | NAV-based entry/exit for CEF/BDC |

**Derived values** (computed at runtime, not stored):

- `annual_dividend = price × (dividend_yield / 100)` — derived from cache; if `price` or `dividend_yield` is null, yield signals are skipped
- `yield_entry_target = dividend_yield × 1.15` — proxy for historical high yield (15% above current yield); signal skipped if `dividend_yield` is null
- `yield_exit_target = dividend_yield × 0.85` — proxy for historical low yield (15% below current yield); signal skipped if `dividend_yield` is null

These proxies are used because historical yield percentile data is not yet available in the platform. When a `yield_history` table is introduced in a future version, these derivations can be replaced with actual percentile values.

### 5.2 Entry Price Calculation

Three signals computed per ticker (where data available). Entry limit = minimum of applicable signals:

| Signal | Formula | Skipped when |
| --- | --- | --- |
| Technical | `max(support_level, sma_200 × 1.01)` | `support_level` and `sma_200` both null |
| Yield-based | `annual_dividend / (yield_entry_target / 100)` | `price` or `dividend_yield` null |
| NAV-based *(CEF/BDC only)* | `nav_value × 0.95` | `nav_value` null or asset_class not CEF/BDC |

`entry_limit = min(applicable signals)`

If all signals are skipped (missing data), `entry_limit = null` and zone status = `UNKNOWN`.

### 5.3 Exit Price Calculation

Three signals computed per ticker. Exit limit = minimum of applicable signals (conservative):

| Signal | Formula | Skipped when |
| --- | --- | --- |
| Technical | `min(resistance_level, week_52_high × 0.95)` | `resistance_level` and `week_52_high` both null |
| Yield compression | `annual_dividend / (yield_exit_target / 100)` | `price` or `dividend_yield` null |
| NAV premium *(CEF/BDC only)* | `nav_value × 1.05` | `nav_value` null or asset_class not CEF/BDC |

`exit_limit = min(applicable signals)`

If all signals are skipped, `exit_limit = null`.

### 5.4 Zone Status

Based on current price vs. entry limit:

| Status | Condition | Colour |
| --- | --- | --- |
| `BELOW_ENTRY` | `price < entry_limit` | Green (strong signal) |
| `IN_ZONE` | `entry_limit ≤ price ≤ entry_limit × 1.03` | Green |
| `NEAR_ENTRY` | `price ≤ entry_limit × 1.05` | Amber |
| `ABOVE_ENTRY` | `price > entry_limit × 1.05` | Red |
| `UNKNOWN` | `entry_limit = null` | Grey |

### 5.5 API Response Extension

`ScanItemResponse` gains an `entry_exit` block:

```json
{
  "entry_exit": {
    "entry_limit": 44.80,
    "exit_limit": 52.80,
    "current_price": 47.10,
    "pct_from_entry": 5.1,
    "zone_status": "ABOVE_ENTRY",
    "signals": {
      "technical_entry": 44.80,
      "yield_entry": 45.60,
      "nav_entry": null,
      "technical_exit": 53.20,
      "yield_exit": 52.80,
      "nav_exit": null
    }
  }
}
```

### 5.6 Frontend Changes

New columns added to results table:

| Column | Content |
| --- | --- |
| Entry $ | `entry_limit` as dollar price (e.g. `$44.80`) |
| Current $ | `current_price` (e.g. `$47.10`) |
| Exit $ | `exit_limit` (e.g. `$52.80`) |

Zone status badge is per-row, displayed inside the `Entry $` cell alongside the dollar price (e.g. `$44.80 🟢`). It uses the colours from §5.4. There is no column-level badge.

Expanded inline row (click to expand) shows:

- Technical: 52w range progress bar, SMA-200 delta, RSI-14d
- Yield: current yield vs. entry/exit yield targets
- NAV: discount/premium to NAV (CEF/BDC only)
- All three signal prices for entry and exit side by side

---

## 6. Slice 4 — Proposal Handoff

### 6.1 Selection

Checkbox column in results table. "Generate Proposal →" button enabled when ≥1 ticker selected.

### 6.2 Target Portfolio Selection

Before submission, the user must select a **target portfolio** — the portfolio the proposed positions will be added to. This is a required field.

- Presented as a dropdown in the confirmation modal, populated from `platform_shared.portfolios`
- If the scanner was run in Portfolio input mode, the scanned portfolio is pre-selected as the default but remains changeable
- Submission is blocked until a target portfolio is chosen

### 6.3 Handoff Endpoint

Agent 07 exposes a stub endpoint:

```text
POST /scan/{scan_id}/propose
Body: {
  "selected_tickers": ["MAIN", "ARCC"],
  "target_portfolio_id": "uuid"
}
Response: {
  "proposal_id": "uuid",
  "status": "DRAFT",
  "tickers": [...],
  "entry_limits": {...},
  "target_portfolio_id": "uuid"
}
```

`target_portfolio_id` is required. Returns 422 if omitted or if the portfolio does not exist.

Payload forwarded to Agent 12 when available. In the interim, Agent 07 writes the proposal draft to `platform_shared.proposal_drafts`.

Capital allocation per position is Agent 12's responsibility — not computed here.

### 6.4 Frontend

Confirmation modal shows:

- Selected tickers with their entry limit prices
- Target portfolio dropdown (required, pre-filled when applicable)
- Submit button disabled until portfolio selected

On success: toast notification with proposal ID. Redirect to Proposals page when it exists; otherwise stays on Scanner with success state.

---

## 7. Data Model Changes

### 7.1 market_data_cache — no changes

All required columns already exist.

### 7.2 scan_results — no schema changes

New `portfolio_context` and `entry_exit` fields stored within existing `items` JSONB column.

### 7.3 proposal_drafts — new table (Slice 4)

```sql
CREATE TABLE platform_shared.proposal_drafts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id             UUID REFERENCES platform_shared.scan_results(id),
    target_portfolio_id UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    tickers             JSONB NOT NULL,   -- [{"ticker": "MAIN", "entry_limit": 44.80, "exit_limit": 52.80, ...}]
    entry_limits        JSONB NOT NULL,   -- {"MAIN": 44.80, "ARCC": 18.90} — keyed by ticker for fast lookup
    status              TEXT NOT NULL DEFAULT 'DRAFT',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 8. Error Handling

| Scenario | Behaviour |
| --- | --- |
| Agent 03 failure for a ticker | Ticker skipped (existing behaviour); no entry_exit block |
| market_data_cache miss for a ticker | entry_exit block returned with nulls; zone_status = UNKNOWN |
| portfolio_id not found | 404 returned; scan does not proceed |
| portfolio has no positions | Scan proceeds on empty set; lens returns empty results |
| scan_id not found on POST /scan/{scan_id}/propose | 404 returned with `detail: "Scan {scan_id} not found"` |
| target_portfolio_id missing or invalid | 422 returned; proposal draft not written |
| Agent 12 unavailable (Slice 4) | proposal_drafts row written locally; user notified of pending status |

---

## 9. Testing

| Slice | New tests | Target |
| --- | --- | --- |
| 1 | Frontend component tests (InputPanel, FilterPanel, ResultsTable) | Vitest |
| 2 | Engine: portfolio annotation, lens filtering, underperformer detection | pytest (≥40 tests) |
| 3 | EntryExitEngine: all signal formulas, zone status thresholds, null-safety | pytest (≥40 tests) |
| 4 | Handoff endpoint: happy path, missing scan_id, missing portfolio, Agent 12 unavailable | pytest (≥15 tests) |

Existing 100 Agent 07 tests must continue to pass after each slice.

---

## 10. Out of Scope

- Agent 01 changes — not needed
- Agent 12 full implementation — Slice 4 provides stub + contract only
- Scheduled / automated scans — not in this iteration
- Score trend tracking (rising/falling movers) — backlog
- Historical yield percentile data — yield entry/exit signals use current yield as proxy where history unavailable
