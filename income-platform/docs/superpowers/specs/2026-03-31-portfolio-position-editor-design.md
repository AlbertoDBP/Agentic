# Portfolio Position Editor & Enriched Detail Pane — Design Spec

**Date:** 2026-03-31
**Status:** Approved

---

## 1. Overview

Two related frontend improvements to the portfolio page:

1. **Manage Positions Panel** — a collapsible section at the top of the portfolio tab allowing users to add new positions and edit or remove existing ones (shares, average cost, purchase date).
2. **Enriched Position Detail Pane** — the existing read-only detail panel gains two new sections: *Portfolio Context* (concentration metrics computed client-side) and *Technicals* (SMA, RSI, 52-week range from existing position data).

Both are **purely frontend**. The admin-panel backend already exposes all required CRUD endpoints. No new backend work is needed.

---

## 2. Scope

### In scope
- Collapsible Manage Positions panel on the portfolio tab
- Inline row editing (shares, avg cost, purchase date)
- Add new position form (ticker, shares, avg cost, optional date)
- Remove position with inline confirmation
- Score refresh triggered after any mutation
- Portfolio Context section in the detail pane
- Technicals section in the detail pane

### Out of scope
- Bulk CSV import
- Portfolio creation / deletion
- Editing any field other than shares, avg cost, and acquired date
- Any backend changes

---

## 3. Architecture

### Files created
| File | Purpose |
|---|---|
| `src/frontend/src/app/api/portfolios/[id]/positions/route.ts` | Next.js proxy → `POST /api/portfolios/{id}/positions` on admin-panel |
| `src/frontend/src/app/api/positions/[id]/route.ts` | Next.js proxy → `PATCH` and `DELETE /api/positions/{id}` on admin-panel |

### Files modified
| File | Change |
|---|---|
| `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx` | Add Manage Positions panel; enrich detail pane with Portfolio Context + Technicals sections |

### Data flow
- All position context metrics (portfolio weight %, sector weight %, income weight %, rank) are derived from the `positions` array already loaded in component state — no extra API calls.
- Mutations (add, edit, delete) call the Next.js proxy routes, which forward to the admin-panel service.
- After a successful mutation, `POST /api/portfolios/{id}/refresh` fires in the background. A toast notification confirms when scores have updated.

---

## 4. Manage Positions Panel

### Placement & visibility
- Rendered at the top of the portfolio tab, above the holdings data table.
- Collapsed by default. Expand/collapse state persisted in `localStorage` keyed by `manage-positions-{portfolioId}`.
- Header shows: "Manage Positions" + chevron + position count badge.

### Add Position form
Always visible when panel is expanded. Fields:

| Field | Type | Validation |
|---|---|---|
| Ticker | text (uppercase) | Required, non-empty |
| Shares | number | Required, > 0 |
| Avg Cost / share | number (USD) | Required, > 0 |
| Purchase Date | date input | Optional |

- **"Add Position"** button disabled until Ticker and Shares and Avg Cost are valid.
- On submit: `POST /api/portfolios/{id}/positions` with `{ symbol, shares, cost_basis, acquired_date }`.
- On success: form clears, positions list refreshes, background refresh triggered.
- On error: inline error message below the form.

### Existing positions table
Columns: Ticker · Shares · Avg Cost · Total Cost (read-only, computed) · Date Acquired · Actions

**Read mode (default):**
- Ticker shown in monospace bold.
- Total Cost = shares × avg_cost (displayed, never sent to API).
- Date Acquired shows "—" if absent.
- Actions: **Edit** (indigo text) · **Remove** (red text).

**Edit mode (one row at a time):**
- Clicking Edit on a row converts Shares, Avg Cost, Date Acquired cells into inputs.
- Any other row in edit mode is cancelled automatically.
- Actions become: **Save** · **Cancel**.
- Save calls `PATCH /api/positions/{id}` with `{ quantity, avg_cost_basis, acquired_date }`.
- Cancel restores the original values with no API call.

**Remove flow:**
- Clicking Remove shows inline confirmation within the row: "Remove {TICKER}? **Confirm** · Cancel"
- Confirm calls `DELETE /api/positions/{id}`.
- On success: row removed from local state, background refresh triggered.

### Score refresh after mutation

After any successful add, edit, or delete:

