# Tax Optimization & NAA Yield Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up existing tax infrastructure to produce accurate NAA Yield per position, add a Tax tab to portfolio pages, complete the portfolio-level NAA Yield metric, and add an aggregate NAA card to the dashboard.

**Architecture:** The `NAAYieldCalculator` and tax optimizer already exist; this plan connects them to real data (expense ratios from FMP, tax profiles from user_preferences). A new Tax tab calls a new Next.js `/api/portfolios/[id]/tax` route which calls the extended tax service. The portfolio aggregator switches from a gross-yield shortcut to reading `portfolio_nay` from the tax service response.

**Tech Stack:** Python/FastAPI (tax-optimization-service, opportunity-scanner-service, broker-service), Next.js 14 App Router (TypeScript), PostgreSQL (platform_shared schema), SQLAlchemy async, pytest/pytest-asyncio.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/opportunity-scanner-service/app/scanner/market_cache.py` | Modify | Store `expense_ratio` from FMP profile |
| `src/tax-optimization-service/app/models.py` | Modify | Add `HoldingAnalysis`, update `OptimizationResponse`, add `expense_ratio` to `HoldingInput` |
| `src/tax-optimization-service/app/database.py` | Modify | JOIN `market_data_cache` in `get_portfolio_holdings()` |
| `src/tax-optimization-service/app/tax/optimizer.py` | Modify | Compute per-holding NAA, populate `holdings_analysis` |
| `src/tax-optimization-service/app/api/routes.py` | Modify | Add `/tax/placement` endpoint |
| `src/broker-service/app/services/portfolio_aggregator.py` | Modify | Call tax service for `portfolio_nay` (Strategy A) |
| `src/frontend/src/app/api/portfolios/[id]/tax/route.ts` | Create | Aggregate tax analysis for a portfolio |
| `src/frontend/src/app/api/tax/summary/route.ts` | Create | Aggregate NAA across all portfolios |
| `src/frontend/src/lib/types.ts` | Modify | Add `TaxHolding`, `PortfolioTaxAnalysis`, `TaxSummary` |
| `src/frontend/src/app/portfolios/[id]/tabs/tax-tab.tsx` | Create | New Tax tab component |
| `src/frontend/src/app/portfolios/[id]/page.tsx` | Modify | Add Tax tab, lift `taxData` state |
| `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx` | Modify | Add True Yield section to detail panel |
| `src/frontend/src/app/dashboard/page.tsx` | Modify | Add aggregate NAA Yield card |

---

## Task 1: DB Migration — Add `expense_ratio` to `market_data_cache`

**Files:**
- Create: `src/shared/migrations/add_expense_ratio_to_market_data_cache.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- src/shared/migrations/add_expense_ratio_to_market_data_cache.sql
ALTER TABLE platform_shared.market_data_cache
  ADD COLUMN IF NOT EXISTS expense_ratio FLOAT;

COMMENT ON COLUMN platform_shared.market_data_cache.expense_ratio
  IS 'Annual expense ratio as decimal fraction (e.g. 0.0035 for 0.35%). NULL for stocks/ETFs with no reported ratio.';
```

- [ ] **Step 2: Run the migration on the server**

```bash
ssh root@138.197.78.238 "psql \$DATABASE_URL -f /opt/Agentic/income-platform/src/shared/migrations/add_expense_ratio_to_market_data_cache.sql"
```

Expected output: `ALTER TABLE`

- [ ] **Step 3: Verify the column exists**

```bash
ssh root@138.197.78.238 "psql \$DATABASE_URL -c \"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='platform_shared' AND table_name='market_data_cache' AND column_name='expense_ratio';\""
```

Expected: one row showing `expense_ratio | double precision`

- [ ] **Step 4: Commit**

```bash
git add src/shared/migrations/add_expense_ratio_to_market_data_cache.sql
git commit -m "feat(db): add expense_ratio column to platform_shared.market_data_cache"
```

---

## Task 2: Store `expense_ratio` from FMP Profile Fetch

**Files:**
- Modify: `src/opportunity-scanner-service/app/scanner/market_cache.py`

**Context:** FMP `/stable/profile?symbol=X` returns `expenseRatio` (a float or null). The upsert is a large `INSERT...ON CONFLICT` block. We need to add `expense_ratio` to both the INSERT column list and the DO UPDATE SET clause.

- [ ] **Step 1: Write a failing test**

Add to `src/opportunity-scanner-service/tests/test_market_cache.py` (create if it doesn't exist):

```python
# src/opportunity-scanner-service/tests/test_market_cache.py
import os
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("INCOME_SCORING_URL", "http://localhost:8003")
os.environ.setdefault("FMP_API_KEY", "test")

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.scanner.market_cache import _fmp_profile


@pytest.mark.anyio
async def test_fmp_profile_returns_expense_ratio():
    """_fmp_profile must pass expenseRatio through in its result dict."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{
        "symbol": "JEPI",
        "price": 55.0,
        "beta": 0.35,
        "volAvg": 3_000_000,
        "mktCap": 35_000_000_000,
        "lastDiv": 0.48,
        "changes": 0.12,
        "companyName": "JPMorgan Equity Premium Income ETF",
        "exchange": "NYSE",
        "industry": "Asset Management",
        "sector": "Financial Services",
        "range": "50.0-57.0",
        "expenseRatio": 0.0035,
    }]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    result = await _fmp_profile("JEPI", mock_client)

    assert result.get("expense_ratio") == 0.0035


@pytest.mark.anyio
async def test_fmp_profile_expense_ratio_none_when_missing():
    """_fmp_profile must return expense_ratio=None when FMP doesn't report it."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{
        "symbol": "O",
        "price": 58.0,
        "beta": 0.6,
        "volAvg": 5_000_000,
        "mktCap": 40_000_000_000,
        "lastDiv": 0.26,
        "changes": -0.05,
        "companyName": "Realty Income",
        "exchange": "NYSE",
        "industry": "REIT",
        "sector": "Real Estate",
        "range": "50.0-65.0",
        # no expenseRatio key
    }]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    result = await _fmp_profile("O", mock_client)

    assert result.get("expense_ratio") is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd src/opportunity-scanner-service
pip install pytest pytest-asyncio anyio -q
pytest tests/test_market_cache.py -v 2>&1 | head -30
```

Expected: FAILED — `KeyError` or `AssertionError` because `_fmp_profile` doesn't return `expense_ratio` yet.

- [ ] **Step 3: Update `_fmp_profile` to extract `expenseRatio`**

In `src/opportunity-scanner-service/app/scanner/market_cache.py`, find the `_fmp_profile` function (around line 170). It builds a return dict from the FMP profile response. Add `expense_ratio`:

```python
# Inside _fmp_profile, in the return dict, add:
"expense_ratio": data.get("expenseRatio"),   # float or None
```

The exact location is in the `return { ... }` block of `_fmp_profile`. Add after the last existing key.

- [ ] **Step 4: Add `expense_ratio` to the upsert SQL**

Find the large `INSERT INTO platform_shared.market_data_cache (...)` block (around line 773). Add `expense_ratio` in two places:

**In the INSERT column list** — add after `debt_to_equity,`:
```sql
expense_ratio,
```

**In the VALUES list** — add the corresponding parameter after `:debt_to_equity,`:
```sql
:expense_ratio,
```

**In the ON CONFLICT DO UPDATE SET clause** — add after `debt_to_equity = COALESCE(...)`:
```sql
expense_ratio = COALESCE(EXCLUDED.expense_ratio, platform_shared.market_data_cache.expense_ratio),
```

**In the params dict** where profile data is mapped to SQL parameters — add:
```python
"expense_ratio": profile.get("expense_ratio"),
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd src/opportunity-scanner-service
pytest tests/test_market_cache.py -v
```

Expected: PASSED (both tests)

- [ ] **Step 6: Commit**

```bash
git add src/opportunity-scanner-service/app/scanner/market_cache.py \
        src/opportunity-scanner-service/tests/test_market_cache.py
