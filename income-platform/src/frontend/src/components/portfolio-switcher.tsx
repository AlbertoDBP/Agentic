"use client";

import { ChevronDown } from "lucide-react";
import { usePortfolio } from "@/lib/portfolio-context";

export function PortfolioSwitcher() {
  const { portfolios, activePortfolio, setActiveId } = usePortfolio();

  if (portfolios.length === 0) {
    return (
      <div className="rounded-md border border-border bg-secondary px-3 py-1.5 text-xs text-muted-foreground">
        No portfolios
      </div>
    );
  }

  return (
    <div className="relative">
      <select
        value={activePortfolio?.id || ""}
        onChange={(e) => setActiveId(e.target.value)}
        className="w-full appearance-none rounded-md border border-border bg-secondary px-3 py-1.5 pr-8 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        {portfolios.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}
