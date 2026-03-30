// src/frontend/src/components/analyst-ideas-drawer.tsx
"use client";

import { useState, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { ScanItem, ScanResult, PortfolioListItem, PositionOverrides } from "@/lib/types";

interface AnalystIdeasDrawerProps {
  open: boolean;
  onClose: () => void;
  selectedTickers: Set<string>;
  scanResult: ScanResult | null;
  portfolios: PortfolioListItem[];
  onSuccess: (proposalId: string) => void;
}

export function AnalystIdeasDrawer({
  open,
  onClose,
  selectedTickers,
  scanResult,
  portfolios,
  onSuccess,
}: AnalystIdeasDrawerProps) {
  const [targetPortfolioId, setTargetPortfolioId] = useState<string>("");
  const [allocationMode, setAllocationMode] = useState<"auto" | "manual">("auto");
  const [overrides, setOverrides] = useState<Record<string, { amount_usd: string; target_price: string }>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedItems: ScanItem[] = useMemo(
    () => (scanResult?.items ?? []).filter((i) => selectedTickers.has(i.ticker)),
    [scanResult, selectedTickers]
  );

  const activePortfolios = portfolios;
  const selectedPortfolio = portfolios.find((p) => p.id === targetPortfolioId);
  const cashBalance: number | null = (selectedPortfolio as any)?.cash_balance ?? null;

  const totalCommitted = useMemo(() => {
    if (allocationMode !== "manual") return 0;
    return Object.values(overrides).reduce((sum, o) => sum + (parseFloat(o.amount_usd) || 0), 0);
  }, [overrides, allocationMode]);

  const belowGateItems = selectedItems.filter((i) => !i.passed_quality_gate);

  const handleSubmit = async () => {
    if (!targetPortfolioId || !scanResult) return;
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        scan_id: scanResult.scan_id,
        selected_tickers: [...selectedTickers],
        target_portfolio_id: targetPortfolioId,
      };
      if (allocationMode === "manual") {
        const position_overrides: PositionOverrides = {};
        for (const [ticker, vals] of Object.entries(overrides)) {
          if (vals.amount_usd || vals.target_price) {
            position_overrides[ticker] = {
              amount_usd: parseFloat(vals.amount_usd) || 0,
              target_price: parseFloat(vals.target_price) || 0,
            };
          }
        }
        body.position_overrides = position_overrides;
      }
      const resp = await fetch("/api/scanner/propose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Failed to create proposal");
      onSuccess(data.proposal_id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create Proposal</DialogTitle>
          <p className="text-sm text-muted-foreground">{selectedItems.length} idea{selectedItems.length !== 1 ? "s" : ""} selected</p>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Target portfolio */}
          <div className="space-y-2">
            <Label className="text-sm">Target Portfolio <span className="text-red-500">*</span></Label>
            <Select value={targetPortfolioId} onValueChange={(v) => setTargetPortfolioId(v ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="Select target portfolio..." />
              </SelectTrigger>
              <SelectContent>
                {activePortfolios.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}{p.broker ? ` · ${p.broker}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Cash balance */}
          {cashBalance != null && (
            <div className="flex items-center justify-between rounded-md bg-emerald-950/40 border border-emerald-900/50 px-3 py-2 text-sm">
              <span className="text-muted-foreground">Available cash</span>
              <span className="font-semibold text-emerald-400">
                ${cashBalance.toLocaleString("en-US", { minimumFractionDigits: 0 })}
              </span>
            </div>
          )}

          {/* Allocation mode toggle */}
          <div className="flex rounded-md border border-border overflow-hidden text-sm">
            <button
              onClick={() => setAllocationMode("auto")}
              className={cn(
                "flex-1 px-3 py-1.5 text-xs font-medium transition-colors",
                allocationMode === "auto"
                  ? "bg-violet-600/20 text-violet-300 border-r border-border"
                  : "bg-muted/20 text-muted-foreground hover:text-foreground border-r border-border"
              )}
            >
              Agent 12 auto-allocates
            </button>
            <button
              onClick={() => setAllocationMode("manual")}
              className={cn(
                "flex-1 px-3 py-1.5 text-xs font-medium transition-colors",
                allocationMode === "manual"
                  ? "bg-muted text-foreground"
                  : "bg-muted/20 text-muted-foreground hover:text-foreground"
              )}
            >
              Specify amounts
            </button>
          </div>

          {/* Selected ideas */}
          <div className="space-y-1">
            <p className="text-sm font-medium">
              {allocationMode === "manual" ? "Selected Ideas — specify amounts" : "Selected Ideas"}
            </p>
            <div className="rounded-md border border-border bg-muted/30 divide-y divide-border max-h-52 overflow-y-auto">
              {selectedItems.map((item) => {
                const isBelow = !item.passed_quality_gate;
                const ctx = item.analyst_context;
                return (
                  <div
                    key={item.ticker}
                    className={cn(
                      "px-3 py-2.5",
                      isBelow && "bg-amber-950/20 border-l-2 border-amber-600/50"
                    )}
                  >
                    <div className="flex justify-between items-center mb-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-medium text-sm">{item.ticker}</span>
                        {ctx?.is_proposed && (
                          <span
                            className="text-[9px] font-medium rounded-full px-1.5 py-0 bg-violet-900/40 text-violet-400 border border-violet-800/40"
                            title={ctx.proposed_at ? `Submitted ${new Date(ctx.proposed_at).toLocaleDateString()}` : "Proposed"}
                          >
                            PROPOSED
                          </span>
                        )}
                      </div>
                      <span className={cn("text-xs font-medium", item.recommendation === "BUY" ? "text-emerald-400" : "text-red-400")}>
                        {item.recommendation}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mb-1">
                      {ctx?.analyst_name ?? "—"} · {item.grade} · {Math.round(item.score)}
                      {item.entry_exit?.entry_limit != null && ` · entry $${item.entry_exit.entry_limit.toFixed(2)}`}
                    </div>
                    {isBelow && (
                      <Badge variant="outline" className="text-amber-400 border-amber-600/40 text-[10px] px-1.5 py-0">
                        ⚠ AT RISK — below quality gate
                      </Badge>
                    )}
                    {allocationMode === "manual" && (
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        <div>
                          <label className="text-[10px] text-muted-foreground block mb-1">$ Amount</label>
                          <input
                            type="number"
                            placeholder="0"
                            value={overrides[item.ticker]?.amount_usd ?? ""}
                            onChange={(e) =>
                              setOverrides((prev) => ({
                                ...prev,
                                [item.ticker]: { ...prev[item.ticker], amount_usd: e.target.value },
                              }))
                            }
                            className={cn(
                              "w-full rounded border px-2 py-1 text-xs bg-background",
                              isBelow ? "border-amber-800/50" : "border-border"
                            )}
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-muted-foreground block mb-1">Target Price</label>
                          <input
                            type="number"
                            placeholder={item.entry_exit?.entry_limit?.toFixed(2) ?? "0"}
                            value={overrides[item.ticker]?.target_price ?? ""}
                            onChange={(e) =>
                              setOverrides((prev) => ({
                                ...prev,
                                [item.ticker]: { ...prev[item.ticker], target_price: e.target.value },
                              }))
                            }
                            className={cn(
                              "w-full rounded border px-2 py-1 text-xs bg-background",
                              isBelow ? "border-amber-800/50" : "border-border"
                            )}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Running total (manual mode only) */}
          {allocationMode === "manual" && (
            <div className={cn(
              "flex justify-between items-center rounded-md border px-3 py-2 text-xs",
              cashBalance != null && totalCommitted > cashBalance
                ? "border-amber-600/40 bg-amber-950/20"
                : "border-border bg-muted/20"
            )}>
              <span className="text-muted-foreground">Total committed</span>
              <div className="text-right">
                <span className="font-semibold">${totalCommitted.toLocaleString("en-US", { minimumFractionDigits: 0 })}</span>
                {cashBalance != null && (
                  <span className={cn("ml-2 text-[10px]", totalCommitted > cashBalance ? "text-amber-400" : "text-emerald-400")}>
                    ${(cashBalance - totalCommitted).toLocaleString("en-US", { minimumFractionDigits: 0 })} remaining
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Agent 12 info (auto mode) */}
          {allocationMode === "auto" && (
            <div className="rounded-md bg-violet-950/30 border border-violet-900/40 px-3 py-2 text-xs text-violet-300">
              ✦ Agent 12 will determine position sizes based on portfolio balance and risk rules.
            </div>
          )}

          {/* Risk warning */}
          {belowGateItems.length > 0 && (
            <div className="rounded-md bg-amber-950/30 border border-amber-800/40 px-3 py-2 text-xs text-amber-300">
              ⚠ {belowGateItems.map((i) => i.ticker).join(", ")} {belowGateItems.length === 1 ? "is" : "are"} below quality gate. Submitted at your risk.
            </div>
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={loading || !targetPortfolioId || selectedItems.length === 0}
          >
            {loading ? "Submitting…" : "Submit Proposal"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
