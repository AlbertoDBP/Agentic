"use client";
import { useState, useEffect, useMemo, useRef } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import { ColHeader } from "@/components/help-tooltip";
import { HHS_HELP, HOLDINGS_HELP } from "@/lib/help-content";
import { formatCurrency, formatDate, scoreTextColor } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import type { Position } from "@/lib/types";
import {
  computePortfolioWeight,
  computeSectorWeight,
  computeIncomeWeight,
  computeRankByValue,
  computeRankByIncome,
  formatSmaDeviation,
  rsiLabel,
} from "@/lib/portfolio-context";

interface PortfolioTabProps {
  portfolioId: string;
  refreshKey?: number;
}

function fmtDate(v: string | null | undefined) {
  if (!v) return "—";
  try { return formatDate(v); } catch { return v; }
}

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

export function PortfolioTab({ portfolioId, refreshKey = 0 }: PortfolioTabProps) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Position | null>(null);

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
  const timeoutIdsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    return () => {
      timeoutIdsRef.current.forEach(clearTimeout);
    };
  }, []);

  useEffect(() => {
    if (!portfolioId) return;
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    setLoading(true);
    setFetchError(null);
    fetch(`${API_BASE_URL}/api/portfolios/${portfolioId}/positions`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => { setPositions(data); setLoading(false); })
      .catch(err => { setFetchError(err.message); setLoading(false); });
  }, [portfolioId, refreshKey]);

  const portfolioContext = useMemo(() => {
    if (!selected) return null;
    return {
      portWeight: computePortfolioWeight(selected, positions),
      sectWeight: computeSectorWeight(selected, positions),
      incomeWeight: computeIncomeWeight(selected, positions),
      rankValue: computeRankByValue(selected, positions),
      rankIncome: computeRankByIncome(selected, positions),
      n: positions.length,
    };
  }, [selected, positions]);

  function showToast(msg: string) {
    setToastMsg(msg);
    timeoutIdsRef.current.push(setTimeout(() => setToastMsg(null), 4000));
  }

  function triggerRefresh() {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    fetch(`${API_BASE_URL}/broker/portfolios/${portfolioId}/refresh`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    }).catch(() => {});
  }

  function refreshPositions() {
    // Use the Next.js proxy route (auth handled server-side)
    fetch(`/api/portfolios/${portfolioId}/positions`)
      .then(res => res.ok ? res.json() : Promise.reject())
      .then(data => setPositions(data))
      .catch(() => {});
  }

  async function handleAdd() {
    setAddError(null);
    setAddPending(true);
    const sharesNum = parseFloat(addForm.shares);
    const avgCostNum = parseFloat(addForm.avgCost);
    if (!Number.isFinite(sharesNum) || sharesNum <= 0 || !Number.isFinite(avgCostNum) || avgCostNum <= 0) {
      setAddError("Please enter valid shares and cost values.");
      setAddPending(false);
      return;
    }
    try {
      const body: Record<string, unknown> = {
        symbol: addForm.symbol.toUpperCase().trim(),
        shares: sharesNum,
        cost_basis: sharesNum * avgCostNum,
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
      timeoutIdsRef.current.push(setTimeout(refreshPositions, 4000));
    } catch {
      setAddError("Failed to add position. Please try again.");
    } finally {
      setAddPending(false);
    }
  }

  async function handleSave(posId: string) {
    setEditError(null);
    setEditPending(true);
    const qtyNum = parseFloat(editForm.shares);
    const avgCbNum = parseFloat(editForm.avgCost);
    if (!Number.isFinite(qtyNum) || qtyNum <= 0 || !Number.isFinite(avgCbNum) || avgCbNum <= 0) {
      setEditError("Please enter valid shares and cost values.");
      setEditPending(false);
      return;
    }
    try {
      const body: Record<string, unknown> = {
        quantity: qtyNum,
        avg_cost_basis: avgCbNum,
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
      timeoutIdsRef.current.push(setTimeout(refreshPositions, 4000));
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
      timeoutIdsRef.current.push(setTimeout(refreshPositions, 4000));
    } catch {
      // leave removingId set so user can retry
    } finally {
      setRemovePending(false);
    }
  }

  function toggleManageOpen() {
    const next = !manageOpen;
    setManageOpen(next);
    if (typeof window !== "undefined") {
      localStorage.setItem(`manage-positions-${portfolioId}`, String(next));
    }
  }

  const columns: ColumnDef<Position>[] = [
    {
      accessorKey: "symbol",
      header: () => <ColHeader label="Ticker" helpKey="symbol" helpMap={HOLDINGS_HELP} />,
      cell: ({ row }) => (
        <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />
      ),
    },
    { accessorKey: "asset_type", header: "Class" },
    { accessorKey: "name", header: "Name" },
    {
      accessorKey: "shares",
      header: "Shares",
      cell: ({ getValue }) => (getValue() as number | null)?.toLocaleString() ?? "—",
    },
    {
      accessorKey: "current_value",
      header: () => <ColHeader label="Mkt Value" helpKey="current_value" helpMap={HOLDINGS_HELP} />,
      meta: { label: "Mkt Value" },
      cell: ({ getValue }) => formatCurrency(getValue() as number),
    },
    {
      accessorKey: "annual_income",
      header: () => <ColHeader label="Ann. Income" helpKey="annual_income" helpMap={HOLDINGS_HELP} />,
      meta: { label: "Ann. Income" },
      cell: ({ getValue }) => formatCurrency(getValue() as number),
    },
    {
      accessorKey: "current_yield",
      header: () => <ColHeader label="Yield" helpKey="current_yield" helpMap={HOLDINGS_HELP} />,
      meta: { label: "Yield" },
      cell: ({ getValue }) =>
        getValue() != null ? `${(getValue() as number).toFixed(2)}%` : "—",
    },
    {
      accessorKey: "hhs_status",
      header: () => <ColHeader label="HHS" helpKey="hhs_score" helpMap={HHS_HELP} />,
      meta: { label: "HHS" },
      cell: ({ row }) => (
        <HhsBadge status={row.original.hhs_status} score={row.original.hhs_score} />
      ),
    },
    // ── Hidden by default — available via Columns picker ──
    {
      accessorKey: "market_price",
      header: "Price",
      meta: { defaultHidden: true, label: "Price" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "avg_cost",
      header: "Avg Cost",
      meta: { defaultHidden: true, label: "Avg Cost" },
      cell: ({ row }) => {
        const v = row.original.avg_cost ?? (row.original.shares ? row.original.cost_basis / row.original.shares : null);
        return v != null ? formatCurrency(v) : "—";
      },
    },
    {
      accessorKey: "cost_basis",
      header: "Cost Basis",
      meta: { defaultHidden: true, label: "Cost Basis" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      id: "unrealized_gl",
      header: "Unr. G/L",
      meta: { defaultHidden: true, label: "Unrealized G/L" },
      accessorFn: (row) => row.current_value - row.cost_basis,
      cell: ({ getValue }) => {
        const v = getValue() as number;
        return <span className={v >= 0 ? "text-green-400" : "text-red-400"}>{v >= 0 ? "+" : ""}{formatCurrency(v)}</span>;
      },
    },
    {
      id: "total_return",
      header: "Total Return",
      meta: { defaultHidden: true, label: "Total Return %" },
      accessorFn: (row) => {
        if (!row.cost_basis) return null;
        return ((row.current_value - row.cost_basis + (row.total_dividends_received ?? 0)) / row.cost_basis) * 100;
      },
      cell: ({ getValue }) => {
        const v = getValue() as number | null;
        if (v == null) return "—";
        return <span className={v >= 0 ? "text-green-400" : "text-red-400"}>{v >= 0 ? "+" : ""}{v.toFixed(1)}%</span>;
      },
    },
    {
      accessorKey: "yield_on_cost",
      header: "YoC",
      meta: { defaultHidden: true, label: "Yield on Cost" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(2)}%` : "—",
    },
    {
      accessorKey: "total_dividends_received",
      header: "Divs Recvd",
      meta: { defaultHidden: true, label: "Total Dividends Received" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "daily_change_pct",
      header: "Daily Chg",
      meta: { defaultHidden: true, label: "Daily Change %" },
      cell: ({ getValue }) => {
        const v = getValue() as number | null;
        if (v == null) return "—";
        return <span className={v >= 0 ? "text-green-400" : "text-red-400"}>{v >= 0 ? "+" : ""}{v.toFixed(2)}%</span>;
      },
    },
    {
      accessorKey: "dividend_frequency",
      header: "Frequency",
      meta: { defaultHidden: true, label: "Dividend Frequency" },
      cell: ({ getValue }) => (getValue() as string | null) ?? "—",
    },
    {
      accessorKey: "ex_div_date",
      header: "Ex-Div",
      meta: { defaultHidden: true, label: "Ex-Dividend Date" },
      cell: ({ getValue }) => fmtDate(getValue() as string | null),
    },
    {
      accessorKey: "pay_date",
      header: "Pay Date",
      meta: { defaultHidden: true, label: "Pay Date" },
      cell: ({ getValue }) => fmtDate(getValue() as string | null),
    },
    {
      accessorKey: "chowder_number",
      header: "Chowder",
      meta: { defaultHidden: true, label: "Chowder Number" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(1)}` : "—",
    },
    {
      accessorKey: "sector",
      header: "Sector",
      meta: { defaultHidden: true, label: "Sector" },
      cell: ({ getValue }) => (getValue() as string | null) ?? "—",
    },
    {
      accessorKey: "industry",
      header: "Industry",
      meta: { defaultHidden: true, label: "Industry" },
      cell: ({ getValue }) => (getValue() as string | null) ?? "—",
    },
    {
      accessorKey: "acquired_date",
      header: "Acquired",
      meta: { defaultHidden: true, label: "Date Acquired" },
      cell: ({ getValue }) => fmtDate(getValue() as string | null),
    },
  ];

  if (loading) return <div className="p-4 text-muted-foreground text-sm animate-pulse">Loading…</div>;
  if (fetchError) return (
    <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-3 text-sm text-red-400">
      Failed to load positions: {fetchError}
    </div>
  );

  const unrealizedGL = selected ? selected.current_value - selected.cost_basis : 0;
  const totalReturn = selected && selected.cost_basis
    ? ((selected.current_value - selected.cost_basis + (selected.total_dividends_received ?? 0)) / selected.cost_basis) * 100
    : null;

  return (
    <div className="flex gap-3">
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

      {selected && (
        <div className="w-85 shrink-0 bg-card border border-border rounded-lg p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-200px)]">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-bold text-base">{selected.symbol}</span>
              {selected.name && <div className="text-xs text-muted-foreground mt-0.5">{selected.name}</div>}
            </div>
            <button
              onClick={() => setSelected(null)}
              className="text-muted-foreground hover:text-foreground text-sm px-1"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          <section>
            <SectionTitle label="Position" />
            <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
              <DetailRow label="Shares" value={selected.shares?.toLocaleString() ?? "—"} />
              <DetailRow label="Avg Cost" value={formatCurrency(selected.avg_cost ?? (selected.shares ? selected.cost_basis / selected.shares : 0))} />
              <DetailRow label="Mkt Price" value={formatCurrency(selected.market_price ?? 0)} />
              <DetailRow label="Mkt Value" value={formatCurrency(selected.current_value)} />
              <DetailRow label="Cost Basis" value={formatCurrency(selected.cost_basis)} />
              <DetailRow
                label="Unrealized G/L"
                value={`${unrealizedGL >= 0 ? "+" : ""}${formatCurrency(unrealizedGL)}`}
                className={unrealizedGL >= 0 ? "text-green-400" : "text-red-400"}
              />
              <DetailRow
                label="Total Return"
                value={totalReturn != null ? `${totalReturn >= 0 ? "+" : ""}${totalReturn.toFixed(1)}%` : "—"}
                className={totalReturn != null ? (totalReturn >= 0 ? "text-green-400" : "text-red-400") : ""}
              />
              <DetailRow label="Divs Received" value={selected.total_dividends_received != null ? formatCurrency(selected.total_dividends_received) : "—"} />
            </div>
          </section>

          <section>
            <SectionTitle label="Income" />
            <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
              <DetailRow label="Annual Income" value={formatCurrency(selected.annual_income)} />
              <DetailRow
                label="Gross Yield"
                value={selected.current_yield != null ? `${selected.current_yield.toFixed(2)}%` : "—"}
              />
              <DetailRow
                label="Yield on Cost"
                value={selected.yield_on_cost != null ? `${selected.yield_on_cost.toFixed(2)}%` : "—"}
              />
              <DetailRow label="Frequency" value={selected.dividend_frequency ?? "—"} />
              <DetailRow label="Ex-Div Date" value={fmtDate(selected.ex_div_date)} />
              <DetailRow label="Pay Date" value={fmtDate(selected.pay_date)} />
              {selected.chowder_number != null && (
                <DetailRow label="Chowder #" value={selected.chowder_number.toFixed(1)} />
              )}
            </div>
          </section>

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
          {portfolioContext && (() => {
            const { portWeight, sectWeight, incomeWeight, rankValue, rankIncome, n } = portfolioContext;
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
              {selected.week52_low != null && selected.week52_high != null && selected.market_price != null && (() => {
                const range52 = (selected.week52_high ?? 0) - (selected.week52_low ?? 0);
                const pricePct52 = range52 > 0
                  ? Math.min(((selected.market_price! - selected.week52_low!) / range52) * 100, 100)
                  : 50;
                return (
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
                          width: `${pricePct52}%`,
                          background: "linear-gradient(to right, #10b981, #6366f1)",
                        }}
                      />
                      <div
                        className="absolute top-[-3px] w-[2px] h-[11px] bg-foreground rounded-sm"
                        style={{
                          left: `${pricePct52}%`,
                        }}
                      />
                    </div>
                    <div className="text-[10px] text-muted-foreground text-center mt-0.5">52-week range</div>
                  </div>
                );
              })()}
            </section>
          )}

          <section>
            <SectionTitle label="Health Summary" />
            {selected.hhs_score != null ? (
              <div className="space-y-2">
                <HhsBadge status={selected.hhs_status} score={selected.hhs_score} />
                <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
                  <DetailRow
                    label="Income Pillar"
                    value={selected.income_pillar_score != null ? `${selected.income_pillar_score.toFixed(0)}/100` : "—"}
                    className={scoreTextColor(selected.income_pillar_score)}
                  />
                  <DetailRow
                    label="Durability Pillar"
                    value={selected.durability_pillar_score != null ? `${selected.durability_pillar_score.toFixed(0)}/100` : "—"}
                    className={scoreTextColor(selected.durability_pillar_score)}
                  />
                </div>
                {selected.unsafe_flag && (
                  <div className="bg-red-950/40 border border-red-900/50 rounded p-2 text-xs text-red-400">
                    UNSAFE — Durability ≤ safety floor ({selected.unsafe_threshold ?? 20})
                  </div>
                )}
              </div>
            ) : (
              <div className="text-muted-foreground text-xs italic">No score — rescore to populate</div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
