# Portfolio Frontend Redesign — Design Spec

**Date:** 2026-03-24
**Status:** Design Approved — Pending Implementation
**Depends on:** `2026-03-24-holding-health-score-framework-design.md` (HHS/IES framework)

---

## 0. Summary

Two interconnected changes:

1. **Backend** — Agent 03 (`ScoreResponse`) gains computed HHS/IES fields so the frontend receives health data in the HHS framework's terms rather than raw V6 pillars.
2. **Frontend** — The portfolio section is redesigned: a Grand Dashboard as the top-level view, a per-portfolio page with a 5-tab structure, and a unified design system applied consistently across all portfolio views.

Simulation and Income Projection tabs adopt the new design system and surface HHS/IES as scoring inputs; their internal logic is unchanged.

---

## 1. Backend Changes — Agent 03 ScoreResponse

### 1.1 New fields added to `ScoreResponse`

The HHS wrapper is implemented by adding computed fields to the existing response model. Agent 03 internals (`valuation_yield_score`, `financial_durability_score`, `technical_entry_score`) are **unchanged and still returned** for backward compatibility.

```python
class ScoreResponse(BaseModel):
    # ... all existing fields unchanged ...

    # ── HHS additions ──
    hhs_score: Optional[float] = None
    income_pillar_score: Optional[float] = None   # 0–100 normalized
    durability_pillar_score: Optional[float] = None  # 0–100 normalized
    income_weight: Optional[float] = None         # e.g. 0.35
    durability_weight: Optional[float] = None     # complement of income_weight
    unsafe_flag: Optional[bool] = None            # None when gate failed/insufficient
    unsafe_threshold: int = 20
    hhs_status: Optional[str] = None             # STRONG|GOOD|WATCH|CONCERN|UNSAFE|GATE_FAIL|INSUFFICIENT

    # ── IES additions ──
    ies_score: Optional[float] = None
    ies_calculated: bool = False
    ies_blocked_reason: Optional[str] = None      # UNSAFE_FLAG|HHS_BELOW_THRESHOLD

    # ── Quality Gate surface ──
    quality_gate_status: str = "PASS"             # PASS|FAIL|INSUFFICIENT_DATA
    quality_gate_reasons: Optional[list] = None

    # ── HHS commentary ──
    hhs_commentary: Optional[str] = None          # new commentary using only INC/DUR components
```

**`unsafe_flag` is `Optional[bool]`:** `None` when `quality_gate_status != "PASS"` (gate-failed or insufficient data). `True` when `durability_pillar_score <= unsafe_threshold`. `False` otherwise. The frontend treats `None` as "not evaluated" (distinct from "safe").

### 1.2 HHS computation logic

Add `_compute_hhs()` helper in `scores.py`, called **after** signal penalty is applied and **before** DB persist (between steps 5b and 6 in `evaluate_score`).

`_compute_ceilings()` is the existing standalone function in `income_scorer.py` — no new import needed (it is already in scope via `from app.scoring.income_scorer import IncomeScorer, ScoreResult`; add `_compute_ceilings` to that import).

The income and durability pillar scores are derived directly from the already-computed sub-totals (`valuation_yield_score`, `financial_durability_score`), normalized to 0–100 using the pillar budget from the weight profile. Scores are clamped to `[0, 100]` to handle edge cases where sub-component totals exceed the pillar ceiling (e.g., NAV erosion applied before this helper runs). `fcf_coverage` is part of `valuation_yield_score` and therefore included in the Income pillar (consistent with §1.3).

**`quality_gate_status` derivation — call site in `evaluate_score`:** In the existing code, failed gates are vetoed before scoring via HTTP 422. The only non-PASS case that reaches the scorer is `GateStatus.INSUFFICIENT_DATA` (treated as provisional pass). Derive the status string at the call site:

```python
# After step 5b (signal penalty), before step 6 (DB persist):
_gate_status = (
    "INSUFFICIENT_DATA"
    if getattr(gate_proxy, "status", None) == GateStatus.INSUFFICIENT_DATA
    else "PASS"
)
hhs_fields  = _compute_hhs(result, weight_profile, _gate_status)
ies_fields  = _compute_ies_gate(result, weight_profile, hhs_fields)
```

