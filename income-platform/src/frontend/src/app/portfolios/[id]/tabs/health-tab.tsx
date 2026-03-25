"use client";
import { useMemo, useState, useEffect } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import { ColHeader } from "@/components/help-tooltip";
import { HHS_HELP, HOLDINGS_HELP } from "@/lib/help-content";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import type { Position } from "@/lib/types";

const FACTOR_PILLAR: Record<string, "INC" | "DUR" | "IES"> = {
  yield_vs_market: "INC", payout_sustainability: "INC", fcf_coverage: "INC",
  debt_safety: "DUR", dividend_consistency: "DUR", volatility_score: "DUR",
  price_momentum: "IES", price_range_position: "IES",
};
const PILLAR_COLOR: Record<string, string> = {
  INC: "text-green-400 bg-green-950/40",
  DUR: "text-blue-400 bg-blue-950/40",
  IES: "text-slate-400 bg-slate-800/40",
};

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

interface HealthTabProps { portfolioId: string; }

export function HealthTab({ portfolioId }: HealthTabProps) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Position | null>(null);

  useEffect(() => {
    if (!portfolioId) return;
    setLoading(true);
    setError(null);
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    fetch(`${API_BASE_URL}/api/portfolios/${portfolioId}/positions`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<Position[]>;
      })
      .then(data => { setPositions(data); setLoading(false); })
      .catch(err => { setError(err.message); setLoading(false); });
  }, [portfolioId]);

  const filtered = useMemo(
    () => positions.filter((p) => p.portfolio_id === portfolioId),
    [positions, portfolioId]
  );

  const columns: ColumnDef<Position>[] = [
    {
      accessorKey: "symbol",
      header: () => <ColHeader label="Ticker" helpKey="symbol" helpMap={HOLDINGS_HELP} />,
      meta: { label: "Ticker" },
      cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />,
    },
    { accessorKey: "asset_type", header: "Class" },
    {
      accessorKey: "hhs_score",
      header: () => <ColHeader label="HHS" helpKey="hhs_score" helpMap={HHS_HELP} />,
      meta: { label: "HHS Score" },
      cell: ({ row }) => <HhsBadge status={row.original.hhs_status} score={row.original.hhs_score} />,
    },
    {
      accessorKey: "income_pillar_score",
      header: () => <ColHeader label="Income" helpKey="income_pillar" helpMap={HHS_HELP} />,
      meta: { label: "Income Pillar" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(0)}/100` : "—",
    },
    {
      accessorKey: "durability_pillar_score",
      header: () => <ColHeader label="Durability" helpKey="durability_pillar" helpMap={HHS_HELP} />,
      meta: { label: "Durability Pillar" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(0)}/100` : "—",
    },
    {
      accessorKey: "ies_score",
      header: () => <ColHeader label="IES" helpKey="ies_score" helpMap={HHS_HELP} />,
      meta: { label: "IES Entry Score" },
      cell: ({ row }) => row.original.ies_calculated
        ? `${row.original.ies_score?.toFixed(0)}/100`
        : <span className="text-muted-foreground text-xs">{row.original.ies_blocked_reason ?? "—"}</span>,
    },
    {
      accessorKey: "quality_gate_status",
      header: "Gate",
      cell: ({ getValue }) => {
        const v = getValue() as string | null;
        return <span className={cn("text-xs font-medium", v === "PASS" ? "text-green-400" : "text-amber-400")}>{v ?? "—"}</span>;
      },
    },
    // ── Hidden by default ──
    {
      accessorKey: "unsafe_flag",
      header: "Unsafe",
      meta: { defaultHidden: true, label: "Unsafe Flag" },
      cell: ({ getValue }) => {
        const v = getValue() as boolean | null;
        if (v == null) return "—";
        return <span className={v ? "text-red-400 font-medium" : "text-green-400"}>{v ? "UNSAFE" : "OK"}</span>;
      },
    },
    {
      accessorKey: "unsafe_threshold",
      header: "Safety Floor",
      meta: { defaultHidden: true, label: "Unsafe Threshold" },
      cell: ({ getValue }) => getValue() != null ? `${getValue()}` : "—",
    },
    {
      accessorKey: "income_weight",
      header: "Inc. Wt",
      meta: { defaultHidden: true, label: "Income Weight" },
      cell: ({ getValue }) => getValue() != null ? `${((getValue() as number) * 100).toFixed(0)}%` : "—",
    },
    {
      accessorKey: "durability_weight",
      header: "Dur. Wt",
      meta: { defaultHidden: true, label: "Durability Weight" },
      cell: ({ getValue }) => getValue() != null ? `${((getValue() as number) * 100).toFixed(0)}%` : "—",
    },
    {
      accessorKey: "ies_calculated",
      header: "IES Calc",
      meta: { defaultHidden: true, label: "IES Calculated" },
      cell: ({ getValue }) => {
        const v = getValue() as boolean | undefined;
        return <span className={v ? "text-green-400" : "text-muted-foreground"}>{v ? "Yes" : "No"}</span>;
      },
    },
    {
      accessorKey: "ies_blocked_reason",
      header: "IES Block",
      meta: { defaultHidden: true, label: "IES Blocked Reason" },
      cell: ({ getValue }) => (getValue() as string | null) ?? "—",
    },
    {
      accessorKey: "chowder_number",
      header: "Chowder",
      meta: { defaultHidden: true, label: "Chowder Number" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(1)}` : "—",
    },
    {
      accessorKey: "hhs_commentary",
      header: "Commentary",
      meta: { defaultHidden: true, label: "HHS Commentary" },
      cell: ({ getValue }) => {
        const v = getValue() as string | null;
        return v ? <span className="text-xs text-muted-foreground">{v.slice(0, 60)}{v.length > 60 ? "…" : ""}</span> : "—";
      },
    },
  ];

  if (loading) return <div className="text-muted-foreground text-sm p-4">Loading...</div>;
  if (error) return <div className="text-red-400 text-sm p-4 bg-red-950/30 border border-red-900/50 rounded">{error}</div>;

  return (
    <div className="flex gap-3">
      <div className="flex-1 min-w-0">
        <DataTable
          columns={columns}
          data={filtered}
          storageKey={`health-tab-${portfolioId}`}
          enableRowSelection
          onRowClick={(row) => setSelected((s) => (s?.symbol === row.symbol ? null : row))}
          frozenColumns={1}
        />
      </div>

      {selected && (
        <div className="w-85 shrink-0 bg-card border border-border rounded-lg p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-200px)]">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-bold text-base">{selected.symbol}</span>
              <div className="text-xs text-muted-foreground mt-0.5">{selected.asset_type}</div>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="text-muted-foreground hover:text-foreground text-sm px-1"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {/* HHS Breakdown */}
          <section>
            <SectionTitle label="HHS Breakdown" />
            {selected.hhs_score != null ? (
              <>
                <HhsBadge status={selected.hhs_status} score={selected.hhs_score} />
                <div className="text-xs text-muted-foreground mt-1.5">
                  HHS = (Income × {((selected.income_weight ?? 0.5) * 100).toFixed(0)}%) + (Durability × {((selected.durability_weight ?? 0.5) * 100).toFixed(0)}%)
                </div>
                <div className="mt-2.5 grid grid-cols-2 gap-y-2.5 gap-x-3">
                  <DetailRow label="Income Pillar" value={selected.income_pillar_score != null ? `${selected.income_pillar_score.toFixed(0)}/100` : "—"} />
                  <DetailRow label="Durability Pillar" value={selected.durability_pillar_score != null ? `${selected.durability_pillar_score.toFixed(0)}/100` : "—"} />
                </div>
                {selected.unsafe_flag && (
                  <div className="mt-2 bg-red-950/40 border border-red-900/50 rounded p-2 text-xs text-red-400">
                    UNSAFE — Durability at or below safety threshold ({selected.unsafe_threshold ?? 20})
                  </div>
                )}
              </>
            ) : (
              <div className="text-muted-foreground text-xs italic">Rescore to see HHS</div>
            )}
          </section>

          {/* Factor breakdown */}
          {selected.factor_details && Object.keys(selected.factor_details).length > 0 && (
            <section>
              <SectionTitle label="Factor Breakdown" />
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-muted-foreground text-[0.65rem] uppercase border-b border-border">
                    <th className="text-left pb-1">Factor</th>
                    <th className="text-center pb-1">Pillar</th>
                    <th className="text-right pb-1">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(selected.factor_details)
                    .filter(([k]) => !["chowder_number", "chowder_signal"].includes(k))
                    .map(([key, val]) => {
                      const pillar = FACTOR_PILLAR[key] ?? "INC";
                      return (
                        <tr key={key} className={cn("border-b border-border/30", pillar === "IES" && "opacity-60")}>
                          <td className="py-1 pr-2">{key.replace(/_/g, " ")}</td>
                          <td className="py-1 text-center">
                            <span className={cn("text-[0.6rem] font-bold px-1 rounded", PILLAR_COLOR[pillar])}>{pillar}</span>
                          </td>
                          <td className="py-1 text-right text-muted-foreground">
                            {val?.score?.toFixed(1) ?? "—"}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </section>
          )}

          {/* IES */}
          <section>
            <SectionTitle label="IES — Entry Score" />
            {selected.ies_calculated ? (
              <div className="text-sm font-bold">{selected.ies_score?.toFixed(0)}/100</div>
            ) : (
              <div className="text-muted-foreground text-xs">
                Blocked: {selected.ies_blocked_reason ?? "—"}
              </div>
            )}
          </section>

          {/* Commentary */}
          {selected.hhs_commentary && (
            <section>
              <SectionTitle label="Commentary" />
              <p className="text-xs text-muted-foreground leading-relaxed">{selected.hhs_commentary}</p>
            </section>
          )}

          {/* Quality Gate */}
          <section>
            <SectionTitle label="Quality Gate" />
            <div className={cn("text-sm font-medium", selected.quality_gate_status === "PASS" ? "text-green-400" : "text-amber-400")}>
              {selected.quality_gate_status ?? "—"}
            </div>
            {selected.quality_gate_reasons?.length ? (
              <ul className="mt-1.5 space-y-1">
                {selected.quality_gate_reasons.map((r, i) => (
                  <li key={i} className="text-xs text-muted-foreground">· {r}</li>
                ))}
              </ul>
            ) : null}
          </section>
        </div>
      )}
    </div>
  );
}
