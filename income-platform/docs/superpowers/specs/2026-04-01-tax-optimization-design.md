# Tax Optimization & NAA Yield — Design Spec

## Goal

Wire up the existing tax infrastructure to produce accurate **NAA Yield** (Net After-All Yield) per position and per portfolio, surface it in a new **Tax tab** on each portfolio, complete the existing portfolio-level NAA Yield metric, and add an aggregate NAA card to the dashboard.

## NAA Yield Formula

```
NAA Yield = (Annual Income − Tax Withheld − Expense Drag) / Current Market Value

Tax Withheld  = Annual Income × effective_rate(asset_type, federal + state + NIIT)
Expense Drag  = expense_ratio × Current Market Value   [funds only; 0 for stocks]
Current Market Value = current_price × shares
```

All NAA Yield values are stored and transmitted as **decimal fractions** (e.g. `0.071` = 7.1%). The existing `NAAYieldCalculator.compute()` returns `naa_yield_pct` as a **percentage** (e.g. `7.1`). Callers must divide by 100 before storing or transmitting: `nay = result.naa_yield_pct / 100`.

- Uses **current market value** (not cost basis) — NAA is a current yield metric
- `expense_ratio` applies to all funds: CEFs, ETFs, BDCs, REITs; zero for individual stocks
- Tax rates derived from user's stored tax profile (`annual_income`, `filing_status`, `state_code`)
- When tax profile is unavailable, `pre_tax_flag = True` and tax drag is treated as 0 (existing `NAAYieldCalculator` behaviour)

## Architecture

### Existing infrastructure (already built, needs wiring)

| Component | Location | Status |
|---|---|---|
| `NAAYieldCalculator` | `income-scoring-service/app/scoring/naa_yield.py` | Built — needs real inputs. Returns `naa_yield_pct` as %, divide by 100 for decimal. |
| `NAAYieldResult`, `TaxProfile` | same file | Built. `TaxProfile` requires income character fractions (roc_pct, qualified_pct, ordinary_pct) + bracket rates — not user preferences directly (see Section 3). |
| `portfolio_aggregator.py` | `broker-service/app/services/` | Uses gross-only shortcut with `naa_yield_pre_tax=True` |
| Tax service endpoints | `tax-optimization-service` port 8005 | Built — needs `/tax/placement` + richer optimize response |
| Portfolio header NAA Yield | `portfolio/[id]/page.tsx` | Rendered — currently pre-tax |
| Portfolio card NAA Yield | `portfolio-card.tsx` | Rendered — currently pre-tax |
| `user_preferences` table | `platform_shared` | Stores `filing_status`, `state_code`, `annual_income` |

### New pieces

| Component | What it does |
|---|---|
| `expense_ratio` column in `market_data_cache` | Stores FMP `expenseRatio` from existing profile fetch |
| `/tax/placement` endpoint | Single-ticker account recommendation for proposal service |
| Extended `/tax/optimize/portfolio` | Adds `holdings_analysis` array + `portfolio_nay` + `portfolio_gross_yield` |
| `GET /api/portfolios/[id]/tax` | Next.js route — powers the Tax tab |
| `GET /api/tax/summary` | Next.js route — powers dashboard aggregate NAA |
| `tax-tab.tsx` | New portfolio tab component |
| Dashboard NAA card | Aggregate NAA Yield across all portfolios |
| Portfolio detail pane additions | Cost Drag, Tax Drag, NAA Yield in position side panel |

---

## Section 1 — Market Data Cache: `expense_ratio`

### DB migration

```sql
ALTER TABLE platform_shared.market_data_cache
  ADD COLUMN expense_ratio FLOAT;
```

### `market_cache.py` — store on profile fetch

FMP `GET /profile/{ticker}` already returns `expenseRatio`. Store it during the existing `_fmp_profile` / `_fetch_all_profiles` flow:

```python
expense_ratio = profile_data.get("expenseRatio")  # float or None
```

Upsert alongside existing profile columns. Null for tickers with no expense ratio (individual stocks).

### Positions endpoint

`GET /api/portfolios/{id}/positions` (Next.js proxy → admin panel) already JOINs `market_data_cache`. Add `expense_ratio` to the SELECT and to the `Position` response shape. Note: `expense_ratio` may already exist on the `Position` type in `lib/types.ts` — verify before adding.

---

## Section 2 — Tax Service Changes

### 2a. New `/tax/placement` endpoint