```python
_HHS_UNSAFE_THRESHOLD = 20  # durability pillar ≤ this → UNSAFE flag


def _compute_hhs(result: ScoreResult, profile: dict, gate_status: str) -> dict:
    if gate_status == "INSUFFICIENT_DATA":
        return {
            "hhs_score": None, "income_pillar_score": None,
            "durability_pillar_score": None, "unsafe_flag": None,
            "hhs_status": "INSUFFICIENT",
            "income_weight": None, "durability_weight": None,
            "unsafe_threshold": _HHS_UNSAFE_THRESHOLD,
        }

    wy = float(profile["weight_yield"])       # e.g. 40.0
    wd = float(profile["weight_durability"])  # e.g. 40.0

    # Normalize each pillar to 0–100, clamp to handle edge values
    inc_norm = min(100.0, round((result.valuation_yield_score  / wy) * 100, 2)) if wy > 0 else 0.0
    dur_norm = min(100.0, round((result.financial_durability_score / wd) * 100, 2)) if wd > 0 else 0.0

    # HHS weights: income vs durability proportionally (technical pillar excluded from HHS)
    total_hhs_budget = wy + wd
    income_w = round(wy / total_hhs_budget, 4) if total_hhs_budget > 0 else 0.5
    dur_w    = round(1.0 - income_w, 4)

    hhs    = round((inc_norm * income_w) + (dur_norm * dur_w), 2)
    unsafe = dur_norm <= _HHS_UNSAFE_THRESHOLD

    if unsafe:
        hhs_status = "UNSAFE"
    elif hhs >= 85:
        hhs_status = "STRONG"
    elif hhs >= 70:
        hhs_status = "GOOD"
    elif hhs >= 50:
        hhs_status = "WATCH"
    else:
        hhs_status = "CONCERN"

    return {
        "hhs_score": hhs,
        "income_pillar_score": inc_norm,
        "durability_pillar_score": dur_norm,
        "income_weight": income_w,
        "durability_weight": dur_w,
        "unsafe_flag": unsafe,
        "unsafe_threshold": _HHS_UNSAFE_THRESHOLD,
        "hhs_status": hhs_status,
    }
```

### 1.3 Factor-to-pillar mapping

The existing `factor_details` keys map to HHS pillars as follows. This mapping is used by the frontend Health Tab factor breakdown table (§5.4).

The **Income pillar score** is the full `valuation_yield_score` (all three yield sub-components: `yield_vs_market` + `payout_sustainability` + `fcf_coverage`), normalized to 0–100. The **Durability pillar score** is the full `financial_durability_score` (three durability sub-components), normalized to 0–100. Technical sub-components feed IES only and are excluded from HHS.

| `factor_details` key | HHS Pillar | Notes |
| ------------------- | --------- | ----- |
| `yield_vs_market` | **INC** | Yield sub-component |
| `payout_sustainability` | **INC** | Yield sub-component (payout ratio) |
| `fcf_coverage` | **INC** | Yield sub-component (dividend coverage by FCF) |
| `debt_safety` | **DUR** | Durability sub-component |
| `dividend_consistency` | **DUR** | Durability sub-component |
| `volatility_score` | **DUR** | Durability sub-component |
| `price_momentum` | **IES** | Technical — not part of HHS |
| `price_range_position` | **IES** | Technical — not part of HHS |
| `chowder_number` | **INC** (informational) | 0% weight, display only |
| `chowder_signal` | **INC** (informational) | display only |

Asset-class specific keys (e.g., `nav_erosion` for CEFs, `nii_coverage` for BDCs) follow the same pillar assignments as the HHS spec §3.3 sub-metric table.

### 1.4 IES gate

IES = Valuation 60% + Technical 40%, normalized to 0–100 using the pillar budgets. `_compute_ies_gate()` is a new helper added to `scores.py`. It receives the `hhs_fields` dict returned by `_compute_hhs()`, unpacks the needed values, and returns a second dict with all IES fields.

