// src/frontend/src/components/portfolio/health-card.tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { GateStatus, RefreshLog } from "@/lib/types";

interface HealthCardProps {
  gate: GateStatus | null;
  refreshLog: RefreshLog | null;
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function stalenessColor(hrs: number | null | undefined): string {
  if (hrs == null) return "text-muted-foreground";
  if (hrs <= 24) return "text-emerald-600 dark:text-emerald-400";
  if (hrs <= 48) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function PortfolioHealthCard({ gate, refreshLog }: HealthCardProps) {
  const [expanded, setExpanded] = useState(false);

  const isBlocked = gate?.status === "blocked";
  const criticalCount = gate?.blocking_issue_count ?? 0;
  const staleness = refreshLog?.market_staleness_hrs;

  const dotColor = isBlocked
    ? "bg-red-500"
    : criticalCount === 0
    ? "bg-emerald-500"
    : "bg-amber-500";

  const label = isBlocked
    ? "Scoring Blocked"
    : criticalCount === 0
    ? "All Good"
    : `${criticalCount} Warning${criticalCount !== 1 ? "s" : ""}`;

  return (
    <div className="rounded-md border border-border bg-card px-4 py-2 text-sm">
      <button
        className="flex w-full items-center justify-between gap-3"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${dotColor}`}
            aria-hidden="true"
          />
          <span className="font-medium text-foreground">
            Data Health:{" "}
            <span
              className={
                isBlocked
                  ? "text-red-600 dark:text-red-400"
                  : "text-foreground"
              }
            >
              {label}
            </span>
          </span>
        </div>
        <div className="flex items-center gap-3 text-muted-foreground">
          {refreshLog?.market_data_refreshed_at && (
            <span>
              Market{" "}
              <span className={stalenessColor(staleness)}>
                {formatTime(refreshLog.market_data_refreshed_at)}
              </span>
            </span>
          )}
          {refreshLog?.scores_recalculated_at && (
            <span>
              · Scores{" "}
              <span className="text-foreground">
                {formatTime(refreshLog.scores_recalculated_at)}
              </span>
            </span>
          )}
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border pt-3 text-xs">
          <div>
            <p className="text-muted-foreground">Market refreshed</p>
            <p className={`font-medium ${stalenessColor(staleness)}`}>
              {formatTime(refreshLog?.market_data_refreshed_at)}
              {staleness != null && ` (${staleness.toFixed(1)}h ago)`}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Scores recalculated</p>
            <p className="font-medium text-foreground">
              {formatTime(refreshLog?.scores_recalculated_at)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Gate status</p>
            <p
              className={`font-medium ${
                isBlocked
                  ? "text-red-600 dark:text-red-400"
                  : "text-emerald-600 dark:text-emerald-400"
              }`}
            >
              {gate?.status ?? "—"}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Holdings complete</p>
            <p className="font-medium text-foreground">
              {refreshLog?.holdings_complete_count != null
                ? `${refreshLog.holdings_complete_count} / ${
                    (refreshLog.holdings_complete_count ?? 0) +
                    (refreshLog.holdings_incomplete_count ?? 0)
                  }`
                : "—"}
            </p>
          </div>
          {isBlocked && (
            <div className="col-span-2">
              <a
                href="/admin/data-quality"
                className="text-blue-600 underline hover:no-underline dark:text-blue-400"
              >
                View Data Quality Dashboard →
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