Fixes the broken proposal integration (`data_fetcher.py` calls this endpoint but it doesn't exist).

```
POST /tax/placement
Authorization: Bearer <jwt>
Body: { "ticker": str, "portfolio_id": str | null }
→ { "recommended_account": "ROTH_IRA", "reason": str, "asset_class": str }
```

**Implementation — inline placement logic** (do not call a non-existent helper):

1. Look up `asset_type` from `platform_shared.securities` WHERE `symbol = ticker`; fall back to Agent 04 if not found
2. Map `asset_class` to `recommended_account` using the same rules already in `optimizer.py`:
   - `_NEVER_SHELTER` (MLP): always `TAXABLE`
   - `_SHELTER_HIGH_YIELD` (COVERED_CALL_ETF, BDC, CLOSED_END_FUND with yield > 8%): `ROTH_IRA`
   - `_SHELTER_PRIORITY` (BOND_ETF, REIT, ORDINARY_INCOME): `TRAD_IRA`
   - `_TAXABLE_FRIENDLY` (DIVIDEND_STOCK, PREFERRED_STOCK): `TAXABLE`
   - Default: `TAXABLE`
3. Return `recommended_account` + a short `reason` string based on the matched rule

### 2b. Extend `/tax/optimize/portfolio` response

**Step 1 — Update `OptimizationResponse` in `app/models.py`:**

Add these fields to the existing Pydantic model (Pydantic will strip unknown fields otherwise, causing silent data loss):

```python
holdings_analysis: list[HoldingAnalysis] = []
portfolio_gross_yield: Optional[float] = None
portfolio_nay: Optional[float] = None          # decimal fraction, e.g. 0.071
suboptimal_count: int = 0
```

Add a new `HoldingAnalysis` Pydantic model to `app/models.py`:

```python
class HoldingAnalysis(BaseModel):
    symbol: str
    asset_class: str
    current_account: str
    recommended_account: str
    placement_mismatch: bool
    treatment: str
    gross_yield: float           # decimal, e.g. 0.423
    effective_tax_rate: float    # decimal, e.g. 0.541
    after_tax_yield: float       # decimal, e.g. 0.194
    expense_ratio: Optional[float]
    expense_drag_pct: float      # decimal
    nay: float                   # decimal — NAAYieldCalculator.naa_yield_pct / 100
    annual_income: float
    tax_withheld: float
    expense_drag_amount: float
    net_annual_income: float
    estimated_annual_tax_savings: float
    reason: str
```

**Step 2 — Update `optimize_portfolio()` in `optimizer.py`:**

`holdings_analysis` must include **every active holding** (not just suboptimally placed ones — this differs from `placement_recommendations` which filters). For each holding:

1. Get tax profile from `calculator.get_effective_rate(asset_class, annual_income, filing_status, state_code)`
2. Compute `gross_yield = annual_income / current_value`
3. Compute `tax_withheld = annual_income × effective_tax_rate`
4. Compute `expense_drag_amount = (expense_ratio or 0) × current_value`
5. Call `NAAYieldCalculator().compute(annual_income, expense_drag_amount, tax_withheld, current_value)` → divide `naa_yield_pct` by 100 for `nay`
6. `placement_mismatch = recommended_account != current_account AND estimated_savings > 1.0`

`suboptimal_count = count(h for h in holdings_analysis if h.placement_mismatch)`.

`portfolio_nay = sum(h.net_annual_income for h in holdings_analysis) / total_portfolio_value`.

**Response JSON example** (all yield values as decimals):

```json
{
  "total_portfolio_value": 250000,
  "current_annual_tax_burden": 4218,
  "optimized_annual_tax_burden": 2378,
  "estimated_annual_savings": 1840,
  "portfolio_gross_yield": 0.124,
  "portfolio_nay": 0.071,
  "suboptimal_count": 5,
  "holdings_analysis": [
    {
      "symbol": "ECC",
      "asset_class": "CEF",
      "current_account": "TAXABLE",
      "recommended_account": "ROTH_IRA",
      "placement_mismatch": true,
      "treatment": "ORDINARY_INCOME",
      "gross_yield": 0.423,
      "effective_tax_rate": 0.541,
      "after_tax_yield": 0.194,
      "expense_ratio": 0.012,
      "expense_drag_pct": 0.012,
      "nay": 0.182,
      "annual_income": 1935.36,
      "tax_withheld": 1046.12,
      "expense_drag_amount": 23.22,
      "net_annual_income": 866.02,
      "estimated_annual_tax_savings": 1240.0,
      "reason": "CEF distributions are primarily ordinary income..."
    }
  ]
}
```

---

## Section 3 — Portfolio Aggregator: Wire Real Inputs

**File:** `broker-service/app/services/portfolio_aggregator.py`

Current shortcut:
```python
naa_yield = round(total_income / total_value, 4) if total_value > 0 else None
```

**Strategy A (preferred) — use extended tax service response:**

After `/tax/optimize/portfolio` is extended (Section 2b), the portfolio aggregator can call that endpoint and read `portfolio_nay` directly. This is the cleanest path — the tax service already does all the per-holding computation.

```python
# Call tax service with user's tax profile
tax_resp = await httpx_client.post(
    f"{settings.tax_service_url}/tax/optimize/portfolio",
    json={"portfolio_id": portfolio_id, "annual_income": annual_income,
          "filing_status": filing_status, "state_code": state_code}
)
naa_yield = tax_resp.json().get("portfolio_nay")   # already a decimal fraction
naa_yield_pre_tax = naa_yield is None
```

**Strategy B (fallback) — estimate without tax service:**

If user has no tax profile or tax service is unavailable, fall back to `NAAYieldCalculator.estimate_tax_drag`:

```python
# TaxProfile requires income character fractions + bracket rates.
# Get these from tax_service.profiler.get_profile(asset_class) which returns
# {primary_treatment, qualified_dividend_eligible, ...} — use that to set:
#   ordinary_pct = 1.0 if treatment == ORDINARY_INCOME else 0.0
#   qualified_pct = 1.0 if qualified_dividend_eligible else 0.0
#   roc_pct = 0.3 if treatment == REIT_DISTRIBUTION else 0.0
# Bracket rates come from user_preferences annual_income + filing_status
#   via calculator.get_bracket_rates(annual_income, filing_status, state_code)
profile = TaxProfile(roc_pct=..., qualified_pct=..., ordinary_pct=...,
                     qualified_rate=..., ordinary_rate=...)
tax_drag = NAAYieldCalculator.estimate_tax_drag(annual_income, profile)
result = NAAYieldCalculator().compute(
    gross_annual_dividends=annual_income,
    annual_fee_drag=expense_ratio * current_value if expense_ratio else 0.0,
    annual_tax_drag=tax_drag,
    total_invested=current_value,
)
naa_yield = result.naa_yield_pct / 100   # convert % → decimal fraction
```

**Strategy A is step 5 in implementation order; it depends on step 4 (extended optimize endpoint) being deployed first.**

Remove `naa_yield_pre_tax: True` flag once Strategy A is wired. Flag stays `True` only when user has no tax profile.

---

## Section 4 — Next.js API Routes

### `GET /api/portfolios/[id]/tax`

Powers the Tax tab. Called on tab mount.

Flow:
1. Read user tax profile from `user_preferences` via DB (or existing preferences endpoint)
2. `POST tax-service/tax/optimize/portfolio` with `{ portfolio_id, annual_income, filing_status, state_code }`
3. **Remap response for frontend:** the tax service returns `placement_recommendations`; the frontend expects `holdings`. The Next.js route merges data:
   - Build a map: `symbol → PlacementRecommendation` from `placement_recommendations`
   - Iterate `holdings_analysis` (which includes ALL holdings); attach `estimated_annual_tax_savings` and `reason` from the map where symbol matches
   - Return as `holdings: TaxHolding[]`
4. Attach `tax_profile` from step 1 to the response

Response shape used by Tax tab:
```typescript
interface PortfolioTaxAnalysis {
  portfolio_gross_yield: number;   // decimal
  portfolio_nay: number;           // decimal
  current_annual_tax_burden: number;
  estimated_annual_savings: number;
  suboptimal_count: number;
  holdings: TaxHolding[];
  tax_profile: { annual_income: number; filing_status: string; state_code: string; };
}
```

### `GET /api/tax/summary`

Powers dashboard aggregate NAA. Called once on dashboard mount.

Flow:
1. Fetch all active portfolios for the current user
2. For each portfolio, call `/tax/optimize/portfolio` (parallel, `Promise.all`)
3. Aggregate: `sum(net_annual_income across all holdings) / sum(current_value across all portfolios)`
4. Return: `{ aggregate_nay, aggregate_gross_yield, total_tax_drag, total_expense_drag, portfolio_count }`

### `PUT /api/user/preferences`

Ensure this endpoint persists `filing_status`, `state_code`, `annual_income` to `user_preferences`. Called when user edits tax profile in Tax tab settings. Verify the existing endpoint handles these fields before adding new code.

---

## Section 5 — Frontend Components

### 5a. `tax-tab.tsx` (new)

**Location:** `src/frontend/src/app/portfolios/[id]/tabs/tax-tab.tsx`

**Props:**
```typescript
interface TaxTabProps {
  portfolioId: string;
  refreshKey?: number;
  onTaxDataLoaded?: (data: PortfolioTaxAnalysis) => void;
}
```

**Layout (approved Option C):**

```
┌─────────────────────────────────────────────────────────────┐
│ BANNER: Tax Drag $X,XXX | Suboptimal Holdings N | Savings $X │
│         Tax Profile: $150k · Single · CA  [Edit ✎]  [ⓘ]    │
├──────────────────────────────────────────┬──────────────────┤
│ [Action bar — visible when rows selected]│                  │
│ ⚡ Generate Rebalance Proposal           │  DETAIL PANEL   │
├─────────┬────────┬────────┬──────────────┤  (when row       │
│ Ticker  │ Class  │Account │ Treatment... │   selected)      │
├─────────┼────────┼────────┼──────────────┤                  │
│ ECC     │ CEF    │TAXABLE │ Ordinary...  │  Tax waterfall:  │
│ JEPI    │ ETF    │TAXABLE │ Ordinary...  │  Gross → Fed →   │
│ O       │ REIT   │ROTH IRA│ REIT Dist.  │  State → NIIT →  │
└─────────┴────────┴────────┴──────────────┴──────────────────┘
```

**Table columns (visible by default):**
- Ticker (`TickerBadge`)
- Class (asset_type)
- Account (color-coded badge: red = TAXABLE for high-tax assets, green = sheltered)
- Treatment (ORDINARY_INCOME, QUALIFIED_DIVIDEND, REIT_DISTRIBUTION, etc.)
- Gross Yield
- Tax Rate (effective combined %)
- After-Tax Yield
- NAA Yield (**bold** — the headline number)
- Placement Rec. (→ ROTH IRA ⚠ / ✓ Optimal / ✓ Tax-Efficient)
- Est. Savings/yr

**Table columns (hidden by default):**
- Federal Rate
- State Rate
- NIIT applies (bool)
- Expense Ratio
- Expense Drag $

**Action bar:** appears when ≥1 row checked. "⚡ Generate Rebalance Proposal" → opens existing `ProposalModal` with `selectedTickers` pre-populated. `ProposalModal` already handles portfolio selection and proposal generation.

**Detail panel:** shown when row clicked (toggle same row to close).
- Tax waterfall: Gross Yield → − Federal Tax → − State Tax → − NIIT → After-Tax Yield → − Expense Drag → **NAA Yield**
- Placement recommendation box with rationale text
- "Est. annual savings if moved: $X,XXX"
- "⚡ Propose Account Transfer" button → same `ProposalModal`, single ticker

**Settings edit modal:** triggered by "Edit ✎" in banner.
- Fields: Annual Income (text input), Filing Status (select), State (select, all 50 states)
- Each field has `ⓘ` tooltip:
  - Annual Income: "Your total gross annual income. Used to determine your federal tax bracket and NIIT eligibility (applies above $200k single / $250k joint)."
  - Filing Status: "Your IRS filing status determines which tax brackets and standard deduction apply."
  - State: "Your state of residence for state income tax calculation. Nine states have no income tax."
- Save → `PUT /api/user/preferences` → refetch tax analysis

**Data loading:**
```typescript
useEffect(() => {
  fetch(`/api/portfolios/${portfolioId}/tax`)
    .then(res => res.json())
    .then(data => {
      setTaxData(data);
      onTaxDataLoaded?.(data);  // lifts to parent
    });
}, [portfolioId, refreshKey]);
```

### 5b. Portfolio `page.tsx` — Tax tab + shared state

Add Tax tab to the tab list:
```typescript
{ value: "tax", label: "Tax" }
```

Lift tax data:
```typescript
const [taxData, setTaxData] = useState<PortfolioTaxAnalysis | null>(null);
```

Pass to tabs:
```typescript
<TaxTab portfolioId={id} refreshKey={tabRefreshKey} onTaxDataLoaded={setTaxData} />
<PortfolioTab ... taxData={taxData} />
```

### 5c. Portfolio detail pane — cost drag + tax drag + NAA

**File:** `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx`

In the position detail side panel, add a new "True Yield" section after the income section. The `SectionTitle` and `DetailRow` components are confirmed to exist (pattern from `health-tab.tsx`).

```tsx
<SectionTitle label="True Yield" />

<DetailRow label="Gross Yield" value={`${(grossYield * 100).toFixed(2)}%`} />

{position.expense_ratio != null && (
  <DetailRow
    label="Cost Drag (Expense Ratio)"
    value={`−${(position.expense_ratio * 100).toFixed(2)}%`}
    className="text-amber-400"
  />
)}

{taxHolding ? (
  <>
    <DetailRow
      label="Tax Drag"
      value={`−${((taxHolding.gross_yield - taxHolding.after_tax_yield) * 100).toFixed(2)}%`}
      className="text-red-400"
    />
    <DetailRow
      label="NAA Yield"
      value={`${(taxHolding.nay * 100).toFixed(2)}%`}
      className="text-green-400 font-bold"
    />
  </>
) : (
  <div className="text-xs text-muted-foreground">
    Open Tax tab to see NAA Yield
  </div>
)}
```

Where `taxHolding = taxData?.holdings.find(h => h.symbol === selected.symbol)`.

### 5d. Dashboard — aggregate NAA card

**File:** existing dashboard page.

Add a new card alongside the existing income/yield cards:

```
┌─────────────────────────────┐
│  NAA Yield (all portfolios) │
│  7.1%  ────────  12.4% gross│
│  Tax + cost drag: −5.3%     │
└─────────────────────────────┘
```

Calls `GET /api/tax/summary` on mount. Shows `—` with a note "Set tax profile to see NAA" if user has no preferences stored.

---

## Section 6 — Types

**`lib/types.ts` additions:**

```typescript
// Verify expense_ratio is not already on Position before adding
expense_ratio?: number | null;

// New types
interface TaxHolding {
  symbol: string;
  asset_class: string;
  current_account: string;
  recommended_account: string;
  placement_mismatch: boolean;
  treatment: string;
  gross_yield: number;           // decimal fraction
  effective_tax_rate: number;    // decimal fraction
  after_tax_yield: number;       // decimal fraction
  expense_ratio: number | null;  // decimal fraction
  expense_drag_pct: number;      // decimal fraction
  nay: number;                   // decimal fraction (NAAYieldCalculator.naa_yield_pct / 100)
  annual_income: number;
  tax_withheld: number;
  expense_drag_amount: number;
  net_annual_income: number;
  estimated_annual_tax_savings: number;
  reason: string;
}

interface PortfolioTaxAnalysis {
  portfolio_gross_yield: number;  // decimal fraction
  portfolio_nay: number;          // decimal fraction
  current_annual_tax_burden: number;
  estimated_annual_savings: number;
  suboptimal_count: number;
  holdings: TaxHolding[];
  tax_profile: {
    annual_income: number;
    filing_status: string;
    state_code: string;
  };
}

interface TaxSummary {
  aggregate_nay: number;           // decimal fraction
  aggregate_gross_yield: number;   // decimal fraction
  total_tax_drag: number;
  total_expense_drag: number;
  portfolio_count: number;
}
```

---

## Implementation Order

1. **DB migration** — add `expense_ratio` to `market_data_cache`
2. **market_cache.py** — store `expense_ratio` from FMP profile fetch
3. **Tax service** — add `/tax/placement` endpoint (inline placement logic, no missing helpers)
4. **Tax service** — update `OptimizationResponse` + `HoldingAnalysis` in `models.py`; extend `optimize_portfolio()` to populate `holdings_analysis` for ALL holdings, `portfolio_nay`, `portfolio_gross_yield`, `suboptimal_count`
5. **Next.js routes** — `/api/portfolios/[id]/tax` (with placement_recommendations → holdings remapping) and `/api/tax/summary`
6. **portfolio_aggregator.py** — wire Strategy A: call extended `/tax/optimize/portfolio`, read `portfolio_nay` directly; Strategy B as fallback using `NAAYieldCalculator.estimate_tax_drag` with `TaxProfile` built from tax profiler + bracket rates (not raw user_preferences)
7. **`lib/types.ts`** — add new types
8. **`tax-tab.tsx`** — new component
9. **`portfolio/[id]/page.tsx`** — add Tax tab + lifted state
10. **`portfolio-tab.tsx`** — detail pane additions (cost drag, tax drag, NAA)
11. **Dashboard** — aggregate NAA card

## Out of Scope

- Tax-loss harvesting tab (existing `/tax` standalone page — not changed)
- Historical tax analytics (`tax_analytics` table — not populated here)
- K-1 generation or actual tax filing
- Cost basis tracking (positions use current market value, not purchase price)
