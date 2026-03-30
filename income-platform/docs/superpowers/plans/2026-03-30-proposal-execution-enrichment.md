# Proposal Execution Panel Enrichment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the proposal execution panel with current price, score sub-components, income/safety grades, and real portfolio context so a buy decision can be made without leaving the page.

**Architecture:** The proposal-service `GET /proposals` endpoint adds a single batch DB lookup (`_enrich_proposals`) that LEFT JOINs `market_data_cache` and the latest `income_scores` row for each returned ticker, appending enrichment fields to `ProposalResponse`. The frontend adds these fields to its TypeScript types, rebuilds the `ExecutionPanel` analysis block with two labeled sections (STOCK and PORTFOLIO), and fixes the portfolio impact bar to use real `annual_income` and `total_value` instead of hardcoded zeros.

**Tech Stack:** Python / FastAPI / SQLAlchemy (proposal-service), TypeScript / Next.js / Tailwind (frontend), PostgreSQL (`platform_shared` schema).

---

## File Map

| File | Action |
|---|---|
| `src/proposal-service/app/api/proposals.py` | Add `_enrich_proposals` helper + extend `ProposalResponse` + update list endpoint |
| `src/proposal-service/tests/test_proposal_enrichment.py` | New test file |
| `src/frontend/src/lib/types.ts` | Add fields to `Portfolio` and `ProposalWithPortfolio` |
| `src/frontend/src/components/proposals/execution-panel.tsx` | Rebuild analysis block + fix impact calc |

---

## Task 1: proposal-service — enrichment helper + extended response

**Files:**
- Modify: `src/proposal-service/app/api/proposals.py` (lines 81–160, 207+)
- Create: `src/proposal-service/tests/test_proposal_enrichment.py`

### Background

`ProposalResponse` (line 81) is a Pydantic model. `_proposal_to_response` (line 124) maps an ORM `Proposal` to it. The `list_proposals` endpoint (search for `@router.get("")` or similar) iterates proposals and calls `_proposal_to_response`. We need to:
1. Add new optional fields to `ProposalResponse`.
2. Add a `_enrich_proposals(db, tickers)` helper that does ONE query.
3. Update `_proposal_to_response(p, enrichment=None)` to accept and map enrichment data.
4. Update `list_proposals` to call `_enrich_proposals` once and pass results in.

**Zone status logic (pure Python, no DB):**
```python
def _compute_zone(current_price, entry_low, entry_high):
    if current_price is None or entry_low is None:
        return "UNKNOWN", None
    pct = (current_price - entry_low) / entry_low
    if current_price < entry_low:
        status = "BELOW_ENTRY"
    elif current_price <= (entry_high or entry_low):
        status = "IN_ZONE"
    else:
        status = "ABOVE_ENTRY"
    return status, round(pct, 4)
```

- [ ] **Step 1: Write failing tests**

Create `src/proposal-service/tests/test_proposal_enrichment.py`:

