# Proposal Execution Workflow — Design Spec

**Date:** 2026-03-30
**Status:** Approved

---

## 1. Problem

The current proposals page is read-only. "Accept" changes a DB status field but places no broker order, records no acquisition data, and gives no feedback. The analyst-to-execution chain is broken.

---

## 2. Goals

1. Before execution: let the user set order parameters (type, limit price, shares/dollars) and see portfolio impact (cash required, added income, new yield, concentration).
2. Execute: place broker orders automatically for connected portfolios; generate paper order sheets for unconnected portfolios.
3. After execution: show live order status (filled, partial, pending, cancelled) with actionable controls; auto-refresh from broker every 10 seconds; manual Refresh button also available.
4. On fill: write the confirmed position back into the portfolio (acquisition date, fill price, shares, cost basis) — server-side, atomically.

---

## 3. Scope

### In scope
- Redesign `src/frontend/src/app/proposals/page.tsx` into a two-phase view: **Execution Setup** → **Order Status**.
- DB migration: add `portfolio_id` column to `platform_shared.proposals`.
- New endpoint on broker-service: `POST /broker/positions/sync-fill` — atomic position upsert on confirmed fill.
- Wire proposal acceptance to broker-service `POST /broker/orders`.
- Broker fill polling via already-implemented `GET /broker/orders/{order_id}?broker=alpaca`.
- New endpoint on proposal-service: `POST /proposals/{id}/fill-confirmed` — transitions proposal to `executed_filled`.
- Paper order generation for non-broker portfolios: formatted block, copy/CSV/mark-as-executed.
- Cancel order via already-implemented `DELETE /broker/orders/{order_id}?broker=alpaca`.
- Partial fill management: cancel remainder or raise limit to market.
- Save Draft: localStorage only (no backend change).

### Out of scope

- Broker account connection setup.
- Historical fill analytics / reporting.
- Mobile layout.

---

## 4. UI Architecture

### Phase 1 — Execution Setup (replaces current detail panel)

**Layout:** two-pane — left list, right execution panel.

**Left pane:** proposals grouped by portfolio. Grouping key is `portfolio_id` on the proposal (added in Section 7). Each row shows ticker, alignment badge, score. Checkboxes for bulk selection. Cash balance shown per portfolio group.

**Right pane — Execution Panel:**

- Portfolio Impact bar at top: Cash Required · Added Annual Income · New Portfolio Yield · Concentration Δ. Computed inline on the frontend (see Section 6).
- Per-ticker tabs. Each tab contains:
  - **Analysis block:** platform score, recommendation, entry price range, NAV discount (if CEF), current concentration, suggested account (tax placement).
  - **Execution form:** Order type pills (Market / Limit / Stop-Limit), limit price input (pre-filled from `entry_price_low`), shares input + dollar input (linked, auto-convert), time-in-force selector (Day / GTC / IOC).
  - Alignment warning if Partial or Divergent.
- **Footer:** total summary ($ committed · +$/yr income · % cash remaining) + Reject All / Save Draft / Submit N Orders to [Broker] buttons.
- For portfolios with no broker: Submit button reads "Generate Paper Orders".

**Save Draft:** stores current form state (order params per ticker) to `localStorage` keyed by `proposal_id`. Restored on page reload for the same proposals. No backend change.

### Phase 2 — Order Status

Shown immediately after submit. Same left pane with status dots and badges (Filled / Partial / Pending / Paper). Right pane:

- Header: "X orders submitted · Y filled · Z partial · W pending" + submitted timestamp + "auto-refreshing" indicator + manual Refresh button.
- Per-ticker tabs, each with status badge.
- **Filled:** green confirmation card — shares, avg price, total paid, yield on cost, annual income added, fill timestamp.
- **Partial fill:** fill progress bar, metrics grid, action banner ("Cancel remaining N shares" / "Raise limit to market $X.XX").
- **Pending:** order details, Cancel Order button.
- **Paper:** formatted order block (BUY / symbol / qty / type / TIF / account), Copy · CSV export · Mark as Executed buttons. Mark as Executed prompts for actual fill price and date before syncing.
- Footer: confirmed filled value · pending value · annual income added so far · Back / Done buttons.

Auto-polling stops when all live orders reach a terminal state (filled / cancelled).

---

## 5. Data Flow

### Execution Setup → Submit

