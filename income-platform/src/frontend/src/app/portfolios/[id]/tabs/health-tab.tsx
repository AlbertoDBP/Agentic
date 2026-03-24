"use client";
import { useMemo, useState, useEffect } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import { ColHeader } from "@/components/help-tooltip";
import { HHS_HELP } from "@/lib/help-content";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import type { Position } from "@/lib/types";

// Factor pillar mapping
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

interface HealthTabProps { portfolioId: string; }

export function HealthTab({ portfolioId }: HealthTabProps) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(false);
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
      .then((r) => r.ok ? r.json() as Promise<Position[]> : Promise.resolve([]))
      .then((data) => { setPositions(data); setLoading(false); })
      .catch(() => { setError("Failed to load positions."); setLoading(false); });
  }, [portfolioId]);

  const filtered = useMemo(
    () => positions.filter((p) => p.portfolio_id === portfolioId),
    [positions, portfolioId]
  );

  const columns: ColumnDef<Position>[] = [
    {
      accessorKey: "symbol",
      header: () => <ColHeader label="Ticker" helpKey="hhs_score" helpMap={HHS_HELP} />,
      cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />,
    },
    { accessorKey: "asset_type", header: "Class" },
    {
      accessorKey: "hhs_score",
      header: () => <ColHeader label="HHS" helpKey="hhs_score" helpMap={HHS_HELP} />,
      cell: ({ row }) => <HhsBadge status={row.original.hhs_status} score={row.original.hhs_score} />,
    },
    {
      accessorKey: "income_pillar_score",
      header: () => <ColHeader label="Income" helpKey="income_pillar" helpMap={HHS_HELP} />,
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(0)}/100` : "—",
    },
    {
      accessorKey: "durability_pillar_score",
      header: () => <ColHeader label="Durability" helpKey="durability_pillar" helpMap={HHS_HELP} />,
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(0)}/100` : "—",
    },
    {
      accessorKey: "ies_score",
      header: () => <ColHeader label="IES" helpKey="ies_score" helpMap={HHS_HELP} />,
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
  ];

  if (loading) {
    return <div className="text-muted-foreground text-sm p-4">Loading...</div>;
  }

  if (error) {
    return <div className="text-red-400 text-sm p-4 bg-red-950/30 border border-red-900/50 rounded">{error}</div>;
  }

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
        <div className="w-[360px] flex-shrink-0 bg-card border border-border rounded-lg p-4 text-sm overflow-y-auto max-h-[calc(100vh-200px)] space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-bold">{selected.symbol}</span>
            <button
              onClick={() => setSelected(null)}
              className="text-muted-foreground text-xs"
              aria-label="Close detail pane"
            >
              &#x2715;
            </button>
          </div>

          {/* HHS Breakdown */}
          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">HHS Breakdown</div>
            {selected.hhs_score != null ? (
              <>
                <HhsBadge status={selected.hhs_status} score={selected.hhs_score} />
                <div className="text-[0.6rem] text-muted-foreground mt-1">
                  HHS = (Income &times; {((selected.income_weight ?? 0.5) * 100).toFixed(0)}%) + (Durability &times; {((selected.durability_weight ?? 0.5) * 100).toFixed(0)}%)
                </div>
                <div className="mt-2 space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-green-400">Income</span>
                    <span>{selected.income_pillar_score?.toFixed(0) ?? "—"}/100</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-blue-400">Durability</span>
                    <span>{selected.durability_pillar_score?.toFixed(0) ?? "—"}/100</span>
                  </div>
                </div>
                {selected.unsafe_flag && (
                  <div className="mt-2 bg-red-950/40 border border-red-900/50 rounded p-2 text-xs text-red-400">
                    UNSAFE — Durability at or below safety threshold ({selected.unsafe_threshold ?? 20})
                  </div>
                )}
              </>
            ) : (
              <div className="text-muted-foreground text-xs italic">
                Rescore to see HHS
              </div>
            )}
          </section>

          {/* Factor breakdown */}
          {selected.factor_details && Object.keys(selected.factor_details).length > 0 && (
            <section>
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Factor Breakdown</div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-muted-foreground text-[0.6rem] uppercase border-b border-border">
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
                            <span className={cn("text-[0.55rem] font-bold px-1 rounded", PILLAR_COLOR[pillar])}>{pillar}</span>
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
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">IES — Entry Score</div>
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
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Commentary</div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {selected.hhs_commentary}
              </p>
            </section>
          )}

          {/* Quality gate */}
          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Quality Gate</div>
            <div className={cn("text-xs font-medium", selected.quality_gate_status === "PASS" ? "text-green-400" : "text-amber-400")}>
              {selected.quality_gate_status ?? "PASS"}
            </div>
            {selected.quality_gate_reasons?.length ? (
              <ul className="mt-1 space-y-0.5">
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
