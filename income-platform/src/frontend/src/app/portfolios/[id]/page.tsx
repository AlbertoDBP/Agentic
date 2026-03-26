"use client";
import { useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { ChevronDown, ChevronUp, ArrowLeft, RefreshCw } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip as ReTip, ResponsiveContainer } from "recharts";
import { usePortfolioSummary } from "@/lib/hooks/use-portfolios";
import { KpiStrip } from "@/components/portfolio/kpi-strip";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import { HHS_HELP } from "@/lib/help-content";
import { cn, formatCurrency } from "@/lib/utils";
import { ASSET_CLASS_COLORS } from "@/lib/config";
import { PortfolioTab }   from "./tabs/portfolio-tab";
import { MarketTab }      from "./tabs/market-tab";
import { HealthTab }      from "./tabs/health-tab";
import { SimulationContent } from "@/app/income-simulation/page";
import { ProjectionContent } from "@/app/income-projection/page";

const SECTOR_COLORS: Record<string, string> = {
  "Financial Services":     "#3b82f6",
  "Real Estate":            "#22c55e",
  "Energy":                 "#f97316",
  "Utilities":              "#eab308",
  "Healthcare":             "#ef4444",
  "Technology":             "#a855f7",
  "Consumer Defensive":     "#14b8a6",
  "Consumer Cyclical":      "#ec4899",
  "Industrials":            "#94a3b8",
  "Communication Services": "#06b6d4",
  "Fixed Income":           "#f59e0b",
  "Other":                  "#475569",
};

const CHART_FALLBACK = "#64748b";

function MiniPie({ data, colorMap }: { data: { name: string; value: number }[]; colorMap: Record<string, string> }) {
  if (!data.length) return null;
  return (
    <div>
      <ResponsiveContainer width="100%" height={130}>
        <PieChart>
          <Pie
            data={data}
            cx="40%"
            cy="50%"
            innerRadius={32}
            outerRadius={55}
            dataKey="value"
            strokeWidth={1}
            stroke="#1e293b"
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={colorMap[entry.name] ?? CHART_FALLBACK} />
            ))}
          </Pie>
          <ReTip
            contentStyle={{ background: "#1a2035", border: "1px solid #334155", borderRadius: 6, fontSize: 11 }}
            labelStyle={{ color: "#e2e4ea" }}
            itemStyle={{ color: "#a0aabb" }}
            formatter={(v) => [`${Number(v).toFixed(1)}%`, ""]}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-x-2 gap-y-1 mt-1">
        {data.map((entry, i) => (
          <div key={i} className="flex items-center gap-1 text-[0.6rem] text-muted-foreground">
            <div className="w-2 h-2 rounded-sm shrink-0" style={{ background: colorMap[entry.name] ?? CHART_FALLBACK }} />
            {entry.name} {entry.value.toFixed(0)}%
          </div>
        ))}
      </div>
    </div>
  );
}

type Tab = "portfolio" | "market" | "health" | "simulation" | "projection";
const TABS: { key: Tab; label: string }[] = [
  { key: "portfolio",  label: "Portfolio" },
  { key: "market",     label: "Market" },
  { key: "health",     label: "Health" },
  { key: "simulation", label: "Simulation" },
  { key: "projection", label: "Income Projection" },
];

