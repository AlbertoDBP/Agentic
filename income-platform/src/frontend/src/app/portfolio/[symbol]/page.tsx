"use client";

import { use, useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, TrendingUp, DollarSign, Activity, AlertTriangle, Loader2 } from "lucide-react";
import { MetricCard } from "@/components/metric-card";
import { ScorePill } from "@/components/score-pill";
import { AlertBadge } from "@/components/alert-badge";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { ASSET_CLASS_COLORS } from "@/lib/config";
import { API_BASE_URL } from "@/lib/config";
import { usePortfolio } from "@/lib/portfolio-context";

interface Position {
  id: string;
  portfolio_id: string;
  symbol: string;
  name: string;
  asset_type: string;
  sector: string;
  shares: number;
  cost_basis: number;
  current_value: number;
  market_price: number;
  avg_cost: number;
  annual_income: number;
  yield_on_cost: number;
  current_yield: number;
  score: number;
  grade: string;
  price_updated_at: string | null;
  updated_at: string | null;
}

export default function TickerDetailPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = use(params);
  const { activePortfolio } = usePortfolio();

  const [position, setPosition] = useState<Position | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activePortfolio?.id) return;

    setLoading(true);
    setError(null);

    fetch(`${API_BASE_URL}/api/portfolios/${activePortfolio.id}/positions`, {
      credentials: "include",
    })
      .then((res) => {
        if (!res.ok) throw new Error(`API ${res.status}`);
        return res.json() as Promise<Position[]>;
      })
      .then((positions) => {
        const match = positions.find(
          (p) => p.symbol.toUpperCase() === symbol.toUpperCase()
        );
        if (match) {
          setPosition(match);
        } else {
          setError(`Position not found: ${symbol.toUpperCase()}`);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [activePortfolio?.id, symbol]);

  const backLink = (
    <Link
      href="/portfolio"
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" /> Back to Portfolio
    </Link>
  );

  if (loading) {
    return (
      <div className="space-y-4">
        {backLink}
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading {symbol.toUpperCase()}…</span>
        </div>
      </div>
    );
  }

  if (error || !position) {
    return (
      <div className="space-y-4">
        {backLink}
        <p className="text-muted-foreground">{error ?? `Position not found: ${symbol}`}</p>
      </div>
    );
  }

  const gain = position.current_value - position.cost_basis;
  const gainPct = position.cost_basis > 0 ? (gain / position.cost_basis) * 100 : 0;
  const color = ASSET_CLASS_COLORS[position.asset_type] || "#64748b";
  const currentPrice = position.market_price || (position.shares > 0 ? position.current_value / position.shares : 0);
  const avgCostPerShare = position.shares > 0 ? position.cost_basis / position.shares : position.avg_cost;

  // Build monthly income bars based on annual_income (flat monthly for simplicity; real data would need dividend calendar)
  const monthlyAmt = position.annual_income / 12;
  const monthlyIncome = Array(12).fill(monthlyAmt);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        {backLink}
        <div className="flex items-center gap-3 mt-3">
          <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
          <h1 className="text-2xl font-semibold">{position.symbol}</h1>
          <span className="rounded bg-secondary px-2 py-0.5 text-xs font-medium">{position.asset_type}</span>
          {position.score > 0 && <ScorePill score={position.score} />}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {position.name}
          {position.sector ? ` · ${position.sector}` : ""}
          {position.grade ? ` · Grade ${position.grade}` : ""}
        </p>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-6 gap-3">
        <MetricCard label="Current Value" value={formatCurrency(position.current_value)} icon={DollarSign} />
        <MetricCard label="Cost Basis" value={formatCurrency(position.cost_basis)} />
        <MetricCard
          label="Gain/Loss"
          value={`${gain >= 0 ? "+" : ""}${formatCurrency(gain)}`}
          delta={`${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(1)}%`}
          deltaType={gain >= 0 ? "positive" : "negative"}
          icon={TrendingUp}
        />
        <MetricCard label="Annual Income" value={formatCurrency(position.annual_income)} icon={DollarSign} />
        <MetricCard label="Yield on Cost" value={formatPercent(position.yield_on_cost * 100)} icon={Activity} />
        <MetricCard label="Current Yield" value={formatPercent(position.current_yield * 100)} />
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Position Details */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Position Details</h2>
          <dl className="space-y-2.5 text-sm">
            {[
              ["Shares", position.shares.toLocaleString()],
              ["Avg Cost/Share", formatCurrency(avgCostPerShare)],
              ["Current Price", formatCurrency(currentPrice)],
              ["Weight", activePortfolio?.total_value
                ? `${((position.current_value / activePortfolio.total_value) * 100).toFixed(1)}%`
                : "—"],
              ["Asset Type", position.asset_type],
              ["Sector", position.sector || "—"],
              ["Last Updated", position.price_updated_at
                ? new Date(position.price_updated_at).toLocaleDateString()
                : "—"],
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
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Monthly Income (Est.)</h2>
          <div className="flex items-end gap-1 h-32">
            {["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"].map((month, i) => {
              const val = monthlyIncome[i];
              const max = Math.max(...monthlyIncome, 1);
              const h = (val / max) * 100;
              return (
                <div key={month} className="flex flex-1 flex-col items-center gap-1">
                  <div className="w-full flex flex-col justify-end" style={{ height: 100 }}>
                    <div
                      className="w-full rounded-t"
                      style={{
                        height: `${h}%`,
                        backgroundColor: val > 0 ? "#10b981" : "#252d3d",
                        minHeight: val > 0 ? 4 : 1,
                      }}
                    />
                  </div>
                  <span className="text-[9px] text-muted-foreground">{month}</span>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex justify-between text-xs">
            <span className="text-muted-foreground">Annual</span>
            <span className="tabular-nums font-medium text-income">{formatCurrency(position.annual_income)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Monthly Avg</span>
            <span className="tabular-nums font-medium">{formatCurrency(position.annual_income / 12)}</span>
          </div>
        </div>

        {/* Analysis & Ratings */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Analysis</h2>
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Income Score</dt>
              <dd>{position.score > 0 ? <ScorePill score={position.score} /> : <span className="text-muted-foreground">—</span>}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Grade</dt>
              <dd className={cn("font-medium tabular-nums",
                position.grade === "A" && "text-income",
                position.grade === "B" && "text-income",
                position.grade === "C" && "text-yellow-400",
                position.grade === "D" && "text-orange-400",
                position.grade === "F" && "text-loss",
              )}>{position.grade || "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Current Yield</dt>
              <dd className="tabular-nums font-medium">{formatPercent(position.current_yield * 100)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Yield on Cost</dt>
              <dd className="tabular-nums font-medium">{formatPercent(position.yield_on_cost * 100)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Annual Income</dt>
              <dd className="tabular-nums font-medium text-income">{formatCurrency(position.annual_income)}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