```python
def _compute_ies_gate(result: ScoreResult, profile: dict, hhs_fields: dict) -> dict:
    hhs_score   = hhs_fields["hhs_score"]    # float or None
    unsafe_flag = hhs_fields["unsafe_flag"]  # bool or None

    # IES requires PASS gate (hhs_score not None) + HHS > 50 + not UNSAFE
    # unsafe_flag is False (not None) must be checked explicitly to avoid
    # treating None (gate-failed / INSUFFICIENT_DATA) as "safe"
    if hhs_score is not None and hhs_score > 50 and unsafe_flag is False:
        wy  = float(profile["weight_yield"])
        wt  = float(profile["weight_technical"])
        raw = result.valuation_yield_score * 0.60 + result.technical_entry_score * 0.40
        mx  = wy * 0.60 + wt * 0.40
        return {
            "ies_score": min(100.0, round((raw / mx) * 100, 2)) if mx > 0 else 0.0,
            "ies_calculated": True,
            "ies_blocked_reason": None,
        }

    # Determine why IES was blocked
    if hhs_score is None:
        reason = "HHS_BELOW_THRESHOLD"   # gate-failed / INSUFFICIENT_DATA → no HHS
    elif unsafe_flag is True:
        reason = "UNSAFE_FLAG"
    else:
        reason = "HHS_BELOW_THRESHOLD"

    return {"ies_score": None, "ies_calculated": False, "ies_blocked_reason": reason}
```

### 1.5 HHS commentary

Add `_generate_hhs_commentary()` alongside existing `_generate_commentary()`. New function references only INC/DUR pillar components. Existing `score_commentary` is unchanged (still V6-based for backward compat). `hhs_commentary` is the field shown in the Health Tab detail pane.

`hhs_commentary` is **persisted as a plain string column** in `income_scores` (same as `score_commentary`). It is generated at score time by `_generate_hhs_commentary()` and written to the DB alongside the other HHS fields. `_orm_to_response()` reads it back directly from the ORM row — it is never regenerated at read time. Legacy rows (no HHS data) have `NULL` for this column; the frontend falls back to `score_commentary` with a "V6 commentary" label.

### 1.6 New portfolio aggregate endpoints

Two new endpoints added to the **`broker-service`** (the existing service that owns portfolio and position data). The broker-service fetches HHS/IES score data for each holding by calling `GET /scores/{ticker}` on Agent 03's API (same pattern used by Agent 07). Aggregation (weighted averages, HHI, concentration bars) is computed in the broker-service from the collected `ScoreResponse` objects. If Agent 03 is unavailable, the endpoint returns portfolio identity fields with all aggregate score fields as `null` and an `"scores_unavailable": true` flag — the frontend renders KPI cells as "—" in this case.

```text
GET /portfolios
→ List of portfolio summaries (id, name, tax_status, broker, holding_count, last_refresh)
  + per-portfolio aggregates: agg_hhs, naa_yield, total_value, annual_income,
    total_return, hhi, sharpe, sortino, unsafe_count, gate_fail_count

GET /portfolios/{id}/summary
→ Full portfolio-level metrics for the portfolio page:
  all fields above + concentration_by_class[], concentration_by_sector[],
  top_income_holdings[] (top 5: ticker, class, annual_income, income_pct),
  unsafe_holdings[] (ticker, durability_score)
```

These endpoints aggregate from existing position and score data in the DB. If NAA Yield data is partially unavailable (tax data missing), individual holdings fall back to gross yield and the aggregate is flagged with `naa_yield_pre_tax: true` (per HHS spec §3.5).

### 1.7 DB migration and ORM hydration

`income_scores` table gains nullable columns for all new `ScoreResponse` fields. Existing rows return `NULL` until re-scored. No data loss.

`_orm_to_response()` in `scores.py` must be updated to hydrate all new HHS/IES fields from the ORM row. New fields read directly from the `IncomeScore` ORM model columns (same names as `ScoreResponse`). The `IncomeScore` SQLAlchemy model must also be extended with these columns. When serving cached scores via `GET /scores/{ticker}`, the new fields populate from the DB row; legacy rows (scored before this release) return `None` for all HHS/IES fields — the frontend treats this as "not yet scored under HHS framework" and shows a "Rescore to see HHS" prompt.

---

## 2. Navigation Architecture

