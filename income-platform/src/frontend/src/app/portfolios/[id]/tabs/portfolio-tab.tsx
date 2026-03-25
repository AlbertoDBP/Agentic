"use client";
import { useState, useEffect } from "react";
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

interface PortfolioTabProps {
  portfolioId: string;
}

function fmtDate(v: string | null | undefined) {
  if (!v) return "—";
  try { return formatDate(v); } catch { return v; }
}

function DetailRow({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground mb-0.5">{label}</div>
      <div className={cn("text-sm font-medium", className)}>{value}</div>
    </div>
  );
}

function SectionTitle({ label }: { label: string }) {
  return <div className="text-xs font-semibold uppercase tracking-wide text-blue-400 mb-2">{label}</div>;
}

export function PortfolioTab({ portfolioId }: PortfolioTabProps) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Position | null>(null);

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
  }, [portfolioId]);

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
      <div className="flex-1 min-w-0">
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