```python
"""Tests for proposal enrichment: zone_status computation and field mapping."""
import pytest
from unittest.mock import MagicMock, patch

# ── Zone status pure function ─────────────────────────────────────────────────

def test_zone_below_entry():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(40.0, 44.0, 47.0)
    assert status == "BELOW_ENTRY"
    assert pct < 0

def test_zone_in_zone():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(45.5, 44.0, 47.0)
    assert status == "IN_ZONE"
    assert pct > 0

def test_zone_above_entry():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(50.0, 44.0, 47.0)
    assert status == "ABOVE_ENTRY"

def test_zone_unknown_when_no_price():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(None, 44.0, 47.0)
    assert status == "UNKNOWN"
    assert pct is None

def test_zone_unknown_when_no_entry():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(45.0, None, None)
    assert status == "UNKNOWN"

# ── Enrichment field mapping in _proposal_to_response ─────────────────────────

def test_proposal_to_response_with_enrichment():
    """_proposal_to_response maps enrichment dict fields onto ProposalResponse."""
    from app.api.proposals import _proposal_to_response
    from app.models import Proposal
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    p = Proposal(
        id=1, ticker="MAIN", status="pending",
        entry_price_low=44.0, entry_price_high=47.0,
        platform_score=72.0, analyst_recommendation="BUY",
        analyst_yield_estimate=0.071, platform_yield_estimate=0.068,
        platform_income_grade="A-", analyst_safety_grade="B+",
        created_at=now, updated_at=now,
    )
    enrichment = {
        "current_price": 45.5,
        "week52_high": 52.0,
        "week52_low": 38.0,
        "nav_value": None,
        "nav_discount_pct": None,
        "valuation_yield_score": 80.0,
        "financial_durability_score": 71.0,
        "technical_entry_score": 58.0,
    }
    resp = _proposal_to_response(p, enrichment=enrichment)
    assert resp.current_price == 45.5
    assert resp.zone_status == "IN_ZONE"
    assert resp.valuation_yield_score == 80.0
    assert resp.financial_durability_score == 71.0
    assert resp.week52_high == 52.0

def test_proposal_to_response_without_enrichment():
    """When enrichment is None, market fields default to None, zone_status to UNKNOWN."""
    from app.api.proposals import _proposal_to_response
    from app.models import Proposal
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    p = Proposal(id=2, ticker="TEST", status="pending", created_at=now, updated_at=now)
    resp = _proposal_to_response(p, enrichment=None)
    assert resp.current_price is None
    assert resp.zone_status == "UNKNOWN"
    assert resp.valuation_yield_score is None

def test_enrich_proposals_called_once_for_batch(test_client, db_session):
    """_enrich_proposals is called exactly once regardless of how many proposals are returned."""
    from unittest.mock import patch
    # Seed two proposals
    from app.models import Proposal
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for ticker in ["MAIN", "ARCC"]:
        db_session.add(Proposal(ticker=ticker, status="pending", created_at=now, updated_at=now))
    db_session.commit()

    with patch("app.api.proposals._enrich_proposals", return_value={}) as mock_enrich:
        resp = test_client.get("/proposals?status=pending", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert mock_enrich.call_count == 1
        # Both tickers passed in single call
        called_tickers = set(mock_enrich.call_args[0][1])
        assert "MAIN" in called_tickers
        assert "ARCC" in called_tickers
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/proposal-service && python -m pytest tests/test_proposal_enrichment.py -v
```

Expected: ImportError or AttributeError — `_compute_zone` and new fields don't exist yet.

- [ ] **Step 3: Add `_compute_zone` and new fields to `proposals.py`**

**3a. Add `_compute_zone` helper** after the existing imports block (before `class GenerateRequest`):

```python
def _compute_zone(
    current_price: Optional[float],
    entry_low: Optional[float],
    entry_high: Optional[float],
) -> tuple[str, Optional[float]]:
    """Classify current price relative to the proposal entry range."""
    if current_price is None or entry_low is None:
        return "UNKNOWN", None
    pct = (current_price - entry_low) / entry_low
    if current_price < entry_low:
        status = "BELOW_ENTRY"
    elif current_price <= (entry_high or entry_low):
        status = "IN_ZONE"
    else:
        status = "ABOVE_ENTRY"
    return status, round(pct, 4)
```

**3b. Add new optional fields to `ProposalResponse`** (after `entry_method` field, before `class Config`):

```python
# Market enrichment (from market_data_cache + income_scores)
current_price: Optional[float] = None
zone_status: Optional[str] = None
pct_from_entry: Optional[float] = None
valuation_yield_score: Optional[float] = None
financial_durability_score: Optional[float] = None
technical_entry_score: Optional[float] = None
week52_high: Optional[float] = None
week52_low: Optional[float] = None
nav_value: Optional[float] = None
nav_discount_pct: Optional[float] = None
```

**3c. Add `_enrich_proposals` helper** after `_compute_zone`:

```python
def _enrich_proposals(db: Session, tickers: list[str]) -> dict[str, dict]:
    """
    Batch-fetch market price and latest score sub-components for a list of tickers.
    Returns dict keyed by ticker. Missing tickers get no entry (caller treats as None).
    Uses LEFT JOIN so missing market data or scores return NULL rows gracefully.
    """
    if not tickers:
        return {}
    placeholders = ", ".join(f":t{i}" for i in range(len(tickers)))
    params = {f"t{i}": t for i, t in enumerate(tickers)}
    rows = db.execute(text(f"""
        SELECT
            m.symbol AS ticker,
            m.price            AS current_price,
            m.week52_high,
            m.week52_low,
            m.nav_value,
            m.nav_discount_pct,
            s.valuation_yield_score,
            s.financial_durability_score,
            s.technical_entry_score
        FROM platform_shared.market_data_cache m
        LEFT JOIN LATERAL (
            SELECT valuation_yield_score, financial_durability_score, technical_entry_score
            FROM platform_shared.income_scores
            WHERE ticker = m.symbol
            ORDER BY scored_at DESC
            LIMIT 1
        ) s ON true
        WHERE m.symbol IN ({placeholders})
    """), params).mappings().all()
    return {row["ticker"]: dict(row) for row in rows}
```