```text
/dashboard
  └── /portfolios/[id]?tab=portfolio|market|health|simulation|projection
```

**No route rename needed:** `/market/[symbol]` already exists in the codebase as the individual-stock detail page. `/portfolio/[symbol]` also exists and is retained unchanged (see §7). The new portfolio-level routes use `/portfolios/[id]` (plural), which has no collision with either existing route.

---

## 3. Grand Dashboard (`/dashboard`)

### 3.1 Layout

```text
┌─ App Nav ───────────────────────────────────────────────────────┐
│  Logo  |  Dashboard · Scanner · Calendar · Alerts · Settings   │
│                                                  Last refresh ? │
└─────────────────────────────────────────────────────────────────┘
┌─ Aggregate Strip (6 KPIs) ──────────────────────────────────────┐
│  Total AUM | Ann. Income | Blended NAA Yield | Avg HHS |        │
│  Portfolios | ⚠ UNSAFE total                                    │
└─────────────────────────────────────────────────────────────────┘
┌─ Portfolio Card Row (horizontal scroll) ────────────────────────┐
│  [ Card 1 ] [ Card 2 ] [ Card 3 ] [ + Add ]  ← scroll →  ◀ ▶  │
└─────────────────────────────────────────────────────────────────┘
```

**Empty state (0 portfolios):** Full-width placeholder card with "No portfolios yet. Create your first portfolio to get started." and a primary CTA button.

**Loading state:** Aggregate strip shows skeleton shimmer cells; card row shows 3 skeleton cards.

**Error state:** Inline error banner with retry button.

### 3.2 Aggregate strip (6 KPIs)

| # | Field | Computation | Help text |
| - | ----- | ----------- | --------- |
| 1 | Total AUM | Sum of market value | "Combined market value across all portfolios." |
| 2 | Ann. Income | Sum of projected annual dividends | "Projected annual income based on current dividends." |
| 3 | Blended NAA Yield | Income-weighted average NAA Yield across all holdings. Holdings missing tax data use gross yield; strip shows `PRE_TAX*` indicator if any fallback applied. | "Net After-All Yield weighted by income contribution. * = some holdings shown pre-tax." |
| 4 | Avg HHS | Value-weighted average `hhs_score` (gate-failed and stale >24h excluded) | "Position-weighted average HHS across all portfolios. Gate-failed and stale holdings excluded." |
| 5 | Portfolios | Count of active portfolios | — |
| 6 | ⚠ UNSAFE | Count of `unsafe_flag = True` across all portfolios | "Holdings where Durability ≤ unsafe threshold. Immediate review recommended." |

### 3.3 Portfolio card

**Width:** 300px fixed (desktop), ~85vw (mobile `< 640px`). Scroll snap align start.

**Sections:**

1. **Header:** Name · meta (tax status, broker, holding count, last refresh) · Aggregate HHS top-right (color-coded, position-weighted same as §4.2 Agg HHS)
2. **KPI grid (3×2):** Value · Ann. Income · NAA Yield · Total Return · HHI · Holdings count
3. **Concentration bar:** Horizontal stacked bar (asset-class color palette) + legend
4. **Footer:** Badge row (UNSAFE count or "✓ All healthy", tax status tag, broker tag) · "Open →" jump button

**Interaction:** Entire card and jump button navigate to `/portfolios/[id]`.

**Add Portfolio card:** Always last; dashed border, ghost style, disabled state with tooltip "Portfolio creation coming soon."

### 3.4 Horizontal scroll

- Single `overflow-x: auto` flex row, `scroll-snap-type: x mandatory`
- ◀ ▶ buttons scroll by one card width (JS `scrollBy`)
- Custom scrollbar: 5px height, rounded, color `--border2`

---

## 4. Portfolio Page (`/portfolios/[id]`)

### 4.1 Portfolio Identity Header

Always visible. Never collapses.

**Left:** Portfolio name · tax status badge · broker badge · UNSAFE badge (red, if unsafe_count > 0)
**Meta row:** holdings count · last refresh timestamp · account (masked) · opened date
**Right:** ← All Portfolios · Refresh ↻ · Export ↓ · ? Help

### 4.2 Compressed KPI Strip (8 metrics)

