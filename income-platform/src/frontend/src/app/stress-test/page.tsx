"use client";

import { useMemo, useState, useEffect } from "react";
import { Shield, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import { type ColumnDef } from "@tanstack/react-table";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";
import { TickerBadge } from "@/components/ticker-badge";
import { DataTable } from "@/components/data-table";
import { usePortfolio } from "@/lib/portfolio-context";
import { apiPost } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PositionImpact {
  symbol: string;
  asset_class: string;
  current_value: number;
  stressed_value: number;
  current_income: number;
  stressed_income: number;
  value_change_pct: number;
  income_change_pct: number;
  vulnerability_rank: number;
}

interface StressResult {
  portfolio_id: string;
  scenario_name: string;
  portfolio_value_before: number;
  portfolio_value_after: number;
  value_change_pct: number;
  annual_income_before: number;
  annual_income_after: number;
  income_change_pct: number;
  position_impacts: PositionImpact[];
  computed_at: string;
}

// ── Scenario presets ──────────────────────────────────────────────────────────

const SCENARIOS = [
  { id: "RATE_HIKE_200BPS",     label: "Rate Hike +200bps",      desc: "Fed raises rates 200bp — hits REITs, CEFs, Preferreds hardest" },
  { id: "RATE_HIKE_400BPS",     label: "Rate Hike +400bps",      desc: "Aggressive rate cycle — 2022-style shock" },
  { id: "MARKET_CORRECTION_20", label: "Market Correction -20%", desc: "Broad equity correction — income assets partially insulated" },
  { id: "CREDIT_SPREAD_WIDEN",  label: "Credit Spread Widening", desc: "IG/HY spreads widen 200bp — BDCs and CLO equity hit hard" },
  { id: "RECESSION_MILD",       label: "Mild Recession",         desc: "GDP -2%, dividend cuts at weakest payers, BDC NAV erosion" },
  { id: "RECESSION_DEEP",       label: "Deep Recession",         desc: "GDP -6%, widespread distribution cuts, credit defaults rise" },
  { id: "INFLATION_SPIKE",      label: "Inflation Spike",        desc: "CPI spikes to 8%+ — real income eroded, TIPS and MLPs hold" },
  { id: "CUSTOM",               label: "Custom Scenario",        desc: "Define your own shock parameters" },
];

// ── Custom scenario params ─────────────────────────────────────────────────────

interface CustomParams {
  equity_shock_pct: string;
  rate_change_bps: string;
  spread_change_bps: string;
  bdc_nav_change_pct: string;
}

// ── Table columns ──────────────────────────────────────────────────────────────

const COLUMNS: ColumnDef<PositionImpact>[] = [
  {
    accessorKey: "vulnerability_rank",
    header: "Rank",
    cell: ({ getValue }) => (
      <span className="tabular-nums text-xs text-muted-foreground">{getValue<number>()}</span>
    ),
    size: 60,
  },
  {
    accessorKey: "symbol",
    header: "Symbol",
    cell: ({ row }) => (
      <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_class} />
    ),
    size: 100,
  },
  {
    accessorKey: "asset_class",
    header: "Class",
    cell: ({ getValue }) => <span className="text-xs text-muted-foreground">{getValue<string>()}</span>,
    size: 80,
  },
  {
    accessorKey: "current_value",
    header: "Value Before",
    cell: ({ getValue }) => <span className="tabular-nums text-xs">{formatCurrency(getValue<number>())}</span>,
    size: 110,
    meta: { align: "right" },
  },
  {
    accessorKey: "stressed_value",
    header: "Value After",
    cell: ({ getValue }) => <span className="tabular-nums text-xs">{formatCurrency(getValue<number>())}</span>,
    size: 110,
    meta: { align: "right" },
  },
  {
    accessorKey: "value_change_pct",
    header: "Δ Value",
    cell: ({ getValue }) => {
      const v = getValue<number>();
      return (
        <span className={cn("tabular-nums text-xs font-medium", v < 0 ? "text-red-400" : "text-income")}>
          {v > 0 ? "+" : ""}{v.toFixed(1)}%
        </span>
      );
    },
    size: 80,
    meta: { align: "right" },
  },
  {
    accessorKey: "current_income",
    header: "Income Before",
    cell: ({ getValue }) => <span className="tabular-nums text-xs text-income">{formatCurrency(getValue<number>())}</span>,
    size: 115,
    meta: { align: "right" },
  },
  {
    accessorKey: "stressed_income",
    header: "Income After",
    cell: ({ getValue }) => <span className="tabular-nums text-xs">{formatCurrency(getValue<number>())}</span>,
    size: 115,
    meta: { align: "right" },
  },
  {
    accessorKey: "income_change_pct",
    header: "Δ Income",
    cell: ({ getValue }) => {
      const v = getValue<number>();
      return (
        <span className={cn("tabular-nums text-xs font-medium", v < 0 ? "text-red-400" : "text-income")}>
          {v > 0 ? "+" : ""}{v.toFixed(1)}%
        </span>
      );
    },
    size: 80,
    meta: { align: "right" },
  },
];

// ── Main page ─────────────────────────────────────────────────────────────────

