"use client";
import { cn } from "@/lib/utils";
import { DESIGN_TOKENS } from "@/lib/config";
import { HelpTooltip } from "@/components/help-tooltip";
import { HHS_HELP } from "@/lib/help-content";

interface HhsBadgeProps {
  status?: string | null;
  score?: number | null;
  showScore?: boolean;
  className?: string;
}

export function HhsBadge({ status, score, showScore = true, className }: HhsBadgeProps) {
  if (!status) return <span className="text-muted-foreground text-xs">—</span>;
  const colorClass = DESIGN_TOKENS.HHS_STATUS_COLORS[status] ?? "text-slate-400";
  return (
    <span className={cn("inline-flex items-center gap-1 font-semibold text-xs", colorClass, className)}>
      {status === "UNSAFE" && <span>⚠</span>}
      {status}
      {showScore && score != null && <span className="font-normal opacity-70">({score.toFixed(0)})</span>}
      <HelpTooltip text={HHS_HELP.hhs_status} />
    </span>
  );
}
