"use client";
import { cn } from "@/lib/utils";
import { HelpTooltip } from "@/components/help-tooltip";

interface KpiItem {
  label: string;
  value: string | number | null | undefined;
  helpText?: string;
  colorClass?: string;
  alert?: boolean;
}

interface KpiStripProps {
  items: KpiItem[];
  className?: string;
}

export function KpiStrip({ items, className }: KpiStripProps) {
  return (
    <div className={cn(
      "grid gap-1.5 mb-3",
      "grid-cols-2 sm:grid-cols-4 lg:grid-cols-8",
      className
    )}>
      {items.map((item, i) => (
        <div
          key={i}
          className={cn(
            "bg-card border rounded-lg px-2.5 py-1.5",
            item.alert && "border-red-900/50 bg-red-950/30"
          )}
        >
          <div className="flex items-center gap-0.5 text-[0.625rem] font-bold uppercase text-muted-foreground tracking-wide">
            {item.label}
            {item.helpText && <HelpTooltip text={item.helpText} />}
          </div>
          <div className={cn("text-sm font-bold mt-0.5", item.colorClass ?? "text-foreground")}>
            {item.value ?? "—"}
          </div>
        </div>
      ))}
    </div>
  );
}