Always visible. Responsive grid: 8col (≥1100px) → 4col (640–1099px) → 2col (<640px).

| Metric | Color | Help text |
| ------ | ----- | --------- |
| Agg HHS | green ≥70 / amber 50–69 / red <50 | "Position-weighted average HHS. Gate-failed and stale holdings excluded." |
| NAA Yield | green | "Net After-All Yield: (Gross Div − Fee Drag − Tax Drag) / Total Invested." |
| Total Value | neutral | — |
| Annual Income | blue | — |
| Total Return | purple/green/red | "(Current Value − Cost Basis + Income − Tax Drag) / Cost Basis." |
| Sharpe | neutral | "Excess return per unit of volatility." |
| HHI | green < threshold / amber ≥ threshold | "Herfindahl-Hirschman Index. Flag at >0.10 (moderate profile)." |
| ⚠ UNSAFE | red alert style if > 0 | "Holdings where Durability ≤ 20. Immediate review." |

Loading state: skeleton shimmer on each KPI cell.

### 4.3 Collapsible Summary Section

Collapsible header bar between KPI strip and tab bar. **Default: expanded.**

**Collapsed state:** Bar shows one-liner with active alerts (e.g., "Fin. Services 48% · 2 UNSAFE · BDC 32%"). Critical info never fully hidden.

**Expanded — three panels (responsive: 3col → 2col → 1col):**

#### Panel A — Asset Class Concentration

- Color bar + row list (class · value · %)
- Sorted by % descending
- Colors from asset-class palette (§6.1)

#### Panel B — Top Income Contributors

- Top 5 holdings by annual income
- Each row: ticker · class badge · annual income · % of total income · inline bar
- UNSAFE tickers shown in amber with ⚠

#### Panel C — Sector / Industry Concentration

- Row list: sector · proportional bar · %
- Amber warning when any single sector exceeds the active risk profile's **sector concentration threshold**: conservative 20% / moderate 25% / aggressive 35% (distinct from the single-holding HHI thresholds in the HHS spec §6.2)
- Risk profile sourced from portfolio settings

### 4.4 Tab Bar

Five tabs, horizontally scrollable on all screen sizes.

```text
[ Portfolio ] [ Market ] [ Health ] [ Simulation ] [ Income Projection ]
```

Active tab state in URL: `?tab=portfolio` (default), `?tab=market`, `?tab=health`, `?tab=simulation`, `?tab=projection`. Deep-linkable.

---

## 5. Tab Designs

### 5.1 Shared Table Conventions

Every tab table implements:

| Feature | Implementation |
| ------- | -------------- |
| **Frozen Ticker column** | `position: sticky; left: 0`; teal left border (`2px solid --teal`) as visual indicator; "Ticker frozen" badge in toolbar |
| **Sortable columns** | Click header to sort asc/desc; ↕ icon on every sortable column header |
| **Column selector** | "Columns ⚙" opens a popover checkbox list of all available columns; preference persisted in `localStorage` per tab |
| **Freeze toggle** | "Freeze ❄" button. Three states cycle: Ticker only → Ticker + Class → None. Current state shown in toolbar. |
| **Filter bar** | Text input for live case-insensitive filtering across ticker and name columns |
| **Scroll elevators** | Fixed bottom rail below each table: ▲▼ vertical + ◀▶ horizontal buttons; JS `scrollBy` on the table scroll container |
| **Sticky header** | `position: sticky; top: 0` on `<thead>` rows |
| **Max height** | Table body: `max-height: calc(100vh - [header offset])` with `overflow-y: auto` so elevators stay in viewport |
| **Export** | "Export ↓" → CSV download of current visible columns |
| **Row selection** | Click row → highlighted; opens detail pane. Click again or press Esc → deselects, closes pane. |
| **Loading state** | Skeleton rows (5 shimmer rows) while data loads |
| **Empty state** | "No holdings found" message with clear-filter button if filter is active |

**Detail pane behavior by viewport:**

- Desktop ≥1100px: side panel (360px fixed width); table narrows
- Tablet 640–1099px: right overlay (80vw, full height, dim backdrop); ✕ or backdrop tap to dismiss
- Mobile <640px: bottom sheet (85vh); swipe down or ✕ to dismiss

