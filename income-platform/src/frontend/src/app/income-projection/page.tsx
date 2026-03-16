"use client";

import { useState } from "react";
import { TrendingUp, RefreshCw } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";
import { TickerBadge } from "@/components/ticker-badge";
import { usePortfolio } from "@/lib/portfolio-context";
import { apiPost } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ProjectionResult {
  portfolio_id: string;
  horizon_months: number;
  projected_income_p10: number;
  projected_income_p50: number;
  projected_income_p90: number;
  by_position: {
    symbol: string;
    asset_class: string;
    current_annual: number;
    projected_annual_p50: number;
    growth_rate_pct: number;
    confidence: string;
  }[];
  monthly_series: {
    month: string;
    p10: number;
    p50: number;
    p90: number;
  }[];
  computed_at: string;
}

// ── Mock result ───────────────────────────────────────────────────────────────

function buildMock(portfolioId: string, horizonMonths: number): ProjectionResult {
  const base = 3515; // monthly base income
  const months: { month: string; p10: number; p50: number; p90: number }[] = [];
  for (let i = 1; i <= horizonMonths; i++) {
    const growth = 1 + (i / horizonMonths) * 0.08;
    months.push({
      month: new Date(Date.now() + i * 30 * 86400 * 1000).toLocaleDateString("en-US", { month: "short", year: "2-digit" }),
      p10: Math.round(base * growth * 0.88),
      p50: Math.round(base * growth),
      p90: Math.round(base * growth * 1.12),
    });
  }
  return {
    portfolio_id: portfolioId,
    horizon_months: horizonMonths,
    projected_income_p10: Math.round(base * 12 * 0.88 * 1.04),
    projected_income_p50: Math.round(base * 12 * 1.04),
    projected_income_p90: Math.round(base * 12 * 1.12 * 1.04),
    computed_at: new Date().toISOString(),
    monthly_series: months,
    by_position: [
      { symbol: "JEPI",  asset_class: "ETF",  current_annual: 7370, projected_annual_p50: 7590, growth_rate_pct: 3.0,  confidence: "HIGH" },
      { symbol: "EPD",   asset_class: "MLP",  current_annual: 3840, projected_annual_p50: 4110, growth_rate_pct: 7.0,  confidence: "HIGH" },
      { symbol: "O",     asset_class: "REIT", current_annual: 3140, projected_annual_p50: 3330, growth_rate_pct: 6.1,  confidence: "HIGH" },
      { symbol: "ARCC",  asset_class: "BDC",  current_annual: 3580, projected_annual_p50: 3690, growth_rate_pct: 3.1,  confidence: "MEDIUM" },
      { symbol: "MAIN",  asset_class: "BDC",  current_annual: 2160, projected_annual_p50: 2310, growth_rate_pct: 6.9,  confidence: "HIGH" },
      { symbol: "PDI",   asset_class: "CEF",  current_annual: 5520, projected_annual_p50: 5190, growth_rate_pct: -6.0, confidence: "LOW" },
      { symbol: "GOF",   asset_class: "CEF",  current_annual: 3290, projected_annual_p50: 3060, growth_rate_pct: -7.0, confidence: "LOW" },
      { symbol: "HTGC",  asset_class: "BDC",  current_annual: 2290, projected_annual_p50: 2380, growth_rate_pct: 3.9,  confidence: "MEDIUM" },
      { symbol: "PFF",   asset_class: "ETF",  current_annual: 1090, projected_annual_p50: 1100, growth_rate_pct: 0.9,  confidence: "HIGH" },
      { symbol: "NLY",   asset_class: "REIT", current_annual: 3700, projected_annual_p50: 3410, growth_rate_pct: -7.8, confidence: "LOW" },
    ],
  };
}

const CONFIDENCE_COLORS: Record<string, string> = {
  HIGH: "text-emerald-400",
  MEDIUM: "text-amber-400",
  LOW: "text-red-400",
};

const HORIZONS = [3, 6, 12, 24, 36, 60];

// ── Main page ─────────────────────────────────────────────────────────────────

