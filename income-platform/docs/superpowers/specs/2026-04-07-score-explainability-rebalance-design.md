# Score Explainability + Rebalance Analysis Design

**Date:** 2026-04-07
**Status:** Approved
**Scope:** Two linked features — score factor breakdown UI and Agent 08 engine improvements with Proposals page integration

---

## Overview

Two complementary features that surface actionable intelligence the platform already computes but doesn't expose clearly:

1. **Score Explainability** — visual breakdown of the 8 scoring sub-components per holding, surfaced as a modal (triggered from any score badge) and inline in the Health tab expander.
2. **Agent 08 Improvements + Rebalance Card** — engine updated to use HHS/UNSAFE/IES signals; results surfaced as a "Portfolio Health Check" card on the Proposals page.

These share one frontend touchpoint: clicking a ticker in the Rebalance card opens the Score Breakdown Modal, making them naturally integrated.

---

## Feature 1: Score Explainability

### Approach

Frontend-only. No backend changes. All required data (`factor_details`) is already returned by Agent 03's score response.

### Data Contract

`factor_details` structure (already in API response — `income_scorer.py` line 388 builds `{value, score, max}` per factor using `ceilings` dict derived from the active weight profile):

```json
{
  "payout_sustainability": { "value": 0.65, "score": 22, "max": 16 },
  "yield_vs_market":       { "value": 0.072, "score": 28, "max": 14 },
  "fcf_coverage":          { "value": 1200000, "score": 18, "max": 10 },
  "debt_safety":           { "score": 34, "value": 0.45, "max": 16 },
  "dividend_consistency":  { "value": 12, "score": 25, "max": 14 },
  "volatility_score":      { "value": 0.18, "score": 12, "max": 10 },
  "price_momentum":        { "value": 0.03, "score": 10, "max": 12 },
  "price_range_position":  { "value": 0.42, "score": 28, "max": 8 }
}
```

Note: the TypeScript `types.ts` definition currently shows `{value, score, weight}` — this is outdated. The actual API returns `{value, score, max}`. The TypeScript type should be updated as part of this task.

Pillar groupings (match existing health-tab.tsx naming conventions):
- **Income Pillar:** payout_sustainability, yield_vs_market, fcf_coverage
- **Durability Pillar:** debt_safety, dividend_consistency, volatility_score
- **IES Pillar (Technical):** price_momentum, price_range_position

### Directionality Labels

Derived from `score / max` ratio (frontend computation, no API change):

| Ratio | Label | Color |
|---|---|---|
| ≥ 0.85 | Strong | green |
| ≥ 0.65 | Moderate | yellow-green |
| ≥ 0.40 | Weak | amber |
| < 0.40 | Critical | red |

### Components

#### `ScoreBreakdownModal`

- Location: `src/frontend/src/components/ScoreBreakdownModal.tsx`
- Triggered by: clicking any HHS or IES badge in the Health tab (or Rebalance card)
- Props: `ticker: string`, `factorDetails: Record<string, {value: number | null, score: number, max: number}>`, `hhsScore`, `iesScore`, `hhsStatus`, `onClose`
- Layout: three sections (Income Pillar / Durability Pillar / IES Pillar), each with horizontal bar per factor showing score/max, label text, and raw `score/max` points
- Bars: filled portion = score/max ratio, color-coded by directionality label
- Footer: shows HHS score, IES score, hhs_status badge

#### Health Tab Inline Expander

- Location: `src/frontend/src/app/portfolios/[id]/tabs/health-tab.tsx`
- Behavior: clicking a row expands it inline to reveal a compact 2-column layout (Income | Durability side by side, Technical below)
- Layout: Income Pillar | Durability Pillar side by side, IES Pillar below
- Uses same directionality logic as modal
- "Full breakdown →" link at bottom opens `ScoreBreakdownModal` for that ticker

#### Score Badge — Clickable

- HHS and IES badges in the health tab gain `onClick` → opens `ScoreBreakdownModal`
- Visual: `cursor-pointer` + subtle ring on hover
- No change to existing badge color/status logic

### Error Handling

- If `factor_details` is null or empty: modal shows "Detailed breakdown not available for this score"
- If individual factor missing: render as 0/max with "–" label