export default function PortfolioPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const rawTab = searchParams.get("tab");
  const activeTab: Tab =
    (TABS.map(t => t.key) as string[]).includes(rawTab ?? "")
      ? (rawTab as Tab)
      : "portfolio";
  const [summaryOpen, setSummaryOpen] = useState(true);

  const { data: summary, isLoading, error, refetch } = usePortfolioSummary(id);

  const setTab = (tab: Tab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tab);
    router.replace(`/portfolios/${id}?${params.toString()}`);
  };

  // built after early-returns; summary may be undefined, handled by ?? fallbacks
  const kpis = [
    { label: "Agg HHS",     value: summary?.agg_hhs?.toFixed(1) ?? "—",
      colorClass: summary?.agg_hhs != null ? (summary.agg_hhs >= 70 ? "text-green-400" : summary.agg_hhs >= 50 ? "text-amber-400" : "text-red-400") : undefined,
      helpText: HHS_HELP.agg_hhs },
    { label: "NAA Yield",   value: summary?.naa_yield != null ? `${(summary.naa_yield * 100).toFixed(2)}%` : "—", colorClass: summary?.naa_yield != null ? "text-green-400" : undefined, helpText: HHS_HELP.naa_yield },
    { label: "Value",       value: summary ? formatCurrency(summary.total_value) : "—" },
    { label: "Ann. Income", value: summary ? formatCurrency(summary.annual_income) : "—", colorClass: "text-blue-400" },
    { label: "HHI",         value: summary?.hhi?.toFixed(3) ?? "—",
      colorClass: (summary?.hhi ?? 0) > 0.10 ? "text-amber-400" : undefined, helpText: HHS_HELP.hhi },
    { label: "Holdings",    value: summary?.holding_count?.toString() ?? "—" },
    { label: "⚠ UNSAFE",   value: (summary?.unsafe_count ?? 0).toString(),
      colorClass: (summary?.unsafe_count ?? 0) > 0 ? "text-red-400" : undefined,
      alert: (summary?.unsafe_count ?? 0) > 0, helpText: HHS_HELP.unsafe_flag },
  ];

  if (isLoading) return <div className="p-4 text-muted-foreground text-sm animate-pulse">Loading portfolio…</div>;
  if (error) return (
    <div className="p-4">
      <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-3 text-sm text-red-400 flex items-center justify-between">
        Failed to load portfolio.
        <button className="underline text-xs" onClick={() => refetch()}>Retry</button>
      </div>
    </div>
  );

  return (
    <div className="p-4 max-w-screen-2xl mx-auto">
      {/* Identity header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <button onClick={() => router.push("/dashboard")} className="text-muted-foreground hover:text-foreground" aria-label="Back to dashboard">
              <ArrowLeft className="h-4 w-4" />
            </button>
            <h1 className="text-lg font-bold">{summary?.name ?? id}</h1>
            {(summary?.unsafe_count ?? 0) > 0 && (
              <span className="bg-red-950 text-red-400 text-[0.6rem] font-bold px-1.5 py-0.5 rounded">
                ⚠ {summary?.unsafe_count} UNSAFE
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 ml-6 mt-0.5 text-xs text-muted-foreground">
            {summary?.tax_status && <span className="bg-muted/80 rounded px-1.5 py-0.5 text-foreground/80">{summary.tax_status}</span>}
            {summary?.broker && <span className="bg-muted/80 rounded px-1.5 py-0.5 text-foreground/80">{summary.broker}</span>}
            {summary?.holding_count != null && <span>{summary.holding_count} holdings</span>}
            {summary?.last_refresh && <span>Refreshed {new Date(summary.last_refresh).toLocaleDateString()}</span>}
          </div>
        </div>
        <button onClick={() => refetch()} className="p-1.5 text-muted-foreground hover:text-foreground" aria-label="Refresh portfolio">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* KPI strip */}
      <KpiStrip items={kpis} />

      {/* Collapsible summary */}
      <div className="bg-card border border-border rounded-lg mb-3 overflow-hidden">
        <button
          className="w-full flex items-center justify-between px-3.5 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground"
          onClick={() => setSummaryOpen(o => !o)}
        >
          <span>
            {!summaryOpen && summary && (
              <span className="text-foreground font-normal">
                {summary.concentration_by_class?.[0] && `${summary.concentration_by_class[0].class} ${Number(summary.concentration_by_class[0].pct).toFixed(0)}%`}
                {(summary?.unsafe_count ?? 0) > 0 && ` · ⚠ ${summary.unsafe_count} UNSAFE`}
              </span>
            )}
            {summaryOpen && "Summary"}
          </span>
          {summaryOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
        {summaryOpen && summary && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 px-3.5 pb-3.5">
            {/* Asset Class box */}
            <div className="rounded-lg border border-border/50 bg-background/40 p-3">
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Asset Class</div>
              <MiniPie
                data={(summary.concentration_by_class ?? []).map(c => ({ name: c.class, value: c.pct }))}
                colorMap={ASSET_CLASS_COLORS}
              />
            </div>

            {/* Top Income box */}
            <div className="rounded-lg border border-border/50 bg-background/40 p-3">
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Top Income</div>
              {(summary.top_income_holdings ?? []).map((h) => (
                <div key={h.ticker} className="mb-2">
                  <div className="flex items-center justify-between text-xs mb-0.5">
                    <span className={cn("font-mono font-medium", h.unsafe ? "text-amber-400" : "text-foreground")}>
                      {h.unsafe && "⚠ "}{h.ticker}
                    </span>
                    <span className="text-foreground/80 tabular-nums text-[10px]">{formatCurrency(h.annual_income)}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div className="h-full rounded-full bg-blue-400/70" style={{ width: `${h.income_pct}%` }} />
                    </div>
                    <span className="text-[10px] text-muted-foreground w-6 text-right tabular-nums">{h.income_pct.toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Sector box */}
            <div className="rounded-lg border border-border/50 bg-background/40 p-3">
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Sector</div>
              <MiniPie
                data={(summary.concentration_by_sector ?? []).map(s => ({ name: s.sector, value: s.pct }))}
                colorMap={SECTOR_COLORS}
              />
            </div>
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 overflow-x-auto pb-1 mb-3 border-b border-border">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "px-3 py-1.5 text-xs font-medium rounded-t whitespace-nowrap transition-colors",
              activeTab === t.key
                ? "bg-card border border-border border-b-card text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "portfolio"  && <PortfolioTab portfolioId={id} />}
      {activeTab === "market"     && <MarketTab portfolioId={id} />}
      {activeTab === "health"     && <HealthTab portfolioId={id} />}
      {activeTab === "simulation" && <SimulationContent defaultPortfolioId={id} />}
      {activeTab === "projection" && <ProjectionContent defaultPortfolioId={id} />}
    </div>
  );
}
