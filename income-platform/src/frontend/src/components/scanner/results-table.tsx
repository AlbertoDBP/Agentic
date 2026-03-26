// src/frontend/src/components/scanner/results-table.tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, ShieldAlert } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { EntryExitBadge, EntryExitExpandedRow } from "./entry-exit-badge";
import { PortfolioBadges } from "./portfolio-badges";
import type { ScanItem, ScanResult } from "@/lib/types";

// Grade color map
const GRADE_COLORS: Record<string, string> = {
  A: "bg-emerald-100 text-emerald-700",
  B: "bg-blue-100 text-blue-700",
  C: "bg-amber-100 text-amber-700",
  D: "bg-orange-100 text-orange-700",
  F: "bg-red-100 text-red-700",
};

function ScorePill({ score, grade }: { score: number; grade: string }) {
  const color = GRADE_COLORS[grade] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums", color)}>
      {score.toFixed(0)} <span className="font-bold">{grade}</span>
    </span>
  );
}

interface ResultsTableProps {
  result: ScanResult | null;
  selectedTickers: Set<string>;
  onToggleTicker: (ticker: string) => void;
  loading?: boolean;
}

export function ResultsTable({ result, selectedTickers, onToggleTicker, loading }: ResultsTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [showVetoed, setShowVetoed] = useState(false);

  const toggleExpand = (ticker: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground text-sm">
        Scanning…
      </div>
    );
  }

  if (!result) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground text-sm">
        Run a scan to see results.
      </div>
    );
  }

  const passed = result.items.filter((i) => !i.veto_flag);
  const vetoed = result.items.filter((i) => i.veto_flag);

  const renderRow = (item: ScanItem) => {
    const expanded = expandedRows.has(item.ticker);
    const selected = selectedTickers.has(item.ticker);

    return (
      <>
        <tr
          key={item.ticker}
          className={cn("border-b border-border hover:bg-muted/30 transition-colors", selected && "bg-primary/5")}
        >
          <td className="px-3 py-2.5 w-8">
            <Checkbox
              checked={selected}
              onCheckedChange={() => onToggleTicker(item.ticker)}
              disabled={item.veto_flag}
            />
          </td>
          <td className="px-3 py-2.5 text-xs text-muted-foreground tabular-nums">{item.rank || "—"}</td>
          <td className="px-3 py-2.5">
            <div>
              <span className="font-mono font-semibold text-sm">{item.ticker}</span>
              {item.portfolio_context && <PortfolioBadges item={item} />}
            </div>
          </td>
          <td className="px-3 py-2.5 text-xs text-muted-foreground">{item.asset_class.replace(/_/g, " ")}</td>
          <td className="px-3 py-2.5">
            <ScorePill score={item.score} grade={item.grade} />
          </td>
          <td className="px-3 py-2.5 text-xs">{item.recommendation.replace(/_/g, " ")}</td>
          <td className="px-3 py-2.5 text-xs tabular-nums">
            {item.entry_exit ? (
              <EntryExitBadge entryExit={item.entry_exit} />
            ) : "—"}
          </td>
          <td className="px-3 py-2.5 text-xs tabular-nums font-medium">
            {item.entry_exit?.current_price != null ? `$${item.entry_exit.current_price.toFixed(2)}` : "—"}
          </td>
          <td className="px-3 py-2.5 text-xs tabular-nums">
            {item.entry_exit?.exit_limit != null ? `$${item.entry_exit.exit_limit.toFixed(2)}` : "—"}
          </td>
          <td className="px-3 py-2.5 text-xs tabular-nums">
            {item.chowder_number != null ? item.chowder_number.toFixed(1) : "—"}
          </td>
          <td className="px-3 py-2.5">
            {item.veto_flag && <ShieldAlert className="h-4 w-4 text-red-500" />}
          </td>
          <td className="px-3 py-2.5 w-6">
            {item.entry_exit && (
              <button onClick={() => toggleExpand(item.ticker)} className="text-muted-foreground hover:text-foreground">
                {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              </button>
            )}
          </td>
        </tr>
        {expanded && item.entry_exit && (
          <tr className="bg-muted/20 border-b border-border">
            <td colSpan={12} className="px-6 py-2">
              <EntryExitExpandedRow entryExit={item.entry_exit} />
            </td>
          </tr>
        )}
      </>
    );
  };

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {/* Stats bar */}
      <div className="px-4 py-2 border-b border-border bg-muted/30 flex gap-4 text-xs text-muted-foreground">
        <span>{result.total_scanned} scanned</span>
        <span className="text-emerald-600 font-medium">{result.total_passed} passed</span>
        <span className="text-red-500">{result.total_vetoed} vetoed</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/20 text-xs text-muted-foreground">
              <th className="px-3 py-2 text-left w-8" />
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">Ticker</th>
              <th className="px-3 py-2 text-left">Class</th>
              <th className="px-3 py-2 text-left">Score</th>
              <th className="px-3 py-2 text-left">Rec</th>
              <th className="px-3 py-2 text-left">Entry $</th>
              <th className="px-3 py-2 text-left">Current $</th>
              <th className="px-3 py-2 text-left">Exit $</th>
              <th className="px-3 py-2 text-left">Chowder</th>
              <th className="px-3 py-2 text-left" />
              <th className="px-3 py-2 w-6" />
            </tr>
          </thead>
          <tbody>
            {passed.map(renderRow)}
            {vetoed.length > 0 && (
              <>
                <tr className="border-b border-border bg-muted/10">
                  <td colSpan={12} className="px-4 py-2">
                    <button
                      onClick={() => setShowVetoed(!showVetoed)}
                      className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                    >
                      {showVetoed ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      Show vetoed ({vetoed.length})
                    </button>
                  </td>
                </tr>
                {showVetoed && vetoed.map(renderRow)}
              </>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
