"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, TrendingUp, DollarSign, Activity, Calendar, AlertTriangle } from "lucide-react";
import { MetricCard } from "@/components/metric-card";
import { ScorePill } from "@/components/score-pill";
import { AlertBadge } from "@/components/alert-badge";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { ASSET_CLASS_COLORS } from "@/lib/config";

// Mock — will be replaced with API calls
const MOCK_TICKER_DATA: Record<string, {
  symbol: string; name: string; asset_type: string; sector: string; industry: string;
  shares: number; cost_basis: number; current_value: number; annual_income: number;
  yield_on_cost: number; current_yield: number; score: number; alert_count: number;
  dividend_frequency: string; last_ex_date: string; next_ex_date: string;
  monthly_income: number[];
  analyst_sentiment: string; analyst_rating: string;
  nav_discount?: number; coverage_ratio?: number;
}> = {
  MAIN: {
    symbol: "MAIN", name: "Main Street Capital", asset_type: "BDC", sector: "Financials", industry: "Capital Markets",
    shares: 500, cost_basis: 19500, current_value: 22000, annual_income: 1680,
    yield_on_cost: 8.62, current_yield: 7.64, score: 92, alert_count: 0,
    dividend_frequency: "Monthly", last_ex_date: "2026-02-28", next_ex_date: "2026-03-28",
    monthly_income: [140, 140, 140, 140, 140, 140, 140, 140, 140, 140, 140, 140],
    analyst_sentiment: "Bullish", analyst_rating: "Strong Buy",
    nav_discount: -2.1, coverage_ratio: 1.25,
  },
  ARCC: {
    symbol: "ARCC", name: "Ares Capital", asset_type: "BDC", sector: "Financials", industry: "Capital Markets",
    shares: 800, cost_basis: 15200, current_value: 16800, annual_income: 1536,
    yield_on_cost: 10.11, current_yield: 9.14, score: 85, alert_count: 1,
    dividend_frequency: "Quarterly", last_ex_date: "2026-02-14", next_ex_date: "2026-05-14",
    monthly_income: [0, 0, 384, 0, 0, 384, 0, 0, 384, 0, 0, 384],
    analyst_sentiment: "Bullish", analyst_rating: "Buy",
    nav_discount: -1.5, coverage_ratio: 1.18,
  },
  PDI: {
    symbol: "PDI", name: "PIMCO Dynamic Income", asset_type: "CEF", sector: "Fixed Income", industry: "Bond Fund",
    shares: 400, cost_basis: 7600, current_value: 6800, annual_income: 864,
    yield_on_cost: 11.37, current_yield: 12.71, score: 45, alert_count: 2,
    dividend_frequency: "Monthly", last_ex_date: "2026-03-10", next_ex_date: "2026-04-10",
    monthly_income: [72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72],
    analyst_sentiment: "Neutral", analyst_rating: "Hold",
    nav_discount: -8.2, coverage_ratio: 0.92,
  },
};

