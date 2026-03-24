"use client";
import { useState, useEffect } from "react";
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

  if (loading) return <div className="p-4 text-muted-foreground text-sm animate-pulse">Loading…</div>;
  if (fetchError) return (
    <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-3 text-sm text-red-400">
      Failed to load positions: {fetchError}
    </div>
  );

  return (
    <div className="flex gap-3">
      <div className="flex-1 min-w-0">
        <DataTable
          columns={columns}
          data={positions}
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
                ["52w High", selected.week52_high != null ? formatCurrency(selected.week52_high) : "—"],
                ["52w Low", selected.week52_low != null ? formatCurrency(selected.week52_low) : "—"],
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
