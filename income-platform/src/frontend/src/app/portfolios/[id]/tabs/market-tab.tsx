"use client";
import { useMemo, useState, useEffect } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { ColHeader } from "@/components/help-tooltip";
import { MARKET_HELP } from "@/lib/help-content";
import { formatCurrency } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import type { Position } from "@/lib/types";

interface MarketTabProps {
  portfolioId: string;
}

export function MarketTab({ portfolioId }: MarketTabProps) {
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
      header: () => <ColHeader label="Ticker" helpKey="symbol" helpMap={MARKET_HELP} />,
      cell: ({ row }) => (
        <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />
      ),
    },
    { accessorKey: "asset_type", header: "Class" },
    {
      accessorKey: "market_price",
      header: () => <ColHeader label="Price" helpKey="price" helpMap={MARKET_HELP} />,
      cell: ({ getValue }) => formatCurrency(getValue() as number),
    },
    {
      accessorKey: "week52_high",
      header: () => (
        <ColHeader label="52w High" helpKey="week52_range" helpMap={MARKET_HELP} />
      ),
      cell: ({ getValue }) =>
        getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "week52_low",
      header: () => (
        <ColHeader label="52w Low" helpKey="week52_range" helpMap={MARKET_HELP} />
      ),
      cell: ({ getValue }) =>
        getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "current_yield",
      header: () => (
        <ColHeader label="Div Yield" helpKey="dividend_yield" helpMap={MARKET_HELP} />
      ),
      cell: ({ getValue }) =>
        getValue() != null ? `${((getValue() as number) * 100).toFixed(2)}%` : "—",
    },
    {
      accessorKey: "beta",
      header: () => <ColHeader label="Beta" helpKey="beta" helpMap={MARKET_HELP} />,
      cell: ({ getValue }) => (getValue() as number | null)?.toFixed(2) ?? "—",
    },
    {
      accessorKey: "market_cap",
      header: () => <ColHeader label="Mkt Cap" helpKey="market_cap" helpMap={MARKET_HELP} />,
      cell: ({ getValue }) =>
        getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
  ];

  return (
    <div className="flex gap-3">
      <div className="flex-1 min-w-0">
        <DataTable
          columns={columns}
          data={filtered}
          storageKey={`market-tab-${portfolioId}`}
          enableRowSelection
          onRowClick={(row) =>
            setSelected((s) => (s?.symbol === row.symbol ? null : row))
          }
          frozenColumns={1}
        />
      </div>

      {selected && (
        <div className="w-[360px] flex-shrink-0 bg-card border border-border rounded-lg p-4 text-sm overflow-y-auto max-h-[calc(100vh-200px)]">
          <div className="flex items-center justify-between mb-3">
            <span className="font-bold">{selected.symbol}</span>
            <button
              onClick={() => setSelected(null)}
              className="text-muted-foreground text-xs"
              aria-label="Close detail pane"
            >
              &#x2715;
            </button>
          </div>
          <div className="grid grid-cols-2 gap-y-1.5 text-xs">
            {(
              [
                ["Price", formatCurrency(selected.market_price ?? 0)],
                ["52w High", formatCurrency(selected.week52_high ?? 0)],
                ["52w Low", formatCurrency(selected.week52_low ?? 0)],
                [
                  "Div Yield",
                  selected.current_yield != null
                    ? `${(selected.current_yield * 100).toFixed(2)}%`
                    : "—",
                ],
                ["P/E", selected.pe_ratio?.toFixed(1) ?? "—"],
                ["Beta", selected.beta?.toFixed(2) ?? "—"],
                [
                  "Market Cap",
                  selected.market_cap != null
                    ? formatCurrency(selected.market_cap)
                    : "—",
                ],
                ["Sector", selected.sector ?? "—"],
                ["Industry", selected.industry ?? "—"],
              ] as [string, string][]
            ).map(([k, v]) => (
              <div key={k}>
                <div className="text-muted-foreground text-[0.6rem] uppercase">{k}</div>
                <div className="font-medium">{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
