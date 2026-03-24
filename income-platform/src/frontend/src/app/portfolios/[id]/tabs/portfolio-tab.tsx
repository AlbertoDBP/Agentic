"use client";
import { useMemo, useState, useEffect } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import { ColHeader } from "@/components/help-tooltip";
import { HHS_HELP, HOLDINGS_HELP } from "@/lib/help-content";
import { formatCurrency, cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import type { Position } from "@/lib/types";

interface PortfolioTabProps {
  portfolioId: string;
}

export function PortfolioTab({ portfolioId }: PortfolioTabProps) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [selected, setSelected] = useState<Position | null>(null);

  useEffect(() => {
    if (!portfolioId) return;
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    fetch(`${API_BASE_URL}/api/portfolios/${portfolioId}/positions`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    })
      .then((r) => r.ok ? r.json() as Promise<Position[]> : Promise.resolve([]))
      .then(setPositions)
      .catch(() => setPositions([]));
  }, [portfolioId]);

  const filtered = useMemo(
    () => positions.filter((p) => p.portfolio_id === portfolioId),
    [positions, portfolioId]
  );

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
    { accessorKey: "shares", header: "Shares" },
    {
      accessorKey: "current_value",
      header: () => <ColHeader label="Mkt Value" helpKey="current_value" helpMap={HOLDINGS_HELP} />,
      cell: ({ getValue }) => formatCurrency(getValue() as number),
    },
    {
      accessorKey: "annual_income",
      header: () => <ColHeader label="Ann. Income" helpKey="annual_income" helpMap={HOLDINGS_HELP} />,
      cell: ({ getValue }) => formatCurrency(getValue() as number),
    },
    {
      accessorKey: "current_yield",
      header: () => <ColHeader label="Yield" helpKey="current_yield" helpMap={HOLDINGS_HELP} />,
      cell: ({ getValue }) =>
        getValue() != null ? `${((getValue() as number) * 100).toFixed(2)}%` : "—",
    },
    {
      accessorKey: "hhs_status",
      header: () => <ColHeader label="HHS" helpKey="hhs_score" helpMap={HHS_HELP} />,
      cell: ({ row }) => (
        <HhsBadge status={row.original.hhs_status} score={row.original.hhs_score} />
      ),
    },
  ];

  return (
    <div className={cn("flex gap-3", selected && "lg:gap-3")}>
      <div className="flex-1 min-w-0">
        <DataTable
          columns={columns}
          data={filtered}
          storageKey={`portfolio-tab-${portfolioId}`}
          enableRowSelection
          onRowClick={(row) =>
            setSelected((s) => (s?.symbol === row.symbol ? null : row))
          }
          frozenColumns={1}
        />
      </div>

      {selected && (
        <div className="w-[360px] flex-shrink-0 bg-card border border-border rounded-lg p-4 text-sm space-y-4 overflow-y-auto max-h-[calc(100vh-200px)]">
          <div className="flex items-center justify-between">
            <span className="font-bold">{selected.symbol}</span>
            <button
              onClick={() => setSelected(null)}
              className="text-muted-foreground hover:text-foreground text-xs"
              aria-label="Close detail pane"
            >
              &#x2715;
            </button>
          </div>

          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Position</div>
            <div className="grid grid-cols-2 gap-y-1.5 text-xs">
              {(
                [
                  ["Shares", String(selected.shares)],
                  [
                    "Avg Cost",
                    formatCurrency(
                      selected.avg_cost ??
                        (selected.shares ? selected.cost_basis / selected.shares : 0)
                    ),
                  ],
                  ["Mkt Price", formatCurrency(selected.market_price ?? 0)],
                  ["Mkt Value", formatCurrency(selected.current_value)],
                  ["Cost Basis", formatCurrency(selected.cost_basis)],
                  [
                    "Unrealized G/L",
                    formatCurrency(selected.current_value - selected.cost_basis),
                  ],
                ] as [string, string][]
              ).map(([k, v]) => (
                <div key={k}>
                  <div className="text-muted-foreground text-[0.6rem] uppercase">{k}</div>
                  <div className="font-medium">{v}</div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Income</div>
            <div className="grid grid-cols-2 gap-y-1.5 text-xs">
              {(
                [
                  ["Annual Income", formatCurrency(selected.annual_income)],
                  [
                    "Gross Yield",
                    selected.current_yield != null
                      ? `${(selected.current_yield * 100).toFixed(2)}%`
                      : "—",
                  ],
                  ["Frequency", selected.dividend_frequency ?? "—"],
                  ["Ex-Date", selected.ex_div_date ?? "—"],
                ] as [string, string][]
              ).map(([k, v]) => (
                <div key={k}>
                  <div className="text-muted-foreground text-[0.6rem] uppercase">{k}</div>
                  <div className="font-medium">{v}</div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">
              Health Summary
            </div>
            {selected.hhs_score != null ? (
              <div className="space-y-1.5">
                <HhsBadge status={selected.hhs_status} score={selected.hhs_score} />
                <div className="flex gap-2 text-xs text-muted-foreground">
                  <span>
                    Income: {selected.income_pillar_score?.toFixed(0) ?? "—"}/100
                  </span>
                  <span>·</span>
                  <span>
                    Durability: {selected.durability_pillar_score?.toFixed(0) ?? "—"}/100
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground text-xs italic">
                Rescore to see HHS
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