export function StressTestContent({ defaultPortfolioId }: { defaultPortfolioId?: string }) {
  const { portfolios } = usePortfolio();
  const [portfolioId, setPortfolioId] = useState(defaultPortfolioId ?? portfolios[0]?.id ?? "");
  const [scenarioId, setScenarioId] = useState("RATE_HIKE_200BPS");
  const [customParams, setCustomParams] = useState<CustomParams>({
    equity_shock_pct: "-20",
    rate_change_bps: "200",
    spread_change_bps: "150",
    bdc_nav_change_pct: "-10",
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<StressResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    if (!portfolioId && portfolios.length > 0) setPortfolioId(portfolios[0].id);
  }, [portfolios, portfolioId]);

  const runTest = async () => {
    setLoading(true);
    setResult(null);
    setRunError(null);
    try {
      const payload: Record<string, unknown> = {
        portfolio_id: portfolioId,
        scenario_type: scenarioId,
        save: false,
      };
      if (scenarioId === "CUSTOM") {
        payload.scenario_params = {
          equity_shock_pct: Number(customParams.equity_shock_pct),
          rate_change_bps: Number(customParams.rate_change_bps),
          spread_change_bps: Number(customParams.spread_change_bps),
          bdc_nav_change_pct: Number(customParams.bdc_nav_change_pct),
        };
      }
      const data = await apiPost<StressResult>("/api/scenarios/stress-test", payload);
      setResult(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Stress test failed";
      setRunError(msg);
    } finally {
      setLoading(false);
    }
  };

  const selectedScenario = SCENARIOS.find((s) => s.id === scenarioId);
  const tableData = useMemo(
    () => result ? [...result.position_impacts].sort((a, b) => a.vulnerability_rank - b.vulnerability_rank) : [],
    [result]
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Stress Test</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Simulate how your portfolio performs under adverse market scenarios
        </p>
      </div>

      {/* Config panel */}
      <div className="rounded-lg border border-border bg-card p-5 space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Portfolio</label>
            <select
              value={portfolioId}
              onChange={(e) => setPortfolioId(e.target.value)}
              className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {portfolios.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Scenario</label>
            <select
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {SCENARIOS.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        {selectedScenario && (
          <p className="text-xs text-muted-foreground bg-secondary rounded-md px-3 py-2">
            {selectedScenario.desc}
          </p>
        )}

        {scenarioId === "CUSTOM" && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 border-t border-border pt-3">
            {[
              { key: "equity_shock_pct",   label: "Equity Shock (%)" },
              { key: "rate_change_bps",    label: "Rate Change (bps)" },
              { key: "spread_change_bps",  label: "Spread Change (bps)" },
              { key: "bdc_nav_change_pct", label: "BDC NAV Change (%)" },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1">
                  {label}
                </label>
                <input
                  type="number"
                  value={(customParams as unknown as Record<string, string>)[key]}
                  onChange={(e) => setCustomParams((p) => ({ ...p, [key]: e.target.value }))}
                  className="w-full rounded-md border border-border bg-secondary px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
            ))}
          </div>
        )}

        <button
          onClick={runTest}
          disabled={loading || !portfolioId}
          className={cn(
            "flex items-center gap-2 rounded-md px-5 py-2 text-sm font-medium transition-colors",
            loading || !portfolioId
              ? "bg-primary/50 text-primary-foreground/50 cursor-not-allowed"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          )}
        >
          {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
          {loading ? "Running..." : "Run Stress Test"}
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
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Portfolio Value Before", value: formatCurrency(result.portfolio_value_before), change: null },
              { label: "Portfolio Value After",  value: formatCurrency(result.portfolio_value_after),  change: result.value_change_pct },
              { label: "Annual Income Before",   value: formatCurrency(result.annual_income_before),   change: null },
              { label: "Annual Income After",    value: formatCurrency(result.annual_income_after),    change: result.income_change_pct },
            ].map(({ label, value, change }) => (
              <div key={label} className="rounded-lg border border-border bg-card p-4">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">{label}</p>
                <p className="text-lg font-semibold tabular-nums">{value}</p>
                {change !== null && (
                  <div className={cn("flex items-center gap-1 mt-1 text-xs font-medium tabular-nums", change < 0 ? "text-red-400" : "text-income")}>
                    {change < 0 ? <TrendingDown className="h-3 w-3" /> : <TrendingUp className="h-3 w-3" />}
                    {change > 0 ? "+" : ""}{change.toFixed(1)}%
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Scenario impact bar */}
          <div className="rounded-lg border border-border bg-card px-4 py-3 flex items-center gap-4">
            <p className="text-xs text-muted-foreground shrink-0">
              Scenario: <span className="text-foreground font-medium">{result.scenario_name}</span>
            </p>
            <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full rounded-full bg-red-400"
                style={{ width: `${Math.min(Math.abs(result.value_change_pct), 100)}%` }}
              />
            </div>
            <p className="text-xs font-medium tabular-nums text-red-400 shrink-0">
              {result.value_change_pct.toFixed(1)}%
            </p>
          </div>

          {/* Position impacts — DataTable */}
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">Position Impacts</h2>
            </div>
            <DataTable
              columns={COLUMNS}
              data={tableData}
              storageKey="stress-test-impacts"
              frozenColumns={2}
              maxHeight="55vh"
            />
          </div>
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && !runError && (
        <div className="rounded-lg border border-border bg-card py-16 text-center">
          <Shield className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Select a portfolio and scenario, then run the stress test</p>
        </div>
      )}
    </div>
  );
}

export default function StressTestPage() {
  return <StressTestContent />;
}
