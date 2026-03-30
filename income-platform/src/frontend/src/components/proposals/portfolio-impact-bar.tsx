// src/frontend/src/components/proposals/portfolio-impact-bar.tsx
"use client";

import { cn } from "@/lib/utils";
import type { PortfolioImpact } from "@/lib/types";

interface PortfolioImpactBarProps {
  impact: PortfolioImpact;
  cashBalance: number | null;
  className?: string;
}

export function PortfolioImpactBar({ impact, cashBalance, className }: PortfolioImpactBarProps) {
  const overBudget = cashBalance != null && impact.cash_required > cashBalance;

  return (
    <div className={cn(
      "flex items-center gap-0 rounded-lg border divide-x divide-border overflow-hidden text-sm",
      overBudget ? "border-amber-600/40 bg-amber-950/20" : "border-border bg-muted/20",
      className
    )}>
      <ImpactCell
        label="Cash Required"
        value={`$${impact.cash_required.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
        valueClass={overBudget ? "text-amber-400" : "text-foreground"}
        sub={cashBalance != null
          ? `${((impact.cash_required / cashBalance) * 100).toFixed(1)}% of cash`
          : undefined}
      />
      <ImpactCell
        label="Added Annual Income"
        value={`+$${impact.added_annual_income.toLocaleString("en-US", { maximumFractionDigits: 0 })}/yr`}
        valueClass="text-emerald-400"
      />
      <ImpactCell
        label="New Portfolio Yield"
        value={impact.new_portfolio_yield != null
          ? `${(impact.new_portfolio_yield * 100).toFixed(2)}%`
          : "—"}
        valueClass="text-foreground"
      />
      {impact.concentration_pct != null && (
        <ImpactCell
          label="Concentration"
          value={`${(impact.concentration_pct * 100).toFixed(1)}%`}
          valueClass={impact.concentration_pct > 0.1 ? "text-amber-400" : "text-foreground"}
        />
      )}
    </div>
  );
}

function ImpactCell({
  label,
  value,
  valueClass,
  sub,
}: {
  label: string;
  value: string;
  valueClass?: string;
  sub?: string;
}) {
  return (
    <div className="flex flex-col px-4 py-2 flex-1 min-w-0">
      <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</span>
      <span className={cn("text-sm font-semibold mt-0.5", valueClass)}>{value}</span>
      {sub && <span className="text-[10px] text-muted-foreground mt-0.5">{sub}</span>}
    </div>
  );
}

// ── Pure calculation helper ───────────────────────────────────────────────────

export function computeImpact(params: {
  proposals: Array<{
    platform_yield_estimate: number | null;
    analyst_yield_estimate: number | null;
  }>;
  orderParams: Array<{ shares: number | null; limit_price: number | null }>;
  currentAnnualIncome: number;
  currentPortfolioValue: number | null;
  cashBalance: number | null;
}): PortfolioImpact {
  const { proposals, orderParams, currentAnnualIncome, currentPortfolioValue, cashBalance } = params;

  let cashRequired = 0;
  let addedAnnualIncome = 0;

  for (let i = 0; i < proposals.length; i++) {
    const p = proposals[i];
    const o = orderParams[i];
    if (!o.shares || !o.limit_price) continue;

    const positionValue = o.shares * o.limit_price;
    cashRequired += positionValue;

    const yield_ = p.platform_yield_estimate ?? p.analyst_yield_estimate ?? 0;
    addedAnnualIncome += positionValue * yield_;
  }

  const newPortfolioYield = currentPortfolioValue != null && (currentPortfolioValue + cashRequired) > 0
    ? (currentAnnualIncome + addedAnnualIncome) / (currentPortfolioValue + cashRequired)
    : null;

  const concentrationPct = currentPortfolioValue != null && cashRequired > 0
    ? cashRequired / (currentPortfolioValue + cashRequired)
    : null;

  return {
    cash_required: cashRequired,
    added_annual_income: addedAnnualIncome,
    new_portfolio_yield: newPortfolioYield,
    concentration_pct: concentrationPct,
  };
}