---

## Feature 2: Agent 08 — Engine Improvements

### Current Gaps

| Gap | Impact |
|---|---|
| Ignores HHS/UNSAFE flag | A critically unsafe holding (durability 14/100) gets same priority as a minor grade issue |
| ADD proposals use any score ≥ 70 | Can recommend adding to a holding with poor entry timing (bad IES) |
| Capital allocation is naive (25% of available) | Doesn't prioritize which ADD closes the most income gap |
| Income gap computed but unused in rationale | User can't see how proposals connect to their income target |
| `violations_summary` is count-only | No HHS-tier picture of portfolio health |

### Engine Changes

**File:** `src/rebalancing-service/app/rebalancer/engine.py`

**Priority order (revised):**

UNSAFE is inserted as a new priority 0; existing priorities 1–4 (VETO, OVERWEIGHT, BELOW_GRADE, DEPLOY_CAPITAL) are unchanged in their relative ordering.

| Priority | Condition | Action |
|---|---|---|
| 0 | `unsafe_flag is True` (HHS durability ≤ 20) — NEW | SELL |
| 1 | `total_score < quality_gate_threshold` — unchanged | SELL |
| 2 | `weight_pct > max_position_pct` — unchanged | TRIM |
| 3 | `grade_val < min_grade_val` — unchanged | SELL |
| 4 | `ies_calculated is True AND ies_score >= 70` AND capital available — updated gate | ADD |

**ADD proposal logic changes:**
- Gate: `ies_calculated === True AND ies_score >= 70` (replaces `total_score >= 70`)
- Ranking: sorted by `estimated_income_contribution_annual` descending (yield_pct × proposed_add_value)
- Reason string includes: "Closes ~X% of your $Y annual income gap"

**New fields on `RebalanceProposal`:**
```python
hhs_score: Optional[float] = None
hhs_status: Optional[str] = None
unsafe_flag: Optional[bool] = None
ies_score: Optional[float] = None
ies_calculated: Optional[bool] = None
income_contribution_est: Optional[float] = None  # estimated annual $ income added
```

**Extended `violations_summary`:**
```python
{
  "count": 4,
  "unsafe": 1,
  "veto": 1,
  "overweight": 0,
  "below_grade": 1,
  "deploy_capital": 1,
  "hhs_tiers": {
    "UNSAFE": 1,
    "CONCERN": 0,
    "WATCH": 3,
    "GOOD": 8,
    "STRONG": 2
  }
}
```

**Scoring client note:**
`scoring_client.py` already returns the full Agent 03 JSON dict. No extraction changes needed there. The engine just needs to read `score_data.get("hhs_score")`, `score_data.get("unsafe_flag")`, etc. from the existing `score_data` dict.

### API Changes

**File:** `src/rebalancing-service/app/api/rebalance.py`

- `RebalanceProposal` model gains the 5 new optional fields above
- `RebalanceResponse` must gain an explicit `violations_summary: dict` field — it currently exposes only `violations_count: int`; the full summary dict is computed in `RebalanceEngineResult` but never serialized to the API response
- No new endpoints; existing `POST /rebalance/{portfolio_id}` returns enriched data

### Tests

New test cases in `src/rebalancing-service/tests/`:
- UNSAFE holding gets priority 0 (above VETO)
- ADD blocked when `ies_calculated = False`
- ADD blocked when `ies_score < 70`
- ADD proposals sorted by income_contribution_est descending
- `violations_summary.hhs_tiers` populated correctly
- Income gap string appears in ADD reason when gap > 0
- ADD reason degrades gracefully when `income_gap_annual is None` (no income metrics for portfolio)

---

## Feature 3: Proposals Page — Portfolio Health Check Card

### New Frontend Route

`src/frontend/src/app/api/portfolios/[id]/rebalance/route.ts`

- `POST` → forwards to Agent 08 `POST /rebalance/{portfolio_id}` with `save=false`
- Auth: uses `SERVICE_JWT_TOKEN` env var in `Authorization: Bearer` header, matching the pattern used by all other Next.js proxy routes (e.g. existing `/api/portfolios/[id]/route.ts`)
- Returns `RebalanceResponse` as-is
- No persistence on frontend side (analysis only)

