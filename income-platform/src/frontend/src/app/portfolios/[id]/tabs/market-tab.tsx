"use client";
import { useState, useEffect } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { ColHeader } from "@/components/help-tooltip";
import { MARKET_HELP } from "@/lib/help-content";
import { formatCurrency, formatDate, rangePositionColor, rangeBarColor } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import type { Position } from "@/lib/types";

interface MarketTabProps {
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
      <div className="text-xs text-muted-foreground mb-0.5">{label}</div>
      <div className={cn("text-sm font-medium", className)}>{value}</div>
    </div>
  );
}

function SectionTitle({ label }: { label: string }) {
  return <div className="text-xs font-semibold uppercase tracking-wide text-blue-400 mb-2">{label}</div>;
}

function Week52Bar({ price, low, high }: { price: number | null; low: number | null; high: number | null }) {
  if (price == null || low == null || high == null || high <= low) return null;
  const range = high - low;
  const positionPct = Math.min(100, Math.max(0, ((price - low) / range) * 100));
  const barFill = rangeBarColor(positionPct);
  return (
    <div className="col-span-2 mt-1">
      <div className="flex justify-between text-[0.6rem] text-muted-foreground mb-1">
        <span>{formatCurrency(low)}</span>
        <span className={cn("font-semibold text-xs tabular-nums", rangePositionColor(positionPct))}>
          {positionPct.toFixed(0)}% of range
        </span>
        <span>{formatCurrency(high)}</span>
      </div>
      <div className="relative h-1.5 w-full rounded-full bg-muted/50">
        <div
          className={cn("absolute top-0 left-0 h-full rounded-full", barFill)}
          style={{ width: `${positionPct}%` }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-foreground border border-background shadow"
          style={{ left: `calc(${positionPct}% - 4px)` }}
        />
      </div>
    </div>
  );
}

export function MarketTab({ portfolioId, refreshKey = 0 }: MarketTabProps) {
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
  }, [portfolioId, refreshKey]);

  const columns: ColumnDef<Position>[] = [
    {
      accessorKey: "symbol",
      header: () => <ColHeader label="Ticker" helpKey="symbol" helpMap={MARKET_HELP} />,
      meta: { label: "Ticker" },
      cell: ({ row }) => (
        <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />
      ),
    },
    { accessorKey: "asset_type", header: "Class" },
    {
      accessorKey: "market_price",
      header: () => <ColHeader label="Price" helpKey="price" helpMap={MARKET_HELP} />,
      meta: { label: "Price" },
      cell: ({ getValue }) => formatCurrency(getValue() as number),
    },
    {
      accessorKey: "daily_change_pct",
      header: "Daily Chg",
      meta: { label: "Daily Change %" },
      cell: ({ getValue }) => {
        const v = getValue() as number | null;
        if (v == null) return "—";
        return <span className={v >= 0 ? "text-green-400" : "text-red-400"}>{v >= 0 ? "+" : ""}{v.toFixed(2)}%</span>;
      },
    },
    {
      id: "week52_range",
      header: () => <ColHeader label="52w Position" helpKey="week52_range" helpMap={MARKET_HELP} />,
      meta: { label: "52w Position" },
      accessorFn: (row) => {
        const p = row.market_price, lo = row.week52_low, hi = row.week52_high;
        if (p == null || lo == null || hi == null || hi <= lo) return null;
        return Math.min(100, Math.max(0, ((p - lo) / (hi - lo)) * 100));
      },
      cell: ({ row, getValue }) => {
        const pct = getValue() as number | null;
        if (pct == null) return <span className="text-muted-foreground">—</span>;
        const lo = row.original.week52_low!, hi = row.original.week52_high!;
        return (
          <div className="min-w-20">
            <div className={cn("text-xs font-medium tabular-nums mb-0.5", rangePositionColor(pct))}>
              {pct.toFixed(0)}%
            </div>
            <div className="relative h-1 w-full rounded-full bg-muted/50">
              <div className={cn("absolute top-0 left-0 h-full rounded-full", rangeBarColor(pct))} style={{ width: `${pct}%` }} />
            </div>
            <div className="flex justify-between text-[0.55rem] text-muted-foreground mt-0.5">
              <span>{formatCurrency(lo)}</span>
              <span>{formatCurrency(hi)}</span>
            </div>
          </div>
        );
      },
    },
    {
      accessorKey: "week52_high",
      header: () => <ColHeader label="52w High" helpKey="week52_range" helpMap={MARKET_HELP} />,
      meta: { label: "52w High", defaultHidden: true },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "week52_low",
      header: () => <ColHeader label="52w Low" helpKey="week52_range" helpMap={MARKET_HELP} />,
      meta: { label: "52w Low", defaultHidden: true },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "current_yield",
      header: () => <ColHeader label="Div Yield" helpKey="dividend_yield" helpMap={MARKET_HELP} />,
      meta: { label: "Div Yield" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(2)}%` : "—",
    },
    {
      accessorKey: "beta",
      header: () => <ColHeader label="Beta" helpKey="beta" helpMap={MARKET_HELP} />,
      meta: { label: "Beta" },
      cell: ({ getValue }) => (getValue() as number | null)?.toFixed(2) ?? "—",
    },
    {
      accessorKey: "market_cap",
      header: () => <ColHeader label="Mkt Cap" helpKey="market_cap" helpMap={MARKET_HELP} />,
      meta: { label: "Mkt Cap" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number, true) : "—",
    },
    // ── Hidden by default ──
    {
      accessorKey: "pe_ratio",
      header: "P/E",
      meta: { defaultHidden: true, label: "P/E Ratio" },
      cell: ({ getValue }) => (getValue() as number | null)?.toFixed(1) ?? "—",
    },
    {
      accessorKey: "payout_ratio",
      header: "Payout",
      meta: { defaultHidden: true, label: "Payout Ratio %" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(1)}%` : "—",
    },
    {
      accessorKey: "nav_value",
      header: "NAV",
      meta: { defaultHidden: true, label: "NAV Value" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "nav_discount_pct",
      header: "NAV Disc",
      meta: { defaultHidden: true, label: "NAV Discount/Premium %" },
      cell: ({ getValue }) => {
        const v = getValue() as number | null;
        if (v == null) return "—";
        return <span className={v < 0 ? "text-green-400" : "text-amber-400"}>{v >= 0 ? "+" : ""}{v.toFixed(1)}%</span>;
      },
    },
    {
      accessorKey: "yield_5yr_avg",
      header: "5yr Avg Yield",
      meta: { defaultHidden: true, label: "5yr Avg Yield" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(2)}%` : "—",
    },
    {
      accessorKey: "chowder_number",
      header: "Chowder",
      meta: { defaultHidden: true, label: "Chowder Number" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(1)}` : "—",
    },
    {
      accessorKey: "div_cagr_3yr",
      header: "Div CAGR 3yr",
      meta: { defaultHidden: true, label: "Dividend CAGR 3yr" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(1)}%` : "—",
    },
    {
      accessorKey: "div_cagr_10yr",
      header: "Div CAGR 10yr",
      meta: { defaultHidden: true, label: "Dividend CAGR 10yr" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(1)}%` : "—",
    },
    {
      accessorKey: "consecutive_growth_yrs",
      header: "Div Growth Yrs",
      meta: { defaultHidden: true, label: "Consecutive Dividend Growth Years" },
      cell: ({ getValue }) => getValue() != null ? `${getValue()}` : "—",
    },
    {
      accessorKey: "rsi_14d",
      header: "RSI 14d",
      meta: { defaultHidden: true, label: "RSI 14-day" },
      cell: ({ getValue }) => {
        const v = getValue() as number | null;
        if (v == null) return "—";
        const color = v >= 70 ? "text-red-400" : v <= 30 ? "text-green-400" : "";
        return <span className={color}>{v.toFixed(1)}</span>;
      },
    },
    {
      accessorKey: "rsi_14w",
      header: "RSI 14w",
      meta: { defaultHidden: true, label: "RSI 14-week" },
      cell: ({ getValue }) => (getValue() as number | null)?.toFixed(1) ?? "—",
    },
    {
      accessorKey: "sma_50",
      header: "SMA 50",
      meta: { defaultHidden: true, label: "50-day SMA" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "sma_200",
      header: "SMA 200",
      meta: { defaultHidden: true, label: "200-day SMA" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "support_level",
      header: "Support",
      meta: { defaultHidden: true, label: "Support Level" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "resistance_level",
      header: "Resistance",
      meta: { defaultHidden: true, label: "Resistance Level" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "interest_coverage_ratio",
      header: "Int. Coverage",
      meta: { defaultHidden: true, label: "Interest Coverage Ratio" },
      cell: ({ getValue }) => (getValue() as number | null)?.toFixed(1) ?? "—",
    },
    {
      accessorKey: "net_debt_ebitda",
      header: "Net Debt/EBITDA",
      meta: { defaultHidden: true, label: "Net Debt / EBITDA" },
      cell: ({ getValue }) => (getValue() as number | null)?.toFixed(1) ?? "—",
    },
    {
      accessorKey: "credit_rating",
      header: "Credit Rating",
      meta: { defaultHidden: true, label: "Credit Rating" },
      cell: ({ getValue }) => (getValue() as string | null) ?? "—",
    },
    {
      accessorKey: "free_cash_flow_yield",
      header: "FCF Yield",
      meta: { defaultHidden: true, label: "Free Cash Flow Yield %" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(1)}%` : "—",
    },
    {
      accessorKey: "return_on_equity",
      header: "ROE",
      meta: { defaultHidden: true, label: "Return on Equity %" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(1)}%` : "—",
    },
    {
      accessorKey: "analyst_price_target",
      header: "Price Target",
      meta: { defaultHidden: true, label: "Analyst Price Target" },
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "insider_ownership_pct",
      header: "Insider Own.",
      meta: { defaultHidden: true, label: "Insider Ownership %" },
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(1)}%` : "—",
    },
    {
      accessorKey: "avg_volume",
      header: "Avg Volume",
      meta: { defaultHidden: true, label: "Avg 10d Volume" },
      cell: ({ getValue }) => getValue() != null ? (getValue() as number).toLocaleString() : "—",
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
      accessorKey: "next_earnings_date",
      header: "Next Earnings",
      meta: { defaultHidden: true, label: "Next Earnings Date" },
      cell: ({ getValue }) => fmtDate(getValue() as string | null),
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
            <SectionTitle label="Price" />
            <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
              <DetailRow label="Price" value={formatCurrency(selected.market_price ?? 0)} />
              <DetailRow
                label="Daily Change"
                value={selected.daily_change_pct != null ? `${selected.daily_change_pct >= 0 ? "+" : ""}${selected.daily_change_pct.toFixed(2)}%` : "—"}
                className={selected.daily_change_pct != null ? (selected.daily_change_pct >= 0 ? "text-green-400" : "text-red-400") : ""}
              />
              <DetailRow label="52w High" value={selected.week52_high != null ? formatCurrency(selected.week52_high) : "—"} />
              <DetailRow label="52w Low" value={selected.week52_low != null ? formatCurrency(selected.week52_low) : "—"} />
              <Week52Bar price={selected.market_price ?? null} low={selected.week52_low ?? null} high={selected.week52_high ?? null} />
              {selected.analyst_price_target != null && (
                <DetailRow label="Price Target" value={formatCurrency(selected.analyst_price_target)} />
              )}
            </div>
          </section>

          <section>
            <SectionTitle label="Income" />
            <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
              <DetailRow label="Div Yield" value={selected.current_yield != null ? `${selected.current_yield.toFixed(2)}%` : "—"} />
              <DetailRow label="Payout Ratio" value={selected.payout_ratio != null ? `${selected.payout_ratio.toFixed(1)}%` : "—"} />
              <DetailRow label="5yr Avg Yield" value={selected.yield_5yr_avg != null ? `${selected.yield_5yr_avg.toFixed(2)}%` : "—"} />
              <DetailRow label="Chowder #" value={selected.chowder_number != null ? selected.chowder_number.toFixed(1) : "—"} />
              <DetailRow label="Div CAGR 3yr" value={selected.div_cagr_3yr != null ? `${selected.div_cagr_3yr.toFixed(1)}%` : "—"} />
              <DetailRow label="Div CAGR 10yr" value={selected.div_cagr_10yr != null ? `${selected.div_cagr_10yr.toFixed(1)}%` : "—"} />
              <DetailRow label="Growth Streak" value={selected.consecutive_growth_yrs != null ? `${selected.consecutive_growth_yrs} yrs` : "—"} />
              <DetailRow label="Ex-Div Date" value={fmtDate(selected.ex_div_date)} />
              <DetailRow label="Pay Date" value={fmtDate(selected.pay_date)} />
            </div>
          </section>

          {(selected.nav_value != null || selected.nav_discount_pct != null) && (
            <section>
              <SectionTitle label="NAV" />
              <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
                {selected.nav_value != null && <DetailRow label="NAV" value={formatCurrency(selected.nav_value)} />}
                {selected.nav_discount_pct != null && (
                  <DetailRow
                    label="Discount/Premium"
                    value={`${selected.nav_discount_pct >= 0 ? "+" : ""}${selected.nav_discount_pct.toFixed(1)}%`}
                    className={selected.nav_discount_pct < 0 ? "text-green-400" : "text-amber-400"}
                  />
                )}
              </div>
            </section>
          )}

          <section>
            <SectionTitle label="Technicals" />
            <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
              <DetailRow label="Beta" value={selected.beta?.toFixed(2) ?? "—"} />
              <DetailRow label="RSI 14d" value={selected.rsi_14d?.toFixed(1) ?? "—"} />
              <DetailRow label="SMA 50" value={selected.sma_50 != null ? formatCurrency(selected.sma_50) : "—"} />
              <DetailRow label="SMA 200" value={selected.sma_200 != null ? formatCurrency(selected.sma_200) : "—"} />
              {selected.support_level != null && <DetailRow label="Support" value={formatCurrency(selected.support_level)} />}
              {selected.resistance_level != null && <DetailRow label="Resistance" value={formatCurrency(selected.resistance_level)} />}
            </div>
          </section>

          <section>
            <SectionTitle label="Fundamentals" />
            <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
              <DetailRow label="P/E" value={selected.pe_ratio?.toFixed(1) ?? "—"} />
              <DetailRow label="Market Cap" value={selected.market_cap != null ? formatCurrency(selected.market_cap, true) : "—"} />
              <DetailRow label="FCF Yield" value={selected.free_cash_flow_yield != null ? `${selected.free_cash_flow_yield.toFixed(1)}%` : "—"} />
              <DetailRow label="ROE" value={selected.return_on_equity != null ? `${selected.return_on_equity.toFixed(1)}%` : "—"} />
              <DetailRow label="Int. Coverage" value={selected.interest_coverage_ratio?.toFixed(1) ?? "—"} />
              <DetailRow label="Net Debt/EBITDA" value={selected.net_debt_ebitda?.toFixed(1) ?? "—"} />
              {selected.credit_rating && <DetailRow label="Credit Rating" value={selected.credit_rating} />}
              {selected.insider_ownership_pct != null && <DetailRow label="Insider Own." value={`${selected.insider_ownership_pct.toFixed(1)}%`} />}
              {selected.next_earnings_date && <DetailRow label="Next Earnings" value={fmtDate(selected.next_earnings_date)} />}
            </div>
          </section>

          <section>
            <SectionTitle label="Classification" />
            <div className="grid grid-cols-2 gap-y-2.5 gap-x-3">
              <DetailRow label="Sector" value={selected.sector ?? "—"} />
              <DetailRow label="Industry" value={selected.industry ?? "—"} />
              {selected.avg_volume != null && <DetailRow label="Avg Volume" value={selected.avg_volume.toLocaleString()} />}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
