# Proposal Execution Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the read-only proposals page into a two-phase execution workflow: set order parameters → submit to broker → track fill status → sync confirmed positions to portfolio.

**Architecture:** Bottom-up: DB migration first, then backend endpoints (proposal-service + broker-service), then frontend components (bottom-up: impact bar → order card → panels → page). Each task is independently testable. The frontend polls broker-service every 10 seconds for fill updates and calls a new `sync-fill` endpoint on confirmed fills to write positions server-side with atomic weighted-average cost basis.

**Tech Stack:** Python/FastAPI (proposal-service, broker-service), SQLAlchemy, PostgreSQL, Next.js 14 App Router, React, TypeScript, Tailwind CSS, shadcn/ui

**Spec:** `docs/superpowers/specs/2026-03-30-proposal-execution-workflow-design.md`

---

## File Map

### New files
- `src/proposal-service/migrations/add_portfolio_id_to_proposals.sql` — DB migration
- `src/proposal-service/tests/test_fill_confirmed.py` — tests for fill-confirmed endpoint
- `src/broker-service/tests/test_sync_fill.py` — tests for sync-fill endpoint
- `src/frontend/src/app/api/proposals/[id]/fill-confirmed/route.ts` — Next.js proxy for fill-confirmed
- `src/frontend/src/components/proposals/portfolio-impact-bar.tsx` — inline impact calculation display
- `src/frontend/src/components/proposals/order-card.tsx` — single order status card (all variants)
- `src/frontend/src/components/proposals/execution-panel.tsx` — Phase 1 right pane
- `src/frontend/src/components/proposals/order-status-panel.tsx` — Phase 2 right pane

### Modified files
- `src/proposal-service/app/models.py` — add `portfolio_id` column
- `src/proposal-service/app/api/proposals.py` — persist `portfolio_id`; add `fill-confirmed` endpoint
- `src/proposal-service/tests/conftest.py` — add `portfolio_id` to test model
- `src/broker-service/app/api/broker.py` — add `POST /broker/positions/sync-fill` endpoint
- `src/frontend/src/app/proposals/page.tsx` — full redesign: two-phase view

### Existing proxy (already works, no changes)

- `src/frontend/src/app/broker/[...path]/route.ts` — proxies all methods to broker-service at URL path `/broker/*`. Frontend calls use `/broker/orders` (not `/api/broker/orders`).

---

## Task 1: DB Migration — add portfolio_id to proposals

**Files:**
- Create: `src/proposal-service/migrations/add_portfolio_id_to_proposals.sql`

Context: The `platform_shared.proposals` table has no `portfolio_id` column. This migration adds it as nullable UUID so existing rows are unaffected. Run manually against the DB server (legato: 138.197.78.238) or as part of the service startup.

- [ ] **Step 1: Write the migration file**

```sql
-- src/proposal-service/migrations/add_portfolio_id_to_proposals.sql
-- Add portfolio_id to proposals table for grouping in execution UI
ALTER TABLE platform_shared.proposals
    ADD COLUMN IF NOT EXISTS portfolio_id UUID NULL;

COMMENT ON COLUMN platform_shared.proposals.portfolio_id
    IS 'Target portfolio for this proposal — set at generation time';
```

- [ ] **Step 2: Verify the file is valid SQL** (no runtime step — just review the file)

- [ ] **Step 3: Commit**

```bash
git add src/proposal-service/migrations/add_portfolio_id_to_proposals.sql
git commit -m "feat(db): add portfolio_id column to platform_shared.proposals"
```

---

## Task 2: proposal-service — portfolio_id column in model and API

**Files:**
- Modify: `src/proposal-service/app/models.py`
- Modify: `src/proposal-service/app/api/proposals.py`
- Modify: `src/proposal-service/tests/conftest.py`

Context: `models.py` currently has no `portfolio_id` column. `proposals.py` accepts `portfolio_id` in `GenerateRequest` but never persists it. `_persist_proposal` must write it. `ProposalResponse` must expose it. The test conftest has a SQLite mirror of the Proposal model that needs updating too.

- [ ] **Step 1: Write the failing test**

In `src/proposal-service/tests/test_api.py`, add to the existing test file after the existing tests:

```python
def test_generate_proposal_persists_portfolio_id(client, auth_headers, monkeypatch):
    """portfolio_id passed to /generate is stored on the proposal row."""
    from unittest.mock import AsyncMock, patch
    from tests.conftest import make_signal, make_score, make_entry_price, make_tax_placement

    with patch("app.proposal_engine.data_fetcher.fetch_all", new=AsyncMock(
        return_value=(make_signal(), make_score(), make_entry_price(), make_tax_placement())
    )):
        resp = client.post(
            "/proposals/generate",
            json={"ticker": "O", "portfolio_id": "a1b2c3d4-0000-0000-0000-000000000001"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["portfolio_id"] == "a1b2c3d4-0000-0000-0000-000000000001"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src/proposal-service && python -m pytest tests/test_api.py::test_generate_proposal_persists_portfolio_id -v
```

Expected: `FAIL` — `KeyError: 'portfolio_id'` or assertion error (field not in response)

- [ ] **Step 3: Add portfolio_id to the ORM model**

In `src/proposal-service/app/models.py`, after line 46 (`trigger_ref_id = Column(Text, nullable=True)`):

```python
    portfolio_id = Column(Text, nullable=True)   # UUID stored as text for SQLite compat
```

- [ ] **Step 4: Add portfolio_id to test conftest model**

In `src/proposal-service/tests/conftest.py`, the `Proposal` class (line 51) mirrors the real model. After the `trigger_ref_id` line (~line 79):

```python
    portfolio_id = Column(Text, nullable=True)
```

Also drop and recreate the table so the new column exists:

```python
# At the bottom of the TestBase.metadata.create_all call (line 98), it's already there.
# BUT the table was already created without portfolio_id. Add this after line 98:
TestBase.metadata.drop_all(bind=test_engine)
TestBase.metadata.create_all(bind=test_engine)
```

- [ ] **Step 5: Update _persist_proposal to write portfolio_id**

In `src/proposal-service/app/api/proposals.py`, `_persist_proposal` function (line 145). The `ProposalResult` dataclass in `engine.py` does not have `portfolio_id` — pass it directly to `_persist_proposal` as an argument.

Change the function signature:

```python
def _persist_proposal(db: Session, result: ProposalResult, portfolio_id: Optional[str] = None) -> Proposal:
    """Write a ProposalResult to the DB and return the ORM object."""
    now = datetime.now(timezone.utc)
    proposal = Proposal(
        ticker=result.ticker,
        analyst_signal_id=result.analyst_signal_id,
        analyst_id=result.analyst_id,
        platform_score=result.platform_score,
        platform_alignment=result.platform_alignment,
        veto_flags=result.veto_flags,
        divergence_notes=result.divergence_notes,
        analyst_recommendation=result.analyst_recommendation,
        analyst_sentiment=result.analyst_sentiment,
        analyst_thesis_summary=result.analyst_thesis_summary,
        analyst_yield_estimate=result.analyst_yield_estimate,
        analyst_safety_grade=result.analyst_safety_grade,
        platform_yield_estimate=result.platform_yield_estimate,
        platform_safety_result=result.platform_safety_result,
        platform_income_grade=result.platform_income_grade,
        entry_price_low=result.entry_price_low,
        entry_price_high=result.entry_price_high,
        position_size_pct=result.position_size_pct,
        recommended_account=result.recommended_account,
        sizing_rationale=result.sizing_rationale,
        status=result.status,
        trigger_mode=result.trigger_mode,
        trigger_ref_id=result.trigger_ref_id,
        expires_at=result.expires_at,
        portfolio_id=portfolio_id,   # NEW
        created_at=now,
        updated_at=now,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal
```

In `generate_proposal` endpoint, update the call to `_persist_proposal`:

```python
proposal = _persist_proposal(db, result, portfolio_id=body.portfolio_id)
```

- [ ] **Step 5b: Also update re_evaluate_proposal to preserve portfolio_id**

In `re_evaluate_proposal` endpoint (~line 417), find the `_persist_proposal(db, result)` call and update it to:

```python
new_proposal = _persist_proposal(db, result, portfolio_id=old.portfolio_id)
```

This preserves the original proposal's `portfolio_id` on re-evaluated proposals.

- [ ] **Step 6: Add portfolio_id to ProposalResponse**

In `ProposalResponse` class (line 66), add after `updated_at`:

```python
    portfolio_id: Optional[str] = None
```

In `_proposal_to_response` (line 108), add after `updated_at=...`:

```python
        portfolio_id=p.portfolio_id,
```

- [ ] **Step 7: Run the test to verify it passes**

```bash
cd src/proposal-service && python -m pytest tests/test_api.py::test_generate_proposal_persists_portfolio_id -v
```

Expected: `PASS`

- [ ] **Step 8: Run full test suite to check no regressions**

```bash
cd src/proposal-service && python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 9: Commit**

```bash
git add src/proposal-service/app/models.py \
        src/proposal-service/app/api/proposals.py \
        src/proposal-service/tests/conftest.py \
        src/proposal-service/tests/test_api.py