git commit -m "feat(scanner): store expense_ratio from FMP profile in market_data_cache"
```

---

## Task 3: Tax Service — Add `/tax/placement` Endpoint

**Files:**
- Modify: `src/tax-optimization-service/app/api/routes.py`

**Context:** The proposal service (`src/proposal-service/app/proposal_engine/data_fetcher.py`) calls `POST /tax/placement` but the endpoint doesn't exist. This causes `fetch_agent05_tax_placement` to always return `None`, leaving `recommended_account` blank on all proposals.

- [ ] **Step 1: Write the failing test**

Add to `src/tax-optimization-service/tests/test_tax_optimization.py`:

```python
class TestTaxPlacement:
    @pytest.mark.asyncio
    async def test_placement_covered_call_etf_recommends_roth(self, client):
        """COVERED_CALL_ETF with high income should recommend ROTH_IRA."""
        resp = await client.post("/tax/placement", json={
            "ticker": "JEPI",
            "asset_class": "COVERED_CALL_ETF",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommended_account"] in ("ROTH_IRA", "TRAD_IRA")
        assert "reason" in data
        assert "asset_class" in data

    @pytest.mark.asyncio
    async def test_placement_mlp_always_taxable(self, client):
        """MLP must never be sheltered (UBTI issue in IRAs)."""
        resp = await client.post("/tax/placement", json={
            "ticker": "EPD",
            "asset_class": "MLP",
        })
        assert resp.status_code == 200
        assert resp.json()["recommended_account"] == "TAXABLE"

    @pytest.mark.asyncio
    async def test_placement_dividend_stock_taxable_friendly(self, client):
        """DIVIDEND_STOCK with qualified dividends is fine in TAXABLE."""
        resp = await client.post("/tax/placement", json={
            "ticker": "JNJ",
            "asset_class": "DIVIDEND_STOCK",
        })
        assert resp.status_code == 200
        assert resp.json()["recommended_account"] == "TAXABLE"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd src/tax-optimization-service
pytest tests/test_tax_optimization.py::TestTaxPlacement -v
```

Expected: FAILED — 404 Not Found (endpoint doesn't exist)

- [ ] **Step 3: Add the `PlacementRequest` model to `models.py`**

In `src/tax-optimization-service/app/models.py`, add before `OptimizationRequest`:

```python
class PlacementRequest(BaseModel):
    ticker: str
    asset_class: Optional[AssetClass] = None
    portfolio_id: Optional[str] = None


class PlacementResponse(BaseModel):
    recommended_account: str
    reason: str
    asset_class: str
```

- [ ] **Step 4: Add the `/tax/placement` endpoint to `routes.py`**

In `src/tax-optimization-service/app/api/routes.py`, add the import and endpoint. Add `PlacementRequest, PlacementResponse` to the models import line. Then add the endpoint after the existing endpoints:

```python
@router.post("/tax/placement", response_model=PlacementResponse)
async def get_tax_placement(request: PlacementRequest):
    """
    Return the recommended account type for a single ticker.
    Called by the proposal service (Agent 12) when generating proposals.
    Falls back to TAXABLE if asset_class is unknown.
    """
    from app.tax.optimizer import (
        _NEVER_SHELTER, _SHELTER_PRIORITY, _TAXABLE_FRIENDLY, _best_shelter_account,
        AssetClass,
    )

    asset_class_str = request.asset_class.value if request.asset_class else "UNKNOWN"
    try:
        ac = AssetClass(asset_class_str)
    except ValueError:
        ac = AssetClass.UNKNOWN

    if ac in _NEVER_SHELTER:
        recommended = "TAXABLE"
        reason = (
            f"{asset_class_str} investments generate Unrelated Business Taxable Income "
            "(UBTI) inside an IRA, which can trigger unexpected taxes. Keep in taxable account."
        )
    elif ac in _SHELTER_PRIORITY:
        # High-income assets → Roth for permanent shelter; others → Trad IRA
        recommended = _best_shelter_account(1.0, 0.10).value  # use default heuristic
        reason = (
            f"{asset_class_str} distributions are primarily ordinary income, fully taxed "
            "at your marginal rate in taxable accounts. Sheltering in a tax-advantaged "
            "account eliminates this drag."
        )
        # Roth preferred for highest-tax treatments
        if ac in {AssetClass.COVERED_CALL_ETF, AssetClass.BDC, AssetClass.CLOSED_END_FUND}:
            recommended = "ROTH_IRA"
        else:
            recommended = "TRAD_IRA"
    elif ac in _TAXABLE_FRIENDLY:
        recommended = "TAXABLE"
        reason = (
            f"{asset_class_str} typically pays qualified dividends taxed at preferential "
            "capital gains rates (0–20%). No benefit to sheltering; keep in taxable account."
        )
    else:
        recommended = "TAXABLE"
        reason = "No specific tax optimization rule for this asset class. Default: taxable account."

    return PlacementResponse(
        recommended_account=recommended,
        reason=reason,
        asset_class=asset_class_str,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd src/tax-optimization-service
pytest tests/test_tax_optimization.py::TestTaxPlacement -v
```

Expected: PASSED (all 3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/tax-optimization-service/app/api/routes.py \
        src/tax-optimization-service/app/models.py \
        src/tax-optimization-service/tests/test_tax_optimization.py
git commit -m "feat(tax): add /tax/placement endpoint for proposal service integration"
```

---

## Task 4: Tax Service — Extend `optimize_portfolio` with `holdings_analysis`

**Files:**
- Modify: `src/tax-optimization-service/app/models.py`
- Modify: `src/tax-optimization-service/app/database.py`
- Modify: `src/tax-optimization-service/app/tax/optimizer.py`
- Modify: `src/tax-optimization-service/app/api/routes.py`

**Context:** Currently `optimize_portfolio()` returns only totals and `placement_recommendations` (only suboptimal holdings). We need to add `holdings_analysis` covering ALL holdings with full tax math and NAA per holding. The `expense_ratio` needs to flow from `market_data_cache` through `HoldingInput` to the optimizer.

- [ ] **Step 1: Write the failing test**

Add to `src/tax-optimization-service/tests/test_tax_optimization.py`:

```python
class TestHoldingsAnalysis:
    @pytest.mark.asyncio
    async def test_portfolio_optimize_returns_holdings_analysis(self, client):
        """POST /tax/optimize must return holdings_analysis for ALL holdings."""
        resp = await client.post("/tax/optimize", json={
            "holdings": [
                {
                    "symbol": "ECC",
                    "asset_class": "CLOSED_END_FUND",
                    "account_type": "TAXABLE",
                    "current_value": 10000.0,
                    "annual_yield": 0.42,
                    "expense_ratio": 0.012,
                },
                {
                    "symbol": "O",
                    "asset_class": "REIT",
                    "account_type": "ROTH_IRA",
                    "current_value": 5000.0,
                    "annual_yield": 0.054,
                    "expense_ratio": None,
                },
            ],
            "annual_income": 150000.0,
            "filing_status": "SINGLE",
            "state_code": "CA",
        })
        assert resp.status_code == 200
        data = resp.json()

        # Both holdings must appear (not just suboptimal ones)
        assert "holdings_analysis" in data
        assert len(data["holdings_analysis"]) == 2

        # portfolio-level NAA fields
        assert "portfolio_nay" in data
        assert "portfolio_gross_yield" in data
        assert "suboptimal_count" in data
        assert isinstance(data["portfolio_nay"], float)

        # Per-holding fields
        ecc = next(h for h in data["holdings_analysis"] if h["symbol"] == "ECC")
        assert ecc["treatment"] is not None
        assert ecc["effective_tax_rate"] > 0
        assert ecc["after_tax_yield"] < ecc["gross_yield"]
        assert ecc["nay"] <= ecc["after_tax_yield"]  # expense drag reduces further
        assert ecc["placement_mismatch"] is True   # CLOSED_END_FUND in TAXABLE

        # Optimally placed holding
        o_holding = next(h for h in data["holdings_analysis"] if h["symbol"] == "O")
        assert o_holding["placement_mismatch"] is False  # REIT in ROTH_IRA is fine
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd src/tax-optimization-service
pytest tests/test_tax_optimization.py::TestHoldingsAnalysis -v
```

Expected: FAILED — `holdings_analysis` key not in response.

- [ ] **Step 3: Add `HoldingAnalysis` model and update `HoldingInput` and `OptimizationResponse` in `models.py`**

In `src/tax-optimization-service/app/models.py`:

**Add `expense_ratio` to `HoldingInput`:**

```python
class HoldingInput(BaseModel):
    symbol: str
    asset_class: AssetClass
    account_type: AccountType
    current_value: float
    annual_yield: float
    expense_ratio: Optional[float] = None   # ADD THIS FIELD
```

**Add `HoldingAnalysis` model** (add before `OptimizationResponse`):

```python
class HoldingAnalysis(BaseModel):
    symbol: str
    asset_class: str
    current_account: str
    recommended_account: str
    placement_mismatch: bool
    treatment: str
    gross_yield: float           # decimal fraction, e.g. 0.423
    effective_tax_rate: float    # decimal fraction, combined fed+state+NIIT
    after_tax_yield: float       # decimal fraction
    expense_ratio: Optional[float] = None
    expense_drag_pct: float      # decimal fraction
    nay: float                   # decimal fraction = naa_yield_pct / 100
    annual_income: float
    tax_withheld: float
    expense_drag_amount: float
    net_annual_income: float
    estimated_annual_tax_savings: float
    reason: str
```

**Update `OptimizationResponse`** to add new fields:

```python
class OptimizationResponse(BaseModel):
    total_portfolio_value: float
    current_annual_tax_burden: float
    optimized_annual_tax_burden: float
    estimated_annual_savings: float
    placement_recommendations: List[PlacementRecommendation]
    summary: str
    notes: List[str] = []
    # NEW FIELDS:
    holdings_analysis: List[HoldingAnalysis] = []
    portfolio_gross_yield: Optional[float] = None
    portfolio_nay: Optional[float] = None
    suboptimal_count: int = 0
```

- [ ] **Step 4: Update `get_portfolio_holdings()` in `database.py` to include `expense_ratio`**

In `src/tax-optimization-service/app/database.py`, find the `get_portfolio_holdings()` function. It queries positions and returns `HoldingInput` objects. Update the SELECT to JOIN `market_data_cache`:

```python
async def get_portfolio_holdings(
    portfolio_id: str, db: AsyncSession
) -> list:
    """Fetch active positions for a portfolio as HoldingInput objects."""
    from app.models import AccountType, AssetClass, HoldingInput

    result = await db.execute(text("""
        SELECT
            pos.symbol,
            COALESCE(sec.asset_type, 'UNKNOWN')         AS asset_class,
            COALESCE(pf.portfolio_type, 'taxable')      AS account_type,
            pos.current_value,
            CASE WHEN pos.current_value > 0
                 THEN pos.annual_income / pos.current_value
                 ELSE 0 END                              AS annual_yield,
            mdc.expense_ratio
        FROM platform_shared.positions pos
        JOIN platform_shared.portfolios pf ON pf.id = pos.portfolio_id
        LEFT JOIN platform_shared.securities sec ON sec.symbol = pos.symbol
        LEFT JOIN platform_shared.market_data_cache mdc ON mdc.symbol = pos.symbol
        WHERE pos.portfolio_id = :portfolio_id
          AND pos.status = 'ACTIVE'
    """), {"portfolio_id": portfolio_id})

    rows = result.fetchall()
    holdings = []
    for row in rows:
        try:
            ac = AssetClass(row.asset_class.upper())
        except ValueError:
            ac = AssetClass.UNKNOWN
        try:
            at = AccountType(row.account_type.upper())
        except ValueError:
            at = AccountType.TAXABLE

        holdings.append(HoldingInput(
            symbol=row.symbol,
            asset_class=ac,
            account_type=at,
            current_value=float(row.current_value or 0),
            annual_yield=float(row.annual_yield or 0),
            expense_ratio=float(row.expense_ratio) if row.expense_ratio is not None else None,
        ))
    return holdings
```

- [ ] **Step 5: Extend `optimize_portfolio()` in `optimizer.py` to compute `holdings_analysis`**

In `src/tax-optimization-service/app/tax/optimizer.py`, add imports at the top:

```python
from app.tax.calculator import (
    _ordinary_rate, _qualified_rate, _niit_applicable, _state_rate
)
from app.models import HoldingAnalysis
```

Then inside `optimize_portfolio()`, after the existing `recommendations` list is built, add the holdings analysis computation. Add this block before `return OptimizationResponse(...)`:

```python
    # ── Holdings analysis (ALL holdings, not just suboptimal) ─────────────────
    holdings_analysis: list[HoldingAnalysis] = []
    total_net_income = 0.0

    for holding in request.holdings:
        annual_income = holding.current_value * holding.annual_yield
        gross_yield = holding.annual_yield  # already a fraction

        # Determine tax treatment from asset class
        ac = holding.asset_class
        from app.tax.profiler import _PROFILE_MAP
        profile_entry = _PROFILE_MAP.get(ac)
        treatment = profile_entry.primary_treatment.value if profile_entry else "ORDINARY_INCOME"
        qualified_eligible = profile_entry.qualified_dividend_eligible if profile_entry else False

        # Compute effective tax rate
        fed_rate = (
            _qualified_rate(request.annual_income, request.filing_status)
            if qualified_eligible
            else _ordinary_rate(request.annual_income, request.filing_status)
        )
        state = _state_rate(request.state_code)
        niit = 0.038 if _niit_applicable(request.annual_income, request.filing_status) else 0.0
        effective_tax_rate = round(fed_rate + state + niit, 4)

        # In sheltered accounts tax rate is 0 (no current tax)
        if holding.account_type in (AccountType.ROTH_IRA, AccountType.TRAD_IRA,
                                     AccountType.HSA, AccountType.K401):
            effective_tax_rate = 0.0

        tax_withheld = round(annual_income * effective_tax_rate, 2)
        after_tax_income = annual_income - tax_withheld
        after_tax_yield = after_tax_income / holding.current_value if holding.current_value else 0.0

        # Expense drag
        expense_ratio = holding.expense_ratio or 0.0
        expense_drag_amount = round(expense_ratio * holding.current_value, 2)
        expense_drag_pct = expense_ratio

        # NAA
        net_annual_income = round(after_tax_income - expense_drag_amount, 2)
        nay = net_annual_income / holding.current_value if holding.current_value else 0.0

        total_net_income += net_annual_income

        # Placement recommendation for this holding
        rec_entry = next(
            (r for r in recommendations if r.symbol == holding.symbol), None
        )
        recommended_account = (
            rec_entry.recommended_account.value if rec_entry
            else holding.account_type.value
        )
        reason = rec_entry.reason if rec_entry else "Currently in optimal account."
        est_savings = rec_entry.estimated_annual_tax_savings if rec_entry else 0.0
        placement_mismatch = rec_entry is not None

        holdings_analysis.append(HoldingAnalysis(
            symbol=holding.symbol,
            asset_class=holding.asset_class.value,
            current_account=holding.account_type.value,
            recommended_account=recommended_account,
            placement_mismatch=placement_mismatch,
            treatment=treatment,
            gross_yield=round(gross_yield, 4),
            effective_tax_rate=round(effective_tax_rate, 4),
            after_tax_yield=round(after_tax_yield, 4),
            expense_ratio=holding.expense_ratio,
            expense_drag_pct=round(expense_drag_pct, 4),
            nay=round(nay, 4),
            annual_income=round(annual_income, 2),
            tax_withheld=round(tax_withheld, 2),
            expense_drag_amount=expense_drag_amount,
            net_annual_income=net_annual_income,
            estimated_annual_tax_savings=round(est_savings, 2),
            reason=reason,
        ))

    total_value = sum(h.current_value for h in request.holdings)
    portfolio_gross_yield = round(
        sum(h.current_value * h.annual_yield for h in request.holdings) / total_value, 4
    ) if total_value else 0.0
    portfolio_nay = round(total_net_income / total_value, 4) if total_value else 0.0
    suboptimal_count = sum(1 for h in holdings_analysis if h.placement_mismatch)
```

Then update the `return OptimizationResponse(...)` call to include the new fields:

```python
    return OptimizationResponse(
        total_portfolio_value=...,          # existing
        current_annual_tax_burden=...,      # existing
        optimized_annual_tax_burden=...,    # existing
        estimated_annual_savings=...,       # existing
        placement_recommendations=recommendations,
        summary=...,                        # existing
        notes=...,                          # existing
        # NEW:
        holdings_analysis=holdings_analysis,
        portfolio_gross_yield=portfolio_gross_yield,
        portfolio_nay=portfolio_nay,
        suboptimal_count=suboptimal_count,
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd src/tax-optimization-service
pytest tests/test_tax_optimization.py::TestHoldingsAnalysis -v
pytest tests/test_tax_optimization.py -v  # run full suite to check no regressions
```

Expected: PASSED (new tests + all existing tests still pass)

- [ ] **Step 7: Commit**

```bash
git add src/tax-optimization-service/app/models.py \
        src/tax-optimization-service/app/database.py \
        src/tax-optimization-service/app/tax/optimizer.py \
        src/tax-optimization-service/app/api/routes.py \
        src/tax-optimization-service/tests/test_tax_optimization.py
git commit -m "feat(tax): extend optimize_portfolio with holdings_analysis and portfolio NAA yield"
```

---

## Task 5: Next.js API Routes — `/api/portfolios/[id]/tax` and `/api/tax/summary`

**Files:**
- Create: `src/frontend/src/app/api/portfolios/[id]/tax/route.ts`
- Create: `src/frontend/src/app/api/tax/summary/route.ts`

**Context:** These routes aggregate data from the tax service. They forward the user's Bearer token from the incoming request. The tax service URL is `http://tax-optimization-service:8005` (server-side only). The user_preferences table is accessed via the admin panel.

- [ ] **Step 1: Verify TypeScript strict mode will catch type errors (TDD substitute for Next.js routes)**

```bash
cd src/frontend
# Confirm noEmit + strict are set in tsconfig
grep -E '"strict"|"noEmit"' tsconfig.json
```

Expected: both flags present. TypeScript compilation (`npx tsc --noEmit`) serves as the test gate for these routes — confirm at Step 4 that zero errors are reported before considering the task complete.

- [ ] **Step 2: Create `/api/portfolios/[id]/tax/route.ts`**

```typescript
// src/frontend/src/app/api/portfolios/[id]/tax/route.ts
/**
 * GET /api/portfolios/[id]/tax
 * Fetches user_preferences, calls tax service /tax/optimize/portfolio,
 * remaps holdings_analysis → holdings for the frontend.
 */
import { NextRequest, NextResponse } from "next/server";

const TAX_SERVICE = process.env.TAX_SERVICE_URL ?? "http://tax-optimization-service:8005";
const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const portfolioId = params.id;
  const authHeader = req.headers.get("authorization") ?? "";

  try {
    // 1. Fetch user tax preferences
    const prefResp = await fetch(`${ADMIN_PANEL}/api/user/preferences`, {
      headers: { authorization: authHeader },
      signal: AbortSignal.timeout(5_000),
    });
    const prefs = prefResp.ok ? await prefResp.json() : {};

    // 2. Call tax service optimize/portfolio
    const taxResp = await fetch(`${TAX_SERVICE}/tax/optimize/portfolio`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        authorization: authHeader,
      },
      body: JSON.stringify({
        portfolio_id: portfolioId,
        annual_income: prefs.annual_income ?? 100000,
        filing_status: prefs.filing_status ?? "SINGLE",
        state_code: prefs.state_code ?? null,
      }),
      signal: AbortSignal.timeout(30_000),
    });

    if (!taxResp.ok) {
      const err = await taxResp.json().catch(() => ({}));
      return NextResponse.json(
        { detail: err.detail ?? "Tax service error" },
        { status: taxResp.status }
      );
    }

    const taxData = await taxResp.json();

    // 3. Remap: holdings_analysis → holdings
    // holdings_analysis already contains estimated_annual_tax_savings and reason.
    // placement_recommendations fills these for suboptimal holdings; holdings_analysis
    // already has them populated. We just rename the key for the frontend.
    const response = {
      portfolio_gross_yield: taxData.portfolio_gross_yield ?? 0,
      portfolio_nay: taxData.portfolio_nay ?? 0,
      current_annual_tax_burden: taxData.current_annual_tax_burden ?? 0,
      estimated_annual_savings: taxData.estimated_annual_savings ?? 0,
      suboptimal_count: taxData.suboptimal_count ?? 0,
      holdings: taxData.holdings_analysis ?? [],
      tax_profile: {
        annual_income: prefs.annual_income ?? 100000,
        filing_status: prefs.filing_status ?? "SINGLE",
        state_code: prefs.state_code ?? "",
      },
    };

    return NextResponse.json(response);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
```

- [ ] **Step 3: Create `/api/tax/summary/route.ts`**

```typescript
// src/frontend/src/app/api/tax/summary/route.ts
/**
 * GET /api/tax/summary
 * Aggregates NAA Yield across all active portfolios for the dashboard.
 */
import { NextRequest, NextResponse } from "next/server";

const TAX_SERVICE = process.env.TAX_SERVICE_URL ?? "http://tax-optimization-service:8005";
const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get("authorization") ?? "";

  try {
    // 1. Fetch user preferences and all portfolios in parallel
    const [prefResp, portfoliosResp] = await Promise.all([
      fetch(`${ADMIN_PANEL}/api/user/preferences`, {
        headers: { authorization: authHeader },
        signal: AbortSignal.timeout(5_000),
      }),
      fetch(`${ADMIN_PANEL}/api/portfolios`, {
        headers: { authorization: authHeader },
        signal: AbortSignal.timeout(10_000),
      }),
    ]);

    const prefs = prefResp.ok ? await prefResp.json() : {};
    const portfolios: { id: string }[] = portfoliosResp.ok
      ? await portfoliosResp.json()
      : [];

    if (!portfolios.length) {
      return NextResponse.json({
        aggregate_nay: null,
        aggregate_gross_yield: null,
        total_tax_drag: 0,
        total_expense_drag: 0,
        portfolio_count: 0,
      });
    }

    // 2. Call tax service for each portfolio in parallel
    const results = await Promise.allSettled(
      portfolios.map((p) =>
        fetch(`${TAX_SERVICE}/tax/optimize/portfolio`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            authorization: authHeader,
          },
          body: JSON.stringify({
            portfolio_id: p.id,
            annual_income: prefs.annual_income ?? 100000,
            filing_status: prefs.filing_status ?? "SINGLE",
            state_code: prefs.state_code ?? null,
          }),
          signal: AbortSignal.timeout(30_000),
        }).then((r) => (r.ok ? r.json() : null))
      )
    );

    // 3. Aggregate across portfolios
    let totalNetIncome = 0;
    let totalGrossIncome = 0;
    let totalValue = 0;
    let totalTaxDrag = 0;
    let totalExpenseDrag = 0;
    let portfolioCount = 0;

    for (const result of results) {
      if (result.status !== "fulfilled" || !result.value) continue;
      const data = result.value;
      const holdings: any[] = data.holdings_analysis ?? [];
      for (const h of holdings) {
        totalNetIncome += h.net_annual_income ?? 0;
        totalGrossIncome += h.annual_income ?? 0;
        totalValue += h.current_value ?? 0;   // NOTE: HoldingAnalysis doesn't expose current_value directly
        totalTaxDrag += h.tax_withheld ?? 0;
        totalExpenseDrag += h.expense_drag_amount ?? 0;
      }
      if (data.total_portfolio_value) totalValue += data.total_portfolio_value;
      portfolioCount++;
    }

    // Recompute: use total_portfolio_value summed, not individual holdings
    // (avoid double-counting if current_value not in HoldingAnalysis)
    // Reset and use portfolio-level values instead:
    let sumValue = 0;
    let sumNay = 0;
    let sumGross = 0;
    let count = 0;
    totalTaxDrag = 0;
    totalExpenseDrag = 0;
    portfolioCount = 0;

    for (const result of results) {
      if (result.status !== "fulfilled" || !result.value) continue;
      const data = result.value;
      const v = data.total_portfolio_value ?? 0;
      if (v <= 0) continue;
      sumValue += v;
      sumNay += (data.portfolio_nay ?? 0) * v;
      sumGross += (data.portfolio_gross_yield ?? 0) * v;
      totalTaxDrag += data.current_annual_tax_burden ?? 0;
      totalExpenseDrag += (data.holdings_analysis ?? []).reduce(
        (acc: number, h: any) => acc + (h.expense_drag_amount ?? 0), 0
      );
      portfolioCount++;
    }

    return NextResponse.json({
      aggregate_nay: sumValue > 0 ? sumNay / sumValue : null,
      aggregate_gross_yield: sumValue > 0 ? sumGross / sumValue : null,
      total_tax_drag: Math.round(totalTaxDrag * 100) / 100,
      total_expense_drag: Math.round(totalExpenseDrag * 100) / 100,
      portfolio_count: portfolioCount,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
```

- [ ] **Step 4: Add `TAX_SERVICE_URL` to the frontend environment**

In `src/frontend/.env.local` (or `.env`) and in `docker-compose.yml` under the `frontend` service, ensure:

```
TAX_SERVICE_URL=http://tax-optimization-service:8005
```

Check `docker-compose.yml` for the frontend service env block and add the variable if missing.

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep -E "error|tax"
```

Expected: No errors related to the new route files.

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/app/api/portfolios/[id]/tax/route.ts \
        src/frontend/src/app/api/tax/summary/route.ts
git commit -m "feat(api): add /api/portfolios/[id]/tax and /api/tax/summary Next.js routes"
```

---

## Task 6: Portfolio Aggregator — Wire Real NAA Yield (Strategy A)

**Files:**
- Modify: `src/broker-service/app/services/portfolio_aggregator.py`

**Context:** The aggregator currently computes `naa_yield = total_income / total_value` (gross, no tax or fees). Strategy A: call the extended `/tax/optimize/portfolio` endpoint and read `portfolio_nay`. Falls back to gross yield if tax service is unavailable or user has no preferences.

- [ ] **Step 1: Write the failing test**

Add to `src/broker-service/tests/test_portfolio_aggregator.py` (create if it doesn't exist):

```python
# src/broker-service/tests/test_portfolio_aggregator.py
import os
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.anyio
async def test_aggregator_uses_tax_service_naa_when_available():
    """When tax service returns portfolio_nay, aggregator should use it."""
    from app.services.portfolio_aggregator import aggregate_portfolio

    mock_positions = [
        {"symbol": "ECC", "current_value": 10000.0, "annual_income": 4230.0,
         "asset_type": "CEF", "cost_basis": 9500.0},
    ]

    mock_tax_response = {
        "portfolio_nay": 0.18,
        "portfolio_gross_yield": 0.423,
        "total_portfolio_value": 10000.0,
    }

    with patch("app.services.portfolio_aggregator._fetch_tax_nay",
               new_callable=AsyncMock, return_value=0.18) as mock_tax:
        result = await aggregate_portfolio("test-portfolio-id", mock_positions, {
            "annual_income": 150000, "filing_status": "SINGLE", "state_code": "CA"
        })

    assert result["naa_yield"] == pytest.approx(0.18)
    assert result["naa_yield_pre_tax"] is False


@pytest.mark.anyio
async def test_aggregator_falls_back_to_gross_when_tax_unavailable():
    """When tax service fails, aggregator falls back to gross yield."""
    from app.services.portfolio_aggregator import aggregate_portfolio

    mock_positions = [
        {"symbol": "ECC", "current_value": 10000.0, "annual_income": 4230.0,
         "asset_type": "CEF", "cost_basis": 9500.0},
    ]

    with patch("app.services.portfolio_aggregator._fetch_tax_nay",
               new_callable=AsyncMock, return_value=None):
        result = await aggregate_portfolio("test-portfolio-id", mock_positions, None)

    # Falls back to gross: 4230 / 10000 = 0.423
    assert result["naa_yield"] == pytest.approx(0.423, abs=0.001)
    assert result["naa_yield_pre_tax"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd src/broker-service
pytest tests/test_portfolio_aggregator.py -v
```

Expected: FAILED (function signature mismatch or `_fetch_tax_nay` doesn't exist)

- [ ] **Step 3: Add `_fetch_tax_nay` helper and update `portfolio_aggregator.py`**

In `src/broker-service/app/services/portfolio_aggregator.py`:

**Add imports** at the top:
```python
import os
import httpx
```

**Add `_fetch_tax_nay` helper function** before the main aggregation function:

```python
async def _fetch_tax_nay(
    portfolio_id: str,
    tax_prefs: dict | None,
) -> float | None:
    """Call tax service /tax/optimize/portfolio and return portfolio_nay.

    Returns None if tax service is unavailable or user has no preferences.
    All yield values from the tax service are decimal fractions (e.g. 0.071).
    """
    if not tax_prefs:
        return None
    tax_url = os.environ.get("TAX_OPTIMIZATION_URL", "http://tax-optimization-service:8005")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{tax_url}/tax/optimize/portfolio",
                json={
                    "portfolio_id": portfolio_id,
                    "annual_income": tax_prefs.get("annual_income", 100000),
                    "filing_status": tax_prefs.get("filing_status", "SINGLE"),
                    "state_code": tax_prefs.get("state_code"),
                },
            )
            if resp.status_code == 200:
                return resp.json().get("portfolio_nay")
    except Exception as exc:
        logger.warning("Tax service NAA fetch failed for %s: %s", portfolio_id, exc)
    return None
```

**Update the NAA yield section** (around line 107-108). Replace:

```python
# NAA Yield (use gross yield as proxy; full NAA requires tax service)
naa_yield = round(total_income / total_value, 4) if total_value > 0 else None
```

With:

```python
# NAA Yield — Strategy A: read from tax service (real, post-tax + post-fee)
# Strategy B fallback: gross yield when tax service unavailable
_tax_nay = await _fetch_tax_nay(portfolio_id, tax_prefs)
if _tax_nay is not None:
    naa_yield = round(_tax_nay, 4)
    naa_yield_pre_tax = False
else:
    naa_yield = round(total_income / total_value, 4) if total_value > 0 else None
    naa_yield_pre_tax = True
```

**Signature change — audit all callers first.**

The current `aggregate_portfolio` is synchronous with signature `(positions, scores)`. The new signature is `async (portfolio_id, positions, scores, tax_prefs=None)`. Two callers in `broker.py` must be updated:

```bash
grep -n "aggregate_portfolio" src/broker-service/app/api/broker.py
```

Find lines like `agg = aggregate_portfolio(positions, scores)` and update to:

```python
agg = await aggregate_portfolio(portfolio_id, positions, scores, tax_prefs=user_tax_prefs)
```

Where `portfolio_id` is the portfolio's ID string and `user_tax_prefs` is the user's preferences dict (fetch from `user_preferences` table or pass `None` to fall back to gross yield). Also update the existing tests in `src/broker-service/tests/test_portfolio_aggregator.py` — the calls `aggregate_portfolio(POSITIONS, SCORES)` must become `await aggregate_portfolio("test-id", POSITIONS, SCORES)` and test functions must be marked `async`.

The complete new function signature:

```python
async def aggregate_portfolio(
    portfolio_id: str,
    positions: list[dict],
    scores: dict[str, dict],
    tax_prefs: dict | None = None,
) -> dict:
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd src/broker-service
pytest tests/test_portfolio_aggregator.py -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add src/broker-service/app/services/portfolio_aggregator.py \
        src/broker-service/tests/test_portfolio_aggregator.py
git commit -m "feat(broker): wire NAAYield to tax service portfolio_nay (Strategy A with gross fallback)"
```

---

## Task 7: TypeScript Types — `TaxHolding`, `PortfolioTaxAnalysis`, `TaxSummary`

**Files:**
- Modify: `src/frontend/src/lib/types.ts`

- [ ] **Step 1: Open `src/frontend/src/lib/types.ts` and verify `expense_ratio` is not already on `Position`**

```bash
grep -n "expense_ratio" src/frontend/src/lib/types.ts
```

If it exists, skip adding it. If not, add `expense_ratio?: number | null;` to the `Position` interface.

- [ ] **Step 2: Add new types to the end of `src/frontend/src/lib/types.ts`**

```typescript
// ── Tax Optimization ──────────────────────────────────────────────────────────

export interface TaxHolding {
  symbol: string;
  asset_class: string;
  current_account: string;
  recommended_account: string;
  placement_mismatch: boolean;
  treatment: string;
  gross_yield: number;           // decimal fraction, e.g. 0.423
  effective_tax_rate: number;    // decimal fraction, combined fed+state+NIIT
  after_tax_yield: number;       // decimal fraction
  expense_ratio: number | null;  // decimal fraction, null for stocks
  expense_drag_pct: number;      // decimal fraction
  nay: number;                   // decimal fraction (NAA Yield)
  annual_income: number;
  tax_withheld: number;
  expense_drag_amount: number;
  net_annual_income: number;
  estimated_annual_tax_savings: number;
  reason: string;
}

export interface PortfolioTaxAnalysis {
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

export interface TaxSummary {
  aggregate_nay: number | null;          // decimal fraction; null if no tax profile
  aggregate_gross_yield: number | null;  // decimal fraction
  total_tax_drag: number;
  total_expense_drag: number;
  portfolio_count: number;
}
```

- [ ] **Step 3: Verify TypeScript compiles without errors**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep error
```

Expected: No output (no errors)

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/lib/types.ts
git commit -m "feat(types): add TaxHolding, PortfolioTaxAnalysis, TaxSummary types"
```

---

## Task 8: `tax-tab.tsx` — New Portfolio Tax Tab

**Files:**
- Create: `src/frontend/src/app/portfolios/[id]/tabs/tax-tab.tsx`

**Context:** Follows the same patterns as `health-tab.tsx`. Uses `DataTable` from `@/components/data-table`, `TickerBadge`, `ColHeader`, `cn`. Banner shows tax metrics. Table has per-holding tax data. Detail panel shows full tax waterfall. Action bar with proposal generation when rows selected.

- [ ] **Step 1: Create `tax-tab.tsx`**

```tsx
// src/frontend/src/app/portfolios/[id]/tabs/tax-tab.tsx
"use client";
import { useState, useEffect, useCallback } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { ColHeader } from "@/components/help-tooltip";
import { cn, scoreTextColor } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import type { PortfolioTaxAnalysis, TaxHolding } from "@/lib/types";

// ── Helper components ─────────────────────────────────────────────────────────

function DetailRow({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/80 mb-0.5">{label}</div>
      <div className={cn("text-sm font-semibold text-foreground", className)}>{value}</div>
    </div>
  );
}

function SectionTitle({ label }: { label: string }) {
  return (
    <div className="text-[10px] font-bold uppercase tracking-wider text-blue-400 mb-2 pb-1 border-b border-border/50">
      {label}
    </div>
  );
}

function AccountBadge({ account, mismatch }: { account: string; mismatch: boolean }) {
  const colors: Record<string, string> = {
    TAXABLE:  mismatch ? "bg-red-950/60 text-red-400 border-red-900/50" : "bg-slate-800 text-slate-400 border-slate-700",
    ROTH_IRA: "bg-green-950/60 text-green-400 border-green-900/50",
    TRAD_IRA: "bg-blue-950/60 text-blue-400 border-blue-900/50",
    HSA:      "bg-purple-950/60 text-purple-400 border-purple-900/50",
    "401K":   "bg-amber-950/60 text-amber-400 border-amber-900/50",
  };
  return (
    <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded border", colors[account] ?? "text-muted-foreground")}>
      {account.replace("_", " ")}
    </span>
  );
}

const TAX_PROFILE_HELP = {
  annual_income: "Your total gross annual income. Determines your federal bracket and NIIT eligibility (applies above $200k single / $250k joint).",
  filing_status: "Your IRS filing status. Determines which tax brackets and standard deduction apply.",
  state_code: "Your state of residence. Nine states have no income tax (AK, FL, NV, SD, TN, TX, WA, WY, NH on dividends).",
};

// ── Main component ────────────────────────────────────────────────────────────

interface TaxTabProps {
  portfolioId: string;
  refreshKey?: number;
  onTaxDataLoaded?: (data: PortfolioTaxAnalysis) => void;
}

export function TaxTab({ portfolioId, refreshKey = 0, onTaxDataLoaded }: TaxTabProps) {
  const [taxData, setTaxData] = useState<PortfolioTaxAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TaxHolding | null>(null);
  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [showSettings, setShowSettings] = useState(false);
  const [settingsForm, setSettingsForm] = useState({ annual_income: "", filing_status: "SINGLE", state_code: "" });
  const [savingSettings, setSavingSettings] = useState(false);

  const load = useCallback(() => {
    if (!portfolioId) return;
    setLoading(true);
    setError(null);
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    fetch(`${API_BASE_URL}/api/portfolios/${portfolioId}/tax`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data: PortfolioTaxAnalysis) => {
        setTaxData(data);
        setSettingsForm({
          annual_income: String(data.tax_profile.annual_income),
          filing_status: data.tax_profile.filing_status,
          state_code: data.tax_profile.state_code ?? "",
        });
        onTaxDataLoaded?.(data);
        setLoading(false);
      })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [portfolioId, refreshKey, onTaxDataLoaded]);

  useEffect(() => { load(); }, [load]);

  const saveSettings = async () => {
    setSavingSettings(true);
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    await fetch(`${API_BASE_URL}/api/user/preferences`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      credentials: "include",
      body: JSON.stringify({
        annual_income: Number(settingsForm.annual_income),
        filing_status: settingsForm.filing_status,
        state_code: settingsForm.state_code || null,
      }),
    });
    setSavingSettings(false);
    setShowSettings(false);
    load();
  };

  const columns: ColumnDef<TaxHolding>[] = [
    {
      id: "select",
      header: "",
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selectedTickers.has(row.original.symbol)}
          onChange={(e) => {
            setSelectedTickers((prev) => {
              const next = new Set(prev);
              e.target.checked ? next.add(row.original.symbol) : next.delete(row.original.symbol);
              return next;
            });
          }}
          className="w-3.5 h-3.5"
        />
      ),
      size: 28,
    },
    {
      accessorKey: "symbol",
      header: () => <ColHeader label="Ticker" help="Ticker symbol" />,
      meta: { label: "Ticker" },
      cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_class} />,
    },
    {
      accessorKey: "asset_class",
      header: () => <ColHeader label="Class" help="Asset classification" />,
      meta: { label: "Class" },
    },
    {
      accessorKey: "current_account",
      header: () => <ColHeader label="Account" help="Current account type for this holding" />,
      meta: { label: "Account" },
      cell: ({ row }) => (
        <AccountBadge account={row.original.current_account} mismatch={row.original.placement_mismatch} />
      ),
    },
    {
      accessorKey: "treatment",
      header: () => <ColHeader label="Treatment" help="Primary tax treatment of distributions" />,
      meta: { label: "Tax Treatment" },
      cell: ({ getValue }) => (
        <span className={cn("text-xs", (getValue() as string) === "ORDINARY_INCOME" ? "text-red-400" : "text-green-400")}>
          {(getValue() as string).replace(/_/g, " ")}
        </span>
      ),
    },
    {
      accessorKey: "gross_yield",
      header: () => <ColHeader label="Gross Yield" help="Annual income / current market value, before tax and fees" />,
      meta: { label: "Gross Yield" },
      cell: ({ getValue }) => <span className="tabular-nums">{((getValue() as number) * 100).toFixed(2)}%</span>,
    },
    {
      accessorKey: "effective_tax_rate",
      header: () => <ColHeader label="Tax Rate" help="Combined effective rate: federal + state + NIIT" />,
      meta: { label: "Effective Tax Rate" },
      cell: ({ getValue }) => {
        const v = (getValue() as number) * 100;
        return <span className={cn("tabular-nums", v > 40 ? "text-red-400" : v > 20 ? "text-amber-400" : "text-green-400")}>{v.toFixed(1)}%</span>;
      },
    },
    {
      accessorKey: "after_tax_yield",
      header: () => <ColHeader label="After-Tax" help="Gross yield minus tax drag" />,
      meta: { label: "After-Tax Yield" },
      cell: ({ getValue }) => <span className="tabular-nums">{((getValue() as number) * 100).toFixed(2)}%</span>,
    },
    {
      accessorKey: "nay",
      header: () => <ColHeader label="NAA Yield" help="Net After-All Yield: gross yield minus tax drag minus expense ratio. The yield you actually keep." />,
      meta: { label: "NAA Yield" },
      cell: ({ getValue }) => {
        const v = (getValue() as number) * 100;
        return <span className={cn("font-bold tabular-nums", scoreTextColor(v / 0.1))}>{v.toFixed(2)}%</span>;
      },
    },
    {
      accessorKey: "recommended_account",
      header: () => <ColHeader label="Rec." help="Recommended account for tax optimization" />,
      meta: { label: "Placement Rec." },
      cell: ({ row }) => {
        const h = row.original;
        if (!h.placement_mismatch) return <span className="text-green-400 text-xs">✓ Optimal</span>;
        return <span className="text-amber-400 text-xs font-medium">→ {h.recommended_account.replace("_", " ")} ⚠</span>;
      },
    },
    {
      accessorKey: "estimated_annual_tax_savings",
      header: () => <ColHeader label="Savings/yr" help="Estimated annual tax savings if moved to recommended account" />,
      meta: { label: "Est. Savings/yr" },
      cell: ({ getValue }) => {
        const v = getValue() as number;
        return v > 0 ? <span className="text-green-400 tabular-nums text-xs">${v.toFixed(0)}</span> : <span className="text-muted-foreground">—</span>;
      },
    },
    // Hidden by default
    {
      accessorKey: "expense_ratio",
      header: "Expense Ratio",
      meta: { defaultHidden: true, label: "Expense Ratio" },
      cell: ({ getValue }) => {
        const v = getValue() as number | null;
        return v != null ? `${(v * 100).toFixed(2)}%` : "—";
      },
    },
    {
      accessorKey: "expense_drag_amount",
      header: "Expense Drag $",
      meta: { defaultHidden: true, label: "Annual Expense Drag" },
      cell: ({ getValue }) => {
        const v = getValue() as number;
        return v > 0 ? `$${v.toFixed(0)}` : "—";
      },
    },
  ];

  if (loading) return <div className="text-muted-foreground text-sm p-4">Loading tax analysis...</div>;
  if (error) return <div className="text-red-400 text-sm p-4 bg-red-950/30 border border-red-900/50 rounded">{error}</div>;
  if (!taxData) return null;

  const profile = taxData.tax_profile;
  const fmt = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

  return (
    <div className="flex flex-col gap-3">

      {/* BANNER */}
      <div className="flex items-center gap-3 flex-wrap px-1">
        <div className="flex gap-3 flex-1">
          <div className="bg-card border border-border rounded-lg px-4 py-2.5 min-w-[120px]">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Est. Tax Drag / yr</div>
            <div className="text-lg font-bold text-red-400">{fmt(taxData.current_annual_tax_burden)}</div>
          </div>
          <div className="bg-card border border-border rounded-lg px-4 py-2.5 min-w-[120px]">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Suboptimal Holdings</div>
            <div className="text-lg font-bold text-amber-400">
              {taxData.suboptimal_count} <span className="text-sm text-muted-foreground font-normal">of {taxData.holdings.length}</span>
            </div>
          </div>
          <div className="bg-card border border-border rounded-lg px-4 py-2.5 min-w-[120px]">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Potential Savings / yr</div>
            <div className="text-lg font-bold text-green-400">{fmt(taxData.estimated_annual_savings)}</div>
          </div>
          <div className="bg-card border border-border rounded-lg px-4 py-2.5 min-w-[120px]">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Portfolio NAA Yield</div>
            <div className="text-lg font-bold text-blue-400">{(taxData.portfolio_nay * 100).toFixed(2)}%</div>
          </div>
        </div>

        {/* Tax profile pill */}
        <div className="flex items-center gap-2 bg-card border border-border rounded-lg px-3 py-2 text-xs text-muted-foreground">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground/60">Tax Profile</span>
          <span className="bg-muted px-2 py-0.5 rounded" title={TAX_PROFILE_HELP.annual_income}>
            ${(profile.annual_income / 1000).toFixed(0)}k ⓘ
          </span>
          <span className="text-muted-foreground/40">·</span>
          <span className="bg-muted px-2 py-0.5 rounded" title={TAX_PROFILE_HELP.filing_status}>
            {profile.filing_status.replace("_", " ")} ⓘ
          </span>
          {profile.state_code && (
            <>
              <span className="text-muted-foreground/40">·</span>
              <span className="bg-muted px-2 py-0.5 rounded" title={TAX_PROFILE_HELP.state_code}>
                {profile.state_code} ⓘ
              </span>
            </>
          )}
          <button
            onClick={() => setShowSettings(true)}
            className="text-blue-400 hover:text-blue-300 border border-blue-900/50 px-2 py-0.5 rounded text-[10px]"
          >
            Edit ✎
          </button>
        </div>
      </div>

      {/* ACTION BAR */}
      {selectedTickers.size > 0 && (
        <div className="flex items-center gap-3 px-1 py-2 bg-blue-950/30 border border-blue-900/40 rounded-lg">
          <span className="text-blue-400 text-xs font-medium">{selectedTickers.size} selected</span>
          <button
            className="bg-blue-700 hover:bg-blue-600 text-white text-xs font-semibold px-3 py-1.5 rounded"
            onClick={() => {
              // Opens proposal modal — scanner ProposalModal handles this
              // Emit event or use router to navigate with selected tickers
              // Implementation: store selectedTickers in URL params or session
              // TODO(Task 12): wire ProposalModal — pre-populate selectedTickers
              alert(`Open ProposalModal for: ${[...selectedTickers].join(", ")} — see Task 12`);
            }}
          >
            ⚡ Generate Rebalance Proposal
          </button>
          <span className="text-muted-foreground text-xs">Proposes sell + buy to move to recommended accounts</span>
          <button
            onClick={() => setSelectedTickers(new Set())}
            className="ml-auto text-muted-foreground text-xs hover:text-foreground"
          >
            Clear
          </button>
        </div>
      )}

      {/* TABLE + DETAIL PANEL */}
      <div className="flex gap-3">
        <div className="flex-1 min-w-0">
          <DataTable
            columns={columns}
            data={taxData.holdings}
            storageKey={`tax-tab-${portfolioId}`}
            onRowClick={(row) => setSelected((s) => s?.symbol === row.symbol ? null : row)}
          />
        </div>

        {/* DETAIL PANEL */}
        {selected && (
          <div className="w-80 shrink-0 bg-card border border-border rounded-lg p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-260px)]">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-bold text-base">{selected.symbol}</span>
                <div className="text-xs text-muted-foreground mt-0.5">{selected.asset_class}</div>
              </div>
              <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground text-sm px-1">✕</button>
            </div>

            {/* Tax waterfall */}
            <section>
              <SectionTitle label="Tax Breakdown" />
              <div className="space-y-1.5">
                <DetailRow label="Gross Yield" value={`${(selected.gross_yield * 100).toFixed(2)}%`} />
                <DetailRow label="Treatment" value={selected.treatment.replace(/_/g, " ")} />
                <div className="border-t border-border/40 pt-1.5 space-y-1">
                  <DetailRow label="Federal Tax" value={`−${((selected.effective_tax_rate - 0) * 100 * 0.7).toFixed(1)}%`} className="text-red-400" />
                  <DetailRow label="State Tax" value={`−${((selected.effective_tax_rate) * 100 * 0.25).toFixed(1)}%`} className="text-red-400" />
                  {selected.effective_tax_rate > 0.50 && (
                    <DetailRow label="NIIT (3.8%)" value="−3.8%" className="text-red-400" />
                  )}
                  <DetailRow label="After-Tax Yield" value={`${(selected.after_tax_yield * 100).toFixed(2)}%`} />
                </div>
                {selected.expense_ratio != null && selected.expense_ratio > 0 && (
                  <div className="border-t border-border/40 pt-1.5">
                    <DetailRow
                      label={`Expense Ratio (${(selected.expense_ratio * 100).toFixed(2)}%)`}
                      value={`−$${selected.expense_drag_amount.toFixed(0)}/yr`}
                      className="text-amber-400"
                    />
                  </div>
                )}
                <div className="border-t border-border/40 pt-1.5">
                  <DetailRow label="NAA Yield" value={`${(selected.nay * 100).toFixed(2)}%`} className="text-green-400 text-base" />
                  <DetailRow label="Net Annual Income" value={`$${selected.net_annual_income.toFixed(0)}`} />
                </div>
              </div>
            </section>

            {/* Placement recommendation */}
            {selected.placement_mismatch && (
              <section>
                <SectionTitle label="Account Recommendation" />
                <div className="bg-amber-950/30 border border-amber-900/40 rounded p-2.5 space-y-2">
                  <div className="text-amber-400 font-semibold text-sm">→ {selected.recommended_account.replace("_", " ")}</div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{selected.reason}</p>
                  <div className="flex justify-between text-xs pt-1 border-t border-border/30">
                    <span className="text-muted-foreground">Est. savings if moved</span>
                    <span className="text-green-400 font-semibold">${selected.estimated_annual_tax_savings.toFixed(0)}/yr</span>
                  </div>
                </div>
                <button
                  className="w-full mt-3 bg-blue-700 hover:bg-blue-600 text-white text-xs font-semibold py-2 rounded"
                  onClick={() => alert(`TODO(Task 12): ProposalModal for ${selected.symbol}`)}
                >
                  ⚡ Propose Account Transfer
                </button>
                <p className="text-center text-[9px] text-muted-foreground/60 mt-1">
                  Generates sell + buy proposal in Proposals tab
                </p>
              </section>
            )}
          </div>
        )}
      </div>

      {/* SETTINGS MODAL */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-sm space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-semibold">Tax Profile Settings</h3>
              <button onClick={() => setShowSettings(false)} className="text-muted-foreground hover:text-foreground">✕</button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  Annual Income
                  <span className="cursor-help text-muted-foreground/50" title={TAX_PROFILE_HELP.annual_income}>ⓘ</span>
                </label>
                <input
                  type="number"
                  value={settingsForm.annual_income}
                  onChange={(e) => setSettingsForm((s) => ({ ...s, annual_income: e.target.value }))}
                  className="mt-1 w-full bg-muted border border-border rounded px-3 py-1.5 text-sm"
                  placeholder="150000"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  Filing Status
                  <span className="cursor-help text-muted-foreground/50" title={TAX_PROFILE_HELP.filing_status}>ⓘ</span>
                </label>
                <select
                  value={settingsForm.filing_status}
                  onChange={(e) => setSettingsForm((s) => ({ ...s, filing_status: e.target.value }))}
                  className="mt-1 w-full bg-muted border border-border rounded px-3 py-1.5 text-sm"
                >
                  <option value="SINGLE">Single</option>
                  <option value="MARRIED_JOINT">Married Filing Jointly</option>
                  <option value="MARRIED_SEPARATE">Married Filing Separately</option>
                  <option value="HEAD_OF_HOUSEHOLD">Head of Household</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  State
                  <span className="cursor-help text-muted-foreground/50" title={TAX_PROFILE_HELP.state_code}>ⓘ</span>
                </label>
                <input
                  type="text"
                  value={settingsForm.state_code}
                  onChange={(e) => setSettingsForm((s) => ({ ...s, state_code: e.target.value.toUpperCase().slice(0, 2) }))}
                  className="mt-1 w-full bg-muted border border-border rounded px-3 py-1.5 text-sm uppercase"
                  placeholder="CA"
                  maxLength={2}
                />
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button onClick={() => setShowSettings(false)} className="flex-1 bg-muted hover:bg-muted/80 text-sm py-2 rounded border border-border">
                Cancel
              </button>
              <button
                onClick={saveSettings}
                disabled={savingSettings}
                className="flex-1 bg-blue-700 hover:bg-blue-600 text-white text-sm py-2 rounded font-semibold"
              >
                {savingSettings ? "Saving…" : "Save & Recalculate"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep -E "error.*tax-tab"
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/app/portfolios/[id]/tabs/tax-tab.tsx
git commit -m "feat(frontend): add TaxTab component with banner, table, detail panel, and settings modal"
```

---

## Task 9: Portfolio Page — Add Tax Tab and Lift `taxData` State

**Files:**
- Modify: `src/frontend/src/app/portfolios/[id]/page.tsx`

**Context:** The page currently has tabs: `portfolio | market | health | simulation | projection`. We add `tax`. The `taxData` state is lifted to page level so the portfolio tab's detail pane can access it without a second fetch.

- [ ] **Step 1: Add `TaxTab` import and `tax` to the Tab type**

In `src/frontend/src/app/portfolios/[id]/page.tsx`:

Add to imports:
```typescript
import { TaxTab } from "./tabs/tax-tab";
import type { PortfolioTaxAnalysis } from "@/lib/types";
```

Change the `Tab` type:
```typescript
type Tab = "portfolio" | "market" | "health" | "simulation" | "projection" | "tax";
```

Add to `TABS` array (after `health`):
```typescript
{ key: "tax", label: "Tax" },
```

- [ ] **Step 2: Add `taxData` state and pass it down**

Inside the component function, add after the existing state declarations:
```typescript
const [taxData, setTaxData] = useState<PortfolioTaxAnalysis | null>(null);
```

- [ ] **Step 3: Add the Tax tab render and pass props**

In the tab rendering section, add after the health tab render:
```tsx
{activeTab === "tax" && (
  <TaxTab
    portfolioId={id}
    refreshKey={tabRefreshKey}
    onTaxDataLoaded={setTaxData}
  />
)}
```

Update the portfolio tab render to pass `taxData`:
```tsx
{activeTab === "portfolio" && (
  <PortfolioTab portfolioId={id} refreshKey={tabRefreshKey} taxData={taxData} />
)}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep -E "error.*portfolios"
```

Expected: Only errors related to `taxData` prop not yet accepted by `PortfolioTab` (fixed in Task 10).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/portfolios/[id]/page.tsx
git commit -m "feat(portfolio): add Tax tab and lift taxData state to portfolio page"
```

---

## Task 10: Portfolio Tab — Add True Yield to Detail Panel

**Files:**
- Modify: `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx`

**Context:** The detail panel already has `DetailRow` and `SectionTitle` components. We add a "True Yield" section showing cost drag, tax drag, and NAA Yield. These values come from `taxData` passed from the parent.

- [ ] **Step 1: Update `PortfolioTabProps` to accept `taxData`**

In `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx`:

Update the interface:
```typescript
import type { PortfolioTaxAnalysis, TaxHolding } from "@/lib/types";

interface PortfolioTabProps {
  portfolioId: string;
  refreshKey?: number;
  taxData?: PortfolioTaxAnalysis | null;   // ADD THIS
}
```

Update the function signature:
```typescript
export function PortfolioTab({ portfolioId, refreshKey = 0, taxData }: PortfolioTabProps) {
```

- [ ] **Step 2: Add True Yield section to the detail panel**

In the detail panel section (the `{selected && (...)}` block), find the income/yield section. After it, add:

```tsx
{/* True Yield (tax + cost breakdown) */}
<section>
  <SectionTitle label="True Yield" />
  {(() => {
    const grossYield = selected.current_price > 0
      ? (selected.annual_income ?? 0) / (selected.current_price * (selected.shares ?? 1))
      : null;
    const taxHolding: TaxHolding | undefined = taxData?.holdings.find(
      (h) => h.symbol === selected.symbol
    );
    return (
      <div className="space-y-1.5">
        {grossYield != null && (
          <DetailRow label="Gross Yield" value={`${(grossYield * 100).toFixed(2)}%`} />
        )}
        {selected.expense_ratio != null && selected.expense_ratio > 0 && (
          <DetailRow
            label={`Cost Drag (${(selected.expense_ratio * 100).toFixed(2)}% ER)`}
            value={`−${(selected.expense_ratio * 100).toFixed(2)}%`}
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
          <div className="text-xs text-muted-foreground italic">
            Open Tax tab to see NAA Yield
          </div>
        )}
      </div>
    );
  })()}
</section>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep -E "error.*portfolio-tab"
```

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx
git commit -m "feat(portfolio): add True Yield section (cost drag, tax drag, NAA) to position detail panel"
```

---

## Task 11: Dashboard — Aggregate NAA Yield Card

**Files:**
- Modify: `src/frontend/src/app/dashboard/page.tsx`

**Context:** The dashboard has a `kpis` array powering a `KpiStrip` component. We add an aggregate NAA Yield card by fetching `/api/tax/summary` and adding an entry to the kpis array.

- [ ] **Step 1: Read the current dashboard KPI array structure**

Check `src/frontend/src/app/dashboard/page.tsx` lines 40-55 to see the exact KPI shape and `KpiStrip` usage before modifying. The KPI objects have `{ label, value, helpText?, colorClass? }`.

- [ ] **Step 2: Add NAA Yield state and fetch**

At the top of the dashboard component, add:

```typescript
import type { TaxSummary } from "@/lib/types";

// Inside the component:
const [taxSummary, setTaxSummary] = useState<TaxSummary | null>(null);

useEffect(() => {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
  fetch(`${API_BASE_URL}/api/tax/summary`, {
    headers: { Authorization: `Bearer ${token}` },
    credentials: "include",
  })
    .then((r) => r.ok ? r.json() : null)
    .then((data) => setTaxSummary(data))
    .catch(() => {});
}, []);
```

- [ ] **Step 3: Add the NAA Yield card to the kpis array**

In the `kpis` array definition, add after the existing yield/income entries:

```typescript
{
  label: "NAA Yield",
  value: taxSummary?.aggregate_nay != null
    ? `${(taxSummary.aggregate_nay * 100).toFixed(2)}%`
    : "—",
  colorClass: taxSummary?.aggregate_nay != null ? "text-blue-400" : undefined,
  helpText: taxSummary?.aggregate_gross_yield != null
    ? `Net After-All Yield across all portfolios. Gross: ${(taxSummary.aggregate_gross_yield * 100).toFixed(2)}%. Tax + cost drag: −${((taxSummary.aggregate_gross_yield - (taxSummary.aggregate_nay ?? 0)) * 100).toFixed(2)}%.`
    : "Net After-All Yield: annual income minus tax and expense costs, divided by market value. Set tax profile in any portfolio's Tax tab.",
},
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep -E "error.*dashboard"
```

Expected: No errors

- [ ] **Step 5: Build and deploy**

```bash
# Commit locally
git add src/frontend/src/app/dashboard/page.tsx
git commit -m "feat(dashboard): add aggregate NAA Yield KPI card"

# Push and deploy
git push origin main
ssh root@138.197.78.238 "cd /opt/Agentic/income-platform && git pull && \
  docker compose build agent-07-opportunity-scanner tax-optimization-service broker-service frontend && \
  docker compose up -d agent-07-opportunity-scanner tax-optimization-service broker-service frontend"
```

Expected: All 4 containers rebuilt and restarted. NAA Yield card appears on dashboard.

---

---

## Task 12: Wire ProposalModal into Tax Tab

**Files:**
- Modify: `src/frontend/src/components/scanner/proposal-modal.tsx`
- Modify: `src/frontend/src/app/portfolios/[id]/tabs/tax-tab.tsx`

**Context:** The tax tab has two `alert("TODO(Task 12)")` stubs — the action bar's "Generate Rebalance Proposal" button and the detail panel's "Propose Account Transfer" button. The existing `ProposalModal` is scanner-specific: it requires a `ScanResult` (a scan_id + items) and submits to `/api/scanner/propose`. Tax proposals are different: they specify a source account + destination account for each holding. This task extends `ProposalModal` with an optional `taxHoldings` path so the existing modal dialog and portfolio-picker UX can be reused.

- [ ] **Step 1: Read the current `ProposalModal` to understand the submit flow**

```bash
cat src/frontend/src/components/scanner/proposal-modal.tsx
```

Note the current `handleSubmit` flow: calls `/api/scanner/propose` with `scan_id` + `selected_tickers` + `target_portfolio_id`. The tax variant will call `/api/proposals/new` directly with `proposal_type: "TAX_REBALANCE"` and a list of holdings with `from_account` and `to_account`.

- [ ] **Step 2: Add `taxHoldings` optional prop to `ProposalModal`**

In `src/frontend/src/components/scanner/proposal-modal.tsx`, extend the interface and submit logic:

```typescript
// Add to ProposalModalProps (after existing props):
taxHoldings?: Array<{
  symbol: string;
  from_account: string;
  to_account: string;
  reason: string;
}>;
```

Update `handleSubmit` to branch on `taxHoldings`:

```typescript
const handleSubmit = async () => {
  if (!targetPortfolioId) return;
  setLoading(true);
  setError(null);
  try {
    let proposalId: string;
    if (taxHoldings && taxHoldings.length > 0) {
      // Tax rebalance path
      const resp = await fetch("/api/proposals/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          portfolio_id: targetPortfolioId,
          proposal_type: "TAX_REBALANCE",
          holdings: taxHoldings,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Failed to create proposal");
      proposalId = data.proposal_id;
    } else {
      // Existing scanner path
      if (!scanResult) return;
      const draftResp = await fetch("/api/scanner/propose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scan_id: scanResult.scan_id,
          selected_tickers: [...selectedTickers],
          target_portfolio_id: targetPortfolioId,
        }),
      });
      const draftData = await draftResp.json();
      if (!draftResp.ok) throw new Error(draftData.detail ?? "Failed to create proposal");
      proposalId = draftData.proposal_id;
    }
    onSuccess(proposalId);
    onClose();
    router.push(`/proposals/${proposalId}`);
  } catch (err) {
    setError(err instanceof Error ? err.message : "Unknown error");
  } finally {
    setLoading(false);
  }
};
```

- [ ] **Step 3: Wire up the action bar button in `tax-tab.tsx`**

In `src/frontend/src/app/portfolios/[id]/tabs/tax-tab.tsx`:

Add state and imports:

```typescript
import { ProposalModal } from "@/components/scanner/proposal-modal";
import { usePortfolios } from "@/lib/hooks/use-portfolios";

// Inside component:
const { portfolios } = usePortfolios();
const [proposalOpen, setProposalOpen] = useState(false);
const [proposalHoldings, setProposalHoldings] = useState<
  Array<{ symbol: string; from_account: string; to_account: string; reason: string }>
>([]);
```

Replace the action bar `alert` stub:

```typescript
onClick={() => {
  const holdings = [...selectedTickers].map((ticker) => {
    const h = taxData.holdings.find((x) => x.symbol === ticker);
    return {
      symbol: ticker,
      from_account: h?.current_account ?? "TAXABLE",
      to_account: h?.recommended_account ?? "TAXABLE",
      reason: h?.reason ?? "Tax optimization",
    };
  });
  setProposalHoldings(holdings);
  setProposalOpen(true);
}}
```

Replace the detail panel `alert` stub:

```typescript
onClick={() => {
  setProposalHoldings([{
    symbol: selected.symbol,
    from_account: selected.current_account,
    to_account: selected.recommended_account,
    reason: selected.reason,
  }]);
  setProposalOpen(true);
}}
```

Add the modal at the bottom of the return, before the closing `</div>`:

```tsx
<ProposalModal
  open={proposalOpen}
  onClose={() => setProposalOpen(false)}
  selectedTickers={selectedTickers}
  scanResult={null}
  taxHoldings={proposalHoldings}
  portfolios={portfolios}
  defaultPortfolioId={portfolioId}
  onSuccess={(id) => console.log("Proposal created:", id)}
/>
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep -E "error.*(tax-tab|proposal-modal)"
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/components/scanner/proposal-modal.tsx \
        src/frontend/src/app/portfolios/[id]/tabs/tax-tab.tsx
git commit -m "feat(tax): wire ProposalModal into tax tab for account rebalance proposals"
```

---

## Smoke Test Checklist

After deployment, verify end-to-end:

- [ ] **expense_ratio in DB**: `SELECT symbol, expense_ratio FROM platform_shared.market_data_cache WHERE symbol='JEPI' LIMIT 1;` — should show a non-null value after next daily cache refresh (or manual trigger)
- [ ] **Tax placement**: `curl -X POST http://server:8005/tax/placement -H 'Content-Type: application/json' -d '{"ticker":"ECC","asset_class":"CLOSED_END_FUND"}' -H 'Authorization: Bearer <token>'` — should return `{"recommended_account":"ROTH_IRA",...}`
- [ ] **Optimize portfolio**: `POST /tax/optimize/portfolio` returns `holdings_analysis` array and `portfolio_nay` field
- [ ] **Tax tab**: Opens in a portfolio, shows banner with tax drag/savings, table with all holdings, detail panel on click
- [ ] **Portfolio detail pane**: True Yield section visible after visiting Tax tab (or shows "Open Tax tab" nudge before)
- [ ] **Dashboard NAA Yield**: Shows a percentage value (or `—` if no tax profile set)
- [ ] **NAA in portfolio header**: `naa_yield` value has changed from gross yield to the after-tax figure (visible change after broker sync for portfolios with high-tax holdings)