```
User sets params per ticker
  → POST /api/broker/orders (one call per selected ticker)
      body: { proposal_id, broker, portfolio_id, symbol, side:"buy",
              qty, order_type, limit_price, time_in_force }
  → broker-service POST /broker/orders
  → returns { order_id, status, broker_ref, broker }
  → frontend stores { order_id, broker } per ticker in component state
  → frontend transitions to Phase 2
  → proposal status set to executed_aligned (already done by existing "Accept" flow — no change needed here)
```

For paper portfolios:
```
  → No broker call
  → Generate paper order object from form values (ticker, qty, order_type, limit_price, TIF, portfolio)
  → Display in Phase 2 paper card
```

### Order Status Polling

Every 10 seconds, and on manual Refresh button click:
```
GET /api/broker/orders/{order_id}?broker={broker}
  → broker-service GET /broker/orders/{order_id}?broker={broker}
  → returns { status, filled_qty, avg_fill_price, filled_at, ... }
  → update per-ticker card in UI
  → on status change to "filled": trigger Post-Fill Portfolio Sync (Section 5.3)
  → on status change to "partially_filled": trigger partial sync for filled_qty so far
```

The `broker` query param comes from the placement response stored in component state. Polling stops when all orders are in a terminal state (filled / cancelled).

### Post-Fill Portfolio Sync

When broker returns `status: "filled"` or `status: "partially_filled"`:

```
POST /api/broker/positions/sync-fill
  body: {
    portfolio_id,
    ticker,
    filled_qty,             ← filled shares from broker response
    avg_fill_price,         ← from broker response
    filled_at,              ← acquisition date from broker response
    proposal_id,
    order_id,
    broker_ref
  }
```

This endpoint (on broker-service, see Section 7) reads the existing position row for `(portfolio_id, ticker)`, adds `filled_qty` shares, recomputes the weighted average cost basis server-side:

```
new_avg_cost = (existing_shares × existing_avg_cost + filled_qty × avg_fill_price)
               / (existing_shares + filled_qty)
```

Then upserts with the new totals and `acquisition_date = filled_at` (for new positions) or `last_add_date = filled_at` (for adds to existing positions).

After successful sync, frontend calls:
```
POST /api/proposals/{proposal_id}/fill-confirmed
  body: { filled_qty, avg_fill_price, filled_at }
```
Transitions proposal status to `executed_filled`.

For paper orders: sync triggered manually when user clicks "Mark as Executed". User enters actual fill price and date; these values are sent in the same `POST /api/broker/positions/sync-fill` body.

### Cancel Order

```
DELETE /api/broker/orders/{order_id}?broker={broker}
  → broker-service DELETE /broker/orders/{order_id}
  → on 200: update order card to Cancelled
  → call POST /api/proposals/{proposal_id}/fill-confirmed with status="cancelled"
      (transitions proposal to cancelled, no position sync)
```

For partial fills with cancel-remainder: `sync-fill` for already-confirmed shares first, then cancel.

### Transaction Record Handling

`POST /broker/orders` currently writes a transaction row immediately using `filled_avg_price or limit_price or 0`. This is acceptable as a placement record (audit trail). The spec adds no change to this behavior. The authoritative position data comes from `sync-fill` on fill confirmation — not from this transaction row. The transaction row should be understood as an order-placed log entry, not a confirmed position.

---

## 6. Portfolio Impact Calculation

Computed entirely on the frontend — no new API call needed.

Inputs already available in component state:

- `PortfolioListItem.cash_balance` — current available cash
- Proposal fields: `entry_price_low`, `position_size_pct`, `platform_yield_estimate` (fall back to `analyst_yield_estimate` if null)
- User-entered overrides: shares and limit price per ticker

Displayed values:

- **Cash Required:** `sum(shares × limit_price)` per selected ticker
- **Added Annual Income:** `sum(shares × limit_price × yield_estimate)` where `yield_estimate = platform_yield_estimate ?? analyst_yield_estimate`
- **New Portfolio Yield:** `(current_annual_income + added_annual_income) / (current_portfolio_value + cash_required)`
- **Concentration Δ:** `(position_value / new_total_portfolio_value)` per ticker

---

## 7. Backend Changes

### DB Migration — proposals table
Add column `portfolio_id UUID` (nullable) to `platform_shared.proposals`.

Update proposal-service persistence in `src/proposal-service/app/api/proposals.py` and the `run_proposal` call in `engine.py`: when `portfolio_id` is passed in the `GenerateRequest`, persist it to the proposals row.

This enables the frontend to group proposals by portfolio in the left pane.

### broker-service (`src/broker-service/app/api/broker.py`)

**New endpoint: `POST /broker/positions/sync-fill`**

