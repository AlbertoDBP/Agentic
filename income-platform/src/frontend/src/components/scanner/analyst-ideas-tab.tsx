// src/frontend/src/components/scanner/analyst-ideas-tab.tsx
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { AnalystIdeasDrawer } from "@/components/analyst-ideas-drawer";
import type { ScanResult, ScanItem, PortfolioListItem } from "@/lib/types";

interface Analyst {
  id: number;
  display_name: string;
  overall_accuracy: number | null;
}

const ASSET_CLASSES = ["BDC", "mREIT", "REIT", "Preferred", "Stock", "CEF", "Bond"];

// Same neutral bg for all grades, colored text — consistent with HHS badge
const GRADE_TEXT: Record<string, string> = {
  A: "text-emerald-400",
  B: "text-lime-400",
  C: "text-amber-400",
  D: "text-orange-400",
  F: "text-red-400",
};

// Shared column template used by both header and rows
// checkbox | rank | ticker | grade+score | rec | analyst | entry | exit
const COL_TEMPLATE = "20px 24px 100px 72px 92px minmax(0,1fr) 80px 68px";

interface AnalystIdeasTabProps {
  portfolios: PortfolioListItem[];
  onSuccess: (proposalId: string) => void;
}

export function AnalystIdeasTab({ portfolios, onSuccess }: AnalystIdeasTabProps) {
  // Filter state
  const [analysts, setAnalysts] = useState<Analyst[]>([]);
  const [selectedAnalystIds, setSelectedAnalystIds] = useState<number[]>([]);
  const [selectedAssetClasses, setSelectedAssetClasses] = useState<string[]>([]);
  const [minStaleness, setMinStaleness] = useState(0.3);
  const [showHistory, setShowHistory] = useState(false);

  // Scan state
  const [result, setResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selection + drawer
  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [drawerOpen, setDrawerOpen] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load analyst list once on mount
  useEffect(() => {
    fetch("/api/analyst-ideas/analysts")
      .then((r) => r.json())
      .then((data: Analyst[]) => setAnalysts(Array.isArray(data) ? data : []))
      .catch(() => {
        console.warn("Could not load analyst list — filter will show all analysts");
      });
  }, []);

  const runScan = useCallback(async (overrides?: {
    analystIds?: number[];
    assetClasses?: string[];
    staleness?: number;
    history?: boolean;
  }) => {
    setLoading(true);
    setError(null);
    setSelectedTickers(new Set());
    const ids = overrides?.analystIds ?? selectedAnalystIds;
    const classes = overrides?.assetClasses ?? selectedAssetClasses;
    const staleness = overrides?.staleness ?? minStaleness;
    const history = overrides?.history ?? showHistory;
    try {
      const resp = await fetch("/api/scanner/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tickers: [],
          use_universe: false,
          source: "analyst_ideas",
          analyst_ids: ids,
          asset_classes: classes.length ? classes : null,
          min_staleness_weight: staleness,
          include_history: history,
          min_score: 0,
          quality_gate_only: false,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Scan failed");
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [selectedAnalystIds, selectedAssetClasses, minStaleness, showHistory]);

  // Auto-scan on mount
  useEffect(() => {
    runScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Debounced re-scan on filter changes
  const debouncedScan = useCallback((overrides?: Parameters<typeof runScan>[0]) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runScan(overrides), 400);
  }, [runScan]);

  const toggleAnalyst = (id: number) => {
    const next = selectedAnalystIds.includes(id)
      ? selectedAnalystIds.filter((a) => a !== id)
      : [...selectedAnalystIds, id];
    setSelectedAnalystIds(next);
    debouncedScan({ analystIds: next });
  };

  const toggleAssetClass = (cls: string) => {
    const next = selectedAssetClasses.includes(cls)
      ? selectedAssetClasses.filter((c) => c !== cls)
      : [...selectedAssetClasses, cls];
    setSelectedAssetClasses(next);
    debouncedScan({ assetClasses: next });
  };

  const handleStalenessChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = parseFloat(e.target.value);
    setMinStaleness(v);
    debouncedScan({ staleness: v });
  };

  const handleToggleHistory = () => {
    const next = !showHistory;
    setShowHistory(next);
    runScan({ history: next });
  };

  const handleToggleTicker = (ticker: string) => {
    setSelectedTickers((prev) => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  };

  const clearFilters = () => {
    setSelectedAnalystIds([]);
    setSelectedAssetClasses([]);
    setMinStaleness(0.3);
    runScan({ analystIds: [], assetClasses: [], staleness: 0.3 });
  };

  // Split active vs history items
  const allItems = result?.items ?? [];
  const activeItems = allItems.filter((i) => i.analyst_context?.is_active !== false);
  const historyItems = allItems.filter((i) => i.analyst_context?.is_active === false);
  const passedCount = allItems.filter((i) => i.passed_quality_gate).length;
  const belowGateCount = allItems.filter((i) => !i.passed_quality_gate).length;
  const sourced_at: string | null = (result?.filters_applied as Record<string, unknown>)?.sourced_at as string ?? null;

  const belowGateSelected = [...selectedTickers].some(
    (t) => allItems.find((i) => i.ticker === t && !i.passed_quality_gate)
  );

  const renderRow = (item: ScanItem, isHistoryRow = false) => {
    const ctx = item.analyst_context;
    const isBelow = !item.passed_quality_gate;
    const gradeKey = item.grade?.[0] ?? "F";
    const gradeTextClass = GRADE_TEXT[gradeKey] ?? GRADE_TEXT.F;

    return (
      <div
        key={`${item.ticker}-${isHistoryRow}`}
        className={cn(
          "grid items-center px-3 py-2 border-b border-border/50 text-sm",
          isHistoryRow && "opacity-55"
        )}
        style={{ gridTemplateColumns: COL_TEMPLATE, gap: "0 6px" }}
      >
        {/* Checkbox */}
        <input
          type="checkbox"
          checked={selectedTickers.has(item.ticker)}
          onChange={() => handleToggleTicker(item.ticker)}
          className="accent-violet-500 w-3.5 h-3.5"
        />

        {/* Rank */}
        <span className="text-muted-foreground text-xs tabular-nums">
          {item.passed_quality_gate ? item.rank : "—"}
        </span>

        {/* Ticker + asset class + badges */}
        <div className="min-w-0">
          <div className="font-mono font-semibold text-[13px] leading-tight">
            {item.ticker}
          </div>
          <div className="text-[10px] text-muted-foreground leading-tight flex flex-wrap items-center gap-x-1">
            <span>{item.asset_class}</span>
            {isHistoryRow && <span className="italic">archived</span>}
            {isBelow && <span className="text-amber-400">⚠</span>}
          </div>
          {ctx?.is_proposed && (
            <span
              className="inline-block text-[9px] font-medium rounded-full px-1.5 py-0 bg-violet-900/40 text-violet-400 border border-violet-800/40"
              title={ctx.proposed_at ? `Submitted ${new Date(ctx.proposed_at).toLocaleDateString()}` : "Proposed"}
            >
              PROPOSED
            </span>
          )}
        </div>

        {/* Grade + Score — neutral bg, colored text by grade (HHS pattern) */}
        <div>
          <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 bg-zinc-900 border border-zinc-700/60 font-semibold">
            <span className={cn("text-[11px]", gradeTextClass)}>{item.grade}</span>
            <span className="text-xs tabular-nums text-zinc-300">{Math.round(item.score)}</span>
          </span>
        </div>

        {/* Recommendation */}
        <span className={cn(
          "text-xs font-semibold",
          item.recommendation === "BUY" ? "text-emerald-400" : "text-red-400"
        )}>
          {item.recommendation}
        </span>

        {/* Analyst name + staleness */}
        <div className="min-w-0 truncate">
          <div className="text-[11px] text-foreground/80 truncate">{ctx?.analyst_name ?? "—"}</div>
          <div className="text-[10px] text-violet-400/70">
            {ctx?.staleness_weight != null ? `w ${ctx.staleness_weight.toFixed(2)}` : ""}
          </div>
        </div>

        {/* Entry zone */}
        <span className="text-[11px] text-muted-foreground tabular-nums">
          {item.entry_exit?.entry_limit != null
            ? `$${item.entry_exit.entry_limit.toFixed(2)}`
            : "—"}
        </span>

        {/* Exit */}
        <span className={cn(
          "text-[11px] tabular-nums",
          item.recommendation === "SELL" ? "text-red-400" : "text-muted-foreground"
        )}>
          {item.entry_exit?.exit_limit != null ? `$${item.entry_exit.exit_limit.toFixed(2)}` : "—"}
        </span>
      </div>
    );
  };

  return (
    <div className="space-y-0">
      {/* Filter panel */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3 mb-4">
        <div className="grid grid-cols-3 gap-4">
          {/* Analysts multi-select */}
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-2">Analysts</label>
            <div className="flex flex-wrap gap-1.5">
              {analysts.length === 0 && (
                <span className="text-xs text-muted-foreground">All analysts</span>
              )}
              {analysts.map((a) => (
                <button
                  key={a.id}
                  onClick={() => toggleAnalyst(a.id)}
                  className={cn(
                    "text-xs rounded-full px-2.5 py-0.5 border transition-colors",
                    selectedAnalystIds.includes(a.id)
                      ? "bg-violet-900/40 text-violet-300 border-violet-700"
                      : "bg-muted/20 text-muted-foreground border-border hover:text-foreground"
                  )}
                >
                  {a.display_name}
                </button>
              ))}
            </div>
          </div>

          {/* Asset class badges */}
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-2">Asset Classes</label>
            <div className="flex flex-wrap gap-1.5">
              {ASSET_CLASSES.map((cls) => (
                <button
                  key={cls}
                  onClick={() => toggleAssetClass(cls)}
                  className={cn(
                    "text-xs rounded px-2 py-0.5 border transition-colors",
                    selectedAssetClasses.includes(cls)
                      ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                      : "bg-muted/20 text-muted-foreground border-border hover:text-foreground"
                  )}
                >
                  {selectedAssetClasses.includes(cls) ? `${cls} ✓` : cls}
                </button>
              ))}
            </div>
          </div>

          {/* Staleness slider */}
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-2">
              Min Staleness <span className="text-violet-400 font-semibold">{minStaleness.toFixed(2)}</span>
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={minStaleness}
              onChange={handleStalenessChange}
              className="w-full mt-2 accent-violet-500"
            />
            <p className="text-[10px] text-muted-foreground mt-1">How fresh and reliable (0 = any, 1 = only very recent high-accuracy ideas)</p>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md bg-red-950/30 border border-red-800/40 px-4 py-2 text-sm text-red-400 mb-3">
          {error}
        </div>
      )}

      {/* Stats bar + history toggle */}
      {result && !loading && (
        <div className="flex items-center justify-between px-1 py-1.5 mb-2">
          <div className="text-xs text-muted-foreground flex gap-3">
            <span>{allItems.length} analyst ideas</span>
            <span className="text-emerald-400">{passedCount} passed quality gate</span>
            {belowGateCount > 0 && (
              <span className="text-amber-400">{belowGateCount} below gate — selectable at your risk</span>
            )}
            {sourced_at && (
              <span className="ml-auto">Last ingestion: {new Date(sourced_at).toLocaleDateString()}</span>
            )}
          </div>
          <button
            onClick={handleToggleHistory}
            className={cn(
              "text-xs px-2.5 py-1 rounded border transition-colors",
              showHistory
                ? "bg-muted/40 text-foreground border-border"
                : "text-muted-foreground border-border/50 hover:text-foreground"
            )}
          >
            {showHistory ? "Hide history" : "Show history"}
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="py-12 text-center text-sm text-muted-foreground">
          Loading analyst ideas…
        </div>
      )}

      {/* Empty state */}
      {!loading && result && allItems.length === 0 && (
        <div className="py-12 text-center text-sm text-muted-foreground">
          No active analyst ideas match your filters. Agent 02 ingests newsletters bi-weekly.{" "}
          <button onClick={clearFilters} className="underline text-violet-400 hover:text-violet-300">
            Clear filters
          </button>
        </div>
      )}

      {/* Results table */}
      {!loading && allItems.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          {/* Header */}
          <div
            className="grid px-3 py-2 bg-muted/20 border-b border-border text-[10px] text-muted-foreground uppercase tracking-wide"
            style={{ gridTemplateColumns: COL_TEMPLATE, gap: "0 6px" }}
          >
            <span />
            <span>#</span>
            <span>Ticker</span>
            <span>Grade</span>
            <span>Rec</span>
            <span>Analyst</span>
            <span>Entry</span>
            <span>Exit</span>
          </div>

          {/* Active rows */}
          {activeItems.map((item) => renderRow(item, false))}

          {/* History rows (when toggle is on) */}
          {showHistory && historyItems.length > 0 && (
            <>
              <div className="px-3 py-1.5 text-[10px] text-muted-foreground/60 italic border-y border-border/50 bg-muted/10 text-center">
                — Previous suggestions (within expiry window) —
              </div>
              {historyItems.map((item) => renderRow(item, true))}
            </>
          )}
        </div>
      )}

      {/* Action bar */}
      {!loading && allItems.length > 0 && (
        <div className="flex items-center gap-3 px-1 py-3 border-t border-border mt-0">
          <span className="text-xs text-muted-foreground">{selectedTickers.size} selected</span>
          <Button
            size="sm"
            disabled={selectedTickers.size === 0}
            onClick={() => setDrawerOpen(true)}
            className="bg-violet-600 hover:bg-violet-500 text-white"
          >
            Create Proposal →
          </Button>
          {belowGateSelected && (
            <span className="text-xs text-amber-400">
              ⚠ {[...selectedTickers].filter((t) => allItems.find((i) => i.ticker === t && !i.passed_quality_gate)).length} below quality gate — included at your risk
            </span>
          )}
        </div>
      )}

      {/* Proposal drawer */}
      <AnalystIdeasDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        selectedTickers={selectedTickers}
        scanResult={result}
        portfolios={portfolios}
        onSuccess={(id) => {
          onSuccess(id);
          setSelectedTickers(new Set());
        }}
      />
    </div>
  );
}