**3d. Update `_proposal_to_response` signature** to accept `enrichment`:

Change: `def _proposal_to_response(p: Proposal) -> ProposalResponse:`
To:     `def _proposal_to_response(p: Proposal, enrichment: Optional[dict] = None) -> ProposalResponse:`

Inside the function, before the `return ProposalResponse(...)` call, add:

```python
enc = enrichment or {}
current_price = enc.get("current_price")
zone_status, pct_from_entry = _compute_zone(
    current_price,
    float(p.entry_price_low) if p.entry_price_low is not None else None,
    float(p.entry_price_high) if p.entry_price_high is not None else None,
)
```

Then add these fields to the `ProposalResponse(...)` constructor call (after `entry_method=...`):

```python
current_price=current_price,
zone_status=zone_status,
pct_from_entry=pct_from_entry,
valuation_yield_score=enc.get("valuation_yield_score"),
financial_durability_score=enc.get("financial_durability_score"),
technical_entry_score=enc.get("technical_entry_score"),
week52_high=enc.get("week52_high"),
week52_low=enc.get("week52_low"),
nav_value=enc.get("nav_value"),
nav_discount_pct=enc.get("nav_discount_pct"),
```

**3e. Update `list_proposals` endpoint** — find the endpoint that lists proposals (look for `@router.get("")` or `@router.get("/")`) and add enrichment call.

Find the line where proposals are fetched and responses are built (something like `return [_proposal_to_response(p) for p in proposals]`). Change it to:

```python
enrichments = _enrich_proposals(db, [p.ticker for p in proposals])
return [_proposal_to_response(p, enrichment=enrichments.get(p.ticker)) for p in proposals]
```

Also update the single-proposal `GET /proposals/{id}` endpoint (find it by `@router.get("/{proposal_id}")`):
```python
enc = _enrich_proposals(db, [proposal.ticker])
return _proposal_to_response(proposal, enrichment=enc.get(proposal.ticker))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/proposal-service && python -m pytest tests/test_proposal_enrichment.py -v
```

Expected: 8 tests PASS (5 zone + 2 response mapping + 1 batch call count).

- [ ] **Step 5: Run full proposal-service test suite**

```bash
cd src/proposal-service && python -m pytest tests/ -v --ignore=tests/test_agent_02_failure.py 2>&1 | tail -20
```

Expected: All previously-passing tests still pass (113 passed or similar). No regressions.

- [ ] **Step 6: Commit**

```bash
git add src/proposal-service/app/api/proposals.py \
        src/proposal-service/tests/test_proposal_enrichment.py
git commit -m "feat(proposals): enrich response with market price, zone status, and score sub-components"
```

---

## Task 2: Frontend types

**Files:**
- Modify: `src/frontend/src/lib/types.ts`

### Background

`Portfolio` (line 1) is used by `portfolio-context.tsx` which fetches from `/api/portfolios`. The broker-service already returns `annual_income` and `blended_yield` in that response but they are silently discarded because the TypeScript type doesn't declare them.

`ProposalWithPortfolio` (line 425) is the frontend model for a proposal. It needs all the new enrichment fields.

- [ ] **Step 1: Write failing type-check** (no separate test file needed — TypeScript compilation is the test)

Add a comment at the top of `src/frontend/src/lib/types.ts` temporarily:
```typescript
// TODO-ENRICHMENT: Portfolio needs annual_income; ProposalWithPortfolio needs market fields
```
Then confirm TypeScript currently compiles: `cd src/frontend && npx tsc --noEmit`. Expected: 0 errors (baseline).

- [ ] **Step 2: Add fields to `Portfolio` type**

In `src/frontend/src/lib/types.ts`, find the `Portfolio` interface (line 1). After `last_refreshed_at?: string | null;` add:

```typescript
// Aggregate KPIs (returned by /api/portfolios, computed server-side)
annual_income?: number | null;
blended_yield?: number | null;
```

- [ ] **Step 3: Add enrichment fields to `ProposalWithPortfolio`**

Find `ProposalWithPortfolio` (around line 425). After `status: string;` add:

