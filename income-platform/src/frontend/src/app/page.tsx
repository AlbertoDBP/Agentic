"use client";

import {
  DollarSign,
  Briefcase,
  Percent,
  Bell,
  ArrowRight,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { MetricCard } from "@/components/metric-card";
import { TickerBadge } from "@/components/ticker-badge";
import { formatCurrency, formatPercent, formatDate, cn } from "@/lib/utils";
import { ASSET_CLASS_COLORS } from "@/lib/config";
import { usePortfolio } from "@/lib/portfolio-context";
import type {
  PortfolioMetrics,
  IncomeProjection,
  AllocationItem,
  DividendEvent,
} from "@/lib/types";
import Link from "next/link";

const MOCK_METRICS: PortfolioMetrics = {
  total_value: 612000,
  annual_income: 47200,
  blended_yield: 7.72,
  active_alerts: 3,
  positions_count: 70,
};

const MOCK_INCOME: IncomeProjection[] = [
  { month: "Apr", projected: 3800, actual: 3800 },
  { month: "May", projected: 4100, actual: 4100 },
  { month: "Jun", projected: 3600, actual: 3600 },
  { month: "Jul", projected: 4200, actual: 4200 },
  { month: "Aug", projected: 3900, actual: 3900 },
  { month: "Sep", projected: 4400 },
  { month: "Oct", projected: 3700 },
  { month: "Nov", projected: 4000 },
  { month: "Dec", projected: 4300 },
  { month: "Jan", projected: 3800 },
  { month: "Feb", projected: 4100 },
  { month: "Mar", projected: 3500 },
];

const MOCK_ALLOCATION: AllocationItem[] = [
  { name: "Common Stock", value: 245000, percentage: 40, color: ASSET_CLASS_COLORS["Common Stock"] },
  { name: "BDC", value: 122000, percentage: 20, color: ASSET_CLASS_COLORS["BDC"] },
  { name: "CEF", value: 98000, percentage: 16, color: ASSET_CLASS_COLORS["CEF"] },
  { name: "Preferred", value: 61000, percentage: 10, color: ASSET_CLASS_COLORS["Preferred"] },
  { name: "MLP", value: 49000, percentage: 8, color: ASSET_CLASS_COLORS["MLP"] },
  { name: "ETF", value: 37000, percentage: 6, color: ASSET_CLASS_COLORS["ETF"] },
];

const MOCK_DIVIDENDS: DividendEvent[] = [
  { symbol: "MAIN", asset_type: "BDC", ex_date: "2026-03-20", pay_date: "2026-03-27", amount: 72.5 },
  { symbol: "O", asset_type: "Common Stock", ex_date: "2026-03-22", pay_date: "2026-03-28", amount: 45.0 },
  { symbol: "ARCC", asset_type: "BDC", ex_date: "2026-03-25", pay_date: "2026-04-01", amount: 120.0 },
  { symbol: "EPD", asset_type: "MLP", ex_date: "2026-03-28", pay_date: "2026-04-10", amount: 95.0 },
  { symbol: "PFF", asset_type: "ETF", ex_date: "2026-04-01", pay_date: "2026-04-07", amount: 55.0 },
];

// Per-portfolio mock summaries
const PORTFOLIO_SUMMARIES = [
  { id: "p1", name: "Income Fortress", account_type: "Taxable", positions: 70, value: 612000, income: 47200, yield: 7.72, gainPct: 4.3 },
  { id: "p2", name: "Roth IRA", account_type: "Roth IRA", positions: 15, value: 85000, income: 5100, yield: 6.0, gainPct: 8.1 },
  { id: "p3", name: "401(k)", account_type: "401(k)", positions: 8, value: 142000, income: 7100, yield: 5.0, gainPct: 12.5 },
];

const QUALITY_TIERS = [
  { label: "High (80+)", count: 42, pct: 60, color: "bg-emerald-400", filter: "high" },
  { label: "Medium (50-79)", count: 21, pct: 30, color: "bg-amber-400", filter: "medium" },
  { label: "Review (<50)", count: 7, pct: 10, color: "bg-red-400", filter: "low" },
];

export default function DashboardPage() {
  const { portfolios, activePortfolio, setActiveId } = usePortfolio();
  const metrics = MOCK_METRICS;
  const incomeData = MOCK_INCOME;
  const allocation = MOCK_ALLOCATION;
  const upcomingDividends = MOCK_DIVIDENDS;
  const pendingProposals = 2;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      {/* KPI Cards — clickable */}
      <div className="grid grid-cols-4 gap-4">
        <Link href="/portfolio">
          <MetricCard
            label="Annual Income"
            value={formatCurrency(metrics.annual_income, true)}
            delta="+$1,200 vs last quarter"
            deltaType="positive"
            icon={DollarSign}
          />
        </Link>
        <Link href="/portfolio">
          <MetricCard
            label="Portfolio Value"
            value={formatCurrency(metrics.total_value, true)}
            delta="+2.1% MTD"
            deltaType="positive"
            icon={Briefcase}
          />
        </Link>
        <Link href="/projection">
          <MetricCard
            label="Blended Yield"
            value={formatPercent(metrics.blended_yield)}
            delta="+0.12% vs target"
            deltaType="positive"
            icon={Percent}
          />
        </Link>
        <Link href="/alerts">
          <MetricCard
            label="Active Alerts"
            value={String(metrics.active_alerts)}
            delta="1 critical"
            deltaType="negative"
            icon={Bell}
          />
        </Link>
      </div>

      {/* Portfolio Summary — compact table */}
      <div className="rounded-lg border border-border bg-card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-muted-foreground">
              <th className="px-4 py-2 text-left font-medium">Portfolio</th>
              <th className="px-3 py-2 text-left font-medium">Account</th>
              <th className="px-3 py-2 text-right font-medium">Positions</th>
              <th className="px-3 py-2 text-right font-medium">Value</th>
              <th className="px-3 py-2 text-right font-medium">Cost</th>
              <th className="px-3 py-2 text-right font-medium">Gain/Loss</th>
              <th className="px-3 py-2 text-right font-medium">Income</th>
              <th className="px-3 py-2 text-right font-medium">Mo. Income</th>
              <th className="px-3 py-2 text-right font-medium">Yield</th>
              <th className="px-3 py-2 text-right font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {PORTFOLIO_SUMMARIES.map((p) => {
              const gain = p.value - (p.value / (1 + p.gainPct / 100));
              return (
                <tr
                  key={p.id}
                  onClick={() => { setActiveId(p.id); window.location.href = "/portfolio"; }}
                  className={cn(
                    "cursor-pointer transition-colors hover:bg-secondary/50",
                    activePortfolio?.id === p.id && "bg-primary/5"
                  )}
                >
                  <td className="px-4 py-2.5 font-medium">{p.name}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{p.account_type}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{p.positions}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatCurrency(p.value, true)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-muted-foreground">{formatCurrency(p.value / (1 + p.gainPct / 100), true)}</td>
                  <td className={cn("px-3 py-2.5 text-right tabular-nums", p.gainPct >= 0 ? "text-income" : "text-loss")}>
                    {p.gainPct >= 0 ? "+" : ""}{p.gainPct.toFixed(1)}%
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-income">{formatCurrency(p.income, true)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatCurrency(p.income / 12, true)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatPercent(p.yield)}</td>
                  <td className="px-3 py-2.5 text-right"><ArrowRight className="inline h-3.5 w-3.5 text-muted-foreground" /></td>
                </tr>
              );
            })}
            {/* Totals row */}
            <tr className="bg-secondary/30 font-medium">
              <td className="px-4 py-2.5">All Portfolios</td>
              <td className="px-3 py-2.5"></td>
              <td className="px-3 py-2.5 text-right tabular-nums">{PORTFOLIO_SUMMARIES.reduce((s, p) => s + p.positions, 0)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{formatCurrency(PORTFOLIO_SUMMARIES.reduce((s, p) => s + p.value, 0), true)}</td>
              <td className="px-3 py-2.5"></td>
              <td className="px-3 py-2.5"></td>
              <td className="px-3 py-2.5 text-right tabular-nums text-income">{formatCurrency(PORTFOLIO_SUMMARIES.reduce((s, p) => s + p.income, 0), true)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{formatCurrency(PORTFOLIO_SUMMARIES.reduce((s, p) => s + p.income, 0) / 12, true)}</td>
              <td className="px-3 py-2.5"></td>
              <td className="px-3 py-2.5"></td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Proposal Strip */}
      {pendingProposals > 0 && (
        <Link href="/proposals" className="flex items-center justify-between rounded-lg border border-warning/30 bg-warning/5 px-4 py-2.5 transition-colors hover:bg-warning/10">
          <p className="text-sm text-warning">
            <span className="font-semibold">{pendingProposals} proposals</span> awaiting review
          </p>
          <span className="rounded-md bg-warning/20 px-3 py-1 text-xs font-medium text-warning">
            Review
          </span>
        </Link>
      )}

      {/* Two-column row: Income Chart + Upcoming Dividends */}
      <div className="grid grid-cols-5 gap-4">
        <Link href="/projection" className="col-span-3 rounded-lg border border-border bg-card p-4 transition-colors hover:border-border/80">
          <h2 className="mb-4 text-sm font-medium text-muted-foreground">Income by Month</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={incomeData} barSize={24}>
              <CartesianGrid strokeDasharray="3 3" stroke="#252d3d" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: "#8891a8", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#8891a8", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}K`} />
              <Tooltip
                contentStyle={{ background: "#111520", border: "1px solid #252d3d", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "#e8eaf0" }}
                formatter={(value) => [formatCurrency(Number(value)), "Income"]}
              />
              <Bar dataKey="actual" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="projected" fill="#3b82f6" opacity={0.5} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Link>

        <Link href="/calendar" className="col-span-2 rounded-lg border border-border bg-card p-4 transition-colors hover:border-border/80">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Upcoming Dividends</h2>
          <div className="space-y-3">
            {upcomingDividends.map((d) => (
              <div key={`${d.symbol}-${d.ex_date}`} className="flex items-center justify-between">
                <div>
                  <TickerBadge symbol={d.symbol} assetType={d.asset_type} />
                  <p className="mt-0.5 text-[11px] text-muted-foreground">Ex: {formatDate(d.ex_date)}</p>
                </div>
                <span className="font-mono text-sm font-medium tabular-nums text-income">
                  {formatCurrency(d.amount)}
                </span>
              </div>
            ))}
          </div>
        </Link>
      </div>

      {/* Three-column row: Allocation, Score Distribution, NAV Watch */}
      <div className="grid grid-cols-3 gap-4">
        {/* Asset Allocation Pie */}
        <Link href="/portfolio" className="rounded-lg border border-border bg-card p-4 transition-colors hover:border-border/80">
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">Asset Allocation</h2>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={allocation}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
                dataKey="value"
              >
                {allocation.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: "#111520", border: "1px solid #252d3d", borderRadius: 8, fontSize: 12 }}
                formatter={(value, name) => [formatCurrency(Number(value)), String(name)]}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
            {allocation.map((a) => (
              <div key={a.name} className="flex items-center gap-1.5 text-[11px]">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: a.color }} />
                <span className="text-muted-foreground">{a.name}</span>
                <span className="ml-auto tabular-nums">{a.percentage}%</span>
              </div>
            ))}
          </div>
        </Link>

        {/* Income Quality — clickable tiers navigate to filtered positions */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-4 text-sm font-medium text-muted-foreground">Income Quality</h2>
          <div className="space-y-4">
            {QUALITY_TIERS.map((tier) => (
              <Link
                key={tier.label}
                href={`/portfolio?quality=${tier.filter}`}
                className="block group"
              >
                <div className="mb-1 flex justify-between text-xs">
                  <span className="text-muted-foreground group-hover:text-foreground transition-colors">{tier.label}</span>
                  <span className="tabular-nums">{tier.count} positions</span>
                </div>
                <div className="h-2 rounded-full bg-secondary">
                  <div
                    className={`h-2 rounded-full ${tier.color} transition-all group-hover:opacity-80`}
                    style={{ width: `${tier.pct}%` }}
                  />
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* NAV Watch */}
        <Link href="/alerts" className="rounded-lg border border-border bg-card p-4 transition-colors hover:border-border/80">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">NAV Watch</h2>
          <div className="space-y-2">
            {[
              { symbol: "PDI", type: "CEF", discount: -8.2, alert: true },
              { symbol: "GOF", type: "CEF", discount: 12.5, alert: true },
              { symbol: "ARCC", type: "BDC", discount: -2.1, alert: false },
              { symbol: "MAIN", type: "BDC", discount: 18.3, alert: false },
            ].map((item) => (
              <div key={item.symbol} className="flex items-center justify-between rounded-md bg-secondary/50 px-2.5 py-1.5">
                <TickerBadge symbol={item.symbol} assetType={item.type} />
                <div className="flex items-center gap-2">
                  <span
                    className={`font-mono text-xs tabular-nums ${
                      item.discount < 0 ? "text-income" : "text-loss"
                    }`}
                  >
                    {item.discount > 0 ? "+" : ""}
                    {item.discount.toFixed(1)}%
                  </span>
                  {item.alert && (
                    <span className="h-2 w-2 rounded-full bg-red-400 animate-pulse" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </Link>
      </div>
    </div>
  );
}
