// src/frontend/src/components/scanner/analyst-ideas-tab.tsx
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { ChevronDown, ChevronRight, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { AnalystIdeasDrawer } from "@/components/analyst-ideas-drawer";
import { ScorePill } from "./results-table";
import { EntryExitBadge, EntryExitExpandedRow } from "./entry-exit-badge";
import type { ScanResult, ScanItem, PortfolioListItem } from "@/lib/types";

interface Analyst {
  id: number;
  display_name: string;
  overall_accuracy: number | null;
}

const ASSET_CLASSES = ["BDC", "mREIT", "REIT", "Preferred", "Stock", "CEF", "Bond"];

// Analyst-sourced recommendation colors (newsletter call, not income score)
const ANALYST_REC_COLOR: Record<string, string> = {
  Buy:          "text-emerald-600",
  BUY:          "text-emerald-600",
  Sell:         "text-red-500",
  SELL:         "text-red-500",
  Hold:         "text-amber-500",
  HOLD:         "text-amber-500",
};

interface AnalystIdeasTabProps {
  portfolios: PortfolioListItem[];
  onSuccess: (proposalId: string) => void;
}

export function AnalystIdeasTab({ portfolios, onSuccess }: AnalystIdeasTabProps) {
  const [analysts, setAnalysts] = useState<Analyst[]>([]);
  const [selectedAnalystIds, setSelectedAnalystIds] = useState<number[]>([]);
  const [selectedAssetClasses, setSelectedAssetClasses] = useState<string[]>([]);
  const [minStaleness, setMinStaleness] = useState(0.3);
  const [showHistory, setShowHistory] = useState(false);
  const [showVetoed, setShowVetoed] = useState(false);

  const [result, setResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [drawerOpen, setDrawerOpen] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetch("/api/analyst-ideas/analysts")
      .then((r) => r.json())
      .then((data: Analyst[]) => setAnalysts(Array.isArray(data) ? data : []))
      .catch(() => {});
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

  useEffect(() => {
    runScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const toggleExpand = (ticker: string) => {
    setExpandedRows((prev) => {
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

  const allItems = result?.items ?? [];
  const activeItems = allItems.filter((i) => i.analyst_context?.is_active !== false);
  const historyItems = allItems.filter((i) => i.analyst_context?.is_active === false);
  const passed = activeItems.filter((i) => !i.veto_flag);
  const vetoed = activeItems.filter((i) => i.veto_flag);
  const sourced_at: string | null = (result?.filters_applied as Record<string, unknown>)?.sourced_at as string ?? null;

  const belowGateSelected = [...selectedTickers].some(
    (t) => allItems.find((i) => i.ticker === t && !i.passed_quality_gate)
  );

  const renderRow = (item: ScanItem, isHistoryRow = false) => {
    const ctx = item.analyst_context;
    const expanded = expandedRows.has(item.ticker);
    const selected = selectedTickers.has(item.ticker);
    const analystRecColor = ANALYST_REC_COLOR[ctx?.recommendation ?? ""] ?? "text-muted-foreground";

    return (
      <>
        <tr
          key={`${item.ticker}-${isHistoryRow}`}
          className={cn(
            "border-b border-border hover:bg-muted/30 transition-colors",
            selected && "bg-primary/5",
            isHistoryRow && "opacity-55"
          )}
        >
          <td className="px-3 py-2.5 w-8">
            <Checkbox
              checked={selected}
              onCheckedChange={() => setSelectedTickers((prev) => {
                const next = new Set(prev);
                next.has(item.ticker) ? next.delete(item.ticker) : next.add(item.ticker);
                return next;
              })}
            />
          </td>
          <td className="px-3 py-2.5 text-xs text-muted-foreground tabular-nums">
            {item.passed_quality_gate ? item.rank : "—"}
          </td>
          <td className="px-3 py-2.5">
            <div>
              <span className="font-mono font-semibold text-sm">{item.ticker}</span>
              {ctx?.is_proposed && (
                <span
                  className="ml-1.5 inline-block text-[9px] font-medium rounded-full px-1.5 py-0 bg-violet-900/40 text-violet-400 border border-violet-800/40"
                  title={ctx.proposed_at ? `Submitted ${new Date(ctx.proposed_at).toLocaleDateString()}` : "Proposed"}
                >
                  PROPOSED
                </span>
              )}
            </div>
          </td>
          <td className="px-3 py-2.5 text-xs text-muted-foreground">
            {item.asset_class.replace(/_/g, " ")}
          </td>
          <td className="px-3 py-2.5">
            <ScorePill score={item.score} grade={item.grade} />
          </td>
          <td className="px-3 py-2.5 text-xs">
            {item.recommendation.replace(/_/g, " ")}
          </td>
          <td className="px-3 py-2.5 text-xs tabular-nums">
            {item.entry_exit ? <EntryExitBadge entryExit={item.entry_exit} /> : "—"}
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
          {/* Analyst column — extra vs Full Universe */}
          <td className="px-3 py-2.5">
            <div className="text-xs text-foreground/80">{ctx?.analyst_name ?? "—"}</div>
            {ctx?.recommendation && (
              <div className={cn("text-[10px] font-medium", analystRecColor)}>
                {ctx.recommendation}
              </div>
            )}
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
            <td colSpan={13} className="px-6 py-2">
              <EntryExitExpandedRow entryExit={item.entry_exit} />
            </td>
          </tr>
        )}
      </>
    );
  };

  return (
    <div className="space-y-4">
      {/* Filter panel */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-2">Analysts</label>
            <div className="flex flex-wrap gap-1.5">
              {analysts.length === 0 && <span className="text-xs text-muted-foreground">All analysts</span>}
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
            <p className="text-[10px] text-muted-foreground mt-1">0 = any, 1 = only very recent high-accuracy ideas</p>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md bg-red-950/30 border border-red-800/40 px-4 py-2 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Results table */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {/* Stats bar */}
        <div className="px-4 py-2 border-b border-border bg-muted/30 flex items-center justify-between gap-4 text-xs text-muted-foreground">
          <div className="flex gap-4">
            {loading ? (
              <span>Loading…</span>
            ) : result ? (
              <>
                <span>{allItems.length} analyst ideas</span>
                <span className="text-emerald-600 font-medium">{passed.length} passed</span>
                {vetoed.length > 0 && <span className="text-red-500">{vetoed.length} vetoed</span>}
                {sourced_at && <span>Last ingestion: {new Date(sourced_at).toLocaleDateString()}</span>}
              </>
            ) : (
              <span>—</span>
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
                <th className="px-3 py-2 text-left">Analyst</th>
                <th className="px-3 py-2 text-left" />
                <th className="px-3 py-2 w-6" />
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={13} className="px-4 py-8 text-center text-muted-foreground text-sm">
                    Loading analyst ideas…
                  </td>
                </tr>
              )}

              {!loading && !result && (
                <tr>
                  <td colSpan={13} className="px-4 py-8 text-center text-muted-foreground text-sm">
                    Run a scan to see results.
                  </td>
                </tr>
              )}

              {!loading && result && allItems.length === 0 && (
                <tr>
                  <td colSpan={13} className="px-4 py-8 text-center text-muted-foreground text-sm">
                    No active analyst ideas match your filters.{" "}
                    <button onClick={clearFilters} className="underline text-violet-400 hover:text-violet-300">
                      Clear filters
                    </button>
                  </td>
                </tr>
              )}

              {/* Passed rows */}
              {!loading && passed.map((item) => renderRow(item, false))}

              {/* Vetoed section */}
              {!loading && vetoed.length > 0 && (
                <>
                  <tr className="border-b border-border bg-muted/10">
                    <td colSpan={13} className="px-4 py-2">
                      <button
                        onClick={() => setShowVetoed(!showVetoed)}
                        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                      >
                        {showVetoed ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                        Show vetoed ({vetoed.length}) — below quality gate, selectable at your risk
                      </button>
                    </td>
                  </tr>
                  {showVetoed && vetoed.map((item) => renderRow(item, false))}
                </>
              )}

              {/* History section */}
              {!loading && showHistory && historyItems.length > 0 && (
                <>
                  <tr className="border-b border-border bg-muted/10">
                    <td colSpan={13} className="px-4 py-1.5 text-[10px] text-muted-foreground/60 italic text-center">
                      — Previous suggestions (within expiry window) —
                    </td>
                  </tr>
                  {historyItems.map((item) => renderRow(item, true))}
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Action bar */}
      {allItems.length > 0 && (
        <div className="flex items-center gap-3 px-1 py-2">
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
              ⚠ {[...selectedTickers].filter((t) => allItems.find((i) => i.ticker === t && !i.passed_quality_gate)).length} below quality gate
            </span>
          )}
        </div>
      )}

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
