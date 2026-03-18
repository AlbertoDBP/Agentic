"use client";

import { useState, useMemo } from "react";
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
import { DollarSign, TrendingUp, Target } from "lucide-react";

// Per-portfolio mock projection data
const PROJECTIONS: Record<string, { month: string; projected: number; low: number; high: number }[]> = {
  p1: [
    { month: "Apr '26", projected: 3800, low: 3400, high: 4200 },
    { month: "May", projected: 4100, low: 3700, high: 4500 },
    { month: "Jun", projected: 3600, low: 3200, high: 4000 },
    { month: "Jul", projected: 4200, low: 3800, high: 4600 },
    { month: "Aug", projected: 3900, low: 3500, high: 4300 },
    { month: "Sep", projected: 4400, low: 3900, high: 4900 },
    { month: "Oct", projected: 3700, low: 3300, high: 4100 },
    { month: "Nov", projected: 4000, low: 3500, high: 4500 },
    { month: "Dec", projected: 4300, low: 3800, high: 4800 },
    { month: "Jan '27", projected: 3800, low: 3400, high: 4200 },
    { month: "Feb", projected: 4100, low: 3600, high: 4600 },
    { month: "Mar", projected: 3500, low: 3100, high: 3900 },
  ],
  p2: [
    { month: "Apr '26", projected: 520, low: 480, high: 560 },
    { month: "May", projected: 540, low: 500, high: 580 },
    { month: "Jun", projected: 510, low: 470, high: 550 },
    { month: "Jul", projected: 560, low: 520, high: 600 },
    { month: "Aug", projected: 530, low: 490, high: 570 },
    { month: "Sep", projected: 570, low: 530, high: 610 },
    { month: "Oct", projected: 500, low: 460, high: 540 },
    { month: "Nov", projected: 550, low: 510, high: 590 },
    { month: "Dec", projected: 580, low: 540, high: 620 },
    { month: "Jan '27", projected: 520, low: 480, high: 560 },
    { month: "Feb", projected: 540, low: 500, high: 580 },
    { month: "Mar", projected: 490, low: 450, high: 530 },
  ],
  p3: [
    { month: "Apr '26", projected: 380, low: 350, high: 410 },
    { month: "May", projected: 390, low: 360, high: 420 },
    { month: "Jun", projected: 370, low: 340, high: 400 },
    { month: "Jul", projected: 400, low: 370, high: 430 },
    { month: "Aug", projected: 385, low: 355, high: 415 },
    { month: "Sep", projected: 410, low: 380, high: 440 },
    { month: "Oct", projected: 375, low: 345, high: 405 },
    { month: "Nov", projected: 395, low: 365, high: 425 },
    { month: "Dec", projected: 420, low: 390, high: 450 },
    { month: "Jan '27", projected: 380, low: 350, high: 410 },
    { month: "Feb", projected: 390, low: 360, high: 420 },
    { month: "Mar", projected: 365, low: 335, high: 395 },
  ],
};

const GOALS: Record<string, number> = {
  p1: 50000,
  p2: 7000,
  p3: 5000,
};

export default function ProjectionPage() {
  const { portfolios, activePortfolio } = usePortfolio();
  const [selectedScope, setSelectedScope] = useState<string>("active");

  const data = useMemo(() => {
    if (selectedScope === "all") {
      // Merge all portfolios' projections
      const months = PROJECTIONS.p1 || [];
      return months.map((m, i) => {
        let projected = 0, low = 0, high = 0;
        for (const pid of Object.keys(PROJECTIONS)) {
          const row = PROJECTIONS[pid]?.[i];
          if (row) { projected += row.projected; low += row.low; high += row.high; }
        }
        return { month: m.month, projected, low, high };
      });
    }
    const pid = selectedScope === "active" ? (activePortfolio?.id || "p1") : selectedScope;
    return PROJECTIONS[pid] || PROJECTIONS.p1 || [];
  }, [selectedScope, activePortfolio]);

  const totalProjected = data.reduce((s, m) => s + m.projected, 0);
  const monthlyAvg = data.length > 0 ? totalProjected / data.length : 0;

  const goal = useMemo(() => {
    if (selectedScope === "all") {
      return Object.values(GOALS).reduce((s, g) => s + g, 0);
    }
    const pid = selectedScope === "active" ? (activePortfolio?.id || "p1") : selectedScope;
    return GOALS[pid] || 50000;
  }, [selectedScope, activePortfolio]);

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

      <div className="grid grid-cols-3 gap-4">
        <MetricCard
          label="12-Month Forecast"
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
          value={formatCurrency(goal, true)}
          delta={`${goalPct.toFixed(0)}% of target`}
          deltaType={goalPct >= 100 ? "positive" : "neutral"}
          icon={Target}
        />
      </div>

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

      {/* Monthly Income Bar Chart */}
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
    </div>
  );
}
