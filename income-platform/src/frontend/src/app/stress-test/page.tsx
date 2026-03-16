"use client";

import { useState } from "react";
import { Shield, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { TickerBadge } from "@/components/ticker-badge";
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
  { id: "RATE_HIKE_200BPS",       label: "Rate Hike +200bps",       desc: "Fed raises rates 200bp — hits REITs, CEFs, Preferreds hardest" },
  { id: "RATE_HIKE_400BPS",       label: "Rate Hike +400bps",       desc: "Aggressive rate cycle — 2022-style shock" },
  { id: "MARKET_CORRECTION_20",   label: "Market Correction -20%",  desc: "Broad equity correction — income assets partially insulated" },
  { id: "CREDIT_SPREAD_WIDEN",    label: "Credit Spread Widening",  desc: "IG/HY spreads widen 200bp — BDCs and CLO equity hit hard" },
  { id: "RECESSION_MILD",         label: "Mild Recession",          desc: "GDP -2%, dividend cuts at weakest payers, BDC NAV erosion" },
  { id: "RECESSION_DEEP",         label: "Deep Recession",          desc: "GDP -6%, widespread distribution cuts, credit defaults rise" },
  { id: "INFLATION_SPIKE",        label: "Inflation Spike",         desc: "CPI spikes to 8%+ — real income eroded, TIPS and MLPs hold" },
  { id: "CUSTOM",                 label: "Custom Scenario",         desc: "Define your own shock parameters" },
];

// ── Mock result ───────────────────────────────────────────────────────────────

const mockResult = (portfolioId: string, scenarioId: string): StressResult => ({
  portfolio_id: portfolioId,
  scenario_name: SCENARIOS.find(s => s.id === scenarioId)?.label ?? scenarioId,
  portfolio_value_before: 485_200,
  portfolio_value_after: 398_700,
  value_change_pct: -17.8,
  annual_income_before: 42_180,
  annual_income_after: 36_540,
  income_change_pct: -13.4,
  computed_at: new Date().toISOString(),
  position_impacts: [
    { symbol: "PDI",  asset_class: "CEF",      current_value: 38400, stressed_value: 27100, current_income: 5520, stressed_income: 4140, value_change_pct: -29.4, income_change_pct: -25.0, vulnerability_rank: 1 },
    { symbol: "GOF",  asset_class: "CEF",      current_value: 22800, stressed_value: 16900, current_income: 3290, stressed_income: 2630, value_change_pct: -25.9, income_change_pct: -20.1, vulnerability_rank: 2 },
    { symbol: "NLY",  asset_class: "REIT",     current_value: 31500, stressed_value: 24300, current_income: 3700, stressed_income: 3200, value_change_pct: -22.9, income_change_pct: -13.5, vulnerability_rank: 3 },
    { symbol: "PFF",  asset_class: "ETF",      current_value: 18200, stressed_value: 14800, current_income: 1090, stressed_income:  870, value_change_pct: -18.7, income_change_pct: -20.2, vulnerability_rank: 4 },
    { symbol: "EPD",  asset_class: "MLP",      current_value: 44600, stressed_value: 39900, current_income: 3840, stressed_income: 3600, value_change_pct: -10.5, income_change_pct:  -6.3, vulnerability_rank: 5 },
    { symbol: "MAIN", asset_class: "BDC",      current_value: 29400, stressed_value: 26500, current_income: 2160, stressed_income: 1980, value_change_pct:  -9.9, income_change_pct:  -8.3, vulnerability_rank: 6 },
    { symbol: "O",    asset_class: "REIT",     current_value: 52300, stressed_value: 47200, current_income: 3140, stressed_income: 2980, value_change_pct:  -9.8, income_change_pct:  -5.1, vulnerability_rank: 7 },
    { symbol: "ARCC", asset_class: "BDC",      current_value: 38700, stressed_value: 35300, current_income: 3580, stressed_income: 3300, value_change_pct:  -8.8, income_change_pct:  -7.8, vulnerability_rank: 8 },
    { symbol: "JEPI", asset_class: "ETF",      current_value: 61400, stressed_value: 56700, current_income: 7370, stressed_income: 6900, value_change_pct:  -7.7, income_change_pct:  -6.4, vulnerability_rank: 9 },
    { symbol: "HTGC", asset_class: "BDC",      current_value: 21800, stressed_value: 20300, current_income: 2290, stressed_income: 2160, value_change_pct:  -6.9, income_change_pct:  -5.7, vulnerability_rank: 10 },
  ],
});

// ── Custom scenario params ────────────────────────────────────────────────────

