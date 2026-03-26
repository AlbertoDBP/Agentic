// src/frontend/src/components/scanner/entry-exit-badge.tsx
import { cn } from "@/lib/utils";
import type { EntryExit } from "@/lib/types";

const ZONE_CONFIG = {
  BELOW_ENTRY: { label: "Below Entry", dot: "bg-emerald-500", text: "text-emerald-600" },
  IN_ZONE:     { label: "In Zone",     dot: "bg-emerald-500", text: "text-emerald-600" },
  NEAR_ENTRY:  { label: "Near Entry",  dot: "bg-amber-500",   text: "text-amber-600" },
  ABOVE_ENTRY: { label: "Above Entry", dot: "bg-red-500",     text: "text-red-600" },
  UNKNOWN:     { label: "No Data",     dot: "bg-gray-400",    text: "text-gray-500" },
} as const;

interface EntryExitBadgeProps {
  entryExit: EntryExit | null | undefined;
  className?: string;
}

function fmt(v: number | null | undefined): string {
  if (v == null) return "—";
  return `$${v.toFixed(2)}`;
}

export function EntryExitBadge({ entryExit, className }: EntryExitBadgeProps) {
  if (!entryExit || entryExit.zone_status === "UNKNOWN") {
    return <span className="text-muted-foreground text-xs">—</span>;
  }

  const cfg = ZONE_CONFIG[entryExit.zone_status] ?? ZONE_CONFIG.UNKNOWN;
  const pct = entryExit.pct_from_entry;
  const sign = pct != null && pct >= 0 ? "+" : "";

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <span className={cn("text-sm font-medium tabular-nums", cfg.text)}>
        {fmt(entryExit.entry_limit)}
      </span>
      <span className={cn("inline-flex items-center gap-1 text-xs rounded-full px-1.5 py-0.5", cfg.text)}>
        <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", cfg.dot)} />
        {pct != null ? `${sign}${pct.toFixed(1)}%` : cfg.label}
      </span>
    </div>
  );
}

export function EntryExitExpandedRow({ entryExit }: { entryExit: EntryExit }) {
  const rows = [
    { label: "Technical entry", value: fmt(entryExit.signals.technical_entry) },
    { label: "Yield entry",     value: fmt(entryExit.signals.yield_entry) },
    { label: "NAV entry",       value: fmt(entryExit.signals.nav_entry) },
    { label: "Technical exit",  value: fmt(entryExit.signals.technical_exit) },
    { label: "Yield exit",      value: fmt(entryExit.signals.yield_exit) },
    { label: "NAV exit",        value: fmt(entryExit.signals.nav_exit) },
  ];

  return (
    <div className="grid grid-cols-3 gap-2 text-xs p-2">
      {rows.map(({ label, value }) => (
        <div key={label} className="flex justify-between gap-2">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-mono font-medium">{value}</span>
        </div>
      ))}
    </div>
  );
}