export default function TickerDetailPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = use(params);
  const ticker = MOCK_TICKER_DATA[symbol.toUpperCase()];

  if (!ticker) {
    return (
      <div className="space-y-4">
        <Link href="/portfolio" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to Portfolio
        </Link>
        <p className="text-muted-foreground">Position not found: {symbol}</p>
      </div>
    );
  }

  const gain = ticker.current_value - ticker.cost_basis;
  const gainPct = ticker.cost_basis > 0 ? (gain / ticker.cost_basis) * 100 : 0;
  const color = ASSET_CLASS_COLORS[ticker.asset_type] || "#64748b";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link href="/portfolio" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3">
          <ArrowLeft className="h-4 w-4" /> Back to Portfolio
        </Link>
        <div className="flex items-center gap-3">
          <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
          <h1 className="text-2xl font-semibold">{ticker.symbol}</h1>
          <span className="rounded bg-secondary px-2 py-0.5 text-xs font-medium">{ticker.asset_type}</span>
          {ticker.score !== undefined && <ScorePill score={ticker.score} />}
          {ticker.alert_count > 0 && <AlertBadge severity="HIGH" count={ticker.alert_count} />}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{ticker.name} · {ticker.sector} · {ticker.industry}</p>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-6 gap-3">
        <MetricCard label="Current Value" value={formatCurrency(ticker.current_value)} icon={DollarSign} />
        <MetricCard label="Cost Basis" value={formatCurrency(ticker.cost_basis)} />
        <MetricCard
          label="Gain/Loss"
          value={`${gain >= 0 ? "+" : ""}${formatCurrency(gain)}`}
          delta={`${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(1)}%`}
          deltaType={gain >= 0 ? "positive" : "negative"}
          icon={TrendingUp}
        />
        <MetricCard label="Annual Income" value={formatCurrency(ticker.annual_income)} icon={DollarSign} />
        <MetricCard label="Yield on Cost" value={formatPercent(ticker.yield_on_cost)} icon={Activity} />
        <MetricCard label="Current Yield" value={formatPercent(ticker.current_yield)} />
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Position Details */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Position Details</h2>
          <dl className="space-y-2.5 text-sm">
            {[
              ["Shares", ticker.shares.toLocaleString()],
              ["Avg Cost/Share", formatCurrency(ticker.cost_basis / ticker.shares)],
              ["Current Price", formatCurrency(ticker.current_value / ticker.shares)],
              ["Weight", "—"],
              ["Div Frequency", ticker.dividend_frequency],
              ["Last Ex-Date", ticker.last_ex_date],
              ["Next Ex-Date", ticker.next_ex_date],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between">
                <dt className="text-muted-foreground">{label}</dt>
                <dd className="tabular-nums font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Income Breakdown */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Monthly Income</h2>
          <div className="flex items-end gap-1 h-32">
            {["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"].map((month, i) => {
              const val = ticker.monthly_income[i];
              const max = Math.max(...ticker.monthly_income);
              const h = max > 0 ? (val / max) * 100 : 0;
              return (
                <div key={month} className="flex flex-1 flex-col items-center gap-1">
                  <div className="w-full flex flex-col justify-end" style={{ height: 100 }}>
                    <div
                      className="w-full rounded-t"
                      style={{ height: `${h}%`, backgroundColor: val > 0 ? "#10b981" : "#252d3d", minHeight: val > 0 ? 4 : 1 }}
                    />
                  </div>
                  <span className="text-[9px] text-muted-foreground">{month}</span>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex justify-between text-xs">
            <span className="text-muted-foreground">Annual</span>
            <span className="tabular-nums font-medium text-income">{formatCurrency(ticker.annual_income)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Monthly Avg</span>
            <span className="tabular-nums font-medium">{formatCurrency(ticker.annual_income / 12)}</span>
          </div>
        </div>

        {/* Analysis & Ratings */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Analysis</h2>
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Income Score</dt>
              <dd><ScorePill score={ticker.score} /></dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Analyst Rating</dt>
              <dd className="font-medium">{ticker.analyst_rating}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Sentiment</dt>
              <dd className={cn("font-medium",
                ticker.analyst_sentiment === "Bullish" && "text-income",
                ticker.analyst_sentiment === "Bearish" && "text-loss"
              )}>{ticker.analyst_sentiment}</dd>
            </div>
            {ticker.nav_discount !== undefined && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">NAV Premium/Discount</dt>
                <dd className={cn("tabular-nums font-medium", ticker.nav_discount < 0 ? "text-income" : "text-loss")}>
                  {ticker.nav_discount > 0 ? "+" : ""}{ticker.nav_discount.toFixed(1)}%
                </dd>
              </div>
            )}
            {ticker.coverage_ratio !== undefined && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Distribution Coverage</dt>
                <dd className={cn("tabular-nums font-medium", ticker.coverage_ratio >= 1 ? "text-income" : "text-loss")}>
                  {ticker.coverage_ratio.toFixed(2)}x
                </dd>
              </div>
            )}
          </dl>
          {ticker.alert_count > 0 && (
            <div className="mt-4 rounded-md bg-red-400/10 px-3 py-2">
              <div className="flex items-center gap-2 text-xs font-medium text-red-400">
                <AlertTriangle className="h-3.5 w-3.5" />
                {ticker.alert_count} active alert{ticker.alert_count > 1 ? "s" : ""}
              </div>
              <Link href="/alerts" className="mt-1 block text-xs text-red-400/80 hover:underline">
                View alerts →
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