1. `POST ${API_BASE_URL}/broker/portfolios/{id}/refresh` fires (fire-and-forget, errors swallowed). This is the same call already used by the manual refresh button on the portfolio page (`page.tsx:118`) — no new proxy route needed.
2. A toast appears: "Saving… scores will update shortly."
3. After 4 seconds the positions list re-fetches to pick up updated scores.

---

## 5. Enriched Detail Pane

### Portfolio Context section
Inserted **between Classification and Health** in the existing detail pane.

All values computed from the `positions` array in component state at render time.

| Row | Computation | Notes |
|---|---|---|
| Portfolio Weight | `position.current_value / Σ(positions.current_value)` | Shown as %, indigo progress bar |
| Sector Weight | `Σ(positions where sector = this.sector).current_value / Σ(all positions.current_value)` | Amber bar + label when > 30% |
| Income Weight | `position.annual_income / Σ(positions.annual_income)` | Only computed if annual_income > 0 |
| Rank by Value | Rank among positions sorted by current_value descending | Shown as "#N of M" |
| Rank by Income | Rank among positions sorted by annual_income descending | Shown as "#N of M" |

Two mini progress bars (5px height, rounded):
- **Portfolio Weight bar** — indigo fill.
- **Sector Weight bar** — green fill when ≤ 30%, amber fill when > 30%, with sector name label.

If `current_value` is zero or null for all positions, the section shows "—" for all computed fields.

### Technicals section
Inserted **between Portfolio Context and Health**.

All fields sourced from the existing `Position` type — no additional fetching.

| Row | Source field | Display |
|---|---|---|
| vs SMA-50 | `(price - sma_50) / sma_50 × 100` | Green "+X.X% ↑" if above, red "−X.X% ↓" if below |
| vs SMA-200 | `(price - sma_200) / sma_200 × 100` | Same pattern |
| RSI (14d) | `rsi_14d` | Raw value + label: < 30 → "oversold", > 70 → "overbought", else "neutral" |
| 52-wk range | `week52_low`, `week52_high`, `market_price` | Range bar with current price marker |

**52-week range bar:**
- 5px tall, full-width bar from `week52_low` to `week52_high`.
- Current price marker (2px vertical line) positioned at `(price - low) / (high - low)`.
- Colour gradient: green (near low) → indigo (near high).
- Low and high values shown as labels at each end; current price shown centred above the marker.

**Null handling:** If any field is null (data quality engine hasn't fetched it yet), that row shows "—" without error.

---

## 6. API Proxy Routes

### POST `/api/portfolios/[id]/positions`
```typescript
// Forwards to admin-panel: POST /api/portfolios/{id}/positions
// Body: { symbol, shares, cost_basis, acquired_date? }
// Returns: created position or error
```

### PATCH `/api/positions/[id]`
```typescript
// Forwards to admin-panel: PATCH /api/positions/{id}
// Body: { quantity?, avg_cost_basis?, acquired_date? }
// Returns: updated position or error
```

### DELETE `/api/positions/[id]`
```typescript
// Forwards to admin-panel: DELETE /api/positions/{id}
// Returns: 204 or error
```

All three use `Authorization: Bearer ${SERVICE_JWT_TOKEN}` header (same pattern as existing proxy routes). Use Next.js 15 async params pattern (`params: Promise<{...}>`).

---

## 7. Error Handling

| Scenario | Behaviour |
|---|---|
| Add ticker that already exists | API returns 409; show inline error "Position already exists — use Edit to update shares" |
| Network error during save | Inline error in the row / form; no state change |
| Refresh call fails after mutation | Silently swallowed; positions list still refreshes on a timer |
| Technicals field null | Row shows "—" |
| No positions in portfolio | Manage panel shows only the Add form; context section shows "—" |

---

## 8. Testing

- Unit: `computePortfolioWeight`, `computeSectorWeight`, `computeIncomeWeight` pure functions — test with sample positions arrays including edge cases (zero values, single position, missing sector).
- Unit: `formatSmaDeviation`, `rsiLabel` helpers.
- Integration: Add → verify row appears in table + refresh toast shown.
- Integration: Edit → Save → verify row updates.
- Integration: Remove → Confirm → verify row disappears.
- TypeScript: `npx tsc --noEmit` must pass with no new errors.
