"use client";

import { useState, useEffect, useMemo } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { usePortfolio } from "@/lib/portfolio-context";
import { MetricCard } from "@/components/metric-card";
import { formatCurrency } from "@/lib/utils";
import { DollarSign, TrendingUp, Target, Loader2 } from "lucide-react";
import { API_BASE_URL } from "@/lib/config";

interface IncomeByMonth {
  portfolio_id: string;
  monthly_totals: { month: string; month_num: number; total: number }[];
  annual_total: number;
}

interface ProjectionRow {
  month: string;
  projected: number;
  low: number;
  high: number;
}

export default function ProjectionPage() {
  const { portfolios, activePortfolio } = usePortfolio();
  const [selectedScope, setSelectedScope] = useState<string>("active");
  const [loading, setLoading] = useState(false);
  const [incomeData, setIncomeData] = useState<Record<string, IncomeByMonth>>({});

  useEffect(() => {
    if (portfolios.length === 0) return;
    setLoading(true);
    Promise.all(
      portfolios.map((p) =>
        fetch(`${API_BASE_URL}/api/portfolios/${p.id}/income-by-month`, { credentials: "include" })
          .then((r) => r.ok ? r.json() as Promise<IncomeByMonth> : null)
          .catch(() => null)
      )
    ).then((results) => {
      const map: Record<string, IncomeByMonth> = {};
      results.forEach((data, i) => { if (data) map[portfolios[i].id] = data; });
      setIncomeData(map);
    }).finally(() => setLoading(false));
  }, [portfolios]);

  const targetPids = useMemo(() => {
    if (selectedScope === "all") return portfolios.map((p) => p.id);
    return [selectedScope === "active" ? (activePortfolio?.id ?? "") : selectedScope];
  }, [selectedScope, portfolios, activePortfolio]);

  const data: ProjectionRow[] = useMemo(() => {
    const merged: Record<number, { month: string; total: number }> = {};
    for (const pid of targetPids) {
      const d = incomeData[pid];
      if (!d) continue;
      for (const mt of d.monthly_totals) {
        if (!merged[mt.month_num]) merged[mt.month_num] = { month: mt.month, total: 0 };
        merged[mt.month_num].total += mt.total;
      }
    }
    return Object.entries(merged)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([, { month, total }]) => ({
        month,
        projected: total,
        low: Math.round(total * 0.9),
        high: Math.round(total * 1.1),
      }));
  }, [incomeData, targetPids]);

  const totalProjected = useMemo(
    () => targetPids.reduce((sum, pid) => sum + (incomeData[pid]?.annual_total ?? 0), 0),
    [incomeData, targetPids]
  );

  const monthlyAvg = data.length > 0 ? totalProjected / 12 : 0;

  const goal = useMemo(() => {
    if (typeof window === "undefined") return 0;
    if (selectedScope === "all") {
      return portfolios.reduce((sum, p) => {
        try { const c = JSON.parse(localStorage.getItem(`portfolioConfig-${p.id}`) ?? "{}"); return sum + (Number(c.income_goal) || 0); } catch { return sum; }
      }, 0);
    }
    const pid = selectedScope === "active" ? (activePortfolio?.id ?? "") : selectedScope;
    try { const c = JSON.parse(localStorage.getItem(`portfolioConfig-${pid}`) ?? "{}"); return Number(c.income_goal) || 0; } catch { return 0; }
  }, [selectedScope, portfolios, activePortfolio]);

  const goalPct = goal > 0 ? (totalProjected / goal) * 100 : 0;

  const scopeLabel = selectedScope === "all"
    ? "All Portfolios"
    : selectedScope === "active"
      ? activePortfolio?.name || "Portfolio"
      : portfolios.find((p) => p.id === selectedScope)?.name || "Portfolio";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Income Projection</h1>
        <div className="flex items-center gap-2">
          {loading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
          <select
            value={selectedScope}
            onChange={(e) => setSelectedScope(e.target.value)}
            className="rounded-md border border-border bg-secondary px-3 py-1.5 text-xs"
          >
            <option value="active">{activePortfolio?.name || "Active Portfolio"}</option>
            <option value="all">All Portfolios</option>
            {portfolios.filter((p) => p.id !== activePortfolio?.id).map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      </div>

      {portfolios.length === 0 && !loading ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-card py-16 text-center">
          <p className="text-sm font-medium">No portfolio data</p>
          <p className="mt-1 text-xs text-muted-foreground">Upload a portfolio with positions to view projections.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <MetricCard
              label="Annual Projected"
              value={formatCurrency(totalProjected, true)}
              icon={DollarSign}
            />
            <MetricCard
              label="Monthly Average"
              value={formatCurrency(monthlyAvg)}
              icon={TrendingUp}
            />
            <MetricCard
              label="Annual Goal"
              value={goal > 0 ? formatCurrency(goal, true) : "Not set"}
              delta={goal > 0 ? `${goalPct.toFixed(0)}% of target` : undefined}
              deltaType={goalPct >= 100 ? "positive" : "neutral"}
              icon={Target}
            />
          </div>

          {data.length === 0 && !loading ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-card py-16 text-center">
              <p className="text-sm font-medium">No income data for this portfolio</p>
              <p className="mt-1 text-xs text-muted-foreground">Add positions to see monthly income projections.</p>
            </div>
          ) : (
            <>
              {/* Projection Chart */}
              <div className="rounded-lg border border-border bg-card p-5">
                <h2 className="mb-4 text-sm font-medium text-muted-foreground">Monthly Income Forecast — {scopeLabel}</h2>
                <ResponsiveContainer width="100%" height={340}>
                  <AreaChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#252d3d" vertical={false} />
                    <XAxis dataKey="month" tick={{ fill: "#8891a8", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#8891a8", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}K`} />
                    <Tooltip
                      contentStyle={{ background: "#111520", border: "1px solid #252d3d", borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: "#e8eaf0" }}
                      formatter={(value) => [formatCurrency(Number(value)), ""]}
                    />
                    <Area type="monotone" dataKey="high" stroke="transparent" fill="#3b82f6" fillOpacity={0.08} />
                    <Area type="monotone" dataKey="low" stroke="transparent" fill="#0a0d11" fillOpacity={1} />
                    <Area type="monotone" dataKey="projected" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Monthly Bar Chart */}
              <div className="rounded-lg border border-border bg-card p-5">
                <h2 className="mb-4 text-sm font-medium text-muted-foreground">Monthly Income Breakdown — {scopeLabel}</h2>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={data} barCategoryGap="20%">
                    <CartesianGrid strokeDasharray="3 3" stroke="#252d3d" vertical={false} />
                    <XAxis dataKey="month" tick={{ fill: "#8891a8", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#8891a8", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}K`} />
                    <Tooltip
                      contentStyle={{ background: "#111520", border: "1px solid #252d3d", borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: "#e8eaf0" }}
                      formatter={(value) => [formatCurrency(Number(value)), "Projected"]}
                    />
                    <Bar dataKey="projected" radius={[4, 4, 0, 0]}>
                      {data.map((entry, index) => (
                        <Cell key={index} fill={entry.projected >= monthlyAvg ? "#10b981" : "#3b82f6"} fillOpacity={0.85} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <p className="mt-2 text-[11px] text-muted-foreground text-center">Green bars = above monthly average · Blue = below</p>
              </div>

              {/* Goal Tracker */}
              {goal > 0 && (
                <div className="rounded-lg border border-border bg-card p-5">
                  <h2 className="mb-4 text-sm font-medium text-muted-foreground">Goal Progress — {scopeLabel}</h2>
                  <div className="flex items-center gap-6">
                    <div className="relative h-32 w-32">
                      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
                        <circle cx="50" cy="50" r="42" fill="none" stroke="#181d2a" strokeWidth="8" />
                        <circle
                          cx="50" cy="50" r="42" fill="none"
                          stroke={goalPct >= 100 ? "#10b981" : "#3b82f6"}
                          strokeWidth="8"
                          strokeDasharray={`${Math.min(goalPct, 100) / 100 * 264} 264`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-lg font-bold tabular-nums">{goalPct.toFixed(0)}%</span>
                        <span className="text-[10px] text-muted-foreground">of goal</span>
                      </div>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex gap-8">
                        <div>
                          <p className="text-muted-foreground">Projected</p>
                          <p className="text-lg font-semibold tabular-nums">{formatCurrency(totalProjected, true)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Goal</p>
                          <p className="text-lg font-semibold tabular-nums">{formatCurrency(goal, true)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Gap</p>
                          <p className={`text-lg font-semibold tabular-nums ${totalProjected >= goal ? "text-income" : "text-loss"}`}>
                            {totalProjected >= goal ? "+" : ""}{formatCurrency(totalProjected - goal, true)}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
