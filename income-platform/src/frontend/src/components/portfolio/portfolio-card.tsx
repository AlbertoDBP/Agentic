"use client";
import Link from "next/link";
import { cn, formatCurrency } from "@/lib/utils";
import type { PortfolioListItem } from "@/lib/types";
import { HhsBadge } from "./hhs-badge";
import { ConcentrationBar } from "./concentration-bar";
import { ArrowRight } from "lucide-react";

interface PortfolioCardProps {
  portfolio: PortfolioListItem;
}

export function PortfolioCard({ portfolio: p }: PortfolioCardProps) {
  return (
    <Link
      href={`/portfolios/${p.id}`}
      className="bg-card border border-border rounded-xl flex-shrink-0 w-[300px] overflow-hidden snap-start hover:border-border/80 transition-colors"
    >
      {/* Header */}
      <div className="flex items-start justify-between px-3.5 pt-3 pb-2 border-b border-border/50">
        <div>
          <div className="font-bold text-sm leading-tight">{p.name}</div>
          <div className="text-[0.6rem] text-muted-foreground mt-0.5 space-x-1.5">
            {p.tax_status && <span className="bg-muted rounded px-1 py-0.5">{p.tax_status}</span>}
            {p.broker && <span className="bg-muted rounded px-1 py-0.5">{p.broker}</span>}
            <span>{p.holding_count} holdings</span>
          </div>
        </div>
        <div className="text-right">
          <HhsBadge
            status={p.agg_hhs != null ? (p.agg_hhs >= 85 ? "STRONG" : p.agg_hhs >= 70 ? "GOOD" : p.agg_hhs >= 50 ? "WATCH" : "CONCERN") : undefined}
            score={p.agg_hhs}
          />
        </div>
      </div>

      {/* KPI grid 3×2 */}
      <div className="grid grid-cols-3 gap-px bg-border/30 border-b border-border/50">
        {[
          { label: "Value",        value: formatCurrency(p.total_value), positive: null },
          { label: "Ann. Income",  value: formatCurrency(p.annual_income), positive: null },
          { label: "NAA Yield",    value: p.naa_yield != null ? `${(p.naa_yield * 100).toFixed(2)}%` : "—", positive: null },
          { label: "YoC",          value: p.agg_yoc != null ? `${(p.agg_yoc * 100).toFixed(2)}%` : "—", positive: null },
          { label: "Total Return", value: p.total_return != null ? `${p.total_return >= 0 ? "+" : ""}${p.total_return.toFixed(1)}%` : "—", positive: p.total_return != null ? p.total_return >= 0 : null },
          { label: "HHI",         value: p.hhi != null ? p.hhi.toFixed(3) : "—", positive: null },
        ].map((kpi, i) => (
          <div key={i} className="bg-card px-2.5 py-1.5">
            <div className="text-[0.55rem] font-bold uppercase text-muted-foreground">{kpi.label}</div>
            <div className={cn("text-xs font-bold mt-0.5", kpi.positive === true ? "text-green-400" : kpi.positive === false ? "text-red-400" : "text-foreground")}>
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      {/* Concentration bar */}
      <div className="px-3.5 py-2.5">
        <ConcentrationBar
          items={(p.concentration_by_class ?? []).map(c => ({ label: c.class, pct: c.pct }))}
        />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-3.5 pb-3">
        <div className="flex items-center gap-1.5 text-[0.6rem] text-muted-foreground">
          {p.unsafe_count > 0 && (
            <span className="bg-red-950 text-red-400 rounded px-1.5 py-0.5 font-bold">⚠ {p.unsafe_count} UNSAFE</span>
          )}
        </div>
        <span className="flex items-center gap-1 text-xs text-blue-400 font-medium">
          Open <ArrowRight className="h-3 w-3" />
        </span>
      </div>
    </Link>
  );
}

export function AddPortfolioCard() {
  return (
    <div className="flex-shrink-0 w-[300px] border-2 border-dashed border-border rounded-xl flex items-center justify-center min-h-[200px] text-muted-foreground text-sm snap-start">
      <div className="text-center p-4">
        <div className="text-2xl mb-2">+</div>
        <div className="font-medium">Add Portfolio</div>
        <div className="text-xs text-muted-foreground/70 mt-1">Coming soon</div>
      </div>
    </div>
  );
}
