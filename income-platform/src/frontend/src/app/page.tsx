"use client";

import { useState, useEffect } from "react";
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
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { ASSET_CLASS_COLORS } from "@/lib/config";
import { usePortfolio } from "@/lib/portfolio-context";
import { API_BASE_URL } from "@/lib/config";
import Link from "next/link";

// ─── Types ───────────────────────────────────────────────────────────────────

interface DashboardMetrics {
  total_value: number;
  annual_income: number;
  blended_yield: number;
  active_alerts: number;
  positions_count: number;
  pending_proposals: number;
}

interface PortfolioSummary {
  id: string;
  name: string;
  account_type: string;
  broker: string;
  positions_count: number;
  total_value: number;
  cost_basis: number;
  annual_income: number;
  blended_yield: number;
  gain_pct: number;
}

interface AllocationItem {
  name: string;
  value: number;
  percentage: number;
}

interface QualityData {
  high: number;
  medium: number;
  low: number;
}

interface MonthlyIncome {
  month: string;
  projected: number;
  actual?: number;
}

interface DashboardData {
  metrics: DashboardMetrics;
  portfolios: PortfolioSummary[];
  allocation: AllocationItem[];
  quality: QualityData;
  income_by_month: MonthlyIncome[];
}

// ─── Static fallback data ─────────────────────────────────────────────────────

const EMPTY_METRICS: DashboardMetrics = {
  total_value: 0, annual_income: 0, blended_yield: 0,
  active_alerts: 0, positions_count: 0, pending_proposals: 0,
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { activePortfolio, setActiveId } = usePortfolio();
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/dashboard`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d: DashboardData) => setData(d))
      .catch((e) => console.warn("Dashboard API unavailable:", e));
  }, []);

  const metrics       = data?.metrics        ?? EMPTY_METRICS;
  const portfolios    = data?.portfolios      ?? [];
  const incomeData    = data?.income_by_month ?? [];
  const qualityRaw    = data?.quality         ?? { high: 0, medium: 0, low: 0 };
  const allocationRaw = data?.allocation      ?? [];
  const pendingProposals = metrics.pending_proposals;

  // Apply colors to allocation items
  const allocation = allocationRaw.map((a) => ({
    ...a,
    color: ASSET_CLASS_COLORS[a.name] ?? "#64748b",
  }));

  // Build quality tiers display
  const qualityTotal = qualityRaw.high + qualityRaw.medium + qualityRaw.low;
  const qualityTiers = [
    { label: "High (80+)",     count: qualityRaw.high,   pct: qualityTotal > 0 ? Math.round((qualityRaw.high   / qualityTotal) * 100) : 0, color: "bg-emerald-400", filter: "high" },
    { label: "Medium (50-79)", count: qualityRaw.medium, pct: qualityTotal > 0 ? Math.round((qualityRaw.medium / qualityTotal) * 100) : 0, color: "bg-amber-400",   filter: "medium" },
    { label: "Review (<50)",   count: qualityRaw.low,    pct: qualityTotal > 0 ? Math.round((qualityRaw.low    / qualityTotal) * 100) : 0, color: "bg-red-400",     filter: "low" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Link href="/portfolio">
          <MetricCard
            label="Annual Income"
            value={formatCurrency(metrics.annual_income, true)}
            icon={DollarSign}
          />
        </Link>
        <Link href="/portfolio">
          <MetricCard
            label="Portfolio Value"
            value={formatCurrency(metrics.total_value, true)}
            icon={Briefcase}
          />
        </Link>
        <Link href="/projection">
          <MetricCard
            label="Blended Yield"
            value={formatPercent(metrics.blended_yield)}
            icon={Percent}
          />
        </Link>
        <Link href="/alerts">
          <MetricCard
            label="Active Alerts"
            value={String(metrics.active_alerts)}
            deltaType={metrics.active_alerts > 0 ? "negative" : "positive"}
            icon={Bell}
          />
        </Link>
      </div>

      {/* Portfolio Summary Table */}
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
            {portfolios.map((p) => (
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
                <td className="px-3 py-2.5 text-right tabular-nums">{p.positions_count}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatCurrency(p.total_value, true)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums text-muted-foreground">{formatCurrency(p.cost_basis, true)}</td>
                <td className={cn("px-3 py-2.5 text-right tabular-nums", p.gain_pct >= 0 ? "text-income" : "text-loss")}>
                  {p.gain_pct >= 0 ? "+" : ""}{p.gain_pct.toFixed(1)}%
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums text-income">{formatCurrency(p.annual_income, true)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatCurrency(p.annual_income / 12, true)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatPercent(p.blended_yield)}</td>
                <td className="px-3 py-2.5 text-right"><ArrowRight className="inline h-3.5 w-3.5 text-muted-foreground" /></td>
              </tr>
            ))}
            {portfolios.length > 0 && (
              <tr className="bg-secondary/30 font-medium">
                <td className="px-4 py-2.5">All Portfolios</td>
                <td className="px-3 py-2.5"></td>
                <td className="px-3 py-2.5 text-right tabular-nums">{portfolios.reduce((s, p) => s + p.positions_count, 0)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatCurrency(portfolios.reduce((s, p) => s + p.total_value, 0), true)}</td>
                <td className="px-3 py-2.5"></td>
                <td className="px-3 py-2.5"></td>
                <td className="px-3 py-2.5 text-right tabular-nums text-income">{formatCurrency(portfolios.reduce((s, p) => s + p.annual_income, 0), true)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatCurrency(portfolios.reduce((s, p) => s + p.annual_income, 0) / 12, true)}</td>
                <td className="px-3 py-2.5"></td>
                <td className="px-3 py-2.5"></td>
              </tr>
            )}
            {portfolios.length === 0 && (
              <tr>
                <td colSpan={10} className="px-4 py-6 text-center text-sm text-muted-foreground">
                  {data === null ? "Loading portfolios…" : "No portfolios found."}
                </td>
              </tr>
            )}
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
          {incomeData.length === 0 ? (
            <div className="flex h-full min-h-45 flex-col items-center justify-center gap-1">
              <p className="text-sm text-muted-foreground">No upcoming dividends</p>
              <p className="text-[11px] text-muted-foreground/60">Upload a portfolio to populate the calendar.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {incomeData.slice(0, 5).map((d) => (
                <div key={d.month} className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{d.month}</span>
                  <span className="font-mono text-sm font-medium tabular-nums text-income">
                    {formatCurrency(d.projected ?? d.actual ?? 0)}
                  </span>
                </div>
              ))}
            </div>
          )}
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

        {/* Income Quality */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-4 text-sm font-medium text-muted-foreground">Income Quality</h2>
          <div className="space-y-4">
            {qualityTiers.map((tier) => (
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
          <div className="flex h-full min-h-32 flex-col items-center justify-center gap-1">
            <p className="text-sm text-muted-foreground">No NAV alerts</p>
            <p className="text-[11px] text-muted-foreground/60">CEF/BDC discount alerts appear here after scoring.</p>
          </div>
        </Link>
      </div>
    </div>
  );
}