### New Component

`src/frontend/src/components/RebalanceCard.tsx`

Props: `defaultPortfolioId?: string` (optional pre-selected portfolio). The component calls `usePortfolio()` internally to get the full `portfolios` list for the dropdown — it does not receive `portfolios[]` as a prop. `defaultPortfolioId` sets the initial selection when the card mounts.

**States:**
- `idle` — shows "Run Analysis" button
- `loading` — spinner while Agent 08 runs
- `result` — shows violations summary + proposals table
- `error` — shows error message with retry

**Result layout:**

```text
┌─ Portfolio Health Check ──────────────────── [▼ collapse] ─┐
│  [Portfolio dropdown if multiple]  [Run Analysis]           │
│                                                              │
│  4 violations · $1,200 tax savings available                 │
│                                                              │
│  UNSAFE ×1  VETO ×1  OVERWEIGHT ×0  BELOW_GRADE ×1         │
│  HHS tiers: 1 UNSAFE · 3 WATCH · 8 GOOD · 2 STRONG         │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│  UNSAFE  JEPI  SELL  −$4,200  Durability: 14/100  [↗ score] │
│  VETO    PSEC  SELL  −$1,800  Score: 58            [↗ score] │
│  ADD     MAIN  ADD   +$2,100  IES: 82 · Closes 12% gap      │
└──────────────────────────────────────────────────────────────┘
```

Note: no "Last run: X ago" timestamp — results are session-only (not persisted). State resets on page refresh. The card shows "Analysis ready" when results exist in session state and "Run Analysis" when idle.

**Behavior:**

- "Run Analysis" calls `POST /api/portfolios/[id]/rebalance`
- Results cached in component state only (no DB write; `save=false`)
- "↗ score" icon on each row opens `ScoreBreakdownModal` for that ticker
- Tax impact shown per SELL/TRIM: "Est. $340 savings · Long-term · No wash-sale risk"
- No "execute" button — this is read-only analysis; execution happens via manual proposals below

### Proposals Page Integration

**File:** `src/frontend/src/app/proposals/page.tsx`

The proposals page uses a fixed `flex h-[calc(100vh-4rem)] overflow-hidden` split layout (left sidebar w-72 + right panel flex-1). The `<RebalanceCard>` is placed **inside the right panel** as the default content shown when no proposals are selected and the sidebar is in "pending" view — replacing the current "Select proposals from the left to begin" empty state placeholder.

Concretely: in the right panel's `setup` phase with no selection and `sidebarView === "pending"`, render `<RebalanceCard>` above the "Select proposals..." message (or as a scrollable section within the right panel's existing overflow container). This requires no layout restructuring.

- Portfolio selector inside the card uses `portfolios` from `usePortfolio()` context (already available on the page)
- Collapsed by default; user expands to trigger analysis

---

## Testing Plan

### Score Explainability
- Unit: `directionality(score, max)` returns correct label for boundary values
- Integration: modal renders all 8 factors when `factor_details` populated
- Integration: modal shows fallback when `factor_details` null
- E2E: clicking HHS badge opens modal with ticker name in header

### Agent 08 Engine
- Unit: UNSAFE priority beats VETO priority
- Unit: ADD proposal not created when `ies_calculated = false`
- Unit: ADD proposal not created when `ies_score < 70`
- Unit: ADD proposals ordered by income_contribution_est desc
- Unit: `violations_summary.hhs_tiers` counts match holding statuses
- Integration: full `run_rebalance()` with mocked Agent 03 returning UNSAFE holding

### Proposals Page Card
- Component: idle state renders "Run Analysis" button
- Component: loading state shows spinner
- Component: result state renders violations summary and proposals
- Component: error state shows message with retry
- API route: forwards POST to Agent 08 and returns response

---

## Out of Scope

- Natural language per-factor commentary (LLM-generated) — deferred
- Persisting rebalance results to DB from the proposals page card (`save=false` always)
- "Execute" button on rebalance proposals — manual proposals workflow handles execution
- Multi-portfolio rebalance (batch) — single portfolio per analysis run
