"use client";

import { useState, useEffect } from "react";
import { TrendingUp, RefreshCw } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";
import { TickerBadge } from "@/components/ticker-badge";
import { usePortfolio } from "@/lib/portfolio-context";
import { apiPost } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

// Raw shape returned by /api/scenarios/income-projection
interface ApiProjectionResult {
  portfolio_id: string;
  horizon_months: number;
  projected_income_p10: number;
  projected_income_p50: number;
  projected_income_p90: number;
  by_position: {
    symbol: string;
    base_income: number;  // current annual income
    p10: number;
    p50: number;          // projected annual P50
    p90: number;
  }[];
  computed_at: string;
}

// Shape used by the UI (derived fields added client-side)
interface ProjectionResult extends ApiProjectionResult {
  by_position: {
    symbol: string;
    base_income: number;
    p10: number;
    p50: number;
    p90: number;
    growth_rate_pct: number;
    confidence: string;
  }[];
  monthly_series: {
    month: string;
    p10: number;
    p50: number;
    p90: number;
  }[];
}

function deriveConfidence(base: number, p10: number, p90: number): string {
  if (base <= 0) return "LOW";
  const spread = (p90 - p10) / base * 100;
  return spread < 5 ? "HIGH" : spread < 12 ? "MEDIUM" : "LOW";
}

const CONFIDENCE_COLORS: Record<string, string> = {
  HIGH: "text-emerald-400",
  MEDIUM: "text-amber-400",
  LOW: "text-red-400",
};

const HORIZONS = [3, 6, 12, 24, 36, 60];

// ── Main page ─────────────────────────────────────────────────────────────────

export function SimulationContent({ defaultPortfolioId }: { defaultPortfolioId?: string }) {
  const { portfolios } = usePortfolio();
  const [portfolioId, setPortfolioId] = useState(defaultPortfolioId ?? portfolios[0]?.id ?? "");
  const [horizonMonths, setHorizonMonths] = useState(12);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ProjectionResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    if (!portfolioId && portfolios.length > 0) setPortfolioId(portfolios[0].id);
  }, [portfolios, portfolioId]);

  const run = async () => {
    setLoading(true);
    setResult(null);
    setRunError(null);
    try {
      const raw = await apiPost<ApiProjectionResult>("/api/scenarios/income-projection", {
        portfolio_id: portfolioId,
        horizon_months: horizonMonths,
      });

      // Compute derived per-position fields
      const byPosition = (raw.by_position || []).map((pos) => ({
        ...pos,
        growth_rate_pct: pos.base_income > 0
          ? ((pos.p50 - pos.base_income) / pos.base_income) * 100
          : 0,
        confidence: deriveConfidence(pos.base_income, pos.p10, pos.p90),
      }));

      // Build monthly interpolation series from current base → projected P10/P50/P90
      const currentMonthly = byPosition.reduce((s, p) => s + (p.base_income || 0), 0) / 12;
      const p10Monthly = raw.projected_income_p10 / 12;
      const p50Monthly = raw.projected_income_p50 / 12;
      const p90Monthly = raw.projected_income_p90 / 12;
      const monthly_series = [];
      for (let i = 1; i <= raw.horizon_months; i++) {
        const t = i / raw.horizon_months;
        monthly_series.push({
          month: new Date(Date.now() + i * 30 * 86400 * 1000).toLocaleDateString("en-US", { month: "short", year: "2-digit" }),
          p10: Math.round(currentMonthly + t * (p10Monthly - currentMonthly)),
          p50: Math.round(currentMonthly + t * (p50Monthly - currentMonthly)),
          p90: Math.round(currentMonthly + t * (p90Monthly - currentMonthly)),
        });
      }

      setResult({ ...raw, by_position: byPosition, monthly_series });
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  };

  const portfolioName = portfolios.find((p) => p.id === portfolioId)?.name ?? portfolioId;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Income Simulation</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Monte Carlo simulation of portfolio income across P10 / P50 / P90 confidence intervals
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
          disabled={loading || !portfolioId}
          className={cn(
            "flex items-center gap-2 rounded-md px-5 py-2 text-sm font-medium transition-colors",
            loading || !portfolioId
              ? "bg-primary/50 text-primary-foreground/50 cursor-not-allowed"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          )}
        >
          {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <TrendingUp className="h-4 w-4" />}
          {loading ? "Projecting..." : "Run Projection"}
        </button>
      </div>

      {/* Error banner */}
      {runError && !loading && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {runError}
        </div>
      )}

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
            {(() => {
              const allVals = result.monthly_series.flatMap(d => [d.p10, d.p50, d.p90]);
              const yMin = Math.min(...allVals);
              const yMax = Math.max(...allVals);
              const yPad = Math.max((yMax - yMin) * 0.25, yMax * 0.04);
              const domainMin = Math.max(0, Math.floor((yMin - yPad) / 50) * 50);
              const domainMax = Math.ceil((yMax + yPad) / 50) * 50;
              return (
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
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#6b7280" }} tickLine={false} axisLine={false} interval={Math.max(0, Math.floor(result.monthly_series.length / 6) - 1)} />
                <YAxis
                  tick={{ fontSize: 10, fill: "#6b7280" }}
                  tickLine={false}
                  axisLine={false}
                  width={60}
                  domain={[domainMin, domainMax]}
                  tickFormatter={(v: number) => {
                    if (v >= 10000) return `$${(v / 1000).toFixed(0)}k`;
                    if (v >= 1000) return `$${(v / 1000).toFixed(1)}k`;
                    return `$${v.toFixed(0)}`;
                  }}
                />
                <Tooltip
                  contentStyle={{ background: "#1a1a2e", border: "1px solid #2d2d44", borderRadius: 6, fontSize: 12 }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={(v: any, n: any) => [formatCurrency(Number(v)), n === "p90" ? "P90 Bull" : n === "p10" ? "P10 Bear" : "P50 Base"] as [string, string]}
                />
                <Area type="monotone" dataKey="p90" stroke="#10b981" strokeWidth={1} strokeDasharray="3 3" fill="url(#p90g)" dot={false} />
                <Area type="monotone" dataKey="p50" stroke="#94a3b8" strokeWidth={2} fill="none" dot={false} />
                <Area type="monotone" dataKey="p10" stroke="#f87171" strokeWidth={1} strokeDasharray="3 3" fill="url(#p10g)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
              );
            })()}
          </div>

          {/* By position table */}
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">By Position</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-secondary/40">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Symbol</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Current Annual</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">P10 Bear</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">P50 Base</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">P90 Bull</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Growth</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {result.by_position.filter((pos) => pos.base_income > 0).map((pos) => (
                    <tr key={pos.symbol} className="border-b border-border/50 hover:bg-secondary/20">
                      <td className="px-3 py-2.5">
                        <TickerBadge symbol={pos.symbol} />
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-xs text-income">{formatCurrency(pos.base_income)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-xs text-red-400">{formatCurrency(pos.p10)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-xs font-medium">{formatCurrency(pos.p50)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-xs text-emerald-400">{formatCurrency(pos.p90)}</td>
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
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && !runError && (
        <div className="rounded-lg border border-border bg-card py-16 text-center">
          <TrendingUp className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Select a portfolio and horizon, then run the projection</p>
        </div>
      )}
    </div>
  );
}

export default function IncomeSimulationPage() {
  return <SimulationContent />;
}
