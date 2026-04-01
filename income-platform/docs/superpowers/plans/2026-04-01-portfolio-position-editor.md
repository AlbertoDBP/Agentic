# Portfolio Position Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible Manage Positions panel and enriched detail pane (Portfolio Context + Technicals) to the portfolio tab, using existing admin-panel CRUD endpoints.

**Architecture:** Two new Next.js proxy routes forward to admin-panel (`POST /api/portfolios/{id}/positions`, `PATCH/DELETE /api/positions/{id}`). A new pure-function helper module `portfolio-context.ts` handles all client-side metric computations. A single component file (`portfolio-tab.tsx`) gains the Manage Positions panel above the DataTable and two new sections in the detail pane.

**Tech Stack:** Next.js 15 (async params), TypeScript, Tailwind CSS, React useState/useEffect, localStorage for panel collapse state.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `src/frontend/src/app/api/portfolios/[id]/positions/route.ts` | **Create** | POST proxy → admin-panel POST /api/portfolios/{id}/positions |
| `src/frontend/src/app/api/positions/[id]/route.ts` | **Create** | PATCH + DELETE proxy → admin-panel PATCH/DELETE /api/positions/{id} |
| `src/frontend/src/lib/portfolio-context.ts` | **Create** | Pure helper functions: computePortfolioWeight, computeSectorWeight, computeIncomeWeight, computeRankByValue, computeRankByIncome, formatSmaDeviation, rsiLabel |
| `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx` | **Modify** | Add Manage Positions panel (before DataTable) + Portfolio Context + Technicals sections (in detail pane) |
| `docker-compose.yml` | **Modify** | Add ADMIN_PANEL_URL=http://admin-panel:8100 to frontend service env |

---

## Task 1: API Proxy Routes + docker-compose env

**Files:**
- Create: `src/frontend/src/app/api/portfolios/[id]/positions/route.ts`
- Create: `src/frontend/src/app/api/positions/[id]/route.ts`
- Modify: `docker-compose.yml` (add ADMIN_PANEL_URL to frontend env block)

### Reference: existing proxy pattern
Study `src/frontend/src/app/api/portfolios/[id]/route.ts` for the established pattern:
```typescript
const AGENT14 = process.env.AGENT14_URL ?? "http://localhost:8014";
function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? "dev-token";
}
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: portfolioId } = await params;
  // ...
}
```

- [ ] **Step 1: Create POST proxy for adding positions**

Create `src/frontend/src/app/api/portfolios/[id]/positions/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? "dev-token";
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: portfolioId } = await params;
  const body = await req.json();

  const res = await fetch(
    `${ADMIN_PANEL_URL}/api/portfolios/${portfolioId}/positions`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${serviceToken()}`,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10_000),
    }
  );

  const data = res.status === 204 ? null : await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
```

- [ ] **Step 2: Create PATCH + DELETE proxy for editing/removing positions**

Create `src/frontend/src/app/api/positions/[id]/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? "dev-token";
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await req.json();

  const res = await fetch(`${ADMIN_PANEL_URL}/api/positions/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${serviceToken()}`,
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(10_000),
  });

  const data = res.status === 204 ? null : await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const res = await fetch(`${ADMIN_PANEL_URL}/api/positions/${id}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${serviceToken()}`,
    },
    signal: AbortSignal.timeout(10_000),
  });

  return new NextResponse(null, { status: res.status });
}
```

- [ ] **Step 3: Add ADMIN_PANEL_URL to docker-compose frontend env**

Find the `frontend` service environment block in `docker-compose.yml` and add:
```yaml
- ADMIN_PANEL_URL=http://admin-panel:8100
```

- [ ] **Step 4: TypeScript check + lint**

```bash
cd src/frontend && npx tsc --noEmit && npm run lint
```
Expected: no new errors or warnings

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/api/portfolios/[id]/positions/route.ts \
        src/frontend/src/app/api/positions/[id]/route.ts \
        docker-compose.yml
git commit -m "feat(frontend): add proxy routes for position CRUD and ADMIN_PANEL_URL env"
```

---

## Task 2: Portfolio Context Helper Functions