git commit -m "feat(proposals): persist and expose portfolio_id on proposals"
```

---

## Task 3: proposal-service — fill-confirmed endpoint

**Files:**
- Modify: `src/proposal-service/app/api/proposals.py`
- Create: `src/proposal-service/tests/test_fill_confirmed.py`

Context: After a broker order fills, the frontend calls `POST /proposals/{id}/fill-confirmed` to transition the proposal status. Valid transitions: `executed_aligned → executed_filled`, `executed_aligned → partially_filled`, `executed_aligned → cancelled`. The endpoint returns the updated proposal.

- [ ] **Step 1: Write the failing tests**

Create `src/proposal-service/tests/test_fill_confirmed.py`:

```python
"""Tests for POST /proposals/{id}/fill-confirmed endpoint."""
import pytest
from datetime import datetime, timezone
from tests.conftest import Proposal, TestingSessionLocal


def _create_proposal(status: str = "executed_aligned") -> int:
    db = TestingSessionLocal()
    try:
        p = Proposal(
            ticker="RVT",
            status=status,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p.id
    finally:
        db.close()


def test_fill_confirmed_transitions_to_executed_filled(client, auth_headers):
    pid = _create_proposal("executed_aligned")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={
            "filled_qty": 20.0,
            "avg_fill_price": 18.42,
            "filled_at": "2026-03-30T10:00:00Z",
            "status": "filled",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "executed_filled"


def test_fill_confirmed_partial_fill(client, auth_headers):
    pid = _create_proposal("executed_aligned")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={
            "filled_qty": 14.0,
            "avg_fill_price": 18.42,
            "filled_at": "2026-03-30T10:00:00Z",
            "status": "partially_filled",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "partially_filled"


def test_fill_confirmed_cancelled(client, auth_headers):
    pid = _create_proposal("executed_aligned")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={
            "filled_qty": 0.0,
            "avg_fill_price": 0.0,
            "filled_at": "2026-03-30T10:00:00Z",
            "status": "cancelled",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_fill_confirmed_rejects_invalid_status(client, auth_headers):
    pid = _create_proposal("executed_aligned")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={
            "filled_qty": 5.0,
            "avg_fill_price": 18.0,
            "filled_at": "2026-03-30T10:00:00Z",
            "status": "blah",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_fill_confirmed_404_on_missing(client, auth_headers):
    resp = client.post(
        "/proposals/9999/fill-confirmed",
        json={"filled_qty": 1.0, "avg_fill_price": 10.0,
              "filled_at": "2026-03-30T10:00:00Z", "status": "filled"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_fill_confirmed_rejects_pending_proposal(client, auth_headers):
    pid = _create_proposal("pending")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={"filled_qty": 1.0, "avg_fill_price": 10.0,
              "filled_at": "2026-03-30T10:00:00Z", "status": "filled"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/proposal-service && python -m pytest tests/test_fill_confirmed.py -v
```

Expected: `FAIL` — 404 on the endpoint (not found)

- [ ] **Step 3: Add FillConfirmedRequest and the endpoint**

In `src/proposal-service/app/api/proposals.py`, after the `RejectRequest` class (around line 63), add:

```python
class FillConfirmedRequest(BaseModel):
    filled_qty: float
    avg_fill_price: float
    filled_at: str          # ISO datetime string from broker
    status: str             # filled | partially_filled | cancelled

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"filled", "partially_filled", "cancelled"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v
```

At the end of the file, add the new endpoint:

```python
@router.post("/{proposal_id}/fill-confirmed")
def fill_confirmed(
    proposal_id: int,
    body: FillConfirmedRequest,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
) -> ProposalResponse:
    """Mark a proposal as fill-confirmed after broker order completes.

    Transitions:
      executed_aligned → executed_filled    (body.status == "filled")
      executed_aligned → partially_filled   (body.status == "partially_filled")
      executed_aligned → cancelled          (body.status == "cancelled")
    """
    proposal = _get_proposal_or_404(db, proposal_id)

    if proposal.status not in ("executed_aligned", "partially_filled"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot confirm fill on proposal with status '{proposal.status}'",
        )

    status_map = {
        "filled": "executed_filled",
        "partially_filled": "partially_filled",
        "cancelled": "cancelled",
    }

    now = datetime.now(timezone.utc)
    proposal.status = status_map[body.status]
    proposal.decided_at = now
    proposal.updated_at = now
    db.commit()
    db.refresh(proposal)
    return _proposal_to_response(proposal)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/proposal-service && python -m pytest tests/test_fill_confirmed.py -v
```

Expected: all 5 tests `PASS`

- [ ] **Step 5: Run full test suite**

```bash
cd src/proposal-service && python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add src/proposal-service/app/api/proposals.py \
        src/proposal-service/tests/test_fill_confirmed.py
git commit -m "feat(proposals): add fill-confirmed endpoint for broker order lifecycle"
```

---

## Task 4: broker-service — sync-fill endpoint

**Files:**
- Modify: `src/broker-service/app/api/broker.py`
- Create: `src/broker-service/tests/test_sync_fill.py`

Context: After a broker fill, the frontend calls `POST /broker/positions/sync-fill` to upsert the position. If a position row already exists for `(portfolio_id, ticker)` the endpoint reads it, computes weighted-average cost basis, and writes back. All in one DB transaction. The `platform_shared.positions` table uses an upsert on `(portfolio_id, symbol)` — check the existing upsert SQL pattern in broker.py lines ~200-247 for the column names.

- [ ] **Step 1: Check the existing positions upsert column names**

Read `src/broker-service/app/api/broker.py` lines 200–250 to confirm column names in `platform_shared.positions`. Specifically check for: `symbol`, `portfolio_id`, `quantity` (or `shares`), `cost_basis` (or `average_cost`), `acquisition_date`, `last_add_date`.

```bash
cd src/broker-service && grep -n "positions\|acquisition\|cost_basis\|quantity\|average_cost" app/api/broker.py | head -30
```

Note the exact column names from the output before proceeding.

- [ ] **Step 2: Write the failing test**

Create `src/broker-service/tests/test_sync_fill.py`. The broker-service tests do not have a full conftest like proposal-service — use a simple approach with a mock DB session:

```python
"""Tests for POST /broker/positions/sync-fill endpoint."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def app_client():
    import os
    os.environ.setdefault("ALPACA_API_KEY", "test")
    os.environ.setdefault("ALPACA_SECRET_KEY", "test")
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    os.environ.setdefault("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    from sqlalchemy import create_engine, Column, String, Float, text as sa_text
    from sqlalchemy.orm import DeclarativeBase, sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    class Base(DeclarativeBase):
        pass

    # Create a minimal positions table for SQLite
    engine.execute = lambda *a, **kw: None  # noqa — will be overridden
    from sqlalchemy import event

    # Create positions table in SQLite
    with engine.connect() as conn:
        conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS positions (
                id TEXT PRIMARY KEY,
                portfolio_id TEXT,
                symbol TEXT,
                status TEXT DEFAULT 'ACTIVE',
                quantity REAL,
                avg_cost_basis REAL,
                total_cost_basis REAL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(portfolio_id, symbol, status)
            )
        """))
        conn.commit()

    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    from app.main import app
    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app), engine

    app.dependency_overrides.clear()


def test_sync_fill_new_position(app_client):
    """A brand-new position is created with the fill data."""
    client, engine = app_client
    resp = client.post("/broker/positions/sync-fill", json={
        "portfolio_id": "a1b2c3d4-0000-0000-0000-000000000001",
        "ticker": "RVT",
        "filled_qty": 20.0,
        "avg_fill_price": 18.42,
        "filled_at": "2026-03-30T10:00:00Z",
        "proposal_id": "42",
        "order_id": "abc123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "RVT"
    assert data["total_shares"] == 20.0
    assert abs(data["new_avg_cost"] - 18.42) < 0.01
    assert data["is_new_position"] is True


def test_sync_fill_weighted_average(app_client):
    """Existing position gets weighted-average cost basis update."""
    client, engine = app_client
    # Pre-insert existing 10 shares at $18.00
    from sqlalchemy import text as sa_text
    from uuid import uuid4
    with engine.connect() as conn:
        conn.execute(sa_text("""
            INSERT INTO positions (id, portfolio_id, symbol, status, quantity, avg_cost_basis, total_cost_basis, created_at, updated_at)
            VALUES (:id, :pid, 'RVT', 'ACTIVE', 10.0, 18.00, 180.0, datetime('now'), datetime('now'))
        """), {"id": str(uuid4()), "pid": "a1b2c3d4-0000-0000-0000-000000000002"})
        conn.commit()

    resp = client.post("/broker/positions/sync-fill", json={
        "portfolio_id": "a1b2c3d4-0000-0000-0000-000000000002",
        "ticker": "RVT",
        "filled_qty": 10.0,
        "avg_fill_price": 19.00,
        "filled_at": "2026-03-30T11:00:00Z",
    })
    assert resp.status_code == 200
    data = resp.json()
    # Weighted avg: (10 * 18.00 + 10 * 19.00) / 20 = 18.50
    assert abs(data["new_avg_cost"] - 18.50) < 0.01
    assert data["total_shares"] == 20.0
    assert data["is_new_position"] is False
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd src/broker-service && python -m pytest tests/test_sync_fill.py -v 2>&1 | head -30
```

Expected: `FAIL` — 404 or 405 (endpoint does not exist yet)

- [ ] **Step 4: Add SyncFillRequest model and endpoint to broker.py**

In `src/broker-service/app/api/broker.py`, after the `OrderPlaceRequest` class (~line 68), add:

```python
class SyncFillRequest(BaseModel):
    portfolio_id: str
    ticker: str
    filled_qty: float
    avg_fill_price: float
    filled_at: str           # ISO datetime — becomes acquisition_date for new positions
    proposal_id: Optional[str] = None
    order_id: Optional[str] = None
    broker_ref: Optional[str] = None
```

At the end of the file, add the endpoint:

```python
@router.post("/positions/sync-fill")
def sync_fill(req: SyncFillRequest, db: Session = Depends(get_db)):
    """Upsert a position after a confirmed broker fill.

    For new positions: inserts with req.filled_qty, req.avg_fill_price, acquisition_date=req.filled_at.
    For existing positions: adds shares and recomputes weighted-average cost basis atomically.
    """
    # Read existing position row for (portfolio_id, ticker, status='ACTIVE')
    existing = db.execute(text("""
        SELECT quantity, avg_cost_basis
        FROM platform_shared.positions
        WHERE portfolio_id = :pid AND symbol = :sym AND status = 'ACTIVE'
        LIMIT 1
    """), {"pid": req.portfolio_id, "sym": req.ticker.upper()}).fetchone()

    if existing and existing["quantity"]:
        old_qty = float(existing["quantity"])
        old_cost = float(existing["avg_cost_basis"] or 0)
        new_qty = old_qty + req.filled_qty
        new_avg_cost = (old_qty * old_cost + req.filled_qty * req.avg_fill_price) / new_qty
        is_new = False
    else:
        new_qty = req.filled_qty
        new_avg_cost = req.avg_fill_price
        is_new = True

    fill_date = req.filled_at[:10]  # YYYY-MM-DD

    db.execute(text("""
        INSERT INTO platform_shared.positions
            (id, portfolio_id, symbol, status, quantity, avg_cost_basis, total_cost_basis,
             created_at, updated_at)
        VALUES
            (:id, :pid, :sym, 'ACTIVE', :qty, :avg_cb, :total_cb, NOW(), NOW())
        ON CONFLICT (portfolio_id, symbol, status)
        DO UPDATE SET
            quantity         = :qty,
            avg_cost_basis   = :avg_cb,
            total_cost_basis = :total_cb,
            updated_at       = NOW()
    """), {
        "id": str(uuid4()),
        "pid": req.portfolio_id,
        "sym": req.ticker.upper(),
        "qty": new_qty,
        "avg_cb": round(new_avg_cost, 6),
        "total_cb": round(new_qty * new_avg_cost, 2),
    })
    db.commit()

    return {
        "portfolio_id": req.portfolio_id,
        "ticker": req.ticker.upper(),
        "filled_qty": req.filled_qty,
        "avg_fill_price": req.avg_fill_price,
        "total_shares": new_qty,
        "new_avg_cost": round(new_avg_cost, 4),
        "is_new_position": is_new,
    }
```

**Important:** Before writing the SQL, verify the exact column names by checking the grep output from Step 1. If the column is `average_cost` instead of `cost_basis`, or `shares` instead of `quantity`, adjust accordingly. The existing upsert at lines ~200-247 is the authoritative reference.

- [ ] **Step 5: Run the tests**

```bash
cd src/broker-service && python -m pytest tests/test_sync_fill.py -v
```

Expected: tests pass (the mock DB approach means the SQL doesn't actually run; tests verify routing and response shape)

- [ ] **Step 6: Run full broker-service tests**

```bash
cd src/broker-service && python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add src/broker-service/app/api/broker.py \
        src/broker-service/tests/test_sync_fill.py
git commit -m "feat(broker): add sync-fill endpoint for post-fill position upsert"
```

---

## Task 4.5: Frontend — fill-confirmed proxy route

**Files:**
- Create: `src/frontend/src/app/api/proposals/[id]/fill-confirmed/route.ts`

Context: The existing proposals API routes use individual per-action files (not catch-all). The `execute` and `reject` routes at `src/frontend/src/app/api/proposals/[id]/execute/route.ts` show the pattern — proxy to `ADMIN_PANEL` which routes to proposal-service. The fill-confirmed endpoint needs the same treatment.

- [ ] **Step 1: Read the existing execute route for the pattern**

```bash
cat src/frontend/src/app/api/proposals/[id]/execute/route.ts
```

Note: it proxies to `${ADMIN_PANEL}/api/proposals/${id}/execute` using `POST`.

- [ ] **Step 2: Create the fill-confirmed proxy**

```typescript
/**
 * POST /api/proposals/[id]/fill-confirmed — proxy to proposal-service via admin panel
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const body = await req.json().catch(() => ({}));
    const upstream = await fetch(
      `${ADMIN_PANEL}/api/proposals/${id}/fill-confirmed`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(15_000),
      }
    );
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | grep "fill-confirmed" | head -5
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/app/api/proposals/[id]/fill-confirmed/route.ts
git commit -m "feat(frontend): add fill-confirmed proxy route"
```

---

## Task 5: Frontend — shared types for execution workflow

**Files:**
- Modify: `src/frontend/src/lib/types.ts`

Context: The proposals page needs new TypeScript types for order state and execution parameters. Add them to the existing types file. Do not change existing types — only add.

- [ ] **Step 1: Read the current types file**

```bash
cat src/frontend/src/lib/types.ts
```

Note the existing exports to avoid conflicts.

- [ ] **Step 2: Add execution workflow types**

Append to `src/frontend/src/lib/types.ts`:

```typescript
// ── Proposal execution workflow types ────────────────────────────────────────

export interface ProposalWithPortfolio {
  id: number;
  ticker: string;
  portfolio_id: string | null;
  platform_score: number | null;
  platform_alignment: string | null;
  analyst_recommendation: string | null;
  analyst_yield_estimate: number | null;
  platform_yield_estimate: number | null;
  entry_price_low: number | null;
  entry_price_high: number | null;
  position_size_pct: number | null;
  recommended_account: string | null;
  analyst_thesis_summary: string | null;
  analyst_safety_grade: string | null;
  platform_income_grade: string | null;
  sizing_rationale: string | null;
  divergence_notes: string | null;
  veto_flags: Record<string, unknown> | null;
  status: string;
  created_at: string | null;
}

export type OrderType = "market" | "limit" | "stop_limit";
export type TimeInForce = "day" | "gtc" | "ioc";

export interface OrderParams {
  order_type: OrderType;
  limit_price: number | null;    // null for market orders
  shares: number | null;
  dollar_amount: number | null;  // linked to shares via limit_price
  time_in_force: TimeInForce;
}

export type BrokerOrderStatus =
  | "pending"
  | "partially_filled"
  | "filled"
  | "cancelled"
  | "paper";

export interface LiveOrder {
  proposal_id: number;
  ticker: string;
  portfolio_id: string;
  order_id: string;         // broker order ID
  broker: string;           // e.g. "alpaca" — round-tripped from placement response
  status: BrokerOrderStatus;
  qty: number;
  filled_qty: number;
  avg_fill_price: number | null;
  limit_price: number | null;
  filled_at: string | null;
  submitted_at: string | null;
}

export interface PaperOrder {
  proposal_id: number;
  ticker: string;
  portfolio_id: string;
  qty: number;
  order_type: OrderType;
  limit_price: number | null;
  time_in_force: TimeInForce;
  portfolio_name: string;
  executed: boolean;          // true after "Mark as Executed"
}

export interface PortfolioImpact {
  cash_required: number;
  added_annual_income: number;
  new_portfolio_yield: number | null;   // null if portfolio value unknown
  concentration_pct: number | null;     // per-ticker, null if portfolio value unknown
}
```

- [ ] **Step 3: Verify TypeScript compiles cleanly**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors (or only pre-existing errors unrelated to the new types)

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/lib/types.ts
git commit -m "feat(frontend): add execution workflow types for proposals"
```

---

## Task 6: Frontend — PortfolioImpactBar component

**Files:**
- Create: `src/frontend/src/components/proposals/portfolio-impact-bar.tsx`

Context: Displays 4 metrics computed from selected proposals and current portfolio cash balance. Pure display component — receives pre-computed numbers. No API calls.

- [ ] **Step 1: Create the component**

```tsx
// src/frontend/src/components/proposals/portfolio-impact-bar.tsx
"use client";

import { cn } from "@/lib/utils";
import type { PortfolioImpact } from "@/lib/types";

interface PortfolioImpactBarProps {
  impact: PortfolioImpact;
  cashBalance: number | null;
  className?: string;
}

export function PortfolioImpactBar({ impact, cashBalance, className }: PortfolioImpactBarProps) {
  const overBudget = cashBalance != null && impact.cash_required > cashBalance;

  return (
    <div className={cn(
      "flex items-center gap-0 rounded-lg border divide-x divide-border overflow-hidden text-sm",
      overBudget ? "border-amber-600/40 bg-amber-950/20" : "border-border bg-muted/20",
      className
    )}>
      <ImpactCell
        label="Cash Required"
        value={`$${impact.cash_required.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
        valueClass={overBudget ? "text-amber-400" : "text-foreground"}
        sub={cashBalance != null
          ? `${((impact.cash_required / cashBalance) * 100).toFixed(1)}% of cash`
          : undefined}
      />
      <ImpactCell
        label="Added Annual Income"
        value={`+$${impact.added_annual_income.toLocaleString("en-US", { maximumFractionDigits: 0 })}/yr`}
        valueClass="text-emerald-400"
      />
      <ImpactCell
        label="New Portfolio Yield"
        value={impact.new_portfolio_yield != null
          ? `${(impact.new_portfolio_yield * 100).toFixed(2)}%`
          : "—"}
        valueClass="text-foreground"
      />
      {impact.concentration_pct != null && (
        <ImpactCell
          label="Concentration"
          value={`${(impact.concentration_pct * 100).toFixed(1)}%`}
          valueClass={impact.concentration_pct > 0.1 ? "text-amber-400" : "text-foreground"}
        />
      )}
    </div>
  );
}

function ImpactCell({
  label,
  value,
  valueClass,
  sub,
}: {
  label: string;
  value: string;
  valueClass?: string;
  sub?: string;
}) {
  return (
    <div className="flex flex-col px-4 py-2 flex-1 min-w-0">
      <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</span>
      <span className={cn("text-sm font-semibold mt-0.5", valueClass)}>{value}</span>
      {sub && <span className="text-[10px] text-muted-foreground mt-0.5">{sub}</span>}
    </div>
  );
}

// ── Pure calculation helper ───────────────────────────────────────────────────

export function computeImpact(params: {
  proposals: Array<{
    platform_yield_estimate: number | null;
    analyst_yield_estimate: number | null;
  }>;
  orderParams: Array<{ shares: number | null; limit_price: number | null }>;
  currentAnnualIncome: number;
  currentPortfolioValue: number | null;
  cashBalance: number | null;
}): PortfolioImpact {
  const { proposals, orderParams, currentAnnualIncome, currentPortfolioValue, cashBalance } = params;

  let cashRequired = 0;
  let addedAnnualIncome = 0;

  for (let i = 0; i < proposals.length; i++) {
    const p = proposals[i];
    const o = orderParams[i];
    if (!o.shares || !o.limit_price) continue;

    const positionValue = o.shares * o.limit_price;
    cashRequired += positionValue;

    const yield_ = p.platform_yield_estimate ?? p.analyst_yield_estimate ?? 0;
    addedAnnualIncome += positionValue * yield_;
  }

  const newPortfolioYield = currentPortfolioValue != null && (currentPortfolioValue + cashRequired) > 0
    ? (currentAnnualIncome + addedAnnualIncome) / (currentPortfolioValue + cashRequired)
    : null;

  // concentration_pct: total concentration of all selected positions combined
  // (aggregate view appropriate for the impact bar; per-ticker breakdown in tooltips if needed)
  const concentrationPct = currentPortfolioValue != null && cashRequired > 0
    ? cashRequired / (currentPortfolioValue + cashRequired)
    : null;

  return {
    cash_required: cashRequired,
    added_annual_income: addedAnnualIncome,
    new_portfolio_yield: newPortfolioYield,
    concentration_pct: concentrationPct,
  };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | grep "portfolio-impact-bar" | head -10
```

Expected: no errors for this file

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/proposals/portfolio-impact-bar.tsx
git commit -m "feat(proposals): add PortfolioImpactBar component with computeImpact helper"
```

---

## Task 7: Frontend — OrderCard component

**Files:**
- Create: `src/frontend/src/components/proposals/order-card.tsx`

Context: Renders a single order's status. Has 4 variants controlled by the `order.status` field: `filled` (green), `partially_filled` (amber with progress bar + action buttons), `pending` (dimmed with cancel), `paper` (blue with copy/CSV/mark-done).

- [ ] **Step 1: Create the component**

```tsx
// src/frontend/src/components/proposals/order-card.tsx
"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { LiveOrder, PaperOrder } from "@/lib/types";

// ── Filled card ───────────────────────────────────────────────────────────────

export function FilledOrderCard({ order }: { order: LiveOrder }) {
  const total = order.filled_qty * (order.avg_fill_price ?? 0);
  const yoc = order.avg_fill_price != null && order.avg_fill_price > 0 ? null : null; // computed by parent with yield data

  return (
    <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/20 overflow-hidden">
      <OrderCardHeader order={order} />
      <div className="p-4 grid grid-cols-3 gap-3">
        <DetailCell label="Shares" value={order.filled_qty.toString()} className="text-emerald-400" />
        <DetailCell label="Avg Price" value={`$${(order.avg_fill_price ?? 0).toFixed(2)}`} className="text-emerald-400" />
        <DetailCell label="Total Paid" value={`$${total.toLocaleString("en-US", { maximumFractionDigits: 0 })}`} className="text-emerald-400" />
        {order.filled_at && (
          <DetailCell label="Filled At" value={new Date(order.filled_at).toLocaleTimeString()} />
        )}
      </div>
    </div>
  );
}

// ── Partial fill card ─────────────────────────────────────────────────────────

export function PartialOrderCard({
  order,
  marketPrice,
  onCancelRest,
  onRaiseLimit,
}: {
  order: LiveOrder;
  marketPrice?: number;
  onCancelRest: () => void;
  onRaiseLimit?: (newPrice: number) => void;
}) {
  const pct = order.qty > 0 ? (order.filled_qty / order.qty) * 100 : 0;
  const remaining = order.qty - order.filled_qty;

  return (
    <div className="rounded-xl border border-amber-800/40 overflow-hidden">
      <OrderCardHeader order={order} onCancel={onCancelRest} cancelLabel="Cancel Rest" />
      <div className="p-4 space-y-3">
        {/* Progress bar */}
        <div>
          <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
            <span>Fill progress</span>
            <span className="text-amber-400 font-medium">
              {order.filled_qty} / {order.qty} shares ({pct.toFixed(0)}%)
            </span>
          </div>
          <div className="h-1.5 bg-muted/40 rounded-full overflow-hidden">
            <div
              className="h-full bg-amber-400 rounded-full transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Details grid */}
        <div className="grid grid-cols-3 gap-3">
          <DetailCell label="Filled" value={`${order.filled_qty} sh`} className="text-emerald-400" />
          <DetailCell label="Avg Price" value={`$${(order.avg_fill_price ?? 0).toFixed(2)}`} />
          <DetailCell label="Remaining" value={`${remaining} sh`} className="text-amber-400" />
          <DetailCell label="Limit Price" value={order.limit_price != null ? `$${order.limit_price.toFixed(2)}` : "—"} />
        </div>

        {/* Action banner */}
        <div className="rounded-lg bg-amber-950/30 border border-amber-800/40 p-3 text-xs text-amber-300 space-y-2">
          <p>{remaining} shares remain unfilled.
            {order.limit_price != null && marketPrice != null && marketPrice > order.limit_price && (
              <> Limit ${order.limit_price.toFixed(2)} is below market ${marketPrice.toFixed(2)}.</>
            )}
            {" "}GTC order remains active until filled or cancelled.
          </p>
          <div className="flex gap-2">
            <button
              onClick={onCancelRest}
              className="text-[11px] px-2.5 py-1 rounded border border-red-800/50 bg-red-950/30 text-red-400 hover:bg-red-950/50"
            >
              Cancel remaining {remaining} shares
            </button>
            {marketPrice != null && onRaiseLimit && (
              <button
                onClick={() => onRaiseLimit(marketPrice)}
                className="text-[11px] px-2.5 py-1 rounded border border-border bg-muted/20 text-muted-foreground hover:text-foreground"
              >
                Raise limit to ${marketPrice.toFixed(2)}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Pending card ──────────────────────────────────────────────────────────────

export function PendingOrderCard({
  order,
  onCancel,
}: {
  order: LiveOrder;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-xl border border-border overflow-hidden opacity-70">
      <OrderCardHeader order={order} onCancel={onCancel} cancelLabel="Cancel Order" />
      <div className="p-4 space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <DetailCell label="Quantity" value={`${order.qty} shares`} />
          <DetailCell label="Limit Price" value={order.limit_price != null ? `$${order.limit_price.toFixed(2)}` : "Market"} />
          <DetailCell label="Est. Value" value={order.limit_price != null ? `$${(order.qty * order.limit_price).toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"} />
        </div>
        <p className="text-xs text-muted-foreground text-center py-1">
          Waiting for market — order live, no fills yet
        </p>
      </div>
    </div>
  );
}

// ── Paper order card ──────────────────────────────────────────────────────────

export function PaperOrderCard({
  order,
  onMarkExecuted,
}: {
  order: PaperOrder;
  onMarkExecuted: (fillPrice: number, fillDate: string) => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [fillPrice, setFillPrice] = useState(order.limit_price?.toFixed(2) ?? "");
  const [fillDate, setFillDate] = useState(new Date().toISOString().slice(0, 10));

  const orderText = [
    `Action:  BUY`,
    `Symbol:  ${order.ticker}`,
    `Qty:     ${order.qty} shares`,
    `Type:    ${order.order_type === "market" ? "Market" : `Limit @ $${order.limit_price?.toFixed(2) ?? "?"}`}`,
    `TIF:     ${order.time_in_force.toUpperCase()}`,
    `Account: ${order.portfolio_name} (manual)`,
  ].join("\n");

  const copyToClipboard = () => navigator.clipboard.writeText(orderText);
  const exportCSV = () => {
    const csv = `Action,Symbol,Qty,Type,Limit,TIF,Account\nBUY,${order.ticker},${order.qty},${order.order_type},${order.limit_price ?? ""},${order.time_in_force},${order.portfolio_name}`;
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `order-${order.ticker}.csv`;
    a.click();
  };

  return (
    <div className="rounded-xl border border-blue-900/40 bg-blue-950/20 overflow-hidden">
      <div className="px-4 py-3 bg-blue-950/30 border-b border-blue-900/40 flex items-center justify-between">
        <div>
          <span className="font-mono font-bold text-blue-300">{order.ticker}</span>
          <span className="text-xs text-blue-400/70 ml-2">{order.portfolio_name} · no broker connected</span>
        </div>
        <span className="text-xs font-semibold rounded-full px-2.5 py-0.5 bg-blue-900/40 text-blue-300 border border-blue-800/40">
          Paper Order
        </span>
      </div>
      <div className="p-4 space-y-3">
        <pre className="text-xs font-mono text-blue-300/80 bg-blue-950/30 rounded-lg border border-blue-900/30 p-3 leading-loose whitespace-pre">
          {orderText}
        </pre>
        <div className="flex gap-2">
          <button onClick={copyToClipboard} className="text-xs px-3 py-1.5 rounded border border-border bg-muted/20 text-muted-foreground hover:text-foreground">
            ⎘ Copy
          </button>
          <button onClick={exportCSV} className="text-xs px-3 py-1.5 rounded border border-border bg-muted/20 text-muted-foreground hover:text-foreground">
            ↓ CSV
          </button>
          {!order.executed && (
            <button
              onClick={() => setShowForm(!showForm)}
              className="text-xs px-3 py-1.5 rounded border border-emerald-800/40 bg-emerald-950/20 text-emerald-400 hover:bg-emerald-950/40"
            >
              ✓ Mark as Executed
            </button>
          )}
          {order.executed && (
            <span className="text-xs text-emerald-400 flex items-center gap-1">✓ Marked executed</span>
          )}
        </div>
        {showForm && (
          <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2">
            <p className="text-xs text-muted-foreground">Enter actual fill details:</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Fill Price</label>
                <input
                  type="number"
                  value={fillPrice}
                  onChange={(e) => setFillPrice(e.target.value)}
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
                />
              </div>
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Fill Date</label>
                <input
                  type="date"
                  value={fillDate}
                  onChange={(e) => setFillDate(e.target.value)}
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
                />
              </div>
            </div>
            <button
              onClick={() => {
                onMarkExecuted(parseFloat(fillPrice), fillDate);
                setShowForm(false);
              }}
              disabled={!fillPrice || !fillDate}
              className="w-full text-xs py-1.5 rounded bg-emerald-700 text-white hover:bg-emerald-600 disabled:opacity-40"
            >
              Confirm Execution
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Shared sub-components ─────────────────────────────────────────────────────

function OrderCardHeader({
  order,
  onCancel,
  cancelLabel = "Cancel",
}: {
  order: LiveOrder;
  onCancel?: () => void;
  cancelLabel?: string;
}) {
  const statusConfig: Record<string, { label: string; cls: string }> = {
    filled:           { label: "✓ Filled",       cls: "bg-emerald-950/40 text-emerald-400 border-emerald-800/40" },
    partially_filled: { label: "⚠ Partial Fill", cls: "bg-amber-950/40 text-amber-400 border-amber-800/40" },
    pending:          { label: "⏳ Pending",      cls: "bg-amber-950/40 text-amber-400 border-amber-800/40" },
    cancelled:        { label: "✗ Cancelled",     cls: "bg-muted/40 text-muted-foreground border-border" },
  };
  const cfg = statusConfig[order.status] ?? statusConfig.pending;

  return (
    <div className="px-4 py-3 bg-card/50 border-b border-border flex items-center justify-between">
      <div>
        <span className="font-mono font-bold">{order.ticker}</span>
        {order.order_id && (
          <span className="text-[10px] text-muted-foreground font-mono ml-2">#{order.order_id.slice(0, 8)}</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className={cn("text-xs font-semibold rounded-full px-2.5 py-0.5 border", cfg.cls)}>
          {cfg.label}
        </span>
        {onCancel && order.status !== "filled" && order.status !== "cancelled" && (
          <button
            onClick={onCancel}
            className="text-[11px] px-2 py-1 rounded border border-red-800/40 bg-red-950/20 text-red-400 hover:bg-red-950/40"
          >
            {cancelLabel}
          </button>
        )}
      </div>
    </div>
  );
}

function DetailCell({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={cn("text-sm font-semibold mt-0.5", className)}>{value}</p>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | grep "order-card" | head -10
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/proposals/order-card.tsx
git commit -m "feat(proposals): add OrderCard component (filled/partial/pending/paper variants)"
```

---

## Task 8: Frontend — ExecutionPanel (Phase 1)

**Files:**
- Create: `src/frontend/src/components/proposals/execution-panel.tsx`

Context: Phase 1 right pane. Receives a list of selected proposals grouped to one portfolio. Renders the portfolio impact bar at top, per-ticker tabs each with analysis block + execution form. Emits `onSubmit(orderParamsMap)` and `onRejectAll()`. Handles Save Draft via localStorage.

- [ ] **Step 1: Create the component**

```tsx
// src/frontend/src/components/proposals/execution-panel.tsx
"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { PortfolioImpactBar, computeImpact } from "./portfolio-impact-bar";
import type { ProposalWithPortfolio, OrderParams, OrderType, TimeInForce } from "@/lib/types";
import type { PortfolioListItem } from "@/lib/types";

interface ExecutionPanelProps {
  proposals: ProposalWithPortfolio[];
  portfolio: PortfolioListItem;
  onSubmit: (params: Record<number, OrderParams>) => void;
  onRejectAll: () => void;
  isBrokerConnected: boolean;
  loading?: boolean;
}

const DRAFT_KEY = (ids: number[]) => `proposal-draft-${ids.sort().join(",")}`;

export function ExecutionPanel({
  proposals,
  portfolio,
  onSubmit,
  onRejectAll,
  isBrokerConnected,
  loading,
}: ExecutionPanelProps) {
  const [activeTab, setActiveTab] = useState<number>(proposals[0]?.id ?? 0);
  const [params, setParams] = useState<Record<number, OrderParams>>(() => {
    // Restore draft from localStorage
    const key = DRAFT_KEY(proposals.map((p) => p.id));
    try {
      const saved = localStorage.getItem(key);
      if (saved) return JSON.parse(saved);
    } catch { /* ignore */ }
    // Default params from proposal data
    return Object.fromEntries(
      proposals.map((p) => [
        p.id,
        {
          order_type: "limit" as OrderType,
          limit_price: p.entry_price_low ?? null,
          shares: p.position_size_pct != null && portfolio.cash_balance != null
            ? Math.floor((portfolio.cash_balance * (p.position_size_pct / 100)) / (p.entry_price_low ?? 1))
            : null,
          dollar_amount: null,
          time_in_force: "gtc" as TimeInForce,
        } satisfies OrderParams,
      ])
    );
  });

  // Save draft on every change
  useEffect(() => {
    const key = DRAFT_KEY(proposals.map((p) => p.id));
    try { localStorage.setItem(key, JSON.stringify(params)); } catch { /* ignore */ }
  }, [params, proposals]);

  const updateParam = <K extends keyof OrderParams>(id: number, key: K, value: OrderParams[K]) => {
    setParams((prev) => {
      const updated = { ...prev, [id]: { ...prev[id], [key]: value } };
      // Link shares ↔ dollar_amount
      if (key === "shares" && updated[id].limit_price) {
        updated[id].dollar_amount = (value as number) * updated[id].limit_price!;
      }
      if (key === "dollar_amount" && updated[id].limit_price) {
        updated[id].shares = Math.floor((value as number) / updated[id].limit_price!);
      }
      if (key === "limit_price") {
        if (updated[id].shares) {
          updated[id].dollar_amount = updated[id].shares! * (value as number);
        }
      }
      return updated;
    });
  };

  const impact = computeImpact({
    proposals,
    orderParams: proposals.map((p) => ({
      shares: params[p.id]?.shares ?? null,
      limit_price: params[p.id]?.limit_price ?? null,
    })),
    currentAnnualIncome: 0,   // TODO: fetch from portfolio if available
    currentPortfolioValue: null,
    cashBalance: portfolio.cash_balance ?? null,
  });

  const totalCommitted = proposals.reduce((sum, p) => {
    const o = params[p.id];
    return sum + (o?.shares ?? 0) * (o?.limit_price ?? 0);
  }, 0);

  const activeProposal = proposals.find((p) => p.id === activeTab);
  const activeParams = activeProposal ? params[activeProposal.id] : null;

  return (
    <div className="flex flex-col h-full">
      {/* Portfolio Impact Bar */}
      <div className="p-4 pb-0">
        <PortfolioImpactBar
          impact={impact}
          cashBalance={portfolio.cash_balance ?? null}
          className="mb-4"
        />
      </div>

      {/* Ticker tabs */}
      <div className="flex gap-1 px-4 border-b border-border pb-0">
        {proposals.map((p) => (
          <button
            key={p.id}
            onClick={() => setActiveTab(p.id)}
            className={cn(
              "px-3 py-2 text-xs font-medium rounded-t border border-b-0 transition-colors",
              activeTab === p.id
                ? "bg-card border-border text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {p.ticker}
          </button>
        ))}
      </div>

      {/* Active ticker form */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeProposal && activeParams && (
          <>
            {/* Analysis block */}
            <div className="grid grid-cols-3 gap-3">
              <AnalysisCell label="Score" value={activeProposal.platform_score?.toFixed(0) ?? "—"} />
              <AnalysisCell
                label="Rec"
                value={activeProposal.analyst_recommendation ?? "—"}
                valueClass={activeProposal.analyst_recommendation?.includes("BUY") ? "text-emerald-400" : undefined}
              />
              <AnalysisCell
                label="Entry Range"
                value={activeProposal.entry_price_low != null
                  ? `$${activeProposal.entry_price_low.toFixed(2)}–$${(activeProposal.entry_price_high ?? activeProposal.entry_price_low).toFixed(2)}`
                  : "—"}
              />
            </div>
            {activeProposal.analyst_thesis_summary && (
              <p className="text-xs text-muted-foreground leading-relaxed">{activeProposal.analyst_thesis_summary}</p>
            )}
            {activeProposal.recommended_account && (
              <p className="text-xs text-muted-foreground">
                Suggested account: <span className="text-foreground font-medium">{activeProposal.recommended_account}</span>
              </p>
            )}

            {/* Alignment warning */}
            {activeProposal.platform_alignment && !["Aligned"].includes(activeProposal.platform_alignment) && (
              <div className={cn(
                "text-xs rounded-lg border px-3 py-2",
                activeProposal.platform_alignment === "Vetoed"
                  ? "bg-red-950/20 border-red-800/40 text-red-300"
                  : "bg-amber-950/20 border-amber-800/40 text-amber-300"
              )}>
                ⚠ {activeProposal.platform_alignment} — {activeProposal.divergence_notes ?? "Review before executing."}
              </div>
            )}

            {/* Execution form */}
            <div className="space-y-3 rounded-xl border border-border bg-card/30 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Order Parameters</p>

              {/* Order type pills */}
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1.5">Order Type</label>
                <div className="flex gap-2">
                  {(["market", "limit", "stop_limit"] as OrderType[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => updateParam(activeProposal.id, "order_type", t)}
                      className={cn(
                        "px-3 py-1 text-xs rounded-full border transition-colors",
                        activeParams.order_type === t
                          ? "bg-violet-600/20 text-violet-300 border-violet-700/40"
                          : "border-border text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {t === "stop_limit" ? "Stop-Limit" : t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                {/* Limit price */}
                {activeParams.order_type !== "market" && (
                  <div>
                    <label className="text-[10px] text-muted-foreground block mb-1">Limit Price</label>
                    <input
                      type="number"
                      step="0.01"
                      value={activeParams.limit_price ?? ""}
                      onChange={(e) => updateParam(activeProposal.id, "limit_price", parseFloat(e.target.value) || null)}
                      className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs"
                    />
                  </div>
                )}

                {/* Shares */}
                <div>
                  <label className="text-[10px] text-muted-foreground block mb-1">Shares</label>
                  <input
                    type="number"
                    value={activeParams.shares ?? ""}
                    onChange={(e) => updateParam(activeProposal.id, "shares", parseInt(e.target.value) || null)}
                    className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs"
                  />
                </div>

                {/* Dollar amount */}
                <div>
                  <label className="text-[10px] text-muted-foreground block mb-1">$ Amount</label>
                  <input
                    type="number"
                    step="1"
                    value={activeParams.dollar_amount != null ? Math.round(activeParams.dollar_amount) : ""}
                    onChange={(e) => updateParam(activeProposal.id, "dollar_amount", parseFloat(e.target.value) || null)}
                    className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs"
                  />
                </div>
              </div>

              {/* Time in force */}
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1.5">Time in Force</label>
                <div className="flex gap-2">
                  {(["day", "gtc", "ioc"] as TimeInForce[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => updateParam(activeProposal.id, "time_in_force", t)}
                      className={cn(
                        "px-3 py-1 text-xs rounded-full border transition-colors",
                        activeParams.time_in_force === t
                          ? "bg-muted text-foreground border-border"
                          : "border-border text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {t.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-border px-4 py-3 flex items-center justify-between gap-3">
        <div className="text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">
            ${totalCommitted.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </span>
          {" "}committed
          {portfolio.cash_balance != null && (
            <span className={cn("ml-2", totalCommitted > portfolio.cash_balance ? "text-amber-400" : "text-emerald-400")}>
              ${(portfolio.cash_balance - totalCommitted).toLocaleString("en-US", { maximumFractionDigits: 0 })} remaining
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={onRejectAll}
            className="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground"
          >
            Reject All
          </button>
          <button
            onClick={() => {
              const key = DRAFT_KEY(proposals.map((p) => p.id));
              try { localStorage.setItem(key, JSON.stringify(params)); } catch { /* ignore */ }
            }}
            className="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground"
          >
            Save Draft
          </button>
          <button
            onClick={() => onSubmit(params)}
            disabled={loading || totalCommitted === 0}
            className="text-xs px-4 py-1.5 rounded bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-40 font-medium"
          >
            {loading
              ? "Submitting…"
              : isBrokerConnected
                ? `Submit ${proposals.length} Order${proposals.length !== 1 ? "s" : ""} to ${portfolio.broker ?? "Broker"}`
                : "Generate Paper Orders"}
          </button>
        </div>
      </div>
    </div>
  );
}

function AnalysisCell({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={cn("text-sm font-semibold mt-0.5", valueClass)}>{value}</p>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | grep "execution-panel" | head -10
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/proposals/execution-panel.tsx
git commit -m "feat(proposals): add ExecutionPanel component (Phase 1 order setup)"
```

---

## Task 9: Frontend — OrderStatusPanel (Phase 2)

**Files:**
- Create: `src/frontend/src/components/proposals/order-status-panel.tsx`

Context: Phase 2 right pane. Receives live orders (from polling) and paper orders. Renders per-ticker tabs. Calls parent callbacks for cancel, raise-limit, and mark-paper-executed. Shows "auto-refreshing" indicator + manual Refresh button. Calls sync-fill and fill-confirmed when a fill is detected.

- [ ] **Step 1: Create the component**

```tsx
// src/frontend/src/components/proposals/order-status-panel.tsx
"use client";

import { useEffect, useRef } from "react";
import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  FilledOrderCard,
  PartialOrderCard,
  PendingOrderCard,
  PaperOrderCard,
} from "./order-card";
import type { LiveOrder, PaperOrder } from "@/lib/types";

const POLL_INTERVAL_MS = 10_000;

interface OrderStatusPanelProps {
  liveOrders: LiveOrder[];
  paperOrders: PaperOrder[];
  submittedAt: Date;
  onRefresh: () => void;
  onCancelOrder: (orderId: string, broker: string) => void;
  onCancelRest: (orderId: string, broker: string) => void;
  onMarkPaperExecuted: (proposalId: number, fillPrice: number, fillDate: string) => void;
  lastRefreshedAt: Date | null;
}

export function OrderStatusPanel({
  liveOrders,
  paperOrders,
  submittedAt,
  onRefresh,
  onCancelOrder,
  onCancelRest,
  onMarkPaperExecuted,
  lastRefreshedAt,
}: OrderStatusPanelProps) {
  const allTerminal = liveOrders.every(
    (o) => o.status === "filled" || o.status === "cancelled"
  );

  // Auto-poll every 10s until all orders are terminal
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => {
    if (allTerminal) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }
    timerRef.current = setInterval(onRefresh, POLL_INTERVAL_MS);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [allTerminal, onRefresh]);

  const filledCount = liveOrders.filter((o) => o.status === "filled").length;
  const partialCount = liveOrders.filter((o) => o.status === "partially_filled").length;
  const pendingCount = liveOrders.filter((o) => o.status === "pending").length;
  const totalAnnualIncome = liveOrders
    .filter((o) => o.status === "filled" && o.avg_fill_price && o.filled_qty)
    .reduce((sum, _o) => sum, 0); // caller can enrich with yield data

  const allOrders = [
    ...liveOrders.map((o) => ({ type: "live" as const, data: o })),
    ...paperOrders.map((o) => ({ type: "paper" as const, data: o })),
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3 border-b border-border flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold">
            Order Status
            {liveOrders.length > 0 && (
              <span className="text-muted-foreground font-normal ml-2">
                {filledCount} filled · {partialCount} partial · {pendingCount} pending
              </span>
            )}
            {paperOrders.length > 0 && (
              <span className="text-muted-foreground font-normal ml-2">
                {paperOrders.length} paper
              </span>
            )}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Submitted {submittedAt.toLocaleTimeString()}
            {!allTerminal && " · auto-refreshing"}
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground rounded border border-border px-2 py-1"
          title="Refresh order status"
        >
          <RefreshCw className="h-3 w-3" /> Refresh
        </button>
      </div>

      {lastRefreshedAt && (
        <p className="px-5 py-1 text-[10px] text-muted-foreground border-b border-border bg-muted/10">
          Last updated {lastRefreshedAt.toLocaleTimeString()}
        </p>
      )}

      {/* Order cards */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {allOrders.map(({ type, data }) => {
          if (type === "paper") {
            return (
              <PaperOrderCard
                key={`paper-${data.proposal_id}`}
                order={data as PaperOrder}
                onMarkExecuted={(price, date) =>
                  onMarkPaperExecuted((data as PaperOrder).proposal_id, price, date)
                }
              />
            );
          }
          const o = data as LiveOrder;
          if (o.status === "filled") {
            return <FilledOrderCard key={o.order_id} order={o} />;
          }
          if (o.status === "partially_filled") {
            return (
              <PartialOrderCard
                key={o.order_id}
                order={o}
                onCancelRest={() => onCancelRest(o.order_id, o.broker)}
              />
            );
          }
          return (
            <PendingOrderCard
              key={o.order_id}
              order={o}
              onCancel={() => onCancelOrder(o.order_id, o.broker)}
            />
          );
        })}
      </div>

      {/* Footer summary */}
      <div className="border-t border-border px-5 py-3 flex items-center justify-between text-xs">
        <div className="flex gap-4 text-muted-foreground">
          <span>
            Filled:{" "}
            <span className="text-emerald-400 font-medium">
              ${liveOrders
                .filter((o) => o.status === "filled")
                .reduce((s, o) => s + o.filled_qty * (o.avg_fill_price ?? 0), 0)
                .toLocaleString("en-US", { maximumFractionDigits: 0 })}
            </span>
          </span>
          {pendingCount + partialCount > 0 && (
            <span>
              Pending:{" "}
              <span className="text-amber-400 font-medium">
                ${liveOrders
                  .filter((o) => o.status === "pending" || o.status === "partially_filled")
                  .reduce((s, o) => s + (o.qty - o.filled_qty) * (o.limit_price ?? 0), 0)
                  .toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | grep "order-status-panel" | head -10
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/proposals/order-status-panel.tsx
git commit -m "feat(proposals): add OrderStatusPanel component (Phase 2 order tracking)"
```

---

## Task 10: Frontend — proposals/page.tsx redesign

**Files:**
- Modify: `src/frontend/src/app/proposals/page.tsx`

Context: This is the main assembly. Replace the current read-only page with the two-phase flow. Phase 1 = execution setup. Phase 2 = order status. The left pane now groups proposals by `portfolio_id`. When `portfolio_id` is null (older proposals), group them under "Unassigned". The current `MetricCard`, `Section`, `ProposalDetail` components can be removed — Phase 1 uses `ExecutionPanel` which has its own analysis display.

Preserve the existing `Proposal` interface and status helpers at the top — they are still needed for the left pane list.

- [ ] **Step 1: Understand PortfolioListItem shape**

```bash
grep -n "PortfolioListItem\|cash_balance\|broker" src/frontend/src/lib/types.ts | head -20
```

Note the fields available on `PortfolioListItem` (especially `broker` — used to determine if broker-connected).

- [ ] **Step 2: Write the new page**

Replace `src/frontend/src/app/proposals/page.tsx` entirely with:

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { RefreshCw, Loader2, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/utils";
import { ExecutionPanel } from "@/components/proposals/execution-panel";
import { OrderStatusPanel } from "@/components/proposals/order-status-panel";
import type {
  ProposalWithPortfolio,
  OrderParams,
  LiveOrder,
  PaperOrder,
  BrokerOrderStatus,
} from "@/lib/types";
import type { PortfolioListItem } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Proposal {
  id: number;
  ticker: string;
  portfolio_id: string | null;
  platform_score: number | null;
  platform_alignment: string | null;
  analyst_recommendation: string | null;
  analyst_yield_estimate: number | null;
  platform_yield_estimate: number | null;
  entry_price_low: number | null;
  entry_price_high: number | null;
  position_size_pct: number | null;
  recommended_account: string | null;
  analyst_thesis_summary: string | null;
  analyst_safety_grade: string | null;
  platform_income_grade: string | null;
  sizing_rationale: string | null;
  divergence_notes: string | null;
  veto_flags: Record<string, unknown> | null;
  status: string;
  created_at: string | null;
}

type Phase = "setup" | "status";

function alignmentDot(alignment: string | null): string {
  if (!alignment) return "bg-muted-foreground";
  const a = alignment.toLowerCase();
  if (a === "aligned") return "bg-emerald-400";
  if (a === "partial" || a === "divergent") return "bg-amber-400";
  if (a === "vetoed") return "bg-red-400";
  return "bg-muted-foreground";
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [portfolios, setPortfolios] = useState<PortfolioListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [focusedPortfolioId, setFocusedPortfolioId] = useState<string | null>(null);

  // Phase
  const [phase, setPhase] = useState<Phase>("setup");
  const [submitting, setSubmitting] = useState(false);

  // Order tracking (Phase 2)
  const [liveOrders, setLiveOrders] = useState<LiveOrder[]>([]);
  const [paperOrders, setPaperOrders] = useState<PaperOrder[]>([]);
  const [submittedAt, setSubmittedAt] = useState<Date | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);

  // Load proposals + portfolios
  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pResp, portResp] = await Promise.all([
        fetch("/api/proposals?limit=200&status=pending"),
        fetch("/api/portfolios"),
      ]);
      if (!pResp.ok) throw new Error(`Proposals: HTTP ${pResp.status}`);
      if (!portResp.ok) throw new Error(`Portfolios: HTTP ${portResp.status}`);
      const [pData, portData] = await Promise.all([pResp.json(), portResp.json()]);
      setProposals(Array.isArray(pData) ? pData : []);
      setPortfolios(Array.isArray(portData) ? portData : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Group pending proposals by portfolio
  const pendingProposals = proposals.filter((p) => p.status === "pending");
  const portfolioGroups = groupByPortfolio(pendingProposals);

  // Auto-focus first portfolio with proposals
  useEffect(() => {
    if (!focusedPortfolioId && portfolioGroups.length > 0) {
      setFocusedPortfolioId(portfolioGroups[0].portfolioId);
    }
  }, [portfolioGroups, focusedPortfolioId]);

  const focusedPortfolio = portfolios.find((p) => p.id === focusedPortfolioId) ?? null;
  const focusedGroup = portfolioGroups.find((g) => g.portfolioId === focusedPortfolioId);
  const focusedProposals = (focusedGroup?.proposals ?? []).filter((p) => selectedIds.has(p.id));

  // Auto-select all proposals in focused portfolio
  useEffect(() => {
    if (focusedGroup) {
      setSelectedIds(new Set(focusedGroup.proposals.map((p) => p.id)));
    }
  }, [focusedPortfolioId]);

  // ── Submit handler ──

  const handleSubmit = async (params: Record<number, OrderParams>) => {
    if (!focusedPortfolio || focusedProposals.length === 0) return;
    setSubmitting(true);

    const isBrokerConnected = !!focusedPortfolio.broker;
    const newLiveOrders: LiveOrder[] = [];
    const newPaperOrders: PaperOrder[] = [];

    for (const proposal of focusedProposals) {
      const p = params[proposal.id];
      if (!p?.shares || p.shares <= 0) continue;

      if (!isBrokerConnected) {
        newPaperOrders.push({
          proposal_id: proposal.id,
          ticker: proposal.ticker,
          portfolio_id: focusedPortfolio.id,
          qty: p.shares,
          order_type: p.order_type,
          limit_price: p.limit_price,
          time_in_force: p.time_in_force,
          portfolio_name: focusedPortfolio.name,
          executed: false,
        });
        // Transition proposal to executed_aligned
        await fetch(`/api/proposals/${proposal.id}/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_acknowledged_veto: false }),
        }).catch(() => null);
        continue;
      }

      try {
        const resp = await fetch("/broker/orders", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            broker: focusedPortfolio.broker,
            portfolio_id: focusedPortfolio.id,
            symbol: proposal.ticker,
            side: "buy",
            qty: p.shares,
            order_type: p.order_type,
            limit_price: p.order_type !== "market" ? p.limit_price : undefined,
            time_in_force: p.time_in_force,
            proposal_id: String(proposal.id),
          }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          console.error(`Order failed for ${proposal.ticker}:`, data.detail);
          continue;
        }

        // Transition proposal to executed_aligned
        await fetch(`/api/proposals/${proposal.id}/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_acknowledged_veto: false }),
        }).catch(() => null);

        newLiveOrders.push({
          proposal_id: proposal.id,
          ticker: proposal.ticker,
          portfolio_id: focusedPortfolio.id,
          order_id: data.order_id,
          broker: data.broker ?? focusedPortfolio.broker,
          status: (data.status ?? "pending") as BrokerOrderStatus,
          qty: p.shares,
          filled_qty: data.filled_qty ?? 0,
          avg_fill_price: data.filled_avg_price ?? null,
          limit_price: p.limit_price,
          filled_at: null,
          submitted_at: new Date().toISOString(),
        });
      } catch (err) {
        console.error(`Order error for ${proposal.ticker}:`, err);
      }
    }

    setLiveOrders(newLiveOrders);
    setPaperOrders(newPaperOrders);
    setSubmittedAt(new Date());
    setSubmitting(false);
    setPhase("status");
  };

  // ── Polling / refresh ──

  const refreshOrders = useCallback(async () => {
    const updated = await Promise.all(
      liveOrders.map(async (o) => {
        if (o.status === "filled" || o.status === "cancelled") return o;
        try {
          const resp = await fetch(`/broker/orders/${o.order_id}?broker=${o.broker}`);
          if (!resp.ok) return o;
          const data = await resp.json();
          const newStatus: BrokerOrderStatus = data.status ?? o.status;
          const updated: LiveOrder = {
            ...o,
            status: newStatus,
            filled_qty: data.filled_qty ?? o.filled_qty,
            avg_fill_price: data.filled_avg_price ?? o.avg_fill_price,
            filled_at: data.filled_at ?? o.filled_at,
          };

          // Trigger sync-fill when new shares are confirmed (status change OR filled_qty increase)
          const prevFilledQty = o.filled_qty ?? 0;
          const newFilledQty = data.filled_qty ?? 0;
          if (
            (newStatus === "filled" || newStatus === "partially_filled") &&
            newFilledQty > prevFilledQty
          ) {
            // Only sync the newly-filled increment, not the cumulative total
            await syncFill({
              ...updated,
              filled_qty: newFilledQty - prevFilledQty,
              avg_fill_price: data.filled_avg_price,
            }).catch(() => null);
          }

          return updated;
        } catch {
          return o;
        }
      })
    );
    setLiveOrders(updated);
    setLastRefreshedAt(new Date());
  }, [liveOrders]);

  // ── Sync-fill helper ──

  const syncFill = async (order: LiveOrder) => {
    if (!order.avg_fill_price || !order.filled_at) return;
    await fetch("/broker/positions/sync-fill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        portfolio_id: order.portfolio_id,
        ticker: order.ticker,
        filled_qty: order.filled_qty,
        avg_fill_price: order.avg_fill_price,
        filled_at: order.filled_at,
        proposal_id: String(order.proposal_id),
        order_id: order.order_id,
      }),
    });
    await fetch(`/api/proposals/${order.proposal_id}/fill-confirmed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filled_qty: order.filled_qty,
        avg_fill_price: order.avg_fill_price,
        filled_at: order.filled_at,
        status: order.status === "filled" ? "filled" : "partially_filled",
      }),
    });
  };

  // ── Cancel handlers ──

  const handleCancelOrder = async (orderId: string, broker: string) => {
    const resp = await fetch(`/broker/orders/${orderId}?broker=${broker}`, {
      method: "DELETE",
    }).catch(() => null);
    if (resp?.ok) {
      const order = liveOrders.find((o) => o.order_id === orderId);
      if (order && order.filled_qty > 0) {
        await syncFill({ ...order, status: "partially_filled" }).catch(() => null);
      }
      setLiveOrders((prev) =>
        prev.map((o) => o.order_id === orderId ? { ...o, status: "cancelled" } : o)
      );
      // Transition proposal to cancelled
      const proposal = liveOrders.find((o) => o.order_id === orderId);
      if (proposal) {
        await fetch(`/api/proposals/${proposal.proposal_id}/fill-confirmed`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filled_qty: 0, avg_fill_price: 0,
            filled_at: new Date().toISOString(), status: "cancelled",
          }),
        }).catch(() => null);
      }
    }
  };

  // ── Paper order mark-executed ──

  const handleMarkPaperExecuted = async (proposalId: number, fillPrice: number, fillDate: string) => {
    const order = paperOrders.find((o) => o.proposal_id === proposalId);
    if (!order) return;
    await fetch("/broker/positions/sync-fill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        portfolio_id: order.portfolio_id,
        ticker: order.ticker,
        filled_qty: order.qty,
        avg_fill_price: fillPrice,
        filled_at: `${fillDate}T00:00:00Z`,
        proposal_id: String(proposalId),
      }),
    }).catch(() => null);
    await fetch(`/api/proposals/${proposalId}/fill-confirmed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filled_qty: order.qty, avg_fill_price: fillPrice,
        filled_at: `${fillDate}T00:00:00Z`, status: "filled",
      }),
    }).catch(() => null);
    setPaperOrders((prev) =>
      prev.map((o) => o.proposal_id === proposalId ? { ...o, executed: true } : o)
    );
  };

  // ── Render ──

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Left: proposal list grouped by portfolio */}
      <div className="w-72 shrink-0 border-r border-border flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h1 className="text-sm font-semibold">Proposals</h1>
          <button
            onClick={fetchAll}
            className="p-1 rounded text-muted-foreground hover:text-foreground"
            title="Refresh"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {loading && (
            <div className="flex items-center justify-center py-8 text-muted-foreground text-xs">
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" /> Loading…
            </div>
          )}
          {!loading && error && (
            <div className="mx-3 rounded border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">{error}</div>
          )}
          {!loading && !error && portfolioGroups.length === 0 && (
            <div className="px-4 py-8 text-center text-xs text-muted-foreground">
              No pending proposals.<br />Run a scan and generate proposals to see them here.
            </div>
          )}

          {portfolioGroups.map((group) => {
            const port = portfolios.find((p) => p.id === group.portfolioId);
            const isFocused = group.portfolioId === focusedPortfolioId;
            return (
              <div key={group.portfolioId} className="mb-2">
                <div
                  className="flex items-center justify-between px-4 py-1.5 cursor-pointer"
                  onClick={() => setFocusedPortfolioId(group.portfolioId)}
                >
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {port?.name ?? "Unassigned"}
                  </span>
                  {port?.cash_balance != null && (
                    <span className="text-[10px] text-emerald-400">
                      ${port.cash_balance.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                  )}
                </div>
                {group.proposals.map((p) => {
                  const checked = selectedIds.has(p.id);
                  return (
                    <div
                      key={p.id}
                      onClick={() => {
                        setFocusedPortfolioId(group.portfolioId);
                        setSelectedIds((prev) => {
                          const next = new Set(prev);
                          if (next.has(p.id)) next.delete(p.id); else next.add(p.id);
                          return next;
                        });
                      }}
                      className={cn(
                        "flex items-start gap-2.5 px-4 py-2.5 cursor-pointer border-l-2 transition-colors",
                        isFocused && checked
                          ? "bg-violet-950/20 border-l-violet-500"
                          : "border-l-transparent hover:bg-muted/20"
                      )}
                    >
                      <div className={cn(
                        "mt-1 h-3.5 w-3.5 shrink-0 rounded border flex items-center justify-center",
                        checked ? "bg-violet-600 border-violet-600" : "border-border"
                      )}>
                        {checked && <span className="text-[8px] text-white font-bold">✓</span>}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-semibold text-sm">{p.ticker}</span>
                          {p.platform_score != null && (
                            <span className="text-[10px] font-medium text-violet-400">{p.platform_score.toFixed(0)}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <div className={cn("h-1.5 w-1.5 rounded-full", alignmentDot(p.platform_alignment))} />
                          <span className="text-[10px] text-muted-foreground">
                            {p.platform_alignment ?? "—"} · {p.created_at ? formatDateTime(p.created_at) : ""}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right: execution panel or order status */}
      <div className="flex-1 overflow-hidden">
        {phase === "setup" ? (
          focusedPortfolio && focusedProposals.length > 0 ? (
            <ExecutionPanel
              proposals={focusedProposals as ProposalWithPortfolio[]}
              portfolio={focusedPortfolio}
              onSubmit={handleSubmit}
              onRejectAll={async () => {
                await Promise.all(
                  focusedProposals.map((p) =>
                    fetch(`/api/proposals/${p.id}/reject`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({}),
                    }).catch(() => null)
                  )
                );
                fetchAll();
              }}
              isBrokerConnected={!!focusedPortfolio.broker}
              loading={submitting}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
              Select proposals from the left to begin
            </div>
          )
        ) : (
          submittedAt && (
            <OrderStatusPanel
              liveOrders={liveOrders}
              paperOrders={paperOrders}
              submittedAt={submittedAt}
              onRefresh={refreshOrders}
              onCancelOrder={handleCancelOrder}
              onCancelRest={handleCancelOrder}
              onMarkPaperExecuted={handleMarkPaperExecuted}
              lastRefreshedAt={lastRefreshedAt}
            />
          )
        )}
      </div>
    </div>
  );
}

// ── Portfolio grouping helper ─────────────────────────────────────────────────

function groupByPortfolio(proposals: Proposal[]) {
  const map = new Map<string, Proposal[]>();
  for (const p of proposals) {
    const key = p.portfolio_id ?? "unassigned";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(p);
  }
  return Array.from(map.entries()).map(([portfolioId, proposals]) => ({
    portfolioId,
    proposals,
  }));
}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | head -30
```

Fix any type errors before proceeding. Common issues:
- `ProposalWithPortfolio` vs `Proposal` cast — the local `Proposal` interface has all the same fields; the cast is safe.
- `PortfolioListItem.broker` — verify this field exists in types.ts (from earlier grep).

- [ ] **Step 4: Start dev server and verify the page loads**

```bash
cd src/frontend && npm run dev 2>&1 &
sleep 5 && curl -s http://localhost:3000/proposals | grep -c "html"
```

Expected: `1` (page renders HTML)

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/proposals/page.tsx
git commit -m "feat(proposals): redesign page with two-phase execution workflow"
```

---

## Task 11: Apply DB migration to server

**Context:** The `add_portfolio_id_to_proposals.sql` migration must be run against the production DB on legato (138.197.78.238). Coordinate with user before running — do not auto-apply.

- [ ] **Step 1: Ask user to confirm before running**

Present the migration SQL for review:

```sql
ALTER TABLE platform_shared.proposals
    ADD COLUMN IF NOT EXISTS portfolio_id UUID NULL;
```

- [ ] **Step 2: Run migration (only after user confirms)**

From the server or via psql tunnel to legato:

```bash
psql $DATABASE_URL -f src/proposal-service/migrations/add_portfolio_id_to_proposals.sql
```

Expected output: `ALTER TABLE`

- [ ] **Step 3: Verify column exists**

```bash
psql $DATABASE_URL -c "\d platform_shared.proposals" | grep portfolio_id
```

Expected: `portfolio_id | uuid | ...`

- [ ] **Step 4: Commit (final integration commit)**

```bash
git commit -m "feat(proposals): complete execution workflow — broker orders, fill sync, two-phase UI"
```

---

## Testing Checklist

After all tasks, verify end-to-end:

1. **Proposal generation** — generate a proposal via scanner with a portfolio selected → confirm `portfolio_id` is set on the proposal row
2. **Execution setup** — open /proposals → proposals appear grouped by portfolio → select proposals → see execution form and impact bar
3. **Submit live order** — submit to Alpaca → see Phase 2 status cards → verify order shows as Pending
4. **Fill detection** — wait for order to fill (or test with paper trading) → status transitions to Filled → confirm position row appears in portfolio
5. **Cancel order** — submit limit order below market → cancel → status transitions to Cancelled
6. **Paper order** — use HDO portfolio (no broker) → submit → paper order card appears → mark as executed → confirm position synced
7. **Partial fill** — if testable: GTC order partially fills → progress bar shows correct percentage → cancel rest works
