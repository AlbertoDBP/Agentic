// src/frontend/src/components/scanner/filter-panel.tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const ASSET_CLASSES = [
  "DIVIDEND_STOCK", "COVERED_CALL_ETF", "BOND",
  "EQUITY_REIT", "MORTGAGE_REIT", "BDC", "PREFERRED_STOCK",
];

export interface ScanFilters {
  // Group 1
  min_score: number;
  quality_gate_only: boolean;
  asset_classes: string[];
  // Group 2
  min_yield: number;
  max_payout_ratio: string;
  min_volume: string;
  min_market_cap_m: string;
  max_market_cap_m: string;
  min_price: string;
  max_price: string;
  max_pe: string;
  min_nav_discount_pct: string;
}

export const DEFAULT_FILTERS: ScanFilters = {
  min_score: 0,
  quality_gate_only: false,
  asset_classes: [],
  min_yield: 0,
  max_payout_ratio: "",
  min_volume: "",
  min_market_cap_m: "",
  max_market_cap_m: "",
  min_price: "",
  max_price: "",
  max_pe: "",
  min_nav_discount_pct: "",
};

interface FilterPanelProps {
  filters: ScanFilters;
  onChange: (f: ScanFilters) => void;
}

export function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const [open, setOpen] = useState(false);

  const set = (patch: Partial<ScanFilters>) => onChange({ ...filters, ...patch });

  const toggleClass = (cls: string) => {
    const current = filters.asset_classes;
    set({
      asset_classes: current.includes(cls)
        ? current.filter((c) => c !== cls)
        : [...current, cls],
    });
  };

  return (
    <div className="rounded-lg border border-border bg-card">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/50"
      >
        <span>Filters</span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-5 border-t border-border pt-4">
          {/* Group 1 */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Scoring</p>
            <div className="flex items-center gap-4">
              <Label className="text-sm w-24 shrink-0">Min Score: {filters.min_score}</Label>
              <Slider
                min={0} max={100} step={5}
                value={[filters.min_score]}
                onValueChange={([v]) => set({ min_score: v })}
                className="flex-1"
              />
            </div>
            <div className="flex items-center gap-3">
              <Switch
                id="quality-gate"
                checked={filters.quality_gate_only}
                onCheckedChange={(v) => set({ quality_gate_only: v })}
              />
              <Label htmlFor="quality-gate" className="text-sm">Quality gate only (≥70)</Label>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {ASSET_CLASSES.map((cls) => (
                <Badge
                  key={cls}
                  variant={filters.asset_classes.includes(cls) ? "default" : "outline"}
                  className="cursor-pointer select-none text-xs"
                  onClick={() => toggleClass(cls)}
                >
                  {cls.replace(/_/g, " ")}
                </Badge>
              ))}
            </div>
          </div>

          {/* Group 2 */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Market Data</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[
                { label: "Min Yield %", key: "min_yield" },
                { label: "Max Payout %", key: "max_payout_ratio" },
                { label: "Min Volume", key: "min_volume" },
                { label: "Min Cap $M", key: "min_market_cap_m" },
                { label: "Max Cap $M", key: "max_market_cap_m" },
                { label: "Min Price $", key: "min_price" },
                { label: "Max Price $", key: "max_price" },
                { label: "Max P/E", key: "max_pe" },
                { label: "NAV Discount %", key: "min_nav_discount_pct" },
              ].map(({ label, key }) => (
                <div key={key} className="space-y-1">
                  <Label className="text-xs text-muted-foreground">{label}</Label>
                  <Input
                    type="number"
                    value={(filters as Record<string, unknown>)[key] as string}
                    onChange={(e) => set({ [key]: e.target.value } as Partial<ScanFilters>)}
                    className="h-8 text-sm"
                    placeholder="—"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
