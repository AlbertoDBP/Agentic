// src/frontend/src/components/scanner/portfolio-badges.tsx
import { Badge } from "@/components/ui/badge";
import type { ScanItem } from "@/lib/types";

interface PortfolioBadgesProps {
  item: ScanItem;
}

export function PortfolioBadges({ item }: PortfolioBadgesProps) {
  const ctx = item.portfolio_context;
  if (!ctx) return null;

  const income_ok = (item.score_details.valuation_yield_score ?? 40) >= 28;
  const durable_ok = (item.score_details.financial_durability_score ?? 40) >= 28;

  return (
    <div className="flex flex-wrap gap-1 mt-0.5">
      {ctx.already_held && (
        <Badge variant="secondary" className="text-xs px-1.5 py-0">Already Held</Badge>
      )}
      {ctx.class_overweight && (
        <Badge variant="outline" className="text-xs px-1.5 py-0 border-amber-500 text-amber-600">
          Class ⚠ {ctx.asset_class_weight_pct.toFixed(0)}%
        </Badge>
      )}
      {ctx.sector_overweight && (
        <Badge variant="outline" className="text-xs px-1.5 py-0 border-amber-500 text-amber-600">
          Sector ⚠ {ctx.sector_weight_pct.toFixed(0)}%
        </Badge>
      )}
      {ctx.replacing_ticker && (
        <Badge className="text-xs px-1.5 py-0 bg-blue-500 hover:bg-blue-500">
          Replacing: {ctx.replacing_ticker}
        </Badge>
      )}
      <Badge
        variant="outline"
        className={`text-xs px-1.5 py-0 ${income_ok ? "border-emerald-500 text-emerald-600" : "border-amber-500 text-amber-600"}`}
      >
        Income {income_ok ? "✓" : "⚠"}
      </Badge>
      <Badge
        variant="outline"
        className={`text-xs px-1.5 py-0 ${durable_ok ? "border-emerald-500 text-emerald-600" : "border-amber-500 text-amber-600"}`}
      >
        Durable {durable_ok ? "✓" : "⚠"}
      </Badge>
    </div>
  );
}