### 5.2 Portfolio Tab

**Default columns:** Ticker · Class · Name · Shares · Avg Cost · Price · Mkt Value · % Port · Ann. Income · NAA Yield · Gross Yield · Unrealized G/L · Total Return · Ex-Date · Pay Date · Account · HHS

**Selectable columns:** Tax Drag · Fee Drag · Income Type · Opened Date · Lot Count · Monthly Income

**Detail pane sections:**

1. **Position** — shares, avg cost, price, value, cost basis, unrealized G/L, total return, % portfolio, % income
2. **Income** — annual dividend, monthly income, gross yield, NAA yield, tax drag, income type, ex-date, pay date, frequency
3. **Health Summary** — HHS with Income/Durability bars, UNSAFE alert (if applicable), gate status badge, grade, Chowder #/signal, scored timestamp. **Fallback for legacy scores:** when `hhs_score` is `None` (scored before this release), show a muted "Rescore to see HHS" prompt with a Refresh button in place of the pillar bars.

### 5.3 Market Tab

**Default columns:** Ticker · Class · Price · 52w High · 52w Low · YTD % · Div Yield · P/E · RSI · Beta · Mkt Cap

**Selectable columns:** Volume · Avg Vol (90d) · P/NAV · NII Coverage · Leverage · Non-accruals · Duration · Credit Rating · Sector · Industry

**Detail pane sections:**

1. **Price & Range** — price, 52w high/low, YTD return, volume, avg volume
2. **Fundamentals** — class-specific (see below)
3. **Technicals** — RSI, vs 200-DMA, % off 52w high

**Class-specific fundamentals:**

| Class | Fields shown |
| ----- | ------------ |
| BDC | NII/share, NAV/share, P/NAV, NII Coverage, Leverage, Non-accruals |
| REIT | AFFO yield, AFFO payout, Occupancy, Debt/EBITDA |
| CEF (Covered Call) | Distribution yield, NAV erosion (cumulative), Upside capture, Track record, AUM |
| MLP | DCF coverage, Leverage, Distribution growth, Distributable cash flow |
| Dividend Stock | EPS, Payout ratio, FCF/share, Div growth (5yr CAGR) |
| Bond/Bond ETF | YTM, Duration, Credit rating, Yield to worst |
| Preferred | Dividend yield, Cumulative status, Call date, Call protection |

### 5.4 Health Tab

**Default columns:** Ticker · Class · HHS · Income Pillar · Durability Pillar · Status · Gate · Grade · Chowder # · Signal · CB Level · IES · Scored

**CB Level column:** Sourced from Circuit Breaker monitor data when available. Displays "CAUTION", "CRITICAL", "EMERGENCY", or "—" if no active alert. CB integration is a future spec; this column renders "—" for all rows in Phase 1 with a tooltip: "Circuit Breaker integration coming in a future release."

**Status badge color rules:**

| Condition | Badge | Color |
| --------- | ----- | ----- |
| `hhs_status = STRONG` | STRONG | green |
| `hhs_status = GOOD` | GOOD | green |
| `hhs_status = WATCH` | WATCH | amber |
| `hhs_status = CONCERN` | CONCERN | orange (`--orange: #f97316`) |
| `unsafe_flag = true` | ⚠ UNSAFE | red (overrides all above) |
| `quality_gate_status = FAIL` | GATE FAIL | red-dim |
| `quality_gate_status = INSUFFICIENT_DATA` | NO DATA | muted |
| `unsafe_flag = null` | — | muted |

**Detail pane sections:**

1. **HHS Breakdown** — score value, formula line (`HHS = (Income × weight%) + (Durability × weight%)`), Income and Durability pillar bars, UNSAFE alert box (if `unsafe_flag = true`)
2. **Factor Breakdown table** — columns: Factor · Pillar (INC/DUR/IES tag) · Value · Score · Max. Rows use pillar mapping from §1.3. IES factors shown with muted style and labeled "IES — not part of HHS."
3. **IES** — score (0–100) with sub-scores if `ies_calculated = true`; gate-blocked message showing `ies_blocked_reason` if `false`
4. **Score Commentary** — `hhs_commentary` field (INC/DUR based). If null, falls back to `score_commentary` with a note "V6 commentary — HHS commentary not yet generated."
5. **Quality Gate** — status badge, failure reasons list (if FAIL), data completeness %, data quality score, last scored timestamp
6. **CB Alert** — rendered only if `cb_level` is present; shows level badge and description. Hidden in Phase 1 (CB integration deferred).

