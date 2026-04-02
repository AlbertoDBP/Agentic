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

- Uses **current market value** (not cost basis) — NAA is a current yield metric
- `expense_ratio` applies to all funds: CEFs, ETFs, BDCs, REITs; zero for individual stocks
- Tax rates derived from user's stored tax profile (`annual_income`, `filing_status`, `state_code`)
- When tax profile is unavailable, `pre_tax_flag = True` and tax drag is treated as 0 (existing `NAAYieldCalculator` behaviour)

## Architecture

### Existing infrastructure (already built, needs wiring)

| Component | Location | Status |
|---|---|---|
| `NAAYieldCalculator` | `income-scoring-service/app/scoring/naa_yield.py` | Built — needs real inputs |
| `NAAYieldResult`, `TaxProfile` | same file | Built |
| `portfolio_aggregator.py` | `broker-service/app/services/` | Uses gross-only shortcut with `pre_tax_flag=True` |
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

`GET /api/portfolios/{id}/positions` (Next.js proxy → admin panel) already JOINs `market_data_cache`. Add `expense_ratio` to the SELECT and to the `Position` response shape.

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

Implementation:
1. Look up `asset_type` from `platform_shared.securities` WHERE `symbol = ticker`
2. Fall back to Agent 04 (asset classification) if not found
3. Run `optimizer.get_placement_recommendation(asset_class)`
4. Return `recommended_account` + `reason`

### 2b. Extend `/tax/optimize/portfolio` response

Add `holdings_analysis` array and portfolio-level NAA fields to the existing response.

**New fields in response:**

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

**`suboptimal_count`** = count of holdings where `placement_mismatch = true`.

---

## Section 3 — Portfolio Aggregator: Wire Real Inputs

**File:** `broker-service/app/services/portfolio_aggregator.py`

Current shortcut:
```python
naa_yield = round(total_income / total_value, 4) if total_value > 0 else None
```

Replace with a call to `NAAYieldCalculator` fed by:
- `gross_annual_dividends` = position `annual_income`
- `annual_fee_drag` = `expense_ratio × current_value` (from `market_data_cache`)
- `annual_tax_drag` = fetched from tax service per position (or estimated via `NAAYieldCalculator.estimate_tax_drag` using `TaxProfile` from `user_preferences`)
- `total_invested` = `current_price × shares`

Remove `naa_yield_pre_tax: True` flag once tax data is wired. Flag stays `True` only when user has no tax profile set.

---

## Section 4 — Next.js API Routes

### `GET /api/portfolios/[id]/tax`

Powers the Tax tab. Called on tab mount.

Flow:
1. Read user tax profile from `user_preferences` (via DB or existing preferences endpoint)
2. `POST tax-service/tax/optimize/portfolio` with `{ portfolio_id, annual_income, filing_status, state_code }`
3. Return the full response (banner metrics + `holdings_analysis`)

Response shape used by Tax tab:
```typescript
interface PortfolioTaxAnalysis {
  portfolio_gross_yield: number;
  portfolio_nay: number;
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
2. For each portfolio, call `tax/optimize/portfolio` (or read from recent cache if < 24h)
3. Aggregate: `sum(net_annual_income) / sum(current_value)` across all portfolios
4. Return: `{ aggregate_nay, aggregate_gross_yield, total_tax_drag, total_expense_drag, portfolio_count }`

### `PUT /api/user/preferences`

Ensure this endpoint persists `filing_status`, `state_code`, `annual_income` to `user_preferences`. Called when user edits tax profile in Tax tab settings. Existing endpoint — verify it handles these fields.

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

In the position detail side panel, add a new section after the income section:

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
// Add to Position
expense_ratio?: number | null;

// New types
interface TaxHolding {
  symbol: string;
  asset_class: string;
  current_account: string;
  recommended_account: string;
  placement_mismatch: boolean;
  treatment: string;
  gross_yield: number;
  effective_tax_rate: number;
  after_tax_yield: number;
  expense_ratio: number | null;
  expense_drag_pct: number;
  nay: number;
  annual_income: number;
  tax_withheld: number;
  expense_drag_amount: number;
  net_annual_income: number;
  estimated_annual_tax_savings: number;
  reason: string;
}

interface PortfolioTaxAnalysis {
  portfolio_gross_yield: number;
  portfolio_nay: number;
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
  aggregate_nay: number;
  aggregate_gross_yield: number;
  total_tax_drag: number;
  total_expense_drag: number;
  portfolio_count: number;
}
```

---

## Implementation Order

1. **DB migration** — add `expense_ratio` to `market_data_cache`
2. **market_cache.py** — store `expense_ratio` from FMP profile fetch
3. **Tax service** — add `/tax/placement` endpoint
4. **Tax service** — extend `/tax/optimize/portfolio` with `holdings_analysis`
5. **portfolio_aggregator.py** — wire `NAAYieldCalculator` with real fee + tax inputs
6. **Next.js routes** — `/api/portfolios/[id]/tax` and `/api/tax/summary`
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
