"use client";
import { useMemo, useState, useEffect } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import { ColHeader } from "@/components/help-tooltip";
import { HHS_HELP, HOLDINGS_HELP } from "@/lib/help-content";
import { cn, scoreTextColor, scoreBadgeColor } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import type { Position } from "@/lib/types";
import { ScoreBreakdownModal } from "@/components/ScoreBreakdownModal";
import { directionality, DIRECTIONALITY_BAR, DIRECTIONALITY_COLOR, FACTOR_LABEL, PILLAR_FACTORS, PILLAR_LABEL } from "@/lib/score-breakdown";

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

interface HealthTabProps { portfolioId: string; refreshKey?: number; }

export function HealthTab({ portfolioId, refreshKey = 0 }: HealthTabProps) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Position | null>(null);
  const [modalPosition, setModalPosition] = useState<Position | null>(null);

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
  }, [portfolioId, refreshKey]);

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
    {
      accessorKey: "asset_type",
      header: () => <ColHeader label="Class" help="Asset classification: CEF, BDC, REIT, Preferred Stock, etc." />,
      meta: { label: "Class" },
    },
    {
      accessorKey: "hhs_score",
      header: () => <ColHeader label="HHS" helpKey="hhs_score" helpMap={HHS_HELP} />,
      meta: { label: "HHS Score" },
      cell: ({ row }) => (
        <button
          className="cursor-pointer focus:outline-none"
          onClick={(e) => { e.stopPropagation(); setModalPosition(row.original); }}
          title="View factor breakdown"
          aria-label={`View score breakdown for ${row.original.symbol}`}
        >
          <HhsBadge status={row.original.hhs_status} score={row.original.hhs_score} />
        </button>
      ),
    },
    {
      accessorKey: "income_pillar_score",
      header: () => <ColHeader label="Income" helpKey="income_pillar" helpMap={HHS_HELP} />,
      meta: { label: "Income Pillar" },
      cell: ({ getValue }) => {
        const v = getValue() as number | null;
        if (v == null) return <span className="text-muted-foreground">—</span>;
        return <span className={cn("font-medium tabular-nums", scoreTextColor(v))}>{v.toFixed(0)}</span>;
      },
    },
    {
      accessorKey: "durability_pillar_score",
      header: () => <ColHeader label="Durability" helpKey="durability_pillar" helpMap={HHS_HELP} />,
      meta: { label: "Durability Pillar" },
      cell: ({ getValue }) => {
        const v = getValue() as number | null;
        if (v == null) return <span className="text-muted-foreground">—</span>;
        return <span className={cn("font-medium tabular-nums", scoreTextColor(v))}>{v.toFixed(0)}</span>;
      },
    },
    {
      accessorKey: "ies_score",
      header: () => <ColHeader label="IES" helpKey="ies_score" helpMap={HHS_HELP} />,
      meta: { label: "IES Entry Score" },
      cell: ({ row }) => {
        if (!row.original.ies_calculated)
          return <span className="text-muted-foreground text-xs">{row.original.ies_blocked_reason ?? "—"}</span>;
        const v = row.original.ies_score ?? null;
        if (v == null) return <span className="text-muted-foreground">—</span>;
        return <span className={cn("font-medium tabular-nums", scoreTextColor(v))}>{v.toFixed(0)}</span>;
      },
    },
    {
      accessorKey: "quality_gate_status",
      header: () => <ColHeader label="Gate" help="Quality gate determines eligibility for scoring. PASS = all data available and valid." />,
      meta: { label: "Gate" },
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
                <div className="mt-2.5 grid grid-cols-2 gap-2">
                  {selected.income_pillar_score != null && (
                    <div className={cn("rounded p-1.5 text-center border",
                      selected.income_pillar_score >= 70 ? "bg-green-950/40 border-green-800/30" :
                      selected.income_pillar_score >= 50 ? "bg-amber-950/40 border-amber-800/30" : "bg-red-950/40 border-red-800/30"
                    )}>
                      <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Income</div>
                      <div className={cn("text-lg font-bold tabular-nums", scoreTextColor(selected.income_pillar_score))}>
                        {selected.income_pillar_score.toFixed(0)}
                      </div>
                      <div className="text-[9px] text-muted-foreground">/ 100</div>
                    </div>
                  )}
                  {selected.durability_pillar_score != null && (
                    <div className={cn("rounded p-1.5 text-center border",
                      selected.durability_pillar_score >= 70 ? "bg-green-950/40 border-green-800/30" :
                      selected.durability_pillar_score >= 50 ? "bg-amber-950/40 border-amber-800/30" : "bg-red-950/40 border-red-800/30"
                    )}>
                      <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Durability</div>
                      <div className={cn("text-lg font-bold tabular-nums", scoreTextColor(selected.durability_pillar_score))}>
                        {selected.durability_pillar_score.toFixed(0)}
                      </div>
                      <div className="text-[9px] text-muted-foreground">/ 100</div>
                    </div>
                  )}
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
          {selected.factor_details && (
            <section>
              <SectionTitle label="Factor Breakdown" />
              {(["INC", "DUR", "IES"] as const).map((pillar) => {
                const factors = PILLAR_FACTORS[pillar].filter(
                  (k) => selected.factor_details?.[k]
                );
                if (factors.length === 0) return null;
                return (
                  <div key={pillar} className="mb-3">
                    <div className="text-[9px] font-bold uppercase tracking-wide text-muted-foreground/60 mb-1.5">
                      {PILLAR_LABEL[pillar]}
                    </div>
                    <div className="space-y-1.5">
                      {factors.map((k) => {
                        const entry = selected.factor_details![k];
                        if (!entry) return null;
                        const pct = entry.max > 0 ? Math.min(100, (entry.score / entry.max) * 100) : 0;
                        const dir = directionality(entry.score, entry.max);
                        return (
                          <div key={k} className="flex items-center gap-1.5">
                            <div className="w-24 shrink-0 text-[10px] text-muted-foreground truncate">
                              {FACTOR_LABEL[k] ?? k.replace(/_/g, " ")}
                            </div>
                            <div className="flex-1 bg-muted/30 rounded-full h-1 overflow-hidden">
                              <div
                                className={cn("h-full rounded-full", DIRECTIONALITY_BAR[dir])}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <div className={cn("text-[9px] font-semibold px-1 py-0.5 rounded min-w-[42px] text-center", DIRECTIONALITY_COLOR[dir])}>
                              {dir}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
              <button
                className="mt-1 text-[10px] text-blue-400 hover:text-blue-300 underline"
                onClick={() => setModalPosition(selected)}
              >
                Full breakdown →
              </button>
            </section>
          )}

          {/* IES */}
          <section>
            <SectionTitle label="IES — Entry Score" />
            {selected.ies_calculated ? (
              <div className={cn("text-sm font-bold tabular-nums", scoreTextColor(selected.ies_score))}>
                {selected.ies_score?.toFixed(0)}/100
              </div>
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
      {modalPosition && (
        <ScoreBreakdownModal
          ticker={modalPosition.symbol}
          factorDetails={modalPosition.factor_details ?? null}
          hhsScore={modalPosition.hhs_score}
          iesScore={modalPosition.ies_score}
          hhsStatus={modalPosition.hhs_status}
          iesCalculated={modalPosition.ies_calculated}
          iesBlockedReason={modalPosition.ies_blocked_reason}
          onClose={() => setModalPosition(null)}
        />
      )}
    </div>
  );
}