```
Request body:
  portfolio_id: str
  ticker: str
  filled_qty: float
  avg_fill_price: float
  filled_at: datetime          ← acquisition date
  proposal_id: str (optional)
  order_id: str (optional)
  broker_ref: str (optional)

Behavior:
  1. Read current position row for (portfolio_id, ticker) — may not exist for new positions.
  2. Compute new totals:
       total_shares = existing_shares + filled_qty
       new_avg_cost = weighted average (see formula in Section 5.3)
  3. Upsert into platform_shared.positions:
       shares, cost_basis = new_avg_cost, acquisition_date (first buy) or last_add_date (subsequent adds)
  4. Return updated position row.

This is atomic within a DB transaction to prevent race conditions.
```

**Existing endpoints — no changes needed:**

- `GET /broker/orders/{order_id}?broker=alpaca` — already implemented (line 347)
- `DELETE /broker/orders/{order_id}?broker=alpaca` — already implemented (line 369)
- `POST /broker/orders` — already implemented; transaction-write behavior unchanged

### proposal-service (`src/proposal-service/app/api/proposals.py`)

**New endpoint: `POST /proposals/{id}/fill-confirmed`**

```text
Request body:
  filled_qty: float
  avg_fill_price: float
  filled_at: datetime
  status: "filled" | "partially_filled" | "cancelled"

Behavior:
  - "filled": set proposal.status = "executed_filled"
  - "partially_filled": set proposal.status = "partially_filled" (new status value)
  - "cancelled": set proposal.status = "cancelled"
```

Existing status flow: `pending → executed_aligned → executed_filled | cancelled`.

### Next.js proxy (`src/frontend/src/app`)

- `/api/broker/[...path]/route.ts` — already proxies all methods (GET, POST, DELETE). No change needed.
- `/api/proposals/[...path]/route.ts` — verify fill-confirmed endpoint is reachable. No new proxy file needed if existing catch-all handles it.

---

## 8. Error Handling

| Scenario | Behavior |
|---|---|
| Broker order placement fails for one ticker | Show error inline on that ticker's tab; other orders proceed |
| Broker unreachable during polling | Show "Last updated X min ago" warning; keep retrying |
| `sync-fill` fails after confirmed fill | Show warning badge on filled order card; offer manual retry; log error server-side |
| `fill-confirmed` call fails | Proposal stays `executed_aligned`; position is still synced; eventual consistency acceptable |
| Partial fill, GTC limit never hit | Order stays live; user can cancel remainder or raise limit to market |
| Paper "Mark as Executed" | Prompt for actual fill price and date; pass to `sync-fill` |
| Cancel fails at broker | Show error on order card; order remains in current status |

---

## 9. Component Map

| File | Change |
|---|---|
| `src/frontend/src/app/proposals/page.tsx` | Full redesign — Phase 1 execution setup, Phase 2 order status |
| `src/frontend/src/components/proposals/execution-panel.tsx` | New — Phase 1 right pane |
| `src/frontend/src/components/proposals/order-status-panel.tsx` | New — Phase 2 right pane |
| `src/frontend/src/components/proposals/portfolio-impact-bar.tsx` | New — inline impact bar |
| `src/frontend/src/components/proposals/order-card.tsx` | New — order status card (filled/partial/pending/paper variants) |
| `src/broker-service/app/api/broker.py` | Add `POST /broker/positions/sync-fill` endpoint |
| `src/proposal-service/app/api/proposals.py` | Add `POST /proposals/{id}/fill-confirmed` endpoint; persist `portfolio_id` on creation |
| `src/proposal-service/app/models.py` | Add `portfolio_id` column |
| DB migration | Add `portfolio_id UUID` column to `platform_shared.proposals` |

---

## 10. Key Constraints

- **No position record until fill confirmed** — `sync-fill` is only called when broker returns a fill status, not on order placement.
- **Cost basis is server-side only** — weighted average is computed in `sync-fill` endpoint, never on the frontend, to avoid race conditions.
- **Broker param is round-tripped** — `POST /broker/orders` response includes `broker` name; frontend stores it per order_id for use in polling and cancel calls.
- **Paper orders are local objects** — no broker call; position sync is manual via "Mark as Executed".
- **Polling is frontend-driven** — 10s interval, stops on terminal state; no webhook infrastructure needed.
- **Bulk execution is per-portfolio** — submit button scoped to the focused portfolio group.
- **Save Draft is localStorage only** — keyed by proposal_id; no backend state.
- **Transaction row at placement is an audit log** — not the authoritative position record; `sync-fill` is the source of truth.
