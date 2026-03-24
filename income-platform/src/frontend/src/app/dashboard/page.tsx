"use client";
import { useRef, useState, useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { usePortfolios } from "@/lib/hooks/use-portfolios";
import { PortfolioCard, AddPortfolioCard } from "@/components/portfolio/portfolio-card";
import { KpiStrip } from "@/components/portfolio/kpi-strip";
import { formatCurrency } from "@/lib/utils";
import { HHS_HELP } from "@/lib/help-content";

export default function DashboardPage() {
  const { data: portfolios, isLoading, error, refetch } = usePortfolios();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScroll, setCanScroll] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const check = () => setCanScroll(el.scrollWidth > el.clientWidth);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [portfolios]);

  const scroll = (dir: "left" | "right") => {
    scrollRef.current?.scrollBy({ left: dir === "left" ? -316 : 316, behavior: "smooth" });
  };

  // Aggregate strip computations
  const totalAum    = portfolios?.reduce((s, p) => s + (p.total_value ?? 0), 0) ?? 0;
  const totalIncome = portfolios?.reduce((s, p) => s + (p.annual_income ?? 0), 0) ?? 0;
  const unsafeTotal = portfolios?.reduce((s, p) => s + (p.unsafe_count ?? 0), 0) ?? 0;
  const avgHhs = (() => {
    if (!portfolios?.length) return null;
    const withHhs = portfolios.filter(p => p.agg_hhs != null && p.total_value);
    if (!withHhs.length) return null;
    const totalVal = withHhs.reduce((s, p) => s + p.total_value, 0);
    return withHhs.reduce((s, p) => s + (p.agg_hhs! * p.total_value / totalVal), 0);
  })();

  const kpis = [
    { label: "Total AUM",     value: formatCurrency(totalAum),            helpText: "Combined market value across all portfolios." },
    { label: "Ann. Income",   value: formatCurrency(totalIncome),          helpText: "Projected annual income based on current dividends." },
    { label: "Avg HHS",       value: avgHhs != null ? avgHhs.toFixed(1) : "—",
      colorClass: avgHhs != null ? (avgHhs >= 70 ? "text-green-400" : avgHhs >= 50 ? "text-amber-400" : "text-red-400") : undefined,
      helpText: HHS_HELP.agg_hhs },
    { label: "Portfolios",    value: portfolios?.length ?? 0 },
    { label: "⚠ UNSAFE",      value: unsafeTotal, colorClass: unsafeTotal > 0 ? "text-red-400" : undefined,
      alert: unsafeTotal > 0, helpText: HHS_HELP.unsafe_flag },
  ];

  return (
    <div className="p-4 max-w-screen-2xl mx-auto">
      <h1 className="text-lg font-bold mb-3">Dashboard</h1>

      {/* Aggregate KPI strip */}
      <KpiStrip items={kpis} />

      {/* Portfolio card scroll */}
      {isLoading && (
        <div className="flex gap-3 py-2">
          {[1,2,3].map(i => <div key={i} className="flex-shrink-0 w-[300px] h-[220px] bg-card rounded-xl animate-pulse border border-border" />)}
        </div>
      )}
      {error && (
        <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-3 text-sm text-red-400 flex items-center justify-between">
          Failed to load portfolios.
          <button className="underline text-xs" onClick={() => refetch()}>Retry</button>
        </div>
      )}
      {portfolios && (
        <div className="relative">
          <div
            ref={scrollRef}
            className="flex gap-3 overflow-x-auto pb-2 scroll-snap-x mandatory"
            style={{ scrollbarWidth: "thin" }}
          >
            {portfolios.map(p => <PortfolioCard key={p.id} portfolio={p} />)}
            <AddPortfolioCard />
          </div>
          {canScroll && (
            <div className="flex gap-2 justify-end mt-2">
              <button onClick={() => scroll("left")} className="p-1 rounded border border-border text-muted-foreground hover:text-foreground"><ChevronLeft className="h-4 w-4" /></button>
              <button onClick={() => scroll("right")} className="p-1 rounded border border-border text-muted-foreground hover:text-foreground"><ChevronRight className="h-4 w-4" /></button>
            </div>
          )}
          {portfolios.length === 0 && (
            <div className="flex items-center justify-center h-40 text-muted-foreground text-sm border border-dashed border-border rounded-xl">
              No portfolios yet. Create your first portfolio to get started.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
