import { cn, severityColor } from "@/lib/utils";

interface AlertBadgeProps {
  severity: string;
  count?: number;
  pulse?: boolean;
}

export function AlertBadge({ severity, count, pulse }: AlertBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
        severityColor(severity),
        pulse && "animate-pulse"
      )}
    >
      {severity}
      {count !== undefined && count > 0 && (
        <span className="ml-0.5 tabular-nums">({count})</span>
      )}
    </span>
  );
}
