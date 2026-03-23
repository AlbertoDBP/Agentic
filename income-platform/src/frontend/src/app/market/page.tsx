"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { BarChart2, Search, RefreshCw } from "lucide-react";
import { TickerBadge } from "@/components/ticker-badge";
import { usePortfolio } from "@/lib/portfolio-context";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { apiGet } from "@/lib/api";
import type { Asset } from "@/lib/types";

type SortKey = "symbol" | "price" | "change_pct" | "dividend_yield" | "sma_50" | "rsi_14d" | "chowder_number" | "nav";
type SortDir = "asc" | "desc";

function pctBar(value: number | null | undefined, min: number, max: number, color: string) {
  if (value == null) return <span className="text-muted-foreground text-[10px]">—</span>;
  const pct = Math.min(Math.max(((value - min) / (max - min)) * 100, 0), 100);
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1 w-14 rounded-full bg-secondary">
        <div className="h-1 rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="tabular-nums text-[11px]">{value.toFixed(1)}</span>
    </div>
  );
}

function smaSignal(price: number, sma50: number | null | undefined, sma200: number | null | undefined) {
  if (!sma50 && !sma200) return null;
  const above50 = sma50 ? price > sma50 : null;
  const above200 = sma200 ? price > sma200 : null;
  const bullish = above50 && above200;
  const bearish = above50 === false && above200 === false;
  return (
    <span className={cn(
      "rounded px-1.5 py-0.5 text-[10px] font-medium",
      bullish ? "bg-emerald-500/15 text-emerald-400" :
      bearish ? "bg-red-500/15 text-red-400" :
      "bg-yellow-500/15 text-yellow-400"
    )}>
      {bullish ? "Bullish" : bearish ? "Bearish" : "Mixed"}
    </span>
  );
}

export default function MarketPage() {
  const router = useRouter();
  const { activePortfolio, portfolios } = usePortfolio();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("symbol");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const portfolioId = activePortfolio?.id ?? portfolios[0]?.id;

  useEffect(() => {
    if (!portfolioId) return;
    setLoading(true);
    setError(null);
    const url = `/api/market-data/positions?portfolio_id=${encodeURIComponent(portfolioId)}`;
    apiGet<Asset[]>(url)
      .then(setAssets)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [portfolioId]);

  const sorted = useMemo(() => {
    let rows = assets.filter((a) =>
      !search || a.symbol.toLowerCase().includes(search.toLowerCase()) ||
      (a.name ?? "").toLowerCase().includes(search.toLowerCase())
    );
    rows = [...rows].sort((a, b) => {
      const av = (a as unknown as Record<string, unknown>)[sortKey];
      const bv = (b as unknown as Record<string, unknown>)[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [assets, search, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  }

  function Th({ k, label }: { k: SortKey; label: string }) {
    const active = sortKey === k;
    return (
      <th
        className={cn(
          "cursor-pointer select-none px-3 py-2 text-left text-xs font-medium whitespace-nowrap",
          active ? "text-foreground" : "text-muted-foreground hover:text-foreground"
        )}
        onClick={() => toggleSort(k)}
      >
        {label}{active ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
      </th>
    );
  }

  const portfolioName = portfolios.find((p) => p.id === portfolioId)?.name ?? "";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <BarChart2 className="h-5 w-5 text-muted-foreground" />
            Market
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {portfolioName ? `Holdings in ${portfolioName}` : "Portfolio market overview"} — click a row for full asset detail
          </p>
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter symbols…"
            className="rounded-md border border-border bg-secondary pl-8 pr-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring w-48"
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border bg-card overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
            <RefreshCw className="h-4 w-4 animate-spin" />
            <span className="text-sm">Loading market data…</span>
          </div>
        ) : error ? (
          <div className="py-12 text-center text-sm text-red-400">{error}</div>
        ) : sorted.length === 0 ? (
          <div className="py-16 text-center text-sm text-muted-foreground">
            No holdings found{search ? ` matching "${search}"` : ""}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/40">
                <Th k="symbol" label="Symbol" />
                <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Type</th>
                <Th k="price" label="Price" />
                <Th k="change_pct" label="Chg%" />
                <Th k="dividend_yield" label="Yield" />
                <Th k="chowder_number" label="Chowder" />
                <Th k="sma_50" label="SMA50" />
                <Th k="rsi_14d" label="RSI14" />
                <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">Trend</th>
                <Th k="nav" label="NAV Prem/Disc" />
                <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">Ex-Date</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((a) => (
                <tr
                  key={a.symbol}
                  className="border-b border-border/50 hover:bg-secondary/20 cursor-pointer"
                  onClick={() => router.push(`/market/${encodeURIComponent(a.symbol)}`)}
                >
                  <td className="px-3 py-2.5">
                    <TickerBadge symbol={a.symbol} assetType={a.asset_type} />
                    <div className="text-[10px] text-muted-foreground mt-0.5 max-w-35 truncate">{a.name}</div>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium">{a.asset_type}</span>
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-xs font-medium">{formatCurrency(a.price)}</td>
                  <td className={cn("px-3 py-2.5 tabular-nums text-xs font-medium",
                    a.change_pct >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {a.change_pct >= 0 ? "+" : ""}{a.change_pct.toFixed(2)}%
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-xs text-income">
                    {a.dividend_yield > 0 ? formatPercent(a.dividend_yield) : "—"}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-xs">
                    {a.chowder_number != null
                      ? <span className={cn(a.chowder_number >= 12 ? "text-income" : a.chowder_number >= 8 ? "text-yellow-400" : "text-red-400")}>{a.chowder_number.toFixed(1)}</span>
                      : "—"}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-xs">
                    {a.sma_50 != null
                      ? <span className={cn(a.price > a.sma_50 ? "text-income" : "text-red-400")}>{formatCurrency(a.sma_50)}</span>
                      : "—"}
                  </td>
                  <td className="px-3 py-2.5">
                    {pctBar(a.rsi_14d, 0, 100, a.rsi_14d != null && a.rsi_14d > 70 ? "#f87171" : a.rsi_14d != null && a.rsi_14d < 30 ? "#10b981" : "#94a3b8")}
                  </td>
                  <td className="px-3 py-2.5">
                    {smaSignal(a.price, a.sma_50, a.sma_200)}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-xs">
                    {a.premium_discount != null
                      ? <span className={cn(a.premium_discount > 0 ? "text-yellow-400" : "text-income")}>
                          {a.premium_discount >= 0 ? "+" : ""}{a.premium_discount.toFixed(2)}%
                        </span>
                      : "—"}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                    {a.ex_date ? new Date(a.ex_date).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground text-right">{sorted.length} holdings shown</p>
    </div>
  );
}