**Files:**
- Create: `src/frontend/src/lib/portfolio-context.ts`

These are pure functions with no side effects — easy to reason about and test manually.

- [ ] **Step 1: Create `src/frontend/src/lib/portfolio-context.ts`**

```typescript
import type { Position } from "./types";

/** Portfolio weight of a position as a percentage (0–100). Returns null if total value is 0. */
export function computePortfolioWeight(
  position: Position,
  positions: Position[]
): number | null {
  const total = positions.reduce((s, p) => s + (p.current_value ?? 0), 0);
  if (!total) return null;
  return ((position.current_value ?? 0) / total) * 100;
}

/** Sector weight of a position's sector as a percentage (0–100). Returns null if total value is 0. */
export function computeSectorWeight(
  position: Position,
  positions: Position[]
): number | null {
  if (!position.sector) return null;
  const total = positions.reduce((s, p) => s + (p.current_value ?? 0), 0);
  if (!total) return null;
  const sectorTotal = positions
    .filter((p) => p.sector === position.sector)
    .reduce((s, p) => s + (p.current_value ?? 0), 0);
  return (sectorTotal / total) * 100;
}

/** Income weight as a percentage (0–100). Returns null if total annual income is 0. */
export function computeIncomeWeight(
  position: Position,
  positions: Position[]
): number | null {
  const total = positions.reduce((s, p) => s + (p.annual_income ?? 0), 0);
  if (!total) return null;
  return ((position.annual_income ?? 0) / total) * 100;
}

/** 1-based rank among positions sorted by current_value descending. Returns null if position not found. */
export function computeRankByValue(
  position: Position,
  positions: Position[]
): number | null {
  const sorted = [...positions].sort(
    (a, b) => (b.current_value ?? 0) - (a.current_value ?? 0)
  );
  const idx = sorted.findIndex((p) => p.id === position.id);
  return idx === -1 ? null : idx + 1;
}

/** 1-based rank among positions sorted by annual_income descending. Returns null if position not found. */
export function computeRankByIncome(
  position: Position,
  positions: Position[]
): number | null {
  const sorted = [...positions].sort(
    (a, b) => (b.annual_income ?? 0) - (a.annual_income ?? 0)
  );
  const idx = sorted.findIndex((p) => p.id === position.id);
  return idx === -1 ? null : idx + 1;
}

/**
 * Format price deviation from SMA as "+2.1% ↑" or "−2.1% ↓".
 * Returns null if price or sma is null/zero.
 */
export function formatSmaDeviation(
  price: number | null | undefined,
  sma: number | null | undefined
): string | null {
  if (!price || !sma) return null;
  const pct = ((price - sma) / sma) * 100;
  const sign = pct >= 0 ? "+" : "−";
  const arrow = pct >= 0 ? "↑" : "↓";
  return `${sign}${Math.abs(pct).toFixed(1)}% ${arrow}`;
}

/** RSI label: < 30 → "oversold", > 70 → "overbought", else → "neutral". Returns null if rsi is null. */
export function rsiLabel(
  rsi: number | null | undefined
): "oversold" | "neutral" | "overbought" | null {
  if (rsi == null) return null;
  if (rsi < 30) return "oversold";
  if (rsi > 70) return "overbought";
  return "neutral";
}
```

- [ ] **Step 2: TypeScript check + lint**

```bash
cd src/frontend && npx tsc --noEmit && npm run lint
```
Expected: no new errors or warnings

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/lib/portfolio-context.ts
git commit -m "feat(frontend): add portfolio-context helper functions"
```

---

## Task 3: Enriched Detail Pane (Portfolio Context + Technicals)

**Files:**
- Modify: `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx`

> **Note:** `formatCurrency` and `fmtDate` are already defined/imported in this file (lines 9 and 18–21 respectively). Do not re-define them.

Insert **Portfolio Context** section between the Classification section (ends line 312) and Health section (starts line 314). Insert **Technicals** section between Portfolio Context and Health.

- [ ] **Step 1: Add imports**

At the top of `portfolio-tab.tsx`, after the existing imports, add:

```typescript
import {
  computePortfolioWeight,
  computeSectorWeight,
  computeIncomeWeight,
  computeRankByValue,
  computeRankByIncome,
  formatSmaDeviation,
  rsiLabel,
} from "@/lib/portfolio-context";
```

- [ ] **Step 2: Add Portfolio Context + Technicals sections after Classification**

Find the end of the Classification section in the detail pane:

```tsx
          {(selected.sector || selected.industry) && (
            <section>
              <SectionTitle label="Classification" />
              <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
                <DetailRow label="Asset Class" value={selected.asset_type ?? "—"} />
                <DetailRow label="Sector" value={selected.sector ?? "—"} />
                {selected.industry && <DetailRow label="Industry" value={selected.industry} />}
              </div>
            </section>
          )}