```typescript
// Market enrichment (from proposal-service DB joins)
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

- [ ] **Step 4: Remove the TODO comment, verify TypeScript compiles**

```bash
cd src/frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/lib/types.ts
git commit -m "feat(types): add annual_income/blended_yield to Portfolio; add market enrichment fields to ProposalWithPortfolio"
```

---

## Task 3: ExecutionPanel — rebuild analysis block + fix impact

**Files:**
- Modify: `src/frontend/src/components/proposals/execution-panel.tsx`

### Background

The current analysis block (lines 132–165) shows 3 cells (Score, Rec, Entry Range) plus thesis and alignment warning. We rebuild this into two labeled sections: **STOCK** and **PORTFOLIO**, using the same inline data-grid style (label + value pairs, 3 columns). The order form and footer are unchanged.

The impact calculation (line 79–88) hardcodes `currentAnnualIncome: 0` and `currentPortfolioValue: null`. These should use `portfolio.annual_income` and `portfolio.total_value`.

### Zone badge helper

```typescript
function ZoneBadge({ status }: { status: string | null | undefined }) {
  const config: Record<string, { label: string; cls: string }> = {
    IN_ZONE:     { label: "✓ In Zone",     cls: "bg-emerald-950/40 text-emerald-400 border-emerald-800/40" },
    BELOW_ENTRY: { label: "↓ Below Entry", cls: "bg-blue-950/40 text-blue-400 border-blue-800/40" },
    ABOVE_ENTRY: { label: "↑ Above Entry", cls: "bg-amber-950/40 text-amber-400 border-amber-800/40" },
    UNKNOWN:     { label: "Unknown",       cls: "bg-muted/20 text-muted-foreground border-border" },
  };
  const c = config[status ?? "UNKNOWN"] ?? config["UNKNOWN"];
  return (
    <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded border", c.cls)}>
      {c.label}
    </span>
  );
}
```

### New STOCK section (replaces old 3-cell grid + thesis paragraph)

```tsx
{/* STOCK section */}
<div>
  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-2">
    Stock · {activeProposal.ticker}
  </p>
  <div className="grid grid-cols-3 gap-2 mb-2">
    <DataCell label="Current Price"
      value={activeProposal.current_price != null ? `$${activeProposal.current_price.toFixed(2)}` : "—"} />
    <DataCell label="Entry Range"
      value={activeProposal.entry_price_low != null
        ? `$${activeProposal.entry_price_low.toFixed(2)}–$${(activeProposal.entry_price_high ?? activeProposal.entry_price_low).toFixed(2)}`
        : "—"} />
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Zone</p>
      <div className="mt-1">
        <ZoneBadge status={activeProposal.zone_status} />
      </div>
    </div>
  </div>
  <div className="grid grid-cols-3 gap-2 mb-2">
    <DataCell label="Score" value={activeProposal.platform_score?.toFixed(0) ?? "—"} />
    <DataCell label="Income Grade"
      value={activeProposal.platform_income_grade ?? "—"}
      valueClass={activeProposal.platform_income_grade?.startsWith("A") ? "text-emerald-400" : undefined} />
    <DataCell label="Safety Grade"
      value={activeProposal.analyst_safety_grade ?? "—"}
      valueClass={activeProposal.analyst_safety_grade?.startsWith("A") || activeProposal.analyst_safety_grade?.startsWith("B") ? "text-emerald-400" : undefined} />
  </div>
  <div className="grid grid-cols-3 gap-2 mb-2">
    <DataCell label="Platform Yield"
      value={activeProposal.platform_yield_estimate != null ? `${(activeProposal.platform_yield_estimate * 100).toFixed(1)}%` : "—"} />
    <DataCell label="Analyst Yield"
      value={activeProposal.analyst_yield_estimate != null ? `${(activeProposal.analyst_yield_estimate * 100).toFixed(1)}%` : "—"} />
    <DataCell label="Analyst Rec"
      value={activeProposal.analyst_recommendation ?? "—"}
      valueClass={activeProposal.analyst_recommendation?.includes("BUY") ? "text-emerald-400" : undefined} />
  </div>
  {/* Score sub-components */}
  {(activeProposal.valuation_yield_score != null ||
    activeProposal.financial_durability_score != null ||
    activeProposal.technical_entry_score != null) && (
    <div className="grid grid-cols-3 gap-2 mb-2">
      <DataCell label="Valuation/Yield" value={activeProposal.valuation_yield_score?.toFixed(0) ?? "—"} small />
      <DataCell label="Durability" value={activeProposal.financial_durability_score?.toFixed(0) ?? "—"} small />
      <DataCell label="Technicals" value={activeProposal.technical_entry_score?.toFixed(0) ?? "—"} small />
    </div>
  )}
  {/* NAV discount for CEFs */}
  {activeProposal.nav_discount_pct != null && (
    <div className="grid grid-cols-3 gap-2 mb-2">
      <DataCell label="NAV" value={activeProposal.nav_value != null ? `$${activeProposal.nav_value.toFixed(2)}` : "—"} />
      <DataCell label="NAV Discount"
        value={`${(activeProposal.nav_discount_pct * 100).toFixed(1)}%`}
        valueClass={activeProposal.nav_discount_pct < 0 ? "text-emerald-400" : "text-amber-400"} />
      <div /> {/* spacer */}
    </div>
  )}
  {activeProposal.analyst_thesis_summary && (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2 mb-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">Thesis</p>
      <p className="text-xs text-muted-foreground leading-relaxed">{activeProposal.analyst_thesis_summary}</p>
    </div>
  )}
  {activeProposal.sizing_rationale && (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2 mb-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">Sizing Rationale</p>
      <p className="text-xs text-muted-foreground leading-relaxed">{activeProposal.sizing_rationale}</p>
    </div>
  )}
  {activeProposal.recommended_account && (
    <p className="text-xs text-muted-foreground">
      Suggested account: <span className="text-foreground font-medium">{activeProposal.recommended_account}</span>
    </p>
  )}
