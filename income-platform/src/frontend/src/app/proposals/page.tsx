"use client";

import { useState, useEffect, useCallback } from "react";
import { RefreshCw, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { usePortfolio } from "@/lib/portfolio-context";
import { ExecutionPanel } from "@/components/proposals/execution-panel";
import { OrderStatusPanel } from "@/components/proposals/order-status-panel";
import type {
  ProposalWithPortfolio,
  OrderParams,
  LiveOrder,
  PaperOrder,
  BrokerOrderStatus,
} from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Proposal {
  id: number;
  ticker: string;
  portfolio_id: string | null;
  platform_score: number | null;
  platform_alignment: string | null;
  analyst_recommendation: string | null;
  analyst_yield_estimate: number | null;
  platform_yield_estimate: number | null;
  entry_price_low: number | null;
  entry_price_high: number | null;
  position_size_pct: number | null;
  recommended_account: string | null;
  analyst_thesis_summary: string | null;
  analyst_safety_grade: string | null;
  platform_income_grade: string | null;
  sizing_rationale: string | null;
  divergence_notes: string | null;
  veto_flags: Record<string, unknown> | null;
  status: string;
  created_at: string | null;
}

type Phase = "setup" | "status";

function alignmentDot(alignment: string | null): string {
  if (!alignment) return "bg-muted-foreground";
  const a = alignment.toLowerCase();
  if (a === "aligned") return "bg-emerald-400";
  if (a === "partial" || a === "divergent") return "bg-amber-400";
  if (a === "vetoed") return "bg-red-400";
  return "bg-muted-foreground";
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

// ── Portfolio grouping helper ─────────────────────────────────────────────────

function groupByPortfolio(proposals: Proposal[]) {
  const map = new Map<string, Proposal[]>();
  for (const p of proposals) {
    const key = p.portfolio_id ?? "unassigned";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(p);
  }
  return Array.from(map.entries()).map(([portfolioId, items]) => ({
    portfolioId,
    proposals: items,
  }));
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ProposalsPage() {
  const { portfolios } = usePortfolio();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [focusedPortfolioId, setFocusedPortfolioId] = useState<string | null>(null);

  // Phase
  const [phase, setPhase] = useState<Phase>("setup");
  const [submitting, setSubmitting] = useState(false);

  // Order tracking (Phase 2)
  const [liveOrders, setLiveOrders] = useState<LiveOrder[]>([]);
  const [paperOrders, setPaperOrders] = useState<PaperOrder[]>([]);
  const [submittedAt, setSubmittedAt] = useState<Date | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);

  // Load proposals
  const fetchProposals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/proposals?limit=200&status=pending");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setProposals(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProposals();
  }, [fetchProposals]);

  // Group pending proposals by portfolio
  const pendingProposals = proposals.filter((p) => p.status === "pending");
  const portfolioGroups = groupByPortfolio(pendingProposals);

  // Auto-focus first portfolio with proposals
  useEffect(() => {
    if (!focusedPortfolioId && portfolioGroups.length > 0) {
      setFocusedPortfolioId(portfolioGroups[0].portfolioId);
    }
  }, [portfolioGroups.length, focusedPortfolioId]);

  const focusedPortfolio = portfolios.find((p) => p.id === focusedPortfolioId) ?? null;
  const focusedGroup = portfolioGroups.find((g) => g.portfolioId === focusedPortfolioId);

  // Auto-select all proposals in focused portfolio on focus change
  useEffect(() => {
    if (focusedGroup) {
      setSelectedIds(new Set(focusedGroup.proposals.map((p) => p.id)));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusedPortfolioId]);

  const focusedProposals = (focusedGroup?.proposals ?? []).filter((p) =>
    selectedIds.has(p.id)
  );

  // ── Submit handler ──

  const handleSubmit = async (params: Record<number, OrderParams>) => {
    if (!focusedPortfolio || focusedProposals.length === 0) return;
    setSubmitting(true);

    const isBrokerConnected = !!focusedPortfolio.broker;
    const newLiveOrders: LiveOrder[] = [];
    const newPaperOrders: PaperOrder[] = [];

    for (const proposal of focusedProposals) {
      const p = params[proposal.id];
      if (!p?.shares || p.shares <= 0) continue;

      if (!isBrokerConnected) {
        newPaperOrders.push({
          proposal_id: proposal.id,
          ticker: proposal.ticker,
          portfolio_id: focusedPortfolio.id,
          qty: p.shares,
          order_type: p.order_type,
          limit_price: p.limit_price,
          time_in_force: p.time_in_force,
          portfolio_name: focusedPortfolio.name,
          executed: false,
        });
        await fetch(`/api/proposals/${proposal.id}/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_acknowledged_veto: false }),
        }).catch(() => null);
        continue;
      }

      try {
        const resp = await fetch("/broker/orders", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            broker: focusedPortfolio.broker,
            portfolio_id: focusedPortfolio.id,
            symbol: proposal.ticker,
            side: "buy",
            qty: p.shares,
            order_type: p.order_type,
            limit_price: p.order_type !== "market" ? p.limit_price : undefined,
            time_in_force: p.time_in_force,
            proposal_id: String(proposal.id),
          }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          console.error(`Order failed for ${proposal.ticker}:`, data.detail);
          continue;
        }

        await fetch(`/api/proposals/${proposal.id}/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_acknowledged_veto: false }),
        }).catch(() => null);

        newLiveOrders.push({
          proposal_id: proposal.id,
          ticker: proposal.ticker,
          portfolio_id: focusedPortfolio.id,
          order_id: data.order_id,
          broker: (data.broker ?? focusedPortfolio.broker) as string,
          status: (data.status ?? "pending") as BrokerOrderStatus,
          qty: p.shares,
          filled_qty: data.filled_qty ?? 0,
          avg_fill_price: data.filled_avg_price ?? null,
          limit_price: p.limit_price,
          filled_at: null,
          submitted_at: new Date().toISOString(),
        });
      } catch (err) {
        console.error(`Order error for ${proposal.ticker}:`, err);
      }
    }

    setLiveOrders(newLiveOrders);
    setPaperOrders(newPaperOrders);
    setSubmittedAt(new Date());
    setSubmitting(false);
    setPhase("status");
  };

  // ── Sync-fill helper ──

  const syncFill = useCallback(async (order: LiveOrder) => {
    if (!order.avg_fill_price || !order.filled_at) return;
    await fetch("/broker/positions/sync-fill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        portfolio_id: order.portfolio_id,
        ticker: order.ticker,
        filled_qty: order.filled_qty,
        avg_fill_price: order.avg_fill_price,
        filled_at: order.filled_at,
        proposal_id: String(order.proposal_id),
        order_id: order.order_id,
      }),
    });
    await fetch(`/api/proposals/${order.proposal_id}/fill-confirmed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filled_qty: order.filled_qty,
        avg_fill_price: order.avg_fill_price,
        filled_at: order.filled_at,
        status: order.status === "filled" ? "filled" : "partially_filled",
      }),
    });
  }, []);

  // ── Polling / refresh ──

  const refreshOrders = useCallback(async () => {
    const updated = await Promise.all(
      liveOrders.map(async (o) => {
        if (o.status === "filled" || o.status === "cancelled") return o;
        try {
          const resp = await fetch(`/broker/orders/${o.order_id}?broker=${o.broker}`);
          if (!resp.ok) return o;
          const data = await resp.json();
          const newStatus: BrokerOrderStatus = data.status ?? o.status;
          const updatedOrder: LiveOrder = {
            ...o,
            status: newStatus,
            filled_qty: data.filled_qty ?? o.filled_qty,
            avg_fill_price: data.filled_avg_price ?? o.avg_fill_price,
            filled_at: data.filled_at ?? o.filled_at,
          };

          // Trigger sync-fill only for newly-filled shares
          const prevFilledQty = o.filled_qty ?? 0;
          const newFilledQty = data.filled_qty ?? 0;
          if (
            (newStatus === "filled" || newStatus === "partially_filled") &&
            newFilledQty > prevFilledQty
          ) {
            await syncFill({
              ...updatedOrder,
              filled_qty: newFilledQty - prevFilledQty,
              avg_fill_price: data.filled_avg_price,
            }).catch(() => null);
          }

          return updatedOrder;
        } catch {
          return o;
        }
      })
    );
    setLiveOrders(updated);
    setLastRefreshedAt(new Date());
  }, [liveOrders, syncFill]);

  // ── Cancel handlers ──

  const handleCancelOrder = async (orderId: string, broker: string) => {
    const resp = await fetch(`/broker/orders/${orderId}?broker=${broker}`, {
      method: "DELETE",
    }).catch(() => null);
    if (resp?.ok) {
      const order = liveOrders.find((o) => o.order_id === orderId);
      if (order && order.filled_qty > 0) {
        await syncFill({ ...order, status: "partially_filled" }).catch(() => null);
      }
      setLiveOrders((prev) =>
        prev.map((o) => (o.order_id === orderId ? { ...o, status: "cancelled" } : o))
      );
      const proposal = liveOrders.find((o) => o.order_id === orderId);
      if (proposal) {
        await fetch(`/api/proposals/${proposal.proposal_id}/fill-confirmed`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filled_qty: 0,
            avg_fill_price: 0,
            filled_at: new Date().toISOString(),
            status: "cancelled",
          }),
        }).catch(() => null);
      }
    }
  };

  // ── Paper order mark-executed ──

  const handleMarkPaperExecuted = async (
    proposalId: number,
    fillPrice: number,
    fillDate: string
  ) => {
    const order = paperOrders.find((o) => o.proposal_id === proposalId);
    if (!order) return;
    await fetch("/broker/positions/sync-fill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        portfolio_id: order.portfolio_id,
        ticker: order.ticker,
        filled_qty: order.qty,
        avg_fill_price: fillPrice,
        filled_at: `${fillDate}T00:00:00Z`,
        proposal_id: String(proposalId),
      }),
    }).catch(() => null);
    await fetch(`/api/proposals/${proposalId}/fill-confirmed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filled_qty: order.qty,
        avg_fill_price: fillPrice,
        filled_at: `${fillDate}T00:00:00Z`,
        status: "filled",
      }),
    }).catch(() => null);
    setPaperOrders((prev) =>
      prev.map((o) => (o.proposal_id === proposalId ? { ...o, executed: true } : o))
    );
  };

  // ── Render ──

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Left: proposal list grouped by portfolio */}
      <div className="w-72 shrink-0 border-r border-border flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h1 className="text-sm font-semibold">Proposals</h1>
          <button
            onClick={fetchProposals}
            className="p-1 rounded text-muted-foreground hover:text-foreground"
            title="Refresh"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {loading && (
            <div className="flex items-center justify-center py-8 text-muted-foreground text-xs">
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" /> Loading…
            </div>
          )}
          {!loading && error && (
            <div className="mx-3 rounded border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
              {error}
            </div>
          )}
          {!loading && !error && portfolioGroups.length === 0 && (
            <div className="px-4 py-8 text-center text-xs text-muted-foreground">
              No pending proposals.
              <br />
              Run a scan and generate proposals to see them here.
            </div>
          )}

          {portfolioGroups.map((group) => {
            const port = portfolios.find((p) => p.id === group.portfolioId);
            const isFocused = group.portfolioId === focusedPortfolioId;
            return (
              <div key={group.portfolioId} className="mb-2">
                <div
                  className="flex items-center justify-between px-4 py-1.5 cursor-pointer"
                  onClick={() => setFocusedPortfolioId(group.portfolioId)}
                >
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {port?.name ?? "Unassigned"}
                  </span>
                  {port?.cash_balance != null && (
                    <span className="text-[10px] text-emerald-400">
                      $
                      {port.cash_balance.toLocaleString("en-US", {
                        maximumFractionDigits: 0,
                      })}
                    </span>
                  )}
                </div>
                {group.proposals.map((p) => {
                  const checked = selectedIds.has(p.id);
                  return (
                    <div
                      key={p.id}
                      onClick={() => {
                        setFocusedPortfolioId(group.portfolioId);
                        setSelectedIds((prev) => {
                          const next = new Set(prev);
                          if (next.has(p.id)) next.delete(p.id);
                          else next.add(p.id);
                          return next;
                        });
                      }}
                      className={cn(
                        "flex items-start gap-2.5 px-4 py-2.5 cursor-pointer border-l-2 transition-colors",
                        isFocused && checked
                          ? "bg-violet-950/20 border-l-violet-500"
                          : "border-l-transparent hover:bg-muted/20"
                      )}
                    >
                      <div
                        className={cn(
                          "mt-1 h-3.5 w-3.5 shrink-0 rounded border flex items-center justify-center",
                          checked ? "bg-violet-600 border-violet-600" : "border-border"
                        )}
                      >
                        {checked && (
                          <span className="text-[8px] text-white font-bold">✓</span>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-semibold text-sm">{p.ticker}</span>
                          {p.platform_score != null && (
                            <span className="text-[10px] font-medium text-violet-400">
                              {p.platform_score.toFixed(0)}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <div
                            className={cn(
                              "h-1.5 w-1.5 rounded-full",
                              alignmentDot(p.platform_alignment)
                            )}
                          />
                          <span className="text-[10px] text-muted-foreground">
                            {p.platform_alignment ?? "—"} · {fmtDate(p.created_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right: execution panel or order status */}
      <div className="flex-1 overflow-hidden">
        {phase === "setup" ? (
          focusedPortfolio && focusedProposals.length > 0 ? (
            <ExecutionPanel
              proposals={focusedProposals as ProposalWithPortfolio[]}
              portfolio={focusedPortfolio}
              onSubmit={handleSubmit}
              onRejectAll={async () => {
                await Promise.all(
                  focusedProposals.map((p) =>
                    fetch(`/api/proposals/${p.id}/reject`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({}),
                    }).catch(() => null)
                  )
                );
                fetchProposals();
              }}
              isBrokerConnected={!!focusedPortfolio.broker}
              loading={submitting}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
              Select proposals from the left to begin
            </div>
          )
        ) : submittedAt ? (
          <OrderStatusPanel
            liveOrders={liveOrders}
            paperOrders={paperOrders}
            submittedAt={submittedAt}
            onRefresh={refreshOrders}
            onCancelOrder={handleCancelOrder}
            onCancelRest={handleCancelOrder}
            onMarkPaperExecuted={handleMarkPaperExecuted}
            lastRefreshedAt={lastRefreshedAt}
          />
        ) : null}
      </div>
    </div>
  );
}