```

Replace with:

```tsx
          {(selected.sector || selected.industry) && (
            <section>
              <SectionTitle label="Classification" />
              <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
                <DetailRow label="Asset Class" value={selected.asset_type ?? "—"} />
                <DetailRow label="Sector" value={selected.sector ?? "—"} />
                {selected.industry && <DetailRow label="Industry" value={selected.industry} />}
              </div>
            </section>
          )}

          {/* Portfolio Context */}
          {(() => {
            const portWeight = computePortfolioWeight(selected, positions);
            const sectWeight = computeSectorWeight(selected, positions);
            const incomeWeight = computeIncomeWeight(selected, positions);
            const rankValue = computeRankByValue(selected, positions);
            const rankIncome = computeRankByIncome(selected, positions);
            const n = positions.length;
            const sectOver = sectWeight != null && sectWeight > 30;
            return (
              <section>
                <SectionTitle label="Portfolio Context" />
                <div className="grid grid-cols-2 gap-y-2.5 gap-x-3 mb-3">
                  <DetailRow label="Portfolio Weight" value={portWeight != null ? `${portWeight.toFixed(1)}%` : "—"} />
                  <DetailRow
                    label="Sector Weight"
                    value={sectWeight != null ? `${sectWeight.toFixed(1)}%` : "—"}
                    className={sectOver ? "text-amber-400" : undefined}
                  />
                  <DetailRow label="Income Weight" value={incomeWeight != null ? `${incomeWeight.toFixed(1)}%` : "—"} />
                  <DetailRow label="Rank by Value" value={rankValue != null ? `#${rankValue} of ${n}` : "—"} className="text-muted-foreground" />
                  <DetailRow label="Rank by Income" value={rankIncome != null ? `#${rankIncome} of ${n}` : "—"} className="text-muted-foreground" />
                </div>
                {portWeight != null && (
                  <div className="space-y-2">
                    <div>
                      <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
                        <span>Portfolio</span><span>{portWeight.toFixed(1)}%</span>
                      </div>
                      <div className="h-[5px] rounded-full bg-border overflow-hidden">
                        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.min(portWeight, 100)}%` }} />
                      </div>
                    </div>
                    {sectWeight != null && (
                      <div>
                        <div className="flex justify-between text-[10px] mb-0.5">
                          <span className="text-muted-foreground">Sector ({selected.sector})</span>
                          <span className={sectOver ? "text-amber-400" : "text-muted-foreground"}>{sectWeight.toFixed(1)}%</span>
                        </div>
                        <div className="h-[5px] rounded-full bg-border overflow-hidden">
                          <div
                            className={`h-full rounded-full ${sectOver ? "bg-amber-400" : "bg-green-500"}`}
                            style={{ width: `${Math.min(sectWeight, 100)}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </section>
            );
          })()}

          {/* Technicals */}
          {(selected.sma_50 != null || selected.sma_200 != null || selected.rsi_14d != null || selected.week52_low != null) && (
            <section>
              <SectionTitle label="Technicals" />
              <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
                {selected.sma_50 != null && (
                  <>
                    <DetailRow
                      label="vs SMA-50"
                      value={formatSmaDeviation(selected.market_price, selected.sma_50) ?? "—"}
                      className={(selected.market_price ?? 0) >= selected.sma_50 ? "text-green-400" : "text-red-400"}
                    />
                  </>
                )}
                {selected.sma_200 != null && (
                  <>
                    <DetailRow
                      label="vs SMA-200"
                      value={formatSmaDeviation(selected.market_price, selected.sma_200) ?? "—"}
                      className={(selected.market_price ?? 0) >= selected.sma_200 ? "text-green-400" : "text-red-400"}
                    />
                  </>
                )}
                {selected.rsi_14d != null && (
                  <div className="col-span-2">
                    <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/80 mb-0.5">RSI (14d)</div>
                    <div className="text-sm font-semibold">
                      {selected.rsi_14d.toFixed(0)}{" "}
                      <span className={`text-xs font-normal ${
                        rsiLabel(selected.rsi_14d) === "oversold" ? "text-green-400" :
                        rsiLabel(selected.rsi_14d) === "overbought" ? "text-red-400" :
                        "text-muted-foreground"
                      }`}>
                        {rsiLabel(selected.rsi_14d)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
              {selected.week52_low != null && selected.week52_high != null && selected.market_price != null && (
                <div className="mt-3">
                  <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
                    <span>{formatCurrency(selected.week52_low)}</span>
                    <span className="font-semibold text-foreground">{formatCurrency(selected.market_price)}</span>
                    <span>{formatCurrency(selected.week52_high)}</span>
                  </div>
                  <div className="h-[5px] rounded-full bg-border relative overflow-visible">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(((selected.market_price - selected.week52_low) / (selected.week52_high - selected.week52_low)) * 100, 100)}%`,
                        background: "linear-gradient(to right, #10b981, #6366f1)",
                      }}
                    />
                    <div
                      className="absolute top-[-3px] w-[2px] h-[11px] bg-foreground rounded-sm"
                      style={{
                        left: `${Math.min(((selected.market_price - selected.week52_low) / (selected.week52_high - selected.week52_low)) * 100, 100)}%`,
                      }}
                    />
                  </div>
                  <div className="text-[10px] text-muted-foreground text-center mt-0.5">52-week range</div>
                </div>
              )}
            </section>
          )}
```

- [ ] **Step 3: TypeScript check**

```bash
cd src/frontend && npx tsc --noEmit
```
Expected: no new errors

- [ ] **Step 4: Visual smoke test**

Start dev server (`npm run dev` in `src/frontend`), open a portfolio, click a position. Verify:
- Portfolio Context section appears between Classification and Health
- Weight bars render (indigo for portfolio, green/amber for sector)
- Technicals section appears with SMA deviation, RSI, 52-week range bar
- Null fields show "—" without error

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx
git commit -m "feat(frontend): add Portfolio Context and Technicals to position detail pane"
```

---

## Task 4: Manage Positions Panel

**Files:**
- Modify: `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx`

Add a collapsible Manage Positions panel above the DataTable. The panel holds an "Add Position" form and an inline-editable positions table.

- [ ] **Step 1: Add state variables**

Inside `PortfolioTab`, after the existing `useState` declarations (after line 44), add:

```typescript
  // Manage Positions panel state
  const [manageOpen, setManageOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(`manage-positions-${portfolioId}`) === "true";
  });
  const [addForm, setAddForm] = useState({ symbol: "", shares: "", avgCost: "", acquiredDate: "" });
  const [addError, setAddError] = useState<string | null>(null);
  const [addPending, setAddPending] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ shares: "", avgCost: "", acquiredDate: "" });
  const [editError, setEditError] = useState<string | null>(null);
  const [editPending, setEditPending] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [removePending, setRemovePending] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
```

- [ ] **Step 2: Add helper functions (refreshPositions, triggerRefresh, showToast)**

After the state declarations, add these helper functions:

```typescript
  function showToast(msg: string) {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4000);
  }

  function triggerRefresh() {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    // fire-and-forget background score refresh
    fetch(`${API_BASE_URL}/broker/portfolios/${portfolioId}/refresh`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    }).catch(() => {/* swallow */});
  }

  function refreshPositions() {
    // Use the Next.js proxy route (not API_BASE_URL directly — auth is handled server-side)
    fetch(`/api/portfolios/${portfolioId}/positions`)
      .then(res => res.ok ? res.json() : Promise.reject())
      .then(data => setPositions(data))
      .catch(() => {/* swallow */});
  }
```

- [ ] **Step 3: Add handleAdd function**

```typescript
  async function handleAdd() {
    setAddError(null);
    setAddPending(true);
    try {
      const body: Record<string, unknown> = {
        symbol: addForm.symbol.toUpperCase().trim(),
        shares: parseFloat(addForm.shares),
        cost_basis: parseFloat(addForm.avgCost),
      };
      if (addForm.acquiredDate) body.acquired_date = addForm.acquiredDate;
      const res = await fetch(`/api/portfolios/${portfolioId}/positions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.status === 409) {
        setAddError("Position already exists — use Edit to update shares");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setAddForm({ symbol: "", shares: "", avgCost: "", acquiredDate: "" });
      showToast("Saving… scores will update shortly.");
      triggerRefresh();
      setTimeout(refreshPositions, 4000);
    } catch {
      setAddError("Failed to add position. Please try again.");
    } finally {
      setAddPending(false);
    }
  }
```

- [ ] **Step 4: Add handleSave and handleDelete functions**

```typescript
  async function handleSave(posId: string) {
    setEditError(null);
    setEditPending(true);
    try {
      const body: Record<string, unknown> = {
        quantity: parseFloat(editForm.shares),
        avg_cost_basis: parseFloat(editForm.avgCost),
      };
      if (editForm.acquiredDate) body.acquired_date = editForm.acquiredDate;
      const res = await fetch(`/api/positions/${posId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setEditingId(null);
      showToast("Saving… scores will update shortly.");
      triggerRefresh();
      setTimeout(refreshPositions, 4000);
    } catch {
      setEditError("Failed to save changes. Please try again.");
    } finally {
      setEditPending(false);
    }
  }

  async function handleDelete(posId: string) {
    setRemovePending(true);
    try {
      const res = await fetch(`/api/positions/${posId}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRemovingId(null);
      setPositions(prev => prev.filter(p => p.id !== posId));
      showToast("Saving… scores will update shortly.");
      triggerRefresh();
      setTimeout(refreshPositions, 4000);
    } catch {
      // leave removingId set so user can retry
    } finally {
      setRemovePending(false);
    }
  }
```

- [ ] **Step 5: Add toggle with localStorage persistence**

```typescript
  function toggleManageOpen() {
    const next = !manageOpen;
    setManageOpen(next);
    if (typeof window !== "undefined") {
      localStorage.setItem(`manage-positions-${portfolioId}`, String(next));
    }
  }
```

- [ ] **Step 6: Add the Manage Positions panel JSX**

In the return statement, find the inner `<div className="flex-1 min-w-0">` (the div wrapping `<DataTable>`). Replace it with:

```tsx
      <div className="flex-1 min-w-0 space-y-3">
        {/* Toast notification */}
        {toastMsg && (
          <div className="bg-indigo-950/60 border border-indigo-500/30 rounded-lg px-3 py-2 text-sm text-indigo-300">
            {toastMsg}
          </div>
        )}

        {/* Manage Positions panel */}
        <div className="border border-border rounded-lg overflow-hidden">
          <button
            onClick={toggleManageOpen}
            className="w-full flex items-center justify-between px-4 py-2.5 bg-card hover:bg-muted/50 transition-colors text-sm font-medium"
          >
            <span className="flex items-center gap-2">
              <span>Manage Positions</span>
              <span className="text-xs text-muted-foreground bg-muted rounded-full px-2 py-0.5">{positions.length}</span>
            </span>
            <span className="text-muted-foreground">{manageOpen ? "▲" : "▼"}</span>
          </button>

          {manageOpen && (
            <div className="border-t border-border">
              {/* Add Position form */}
              <div className="bg-muted/20 px-4 py-3 border-b border-border">
                <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2">Add New Position</div>
                <div className="flex flex-wrap gap-2 items-end">
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-muted-foreground uppercase tracking-wide">Ticker</label>
                    <input
                      className="h-8 px-2 text-sm bg-background border border-border rounded w-24 uppercase placeholder:normal-case placeholder:text-muted-foreground"
                      placeholder="SCHD"
                      value={addForm.symbol}
                      onChange={e => setAddForm(f => ({ ...f, symbol: e.target.value.toUpperCase() }))}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-muted-foreground uppercase tracking-wide">Shares</label>
                    <input
                      className="h-8 px-2 text-sm bg-background border border-border rounded w-24"
                      placeholder="100"
                      type="number"
                      min="0"
                      step="any"
                      value={addForm.shares}
                      onChange={e => setAddForm(f => ({ ...f, shares: e.target.value }))}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-muted-foreground uppercase tracking-wide">Avg Cost / share</label>
                    <input
                      className="h-8 px-2 text-sm bg-background border border-border rounded w-28"
                      placeholder="76.42"
                      type="number"
                      min="0"
                      step="any"
                      value={addForm.avgCost}
                      onChange={e => setAddForm(f => ({ ...f, avgCost: e.target.value }))}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-muted-foreground uppercase tracking-wide">Purchase Date (optional)</label>
                    <input
                      className="h-8 px-2 text-sm bg-background border border-border rounded w-36"
                      type="date"
                      value={addForm.acquiredDate}
                      onChange={e => setAddForm(f => ({ ...f, acquiredDate: e.target.value }))}
                    />
                  </div>
                  <button
                    className="h-8 px-3 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={!addForm.symbol.trim() || !(parseFloat(addForm.shares) > 0) || !(parseFloat(addForm.avgCost) > 0) || addPending}
                    onClick={handleAdd}
                  >
                    {addPending ? "Adding…" : "+ Add Position"}
                  </button>
                </div>
                {addError && <div className="mt-2 text-xs text-red-400">{addError}</div>}
              </div>

              {/* Existing positions table */}
              {positions.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/30 text-[10px] uppercase tracking-wider text-muted-foreground">
                        <th className="text-left px-4 py-2 font-semibold">Ticker</th>
                        <th className="text-right px-3 py-2 font-semibold">Shares</th>
                        <th className="text-right px-3 py-2 font-semibold">Avg Cost</th>
                        <th className="text-right px-3 py-2 font-semibold">Total Cost</th>
                        <th className="text-left px-3 py-2 font-semibold">Date Acquired</th>
                        <th className="text-right px-4 py-2 font-semibold">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map(pos => {
                        const avgCostVal = pos.avg_cost ?? (pos.shares ? pos.cost_basis / pos.shares : 0);
                        const isEditing = editingId === pos.id;
                        const isRemoving = removingId === pos.id;
                        return (
                          <tr
                            key={pos.id}
                            className={`border-b border-border last:border-0 ${isEditing ? "bg-indigo-950/20" : "hover:bg-muted/20"}`}
                          >
                            <td className="px-4 py-2 font-mono font-bold text-foreground">{pos.symbol}</td>
                            <td className="px-3 py-2 text-right">
                              {isEditing ? (
                                <input
                                  className="h-7 px-2 text-sm bg-background border border-border rounded w-20 text-right"
                                  type="number" min="0" step="any"
                                  value={editForm.shares}
                                  onChange={e => setEditForm(f => ({ ...f, shares: e.target.value }))}
                                />
                              ) : (
                                pos.shares?.toLocaleString() ?? "—"
                              )}
                            </td>
                            <td className="px-3 py-2 text-right">
                              {isEditing ? (
                                <input
                                  className="h-7 px-2 text-sm bg-background border border-border rounded w-24 text-right"
                                  type="number" min="0" step="any"
                                  value={editForm.avgCost}
                                  onChange={e => setEditForm(f => ({ ...f, avgCost: e.target.value }))}
                                />
                              ) : (
                                formatCurrency(avgCostVal)
                              )}
                            </td>
                            <td className="px-3 py-2 text-right text-muted-foreground">
                              {formatCurrency(pos.cost_basis)}
                            </td>
                            <td className="px-3 py-2">
                              {isEditing ? (
                                <input
                                  className="h-7 px-2 text-sm bg-background border border-border rounded w-32"
                                  type="date"
                                  value={editForm.acquiredDate}
                                  onChange={e => setEditForm(f => ({ ...f, acquiredDate: e.target.value }))}
                                />
                              ) : (
                                <span className="text-muted-foreground">{pos.acquired_date ? fmtDate(pos.acquired_date) : "—"}</span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-right">
                              {isRemoving ? (
                                <span className="text-xs">
                                  Remove {pos.symbol}?{" "}
                                  <button
                                    className="text-red-400 hover:text-red-300 font-semibold mr-2 disabled:opacity-50"
                                    disabled={removePending}
                                    onClick={() => handleDelete(pos.id)}
                                  >
                                    {removePending ? "…" : "Confirm"}
                                  </button>
                                  <button className="text-muted-foreground hover:text-foreground" onClick={() => setRemovingId(null)}>
                                    Cancel
                                  </button>
                                </span>
                              ) : isEditing ? (
                                <span className="text-xs">
                                  <button
                                    className="text-indigo-400 hover:text-indigo-300 font-semibold mr-2 disabled:opacity-50"
                                    disabled={editPending}
                                    onClick={() => handleSave(pos.id)}
                                  >
                                    {editPending ? "Saving…" : "Save"}
                                  </button>
                                  <button className="text-muted-foreground hover:text-foreground" onClick={() => setEditingId(null)}>
                                    Cancel
                                  </button>
                                  {editError && <span className="ml-2 text-red-400">{editError}</span>}
                                </span>
                              ) : (
                                <span className="text-xs">
                                  <button
                                    className="text-indigo-400 hover:text-indigo-300 mr-3"
                                    onClick={() => {
                                      setEditingId(pos.id);
                                      setRemovingId(null); // cancel any pending remove on another row
                                      setEditError(null);
                                      setEditForm({
                                        shares: String(pos.shares ?? ""),
                                        avgCost: String(avgCostVal.toFixed(2)),
                                        acquiredDate: pos.acquired_date ?? "",
                                      });
                                    }}
                                  >
                                    Edit
                                  </button>
                                  <button
                                    className="text-red-400 hover:text-red-300"
                                    onClick={() => { setRemovingId(pos.id); setEditingId(null); }}
                                  >
                                    Remove
                                  </button>
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="px-4 py-3 text-sm text-muted-foreground italic">No positions yet — use the form above to add one.</div>
              )}
            </div>
          )}
        </div>

        <DataTable
          columns={columns}
          data={positions}
          storageKey={`portfolio-tab-${portfolioId}`}
          enableRowSelection
          onRowClick={(row) =>
            setSelected((s) => (s?.symbol === row.symbol ? null : row))
          }
          frozenColumns={1}
        />
      </div>
```

- [ ] **Step 7: TypeScript check**

```bash
cd src/frontend && npx tsc --noEmit
```
Expected: no new errors

- [ ] **Step 8: Visual smoke test**

Open portfolio page in dev server. Verify:
- "Manage Positions" header bar visible above the holdings table
- Click header toggles panel open/collapse (state persists on reload)
- Position count badge shows correct number
- Add form: disabled until symbol + shares + avgCost filled
- Edit button puts row into edit mode; Save/Cancel work; only one row editable at a time
- Remove shows inline confirmation; Confirm deletes row; Cancel dismisses
- Toast notification appears after any mutation
- No console errors

- [ ] **Step 9: Commit**

```bash
git add src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx
git commit -m "feat(frontend): add collapsible Manage Positions panel with inline add/edit/remove"
```

---

## Final Verification

- [ ] **TypeScript clean build**

```bash
cd src/frontend && npx tsc --noEmit
```
Expected: zero errors

- [ ] **Lint**

```bash
cd src/frontend && npm run lint
```
Expected: no new warnings or errors

- [ ] **End-to-end smoke test checklist**

1. Open a portfolio page
2. Manage Positions panel collapses/expands and persists state
3. Add a new position → row appears in DataTable + toast shown
4. Edit a position's shares → DataTable updates after toast delay
5. Remove a position → row disappears immediately
6. Click a position row → detail pane opens
7. Portfolio Context section shows weight bars and ranks
8. Sector bar turns amber if sector weight > 30%
9. Technicals section shows SMA deviations, RSI with label, 52-week range bar
10. Fields with null data show "—" without errors