interface CustomParams {
  equity_shock_pct: string;
  rate_change_bps: string;
  spread_change_bps: string;
  bdc_nav_change_pct: string;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function StressTestPage() {
  const { portfolios } = usePortfolio();
  const [portfolioId, setPortfolioId] = useState(portfolios[0]?.id ?? "p1");
  const [scenarioId, setScenarioId] = useState("RATE_HIKE_200BPS");
  const [customParams, setCustomParams] = useState<CustomParams>({
    equity_shock_pct: "-20",
    rate_change_bps: "200",
    spread_change_bps: "150",
    bdc_nav_change_pct: "-10",
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<StressResult | null>(null);
  const [sortBy, setSortBy] = useState<"vulnerability_rank" | "value_change_pct">("vulnerability_rank");

  const runTest = async () => {
    setLoading(true);
    setResult(null);
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
      console.error("Stress test failed:", err);
      // Fall back to mock during development
      setResult(mockResult(portfolioId, scenarioId));
    } finally {
      setLoading(false);
    }
  };

  const sorted = result
    ? [...result.position_impacts].sort((a, b) =>
        sortBy === "vulnerability_rank"
          ? a.vulnerability_rank - b.vulnerability_rank
          : a.value_change_pct - b.value_change_pct
      )
    : [];

  const selectedScenario = SCENARIOS.find((s) => s.id === scenarioId);

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
          {/* Portfolio selector */}
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

          {/* Scenario selector */}
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

        {/* Scenario description */}
        {selectedScenario && (
          <p className="text-xs text-muted-foreground bg-secondary rounded-md px-3 py-2">
            {selectedScenario.desc}
          </p>
        )}

        {/* Custom params */}
        {scenarioId === "CUSTOM" && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 border-t border-border pt-3">
            {[
              { key: "equity_shock_pct",    label: "Equity Shock (%)" },
              { key: "rate_change_bps",     label: "Rate Change (bps)" },
              { key: "spread_change_bps",   label: "Spread Change (bps)" },
              { key: "bdc_nav_change_pct",  label: "BDC NAV Change (%)" },
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
          disabled={loading}
          className={cn(
            "flex items-center gap-2 rounded-md px-5 py-2 text-sm font-medium transition-colors",
            loading
              ? "bg-primary/50 text-primary-foreground/50 cursor-not-allowed"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          )}
        >
          {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
          {loading ? "Running..." : "Run Stress Test"}
        </button>
      </div>

      {/* Results */}
      {result && !loading && (
        <div className="space-y-4">
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Portfolio Value Before",  value: formatCurrency(result.portfolio_value_before),  change: null },
              { label: "Portfolio Value After",   value: formatCurrency(result.portfolio_value_after),   change: result.value_change_pct },
              { label: "Annual Income Before",    value: formatCurrency(result.annual_income_before),    change: null },
              { label: "Annual Income After",     value: formatCurrency(result.annual_income_after),     change: result.income_change_pct },
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

          {/* Impact bar */}
          <div className="rounded-lg border border-border bg-card px-4 py-3 flex items-center gap-4">
            <p className="text-xs text-muted-foreground shrink-0">Scenario: <span className="text-foreground font-medium">{result.scenario_name}</span></p>
            <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full rounded-full bg-red-400"
                style={{ width: `${Math.abs(result.value_change_pct)}%` }}
              />
            </div>
            <p className="text-xs font-medium tabular-nums text-red-400 shrink-0">{result.value_change_pct.toFixed(1)}%</p>
          </div>

          {/* Position impacts table */}
          <div className="rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">Position Impacts</h2>
              <div className="flex gap-2 text-xs">
                <span className="text-muted-foreground">Sort:</span>
                {[
                  { key: "vulnerability_rank", label: "Vulnerability" },
                  { key: "value_change_pct", label: "Value Impact" },
                ].map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => setSortBy(key as typeof sortBy)}
                    className={cn(
                      "rounded px-2 py-0.5 transition-colors",
                      sortBy === key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-secondary/40">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Rank</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Symbol</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Class</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Value Before</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Value After</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Δ Value</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Income Before</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Income After</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Δ Income</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((pos) => (
                    <tr key={pos.symbol} className="border-b border-border/50 hover:bg-secondary/20">
                      <td className="px-3 py-2.5 text-xs tabular-nums text-muted-foreground">{pos.vulnerability_rank}</td>
                      <td className="px-3 py-2.5">
                        <TickerBadge symbol={pos.symbol} assetType={pos.asset_class} />
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">{pos.asset_class}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-xs">{formatCurrency(pos.current_value)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-xs">{formatCurrency(pos.stressed_value)}</td>
                      <td className={cn("px-3 py-2.5 text-right tabular-nums text-xs font-medium", pos.value_change_pct < 0 ? "text-red-400" : "text-income")}>
                        {pos.value_change_pct > 0 ? "+" : ""}{pos.value_change_pct.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-xs text-income">{formatCurrency(pos.current_income)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-xs">{formatCurrency(pos.stressed_income)}</td>
                      <td className={cn("px-3 py-2.5 text-right tabular-nums text-xs font-medium", pos.income_change_pct < 0 ? "text-red-400" : "text-income")}>
                        {pos.income_change_pct > 0 ? "+" : ""}{pos.income_change_pct.toFixed(1)}%
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
      {!result && !loading && (
        <div className="rounded-lg border border-border bg-card py-16 text-center">
          <Shield className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Select a portfolio and scenario, then run the stress test</p>
        </div>
      )}
    </div>
  );
}