### 5.5 Simulation Tab

Existing `/income-simulation` content scoped to the current portfolio via `?portfolio_id=[id]` query param passed at tab load. Standalone `/income-simulation` route remains accessible.

**`portfolio_id` scoping behavior:** When `portfolio_id` is present, the simulation pre-populates the holdings list with the portfolio's current positions and filters all scenario views to that portfolio. Users may still add or remove holdings manually within the simulation. The internal logic (scenarios, projections, calculation engine) is unchanged; only the initial data load is filtered.

**Design-system alignment:**

- Replace current score display with `hhs_score`, `hhs_status`, `unsafe_flag` from `ScoreResponse`
- Apply color tokens from §6.1
- Apply responsive grid breakpoints from §6.3
- Context help (?) on all metric labels
- Table adopts shared conventions from §5.1

**Scoring integration:** `hhs_score` displayed per holding in scenario inputs. Holdings with `unsafe_flag = true` show amber warning in the scenario builder. `ies_score` surfaced where entry timing is evaluated.

### 5.6 Income Projection Tab

Existing `/projection` content scoped via `?portfolio_id=[id]`. Standalone route remains.

Same design-system alignment as §5.5. `hhs_score` used as reliability weighting: lower HHS → wider confidence band on projected income. UNSAFE holdings flagged in the projection timeline with ⚠ annotation.

---

## 6. Design System

### 6.1 Color Tokens

```css
/* Backgrounds */
--bg:       #060e1a
--surface:  #0d1d30
--surface2: #132540
--surface3: #1a2f4a

/* Borders */
--border:   #1e3a5f
--border2:  #2a4a6e

/* Text */
--text:     #e2e8f0   /* primary — 11.5:1 contrast on --bg */
--subtle:   #94a3b8   /* secondary — 5.9:1 on --bg */
--muted:    #64748b   /* labels — 3.1:1 on --bg (used only ≥0.625rem bold) */

/* Semantic */
--green:    #22c55e;  --green-dim: #14532d;  --green-bg: #0d2718
--blue:     #3b82f6;  --blue-dim:  #1e3a5f;  --blue-bg:  #071428
--amber:    #f59e0b;  --amber-dim: #78350f;  --amber-bg: #1a0e00
--orange:   #f97316;  --orange-dim:#7c2d12;  --orange-bg: #1a0d00  /* CONCERN status */
--red:      #ef4444;  --red-dim:   #7f1d1d;  --red-bg:   #1a0808

/* Asset classes */
--bdc:      #a78bfa   /* BDC — purple */
--reit:     #3b82f6   /* REIT — blue */
--cef:      #f59e0b   /* CEF — amber */
--mlp:      #2dd4bf   /* MLP — teal */
--stk:      #22c55e   /* Dividend Stock — green */
--bond:     #fde68a   /* Bond — light yellow */
--pref:     #f472b6   /* Preferred — pink */
```

All semantic text colors (`--text`, `--subtle`) meet WCAG AA (4.5:1) on `--bg`. `--muted` is used only for uppercase labels at ≥0.625rem bold (large text threshold of 3:1 met).

### 6.2 Typography

Body: `system-ui, -apple-system, sans-serif`.

| Use | Size | Weight |
| --- | ---- | ------ |
| Page / portfolio title | 1.05rem | 800 |
| Section label | 0.65rem | 700 uppercase |
| Table header | 0.65rem | 700 uppercase |
| Table cell | 0.78rem | 400 |
| KPI value | 0.95rem | 800 |
| KPI label | **0.625rem** | 700 uppercase |
| Detail pane value | 0.88rem | 700 |
| Detail pane label | 0.625rem | 400 |
| Tooltip | 0.68rem | 400 |
| Badge | 0.66rem | 700 |

