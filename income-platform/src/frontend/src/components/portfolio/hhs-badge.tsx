"use client";
import { cn } from "@/lib/utils";

interface HhsBadgeProps {
  status?: string | null;
  score?: number | null;
  showScore?: boolean;
  className?: string;
}

const STATUS_BG: Record<string, string> = {
  STRONG:       "bg-green-950/70 border border-green-800/40 text-green-300",
  GOOD:         "bg-lime-950/70  border border-lime-800/40  text-lime-300",
  WATCH:        "bg-amber-950/70 border border-amber-800/40 text-amber-300",
  CONCERN:      "bg-red-950/70   border border-red-800/40   text-red-300",
  UNSAFE:       "bg-red-950/70   border border-red-800/40   text-red-300",
  INSUFFICIENT: "bg-muted        border border-border        text-muted-foreground",
};

export function HhsBadge({ status, score, showScore = true, className }: HhsBadgeProps) {
  if (!status) return <span className="text-muted-foreground text-xs">—</span>;
  const colorClass = STATUS_BG[status] ?? "bg-muted text-muted-foreground";
  return (
    <span className={cn(
      "inline-flex items-center gap-1 text-xs font-semibold px-1.5 py-0.5 rounded",
      colorClass, className
    )}>
      {status === "UNSAFE" && <span>⚠</span>}
      {status}
      {showScore && score != null && <span className="font-normal opacity-80">({score.toFixed(0)})</span>}
    </span>
  );
}