</div>
```

### New PORTFOLIO section (after alignment warning, before order form)

```tsx
{/* PORTFOLIO section */}
<div>
  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-2">
    Portfolio · {portfolio.name}
  </p>
  <div className="grid grid-cols-3 gap-2 mb-2">
    <DataCell label="Cash"
      value={portfolio.cash_balance != null ? `$${portfolio.cash_balance.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"}
      valueClass="text-emerald-400" />
    <DataCell label="Total Value"
      value={portfolio.total_value != null ? `$${portfolio.total_value.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"} />
    <DataCell label="Annual Income"
      value={portfolio.annual_income != null ? `$${portfolio.annual_income.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"} />
  </div>
  <div className="grid grid-cols-3 gap-2">
    <DataCell label="Blended Yield"
      value={portfolio.blended_yield != null ? `${(portfolio.blended_yield * 100).toFixed(2)}%` : "—"} />
    <DataCell label="Target Yield"
      value={portfolio.target_yield != null ? `${(portfolio.target_yield * 100).toFixed(2)}%` : "—"} />
    <DataCell label="Income Target"
      value={portfolio.monthly_income_target != null ? `$${portfolio.monthly_income_target.toLocaleString("en-US", { maximumFractionDigits: 0 })}/mo` : "—"} />
  </div>
</div>
```

### `DataCell` helper (replace `AnalysisCell` at bottom of file)

```typescript
function DataCell({
  label, value, valueClass, small,
}: {
  label: string; value: string; valueClass?: string; small?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={cn(small ? "text-xs" : "text-sm", "font-semibold mt-0.5", valueClass)}>{value}</p>
    </div>
  );
}
```

- [ ] **Step 1: Fix the impact calculation first** (smallest change, easiest to verify)

In `src/frontend/src/components/proposals/execution-panel.tsx`, find lines 85–87:
```typescript
    currentAnnualIncome: 0,
    currentPortfolioValue: null,
```

Change to:
```typescript
    currentAnnualIncome: portfolio.annual_income ?? 0,
    currentPortfolioValue: portfolio.total_value ?? null,
```

- [ ] **Step 2: Verify TypeScript compiles after impact fix**

```bash
cd src/frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Replace `AnalysisCell` with `DataCell` + add `ZoneBadge`**

At the bottom of `execution-panel.tsx`, replace the `AnalysisCell` function:

```typescript
function AnalysisCell({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={cn("text-sm font-semibold mt-0.5", valueClass)}>{value}</p>
    </div>
  );
}
```

With `DataCell` and `ZoneBadge` as shown in the Background section above.

- [ ] **Step 4: Replace analysis block JSX**

In the `{activeProposal && activeParams && ( ... )}` section, replace everything from the `{/* Analysis block */}` comment down to (but NOT including) the `{/* Execution form */}` div with:
1. The new STOCK section JSX
2. The existing alignment warning block (keep unchanged)
3. The new PORTFOLIO section JSX

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd src/frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/components/proposals/execution-panel.tsx
git commit -m "feat(proposals): rebuild execution panel with stock/portfolio context sections"
```

---

## Deployment

After all tasks complete, deploy to production:

```bash
# 1. Push to GitHub
git push origin main

# 2. On legato server
ssh root@138.197.78.238 "cd /opt/Agentic && git pull && cd income-platform && docker compose build --no-cache agent-12-proposal frontend && docker compose up -d agent-12-proposal frontend"
```

No DB migration needed — all new data comes from existing tables via JOINs.