Minimum label size is **0.625rem** (10px at 16px base) to meet WCAG AA for bold uppercase text.

### 6.3 Context Help System

Single global tooltip implemented as a **React Portal** (consistent with the existing `HelpTooltip` component pattern). A `<TooltipPortal>` renders into `document.body` at app init.

**Bubble markup:** `<HelpBubble tip="..." />` — reuses the existing `HelpTooltip` component, styled as a 14×14px circle with `?`.

**Positioning:** `position: fixed`, JS-computed from element's `getBoundingClientRect()`. Clamped to viewport. Font 0.68rem, max-width 200px, line-height 1.5.

**Content:** All tip strings live in `src/frontend/src/lib/help-content.ts`. New entries added for all HHS/IES fields, all new UI elements. No existing entries removed.

**Placement:** `?` bubble on every KPI label, table column header, pillar label, badge type, concentration metric, portfolio identity field, and aggregate strip metric.

### 6.4 Responsive Breakpoints

| Viewport | KPI Strip | Summary Panels | Detail Pane | Portfolio Cards |
| -------- | --------- | -------------- | ----------- | --------------- |
| ≥ 1100px | 8 columns | 3 columns | Side panel 360px | 300px fixed |
| 640–1099px | 4 columns | 2 columns | Right overlay 80vw + backdrop | 300px fixed |
| < 640px | 2 columns | 1 column | Bottom sheet 85vh | ~85vw |

Tab bar: `overflow-x: auto` horizontal scroll on all viewports.
Card scroll row: `overflow-x: auto` flex row on all viewports.

---

## 7. Routing

| Route | Page | Notes |
| ----- | ---- | ----- |
| `/dashboard` | Grand Dashboard | New root entry point for portfolio section |
| `/portfolio` | Redirect → `/dashboard` | Backward compat |
| `/portfolios/[id]` | Per-portfolio page, Portfolio tab | New route (plural) |
| `/portfolios/[id]?tab=market` | Market tab | Deep-linkable |
| `/portfolios/[id]?tab=health` | Health tab | Deep-linkable |
| `/portfolios/[id]?tab=simulation` | Simulation tab | Deep-linkable |
| `/portfolios/[id]?tab=projection` | Income Projection tab | Deep-linkable |
| `/portfolio/[symbol]` | Individual stock detail | **Unchanged.** Existing route retained as-is (symbol ≠ portfolio id — no collision) |
| `/market/[symbol]` | Individual stock detail | **Already exists** in the codebase. No action required — this route is already the alias. |

---

## 8. Loading, Error, and Empty States

| Component | Loading | Error | Empty |
| --------- | ------- | ----- | ----- |
| Aggregate strip | Skeleton shimmer per cell | Inline "Could not load" + retry | — |
| Portfolio card row | 3 skeleton cards | Error card with retry | "No portfolios yet" + CTA |
| Portfolio identity header | Skeleton | Error banner | — |
| KPI strip | Skeleton shimmer | Inline "—" per cell | — |
| Summary panels | Skeleton rows | Inline "Data unavailable" | "No holdings" |
| Tables | 5 skeleton rows | Error banner in table area | "No holdings found" / "Clear filter" if filtered |
| Detail pane | Skeleton sections | Error state per section | — |

---

## 9. What This Does Not Change

- Agent 03 internal scoring engine, curves, quality gates, Chowder computation
- V6 SAIS sub-metrics and scoring curves
- Existing `/scanner` page
- Existing `/calendar`, `/alerts`, `/market/[symbol]` (already exists — no change), `/portfolio/[symbol]` pages
- Agent 02–12 behavior
- Simulation and Income Projection internal logic
- `ScoringWeightProfile` model (read-only from frontend)
- `help-content.ts` structure — entries added only

---

## 10. Open Questions (deferred)

- **Portfolio creation UI:** "＋ Add Portfolio" card is rendered but disabled with tooltip. Form spec deferred.
- **Cross-portfolio health sweep:** aggregate holdings across portfolios — future spec.
- **Circuit Breaker integration:** CB Level column renders "—" in Phase 1. Full integration is a future spec.
- **Simulation / Projection deep redesign:** §5.5 and §5.6 cover design-system alignment only.
