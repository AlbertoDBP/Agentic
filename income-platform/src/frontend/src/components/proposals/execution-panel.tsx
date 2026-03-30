// src/frontend/src/components/proposals/execution-panel.tsx
"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { PortfolioImpactBar, computeImpact } from "./portfolio-impact-bar";
import type { ProposalWithPortfolio, OrderParams, OrderType, TimeInForce } from "@/lib/types";
import type { Portfolio } from "@/lib/types";

interface ExecutionPanelProps {
  proposals: ProposalWithPortfolio[];
  portfolio: Portfolio;
  onSubmit: (params: Record<number, OrderParams>) => void;
  onRejectAll: () => void;
  isBrokerConnected: boolean;
  loading?: boolean;
}

const DRAFT_KEY = (ids: number[]) => `proposal-draft-${ids.sort().join(",")}`;

export function ExecutionPanel({
  proposals,
  portfolio,
  onSubmit,
  onRejectAll,
  isBrokerConnected,
  loading,
}: ExecutionPanelProps) {
  const [activeTab, setActiveTab] = useState<number>(proposals[0]?.id ?? 0);
  const [params, setParams] = useState<Record<number, OrderParams>>(() => {
    // Restore draft from localStorage
    const key = DRAFT_KEY(proposals.map((p) => p.id));
    try {
      const saved = localStorage.getItem(key);
      if (saved) return JSON.parse(saved);
    } catch { /* ignore */ }
    // Default params from proposal data
    return Object.fromEntries(
      proposals.map((p) => [
        p.id,
        {
          order_type: "limit" as OrderType,
          limit_price: p.entry_price_low ?? null,
          shares: p.position_size_pct != null && portfolio.cash_balance != null
            ? Math.floor((portfolio.cash_balance * (p.position_size_pct / 100)) / (p.entry_price_low ?? 1))
            : null,
          dollar_amount: null,
          time_in_force: "gtc" as TimeInForce,
        } satisfies OrderParams,
      ])
    );
  });

  // Save draft on every change
  useEffect(() => {
    const key = DRAFT_KEY(proposals.map((p) => p.id));
    try { localStorage.setItem(key, JSON.stringify(params)); } catch { /* ignore */ }
  }, [params, proposals]);

  const updateParam = <K extends keyof OrderParams>(id: number, key: K, value: OrderParams[K]) => {
    setParams((prev) => {
      const updated = { ...prev, [id]: { ...prev[id], [key]: value } };
      // Link shares <=> dollar_amount
      if (key === "shares" && updated[id].limit_price) {
        updated[id].dollar_amount = (value as number) * updated[id].limit_price!;
      }
      if (key === "dollar_amount" && updated[id].limit_price) {
        updated[id].shares = Math.floor((value as number) / updated[id].limit_price!);
      }
      if (key === "limit_price") {
        if (updated[id].shares) {
          updated[id].dollar_amount = updated[id].shares! * (value as number);
        }
      }
      return updated;
    });
  };

  const impact = computeImpact({
    proposals,
    orderParams: proposals.map((p) => ({
      shares: params[p.id]?.shares ?? null,
      limit_price: params[p.id]?.limit_price ?? null,
    })),
    currentAnnualIncome: 0,
    currentPortfolioValue: null,
    cashBalance: portfolio.cash_balance ?? null,
  });

  const totalCommitted = proposals.reduce((sum, p) => {
    const o = params[p.id];
    return sum + (o?.shares ?? 0) * (o?.limit_price ?? 0);
  }, 0);

  const activeProposal = proposals.find((p) => p.id === activeTab);
  const activeParams = activeProposal ? params[activeProposal.id] : null;

  return (
    <div className="flex flex-col h-full">
      {/* Portfolio Impact Bar */}
      <div className="p-4 pb-0">
        <PortfolioImpactBar
          impact={impact}
          cashBalance={portfolio.cash_balance ?? null}
          className="mb-4"
        />
      </div>

      {/* Ticker tabs */}
      <div className="flex gap-1 px-4 border-b border-border pb-0">
        {proposals.map((p) => (
          <button
            key={p.id}
            onClick={() => setActiveTab(p.id)}
            className={cn(
              "px-3 py-2 text-xs font-medium rounded-t border border-b-0 transition-colors",
              activeTab === p.id
                ? "bg-card border-border text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {p.ticker}
          </button>
        ))}
      </div>

      {/* Active ticker form */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeProposal && activeParams && (
          <>
            {/* Analysis block */}
            <div className="grid grid-cols-3 gap-3">
              <AnalysisCell label="Score" value={activeProposal.platform_score?.toFixed(0) ?? "—"} />
              <AnalysisCell
                label="Rec"
                value={activeProposal.analyst_recommendation ?? "—"}
                valueClass={activeProposal.analyst_recommendation?.includes("BUY") ? "text-emerald-400" : undefined}
              />
              <AnalysisCell
                label="Entry Range"
                value={activeProposal.entry_price_low != null
                  ? `$${activeProposal.entry_price_low.toFixed(2)}–$${(activeProposal.entry_price_high ?? activeProposal.entry_price_low).toFixed(2)}`
                  : "—"}
              />
            </div>
            {activeProposal.analyst_thesis_summary && (
              <p className="text-xs text-muted-foreground leading-relaxed">{activeProposal.analyst_thesis_summary}</p>
            )}
            {activeProposal.recommended_account && (
              <p className="text-xs text-muted-foreground">
                Suggested account: <span className="text-foreground font-medium">{activeProposal.recommended_account}</span>
              </p>
            )}

            {/* Alignment warning */}
            {activeProposal.platform_alignment && !["Aligned"].includes(activeProposal.platform_alignment) && (
              <div className={cn(
                "text-xs rounded-lg border px-3 py-2",
                activeProposal.platform_alignment === "Vetoed"
                  ? "bg-red-950/20 border-red-800/40 text-red-300"
                  : "bg-amber-950/20 border-amber-800/40 text-amber-300"
              )}>
                ⚠ {activeProposal.platform_alignment} — {activeProposal.divergence_notes ?? "Review before executing."}
              </div>
            )}

            {/* Execution form */}
            <div className="space-y-3 rounded-xl border border-border bg-card/30 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Order Parameters</p>

              {/* Order type pills */}
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1.5">Order Type</label>
                <div className="flex gap-2">
                  {(["market", "limit", "stop_limit"] as OrderType[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => updateParam(activeProposal.id, "order_type", t)}
                      className={cn(
                        "px-3 py-1 text-xs rounded-full border transition-colors",
                        activeParams.order_type === t
                          ? "bg-violet-600/20 text-violet-300 border-violet-700/40"
                          : "border-border text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {t === "stop_limit" ? "Stop-Limit" : t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                {/* Limit price */}
                {activeParams.order_type !== "market" && (
                  <div>
                    <label className="text-[10px] text-muted-foreground block mb-1">Limit Price</label>
                    <input
                      type="number"
                      step="0.01"
                      value={activeParams.limit_price ?? ""}
                      onChange={(e) => updateParam(activeProposal.id, "limit_price", parseFloat(e.target.value) || null)}
                      className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs"
                    />
                  </div>
                )}

                {/* Shares */}
                <div>
                  <label className="text-[10px] text-muted-foreground block mb-1">Shares</label>
                  <input
                    type="number"
                    value={activeParams.shares ?? ""}
                    onChange={(e) => updateParam(activeProposal.id, "shares", parseInt(e.target.value) || null)}
                    className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs"
                  />
                </div>

                {/* Dollar amount */}
                <div>
                  <label className="text-[10px] text-muted-foreground block mb-1">$ Amount</label>
                  <input
                    type="number"
                    step="1"
                    value={activeParams.dollar_amount != null ? Math.round(activeParams.dollar_amount) : ""}
                    onChange={(e) => updateParam(activeProposal.id, "dollar_amount", parseFloat(e.target.value) || null)}
                    className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs"
                  />
                </div>
              </div>

              {/* Time in force */}
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1.5">Time in Force</label>
                <div className="flex gap-2">
                  {(["day", "gtc", "ioc"] as TimeInForce[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => updateParam(activeProposal.id, "time_in_force", t)}
                      className={cn(
                        "px-3 py-1 text-xs rounded-full border transition-colors",
                        activeParams.time_in_force === t
                          ? "bg-muted text-foreground border-border"
                          : "border-border text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {t.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-border px-4 py-3 flex items-center justify-between gap-3">
        <div className="text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">
            ${totalCommitted.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </span>
          {" "}committed
          {portfolio.cash_balance != null && (
            <span className={cn("ml-2", totalCommitted > portfolio.cash_balance ? "text-amber-400" : "text-emerald-400")}>
              ${(portfolio.cash_balance - totalCommitted).toLocaleString("en-US", { maximumFractionDigits: 0 })} remaining
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={onRejectAll}
            className="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground"
          >
            Reject All
          </button>
          <button
            onClick={() => {
              const key = DRAFT_KEY(proposals.map((p) => p.id));
              try { localStorage.setItem(key, JSON.stringify(params)); } catch { /* ignore */ }
            }}
            className="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground"
          >
            Save Draft
          </button>
          <button
            onClick={() => onSubmit(params)}
            disabled={loading || totalCommitted === 0}
            className="text-xs px-4 py-1.5 rounded bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-40 font-medium"
          >
            {loading
              ? "Submitting…"
              : isBrokerConnected
                ? `Submit ${proposals.length} Order${proposals.length !== 1 ? "s" : ""} to ${portfolio.broker ?? "Broker"}`
                : "Generate Paper Orders"}
          </button>
        </div>
      </div>
    </div>
  );
}

function AnalysisCell({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={cn("text-sm font-semibold mt-0.5", valueClass)}>{value}</p>
    </div>
  );
}
