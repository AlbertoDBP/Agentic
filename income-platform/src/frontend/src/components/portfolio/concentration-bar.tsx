"use client";
import { cn } from "@/lib/utils";
import { DESIGN_TOKENS } from "@/lib/config";
import { HelpTooltip } from "@/components/help-tooltip";

interface ConcentrationItem {
  label: string;
  pct: number;
  colorClass?: string;
}

interface ConcentrationBarProps {
  items: ConcentrationItem[];
  label?: string;
  helpText?: string;
  className?: string;
}

export function ConcentrationBar({ items, label, helpText, className }: ConcentrationBarProps) {
  const withColors = items.map((item) => ({
    ...item,
    colorClass: item.colorClass ?? DESIGN_TOKENS.ASSET_CLASS_COLORS[item.label] ?? "bg-slate-600",
  }));

  return (
    <div className={cn("space-y-1.5", className)}>
      {label && (
        <div className="flex items-center gap-1 text-[0.625rem] font-bold uppercase text-muted-foreground tracking-wide">
          {label}
          {helpText && <HelpTooltip text={helpText} />}
        </div>
      )}
      {/* Stacked bar */}
      <div className="flex h-2.5 w-full rounded overflow-hidden gap-px">
        {withColors.map((item) => (
          <div
            key={item.label}
            className={cn("h-full", item.colorClass)}
            style={{ width: `${item.pct}%` }}
            title={`${item.label}: ${item.pct}%`}
          />
        ))}
      </div>
      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {withColors.map((item) => (
          <div key={item.label} className="flex items-center gap-1 text-[0.6rem] text-muted-foreground">
            <div className={cn("w-2 h-2 rounded-sm flex-shrink-0", item.colorClass)} />
            {item.label} {item.pct.toFixed(0)}%
          </div>
        ))}
      </div>
    </div>
  );
}
