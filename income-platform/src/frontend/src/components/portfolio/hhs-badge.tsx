"use client";
import { cn } from "@/lib/utils";

interface HhsBadgeProps {
  status?: string | null;
  score?: number | null;
  showScore?: boolean;
  className?: string;
}

const STATUS_STYLE: Record<string, string> = {
  STRONG:       "bg-zinc-900 border border-zinc-700/60 text-green-400",
  GOOD:         "bg-zinc-900 border border-zinc-700/60 text-lime-400",
  WATCH:        "bg-zinc-900 border border-zinc-700/60 text-amber-400",
  CONCERN:      "bg-zinc-900 border border-zinc-700/60 text-red-400",
  UNSAFE:       "bg-zinc-900 border border-zinc-700/60 text-red-400",
  INSUFFICIENT: "bg-zinc-900 border border-zinc-700/60 text-zinc-400",
};

export function HhsBadge({ status, score, showScore = true, className }: HhsBadgeProps) {
  if (!status) return <span className="text-muted-foreground text-xs">—</span>;
  const colorClass = STATUS_STYLE[status] ?? "bg-zinc-900 border border-zinc-700/60 text-zinc-400";
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