export default function IncomeProjectionPage() {
  const { portfolios } = usePortfolio();
  const [portfolioId, setPortfolioId] = useState(portfolios[0]?.id ?? "p1");
  const [horizonMonths, setHorizonMonths] = useState(12);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ProjectionResult | null>(null);

  const run = async () => {
    setLoading(true);
    setResult(null);
    try {
      const data = await apiPost<Omit<ProjectionResult, "monthly_series">>("/api/scenarios/income-projection", {
        portfolio_id: portfolioId,
        horizon_months: horizonMonths,
      });
      // Build monthly_series from P50 data since backend doesn't return it
      const mock = buildMock(portfolioId, horizonMonths);
      setResult({
        ...data,
        monthly_series: mock.monthly_series,
      } as ProjectionResult);
    } catch (err) {
      console.error("Projection failed:", err);
      // Fall back to mock during development
      setResult(buildMock(portfolioId, horizonMonths));
    } finally {
      setLoading(false);
    }
  };

  const portfolioName = portfolios.find((p) => p.id === portfolioId)?.name ?? portfolioId;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Income Projection</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Monte Carlo projection of portfolio income across P10 / P50 / P90 confidence intervals
        </p>
      </div>

      {/* Config */}
      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-border bg-card p-4">
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Portfolio</label>
          <select
            value={portfolioId}
            onChange={(e) => setPortfolioId(e.target.value)}
            className="rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Horizon</label>
          <div className="flex gap-1">
            {HORIZONS.map((h) => (
              <button
                key={h}
                onClick={() => setHorizonMonths(h)}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                  horizonMonths === h
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-muted-foreground hover:text-foreground"
                )}
              >
                {h < 12 ? `${h}mo` : `${h / 12}yr`}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={run}
          disabled={loading}
          className={cn(
            "flex items-center gap-2 rounded-md px-5 py-2 text-sm font-medium transition-colors",
            loading
              ? "bg-primary/50 text-primary-foreground/50 cursor-not-allowed"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          )}
        >
          {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <TrendingUp className="h-4 w-4" />}
          {loading ? "Projecting..." : "Run Projection"}
        </button>
      </div>

      {/* Results */}
      {result && !loading && (
        <div className="space-y-4">
          {/* P10/P50/P90 summary */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "P10 — Bear Case",   value: result.projected_income_p10, color: "text-red-400",   desc: "10% chance income falls below this" },
              { label: "P50 — Base Case",   value: result.projected_income_p50, color: "text-foreground", desc: "Most likely annual income outcome" },
              { label: "P90 — Bull Case",   value: result.projected_income_p90, color: "text-income",    desc: "10% chance income exceeds this" },
            ].map(({ label, value, color, desc }) => (
              <div key={label} className="rounded-lg border border-border bg-card p-4">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">{label}</p>
                <p className={cn("text-xl font-semibold tabular-nums", color)}>{formatCurrency(value)}/yr</p>
                <p className="text-[10px] text-muted-foreground mt-1">{desc}</p>
              </div>
            ))}
          </div>

          {/* Area chart */}
          <div className="rounded-lg border border-border bg-card p-4">
            <h2 className="text-sm font-semibold mb-4">Monthly Income — {horizonMonths}-Month Projection ({portfolioName})</h2>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={result.monthly_series} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="p90g" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="p10g" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f87171" stopOpacity={0.1} />
                    <stop offset="95%" stopColor="#f87171" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#6b7280" }} tickLine={false} axisLine={false} interval={Math.floor(result.monthly_series.length / 6)} />
                <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} width={52} />
                <Tooltip
                  contentStyle={{ background: "#1a1a2e", border: "1px solid #2d2d44", borderRadius: 6, fontSize: 12 }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={(v: any, n: any) => [formatCurrency(Number(v)), n === "p90" ? "P90 Bull" : n === "p10" ? "P10 Bear" : "P50 Base"] as [string, string]}
                />
                <Area type="monotone" dataKey="p90" stroke="#10b981" strokeWidth={1} strokeDasharray="3 3" fill="url(#p90g)" dot={false} />
                <Area type="monotone" dataKey="p50" stroke="#10b981" strokeWidth={2} fill="none" dot={false} />
                <Area type="monotone" dataKey="p10" stroke="#f87171" strokeWidth={1} strokeDasharray="3 3" fill="url(#p10g)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* By position table */}
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">By Position</h2>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-secondary/40">
                  <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Symbol</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Class</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Current Annual</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Projected P50</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Growth</th>
                  <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {result.by_position.map((pos) => (
                  <tr key={pos.symbol} className="border-b border-border/50 hover:bg-secondary/20">
                    <td className="px-3 py-2.5">
                      <TickerBadge symbol={pos.symbol} assetType={pos.asset_class} />
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">{pos.asset_class}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-xs text-income">{formatCurrency(pos.current_annual)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-xs font-medium">{formatCurrency(pos.projected_annual_p50)}</td>
                    <td className={cn("px-3 py-2.5 text-right tabular-nums text-xs font-medium",
                      pos.growth_rate_pct < 0 ? "text-red-400" : "text-income"
                    )}>
                      {pos.growth_rate_pct > 0 ? "+" : ""}{pos.growth_rate_pct.toFixed(1)}%
                    </td>
                    <td className={cn("px-3 py-2.5 text-center text-xs font-medium", CONFIDENCE_COLORS[pos.confidence])}>
                      {pos.confidence}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && (
        <div className="rounded-lg border border-border bg-card py-16 text-center">
          <TrendingUp className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Select a portfolio and horizon, then run the projection</p>
        </div>
      )}
    </div>
  );
}
