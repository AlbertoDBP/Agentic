"use client";

import { useState, useEffect } from "react";
import { usePortfolio } from "@/lib/portfolio-context";
import { TickerBadge } from "@/components/ticker-badge";
import { ScorePill } from "@/components/score-pill";
import { formatCurrency, formatPercent, formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { Check, X, Clock, Pencil, Minus, FileText, Zap, AlertTriangle, Loader2 } from "lucide-react";
import { apiPost } from "@/lib/api";

interface ProposalPosition {
  symbol: string;
  name: string;
  asset_type: string;
  shares: number;
  entry_price: number;
  current_price: number;
  yield_estimate: number;
  score: number;
}

interface Proposal {
  id: string;
  portfolio_id: string;
  proposal_type: "BUY" | "REBALANCE" | "TRIM" | "TRANSFER";
  to_portfolio_id?: string;
  summary: string;
  status: "PENDING" | "ACCEPTED" | "REJECTED";
  created_at: string;
  analyst_source?: string;
  analyst_sentiment?: string;
  risk_flags: string[];
  positions: ProposalPosition[];
}

const INITIAL_PROPOSALS: Proposal[] = [];

type Tab = "PENDING" | "ACCEPTED" | "REJECTED";

// Order generated after acceptance
interface Order {
  proposalId: string;
  portfolio: string;
  type: "BUY" | "SELL";
  positions: { symbol: string; shares: number; limit_price: number }[];
  auto_execute: boolean;
  created_at: string;
  // Populated when broker execution succeeds
  broker_orders?: { symbol: string; order_id: string; status: string; qty: number; error?: string }[];
  broker_error?: string;
}

export default function ProposalsPage() {
  const { portfolios } = usePortfolio();
  const [tab, setTab] = useState<Tab>("PENDING");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filterPortfolioId, setFilterPortfolioId] = useState<string>("all");

  // Cash available for the proposal's portfolio
  const getCashBalance = (portfolioId: string): number | undefined =>
    portfolios.find((p) => p.id === portfolioId)?.cash_balance;
  const [proposals, setProposals] = useState<Proposal[]>([]);

  // Persist status changes to localStorage whenever proposals change
  useEffect(() => {
    try {
      const statuses: Record<string, Proposal["status"]> = {};
      proposals.forEach((p) => { statuses[p.id] = p.status; });
      localStorage.setItem("proposalStatuses", JSON.stringify(statuses));
    } catch { /* ignore */ }
  }, [proposals]);

  // Load proposals created from scanner/tax pages
  useEffect(() => {
    try {
      const pending = JSON.parse(localStorage.getItem("pendingProposals") ?? "[]") as Proposal[];
      if (pending.length > 0) {
        setProposals((prev) => {
          // Avoid duplicates by id
          const existingIds = new Set(prev.map((p) => p.id));
          const newOnes = pending.filter((p) => !existingIds.has(p.id));
          return newOnes.length > 0 ? [...prev, ...newOnes] : prev;
        });
        localStorage.removeItem("pendingProposals");
      }
    } catch { /* ignore */ }
  }, []);

  // Editable positions state
  const [editedPositions, setEditedPositions] = useState<Record<string, ProposalPosition[]>>({});
  const [editingId, setEditingId] = useState<string | null>(null);

  // Order overlay
  const [generatedOrder, setGeneratedOrder] = useState<Order | null>(null);
  const [executing, setExecuting] = useState(false);

  // Load portfolio auto-execute setting
  const getAutoExecute = (portfolioId: string): boolean => {
    try {
      const s = localStorage.getItem(`portfolioConfig-${portfolioId}`);
      if (s) return JSON.parse(s).auto_execute_proposals === true;
    } catch { /* ignore */ }
    return false;
  };

  const portfolioFiltered = filterPortfolioId === "all"
    ? proposals
    : proposals.filter((p) => p.portfolio_id === filterPortfolioId);

  const filtered = portfolioFiltered.filter((p) => p.status === tab);
  const selected = proposals.find((p) => p.id === selectedId);

  const getPositions = (proposalId: string): ProposalPosition[] => {
    return editedPositions[proposalId] || proposals.find((p) => p.id === proposalId)?.positions || [];
  };

  const getOriginalPositions = (proposalId: string): ProposalPosition[] => {
    return proposals.find((p) => p.id === proposalId)?.positions || [];
  };

  const startEditing = (proposalId: string) => {
    const orig = proposals.find((p) => p.id === proposalId);
    if (!orig) return;
    setEditedPositions({ ...editedPositions, [proposalId]: orig.positions.map((p) => ({ ...p })) });
    setEditingId(proposalId);
  };

  const updatePosition = (proposalId: string, idx: number, field: keyof ProposalPosition, value: number | string) => {
    const positions = [...getPositions(proposalId)];
    positions[idx] = { ...positions[idx], [field]: value };
    setEditedPositions({ ...editedPositions, [proposalId]: positions });
  };

  const removePosition = (proposalId: string, idx: number) => {
    const positions = getPositions(proposalId).filter((_, i) => i !== idx);
    setEditedPositions({ ...editedPositions, [proposalId]: positions });
  };

  const cancelEditing = () => {
    if (editingId) {
      const next = { ...editedPositions };
      delete next[editingId];
      setEditedPositions(next);
    }
    setEditingId(null);
  };

  const portfolioName = (id: string) => portfolios.find((p) => p.id === id)?.name || (id.startsWith("p") && id.length <= 3 ? `Portfolio ${id.slice(1)}` : id);

  const totalCost = (positions: ProposalPosition[]) =>
    positions.reduce((s, p) => s + Math.abs(p.shares) * p.entry_price, 0);

  const totalIncome = (positions: ProposalPosition[]) =>
    positions.reduce((s, p) => s + Math.abs(p.shares) * p.entry_price * (p.yield_estimate / 100), 0);

  // Impact calculation: compare edited vs original
  const costDelta = (proposalId: string) => {
    if (!editedPositions[proposalId]) return null;
    const origCost = totalCost(getOriginalPositions(proposalId));
    const editCost = totalCost(editedPositions[proposalId]);
    return editCost - origCost;
  };

  const incomeDelta = (proposalId: string) => {
    if (!editedPositions[proposalId]) return null;
    const origInc = totalIncome(getOriginalPositions(proposalId));
    const editInc = totalIncome(editedPositions[proposalId]);
    return editInc - origInc;
  };

  // Accept proposal
  const acceptProposal = async (proposal: Proposal) => {
    const positions = getPositions(proposal.id);
    const autoExec = getAutoExecute(proposal.portfolio_id);

    // Update proposal status
    setProposals((prev) => prev.map((p) => p.id === proposal.id ? { ...p, status: "ACCEPTED" as const } : p));

    // TRANSFER proposals don't generate a market order
    if (proposal.proposal_type === "TRANSFER") {
      const next = { ...editedPositions };
      delete next[proposal.id];
      setEditedPositions(next);
      setEditingId(null);
      return;
    }

    // Generate order
    const order: Order = {
      proposalId: proposal.id,
      portfolio: portfolioName(proposal.portfolio_id),
      type: proposal.proposal_type === "TRIM" ? "SELL" : "BUY",
      positions: positions.map((p) => ({
        symbol: p.symbol,
        shares: Math.abs(p.shares),
        limit_price: p.entry_price,
      })),
      auto_execute: autoExec,
      created_at: new Date().toISOString(),
    };
    setGeneratedOrder(order);

    // Clean up edit state
    const next = { ...editedPositions };
    delete next[proposal.id];
    setEditedPositions(next);
    setEditingId(null);

    // Auto-execute via broker API (one call per position)
    if (autoExec) {
      setExecuting(true);
      try {
        const side = order.type === "BUY" ? "buy" : "sell";
        const results: { symbol: string; order_id: string; status: string; qty: number; error?: string }[] = [];
        for (const p of order.positions) {
          try {
            const r = await apiPost<{ order_id: string; symbol: string; status: string; qty: number }>(
              "/api/broker/orders",
              {
                broker: "alpaca",
                portfolio_id: proposal.portfolio_id,
                symbol: p.symbol,
                side,
                qty: p.shares,
                order_type: "limit",
                limit_price: p.limit_price,
                proposal_id: proposal.id,
              }
            );
            results.push({ symbol: p.symbol, order_id: r?.order_id ?? "", status: r?.status ?? "submitted", qty: p.shares });
          } catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            results.push({ symbol: p.symbol, order_id: "", status: "error", qty: p.shares, error: msg });
          }
        }
        setGeneratedOrder((prev) => prev ? { ...prev, broker_orders: results } : prev);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setGeneratedOrder((prev) => prev ? { ...prev, broker_error: msg } : prev);
      } finally {
        setExecuting(false);
      }
    }
  };

  // Reject proposal
  const rejectProposal = (proposalId: string) => {
    setProposals((prev) => prev.map((p) => p.id === proposalId ? { ...p, status: "REJECTED" as const } : p));
    const next = { ...editedPositions };
    delete next[proposalId];
    setEditedPositions(next);
    setEditingId(null);
    setSelectedId(null);
  };

  // Defer proposal (move created_at forward 7 days — simulated)
  const deferProposal = (proposalId: string) => {
    setProposals((prev) => prev.map((p) => {
      if (p.id !== proposalId) return p;
      const d = new Date(p.created_at);
      d.setDate(d.getDate() + 7);
      return { ...p, created_at: d.toISOString() };
    }));
  };

  // Auto-select first when changing tab/filter
  useEffect(() => {
    if (filtered.length > 0 && !filtered.find((p) => p.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [tab, filterPortfolioId, filtered, selectedId]);

  return (
    <div className="space-y-4">
      {/* Order confirmation overlay */}
      {generatedOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-xl">
            <div className="mb-4 flex items-center gap-2">
              {generatedOrder.auto_execute ? (
                <Zap className="h-5 w-5 text-amber-400" />
              ) : (
                <FileText className="h-5 w-5 text-primary" />
              )}
              <h2 className="text-lg font-semibold">
                {generatedOrder.auto_execute ? "Order Submitted for Execution" : "Order Generated for Manual Execution"}
              </h2>
            </div>

            <div className="mb-4 rounded-md border border-border bg-secondary p-3 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Portfolio</span>
                <span className="font-medium">{generatedOrder.portfolio}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Action</span>
                <span className={cn("font-medium", generatedOrder.type === "BUY" ? "text-income" : "text-loss")}>
                  {generatedOrder.type}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Execution</span>
                <span className={cn("font-medium", generatedOrder.auto_execute ? "text-amber-400" : "text-muted-foreground")}>
                  {generatedOrder.auto_execute ? "Automatic" : "Manual"}
                </span>
              </div>
            </div>

            <table className="w-full text-sm mb-4">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-1 text-left text-xs text-muted-foreground">Symbol</th>
                  <th className="py-1 text-right text-xs text-muted-foreground">Shares</th>
                  <th className="py-1 text-right text-xs text-muted-foreground">Limit Price</th>
                  <th className="py-1 text-right text-xs text-muted-foreground">Total</th>
                </tr>
              </thead>
              <tbody>
                {generatedOrder.positions.map((p) => (
                  <tr key={p.symbol} className="border-b border-border/50">
                    <td className="py-1.5 font-mono font-medium">{p.symbol}</td>
                    <td className="py-1.5 text-right tabular-nums">{p.shares}</td>
                    <td className="py-1.5 text-right tabular-nums">{formatCurrency(p.limit_price)}</td>
                    <td className="py-1.5 text-right tabular-nums">{formatCurrency(p.shares * p.limit_price)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={3} className="py-1.5 text-right text-xs font-medium text-muted-foreground">Total</td>
                  <td className="py-1.5 text-right font-semibold tabular-nums">
                    {formatCurrency(generatedOrder.positions.reduce((s, p) => s + p.shares * p.limit_price, 0))}
                  </td>
                </tr>
              </tfoot>
            </table>

            {/* Cash impact */}
            {(() => {
              const orderTotal = generatedOrder.positions.reduce((s, p) => s + p.shares * p.limit_price, 0);
              const isBuy = generatedOrder.type === "BUY";
              const portfolioId = proposals.find(p => p.id === generatedOrder.proposalId)?.portfolio_id;
              const cash = portfolioId ? getCashBalance(portfolioId) : undefined;
              if (cash === undefined) return null;
              const cashAfter = isBuy ? cash - orderTotal : cash + orderTotal;
              return (
                <div className={cn(
                  "mb-4 rounded-md border px-3 py-2 text-sm",
                  isBuy && cashAfter < 0
                    ? "border-red-400/40 bg-red-400/5"
                    : "border-border bg-secondary"
                )}>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Cash Available</span>
                    <span className="tabular-nums font-medium">{formatCurrency(cash)}</span>
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="text-muted-foreground">Order {isBuy ? "Cost" : "Proceeds"}</span>
                    <span className={cn("tabular-nums font-medium", isBuy ? "text-loss" : "text-income")}>
                      {isBuy ? "-" : "+"}{formatCurrency(orderTotal)}
                    </span>
                  </div>
                  <div className="flex justify-between border-t border-border mt-1.5 pt-1.5">
                    <span className="font-medium">Cash After Execution</span>
                    <span className={cn("tabular-nums font-semibold", cashAfter < 0 ? "text-loss" : "text-income")}>
                      {formatCurrency(cashAfter)}
                    </span>
                  </div>
                  {isBuy && cashAfter < 0 && (
                    <p className="mt-1.5 text-xs text-red-400 flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" />
                      Insufficient cash — additional funds needed.
                    </p>
                  )}
                </div>
              );
            })()}

            {/* Broker execution results */}
            {executing && (
              <div className="mb-4 flex items-center gap-2 rounded-md border border-amber-400/30 bg-amber-400/5 px-3 py-2">
                <Loader2 className="h-4 w-4 text-amber-400 animate-spin shrink-0" />
                <p className="text-xs text-amber-400">Submitting orders to broker…</p>
              </div>
            )}
            {generatedOrder.broker_orders && generatedOrder.broker_orders.length > 0 && (
              <div className="mb-4 rounded-md border border-emerald-400/30 bg-emerald-400/5 px-3 py-2 space-y-1.5">
                <p className="text-xs font-semibold text-emerald-400">Orders submitted to broker</p>
                {generatedOrder.broker_orders.map((o) => (
                  <div key={o.order_id} className="flex justify-between text-xs">
                    <span className="font-mono font-medium">{o.symbol}</span>
                    <span className="text-muted-foreground truncate max-w-[180px]">{o.order_id}</span>
                    <span className={cn(
                      "font-medium",
                      o.status === "accepted" || o.status === "pending_new" || o.status === "new" ? "text-emerald-400" :
                      o.error ? "text-red-400" : "text-muted-foreground"
                    )}>{o.error ?? o.status}</span>
                  </div>
                ))}
              </div>
            )}
            {generatedOrder.broker_error && (
              <div className="mb-4 flex items-start gap-2 rounded-md border border-red-400/30 bg-red-400/5 px-3 py-2">
                <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
                <p className="text-xs text-red-400">{generatedOrder.broker_error}</p>
              </div>
            )}
            {!generatedOrder.auto_execute && (
              <div className="mb-4 flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/5 px-3 py-2">
                <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <p className="text-xs text-amber-400">
                  This order requires manual execution through your broker.
                  Enable auto-execution in Settings → Portfolio Config to automate future orders.
                </p>
              </div>
            )}

            <button
              onClick={() => setGeneratedOrder(null)}
              disabled={executing}
              className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              Done
            </button>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Proposals</h1>
        <select
          value={filterPortfolioId}
          onChange={(e) => { setFilterPortfolioId(e.target.value); setSelectedId(null); }}
          className="rounded-md border border-border bg-secondary px-3 py-1.5 text-xs"
        >
          <option value="all">All Portfolios</option>
          {portfolios.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="flex gap-6">
        {/* Left pane — list */}
        <div className="w-80 shrink-0 space-y-3">
          <div className="flex gap-1 rounded-lg border border-border bg-secondary p-1">
            {(["PENDING", "ACCEPTED", "REJECTED"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setSelectedId(null); }}
                className={cn(
                  "flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  tab === t ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {t}
                <span className="ml-1 tabular-nums">
                  ({portfolioFiltered.filter((p) => p.status === t).length})
                </span>
              </button>
            ))}
          </div>

          <div className="space-y-1">
            {filtered.map((p) => (
              <button
                key={p.id}
                onClick={() => { setSelectedId(p.id); cancelEditing(); }}
                className={cn(
                  "w-full rounded-lg border p-3 text-left transition-colors",
                  selectedId === p.id
                    ? "border-primary/50 bg-card"
                    : "border-border hover:bg-secondary"
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{portfolioName(p.portfolio_id)}</span>
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-bold",
                      p.proposal_type === "BUY" && "bg-emerald-400/10 text-emerald-400",
                      p.proposal_type === "TRIM" && "bg-red-400/10 text-red-400",
                      p.proposal_type === "REBALANCE" && "bg-amber-400/10 text-amber-400",
                      p.proposal_type === "TRANSFER" && "bg-cyan-400/10 text-cyan-400"
                    )}
                  >
                    {p.proposal_type}
                  </span>
                </div>
                <div className="mt-1 flex gap-1.5">
                  {p.positions.map((pos) => (
                    <span key={pos.symbol} className="text-xs font-mono font-medium">{pos.symbol}</span>
                  ))}
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{p.summary}</p>
                <p className="mt-1 text-[10px] text-muted-foreground">{formatDateTime(p.created_at)}</p>
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="py-8 text-center text-sm text-muted-foreground">No {tab.toLowerCase()} proposals.</p>
            )}
          </div>
        </div>

        {/* Right pane — detail */}
        {selected ? (
          <div className="flex-1 rounded-lg border border-border bg-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">{portfolioName(selected.portfolio_id)}</span>
                <span
                  className={cn(
                    "rounded px-2 py-0.5 text-xs font-bold",
                    selected.proposal_type === "BUY" && "bg-emerald-400/10 text-emerald-400",
                    selected.proposal_type === "TRIM" && "bg-red-400/10 text-red-400",
                    selected.proposal_type === "REBALANCE" && "bg-amber-400/10 text-amber-400",
                    selected.proposal_type === "TRANSFER" && "bg-cyan-400/10 text-cyan-400"
                  )}
                >
                  {selected.proposal_type}
                </span>
                {selected.status !== "PENDING" && (
                  <span className={cn(
                    "rounded px-2 py-0.5 text-[10px] font-bold uppercase",
                    selected.status === "ACCEPTED" && "bg-emerald-400/10 text-emerald-400",
                    selected.status === "REJECTED" && "bg-red-400/10 text-red-400"
                  )}>
                    {selected.status}
                  </span>
                )}
              </div>
              <span className="text-xs text-muted-foreground">{formatDateTime(selected.created_at)}</span>
            </div>

            <p className="mb-4 text-sm leading-relaxed">{selected.summary}</p>

            {/* TRANSFER: from → to display */}
            {selected.proposal_type === "TRANSFER" && (() => {
              const fromFlag = selected.risk_flags.find((f) => f.startsWith("From:"));
              const toFlag = selected.risk_flags.find((f) => f.startsWith("To:"));
              const fromName = fromFlag ? fromFlag.replace("From: ", "") : portfolioName(selected.portfolio_id);
              const toName = toFlag ? toFlag.replace("To: ", "") : ((selected as Proposal & { to_portfolio_id?: string }).to_portfolio_id ? portfolioName((selected as Proposal & { to_portfolio_id?: string }).to_portfolio_id!) : "—");
              return (
                <div className="mb-4 flex items-center gap-3 rounded-lg border border-cyan-400/20 bg-cyan-400/5 px-4 py-3">
                  <div className="flex-1 text-center">
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">From</p>
                    <p className="text-sm font-semibold text-foreground">{fromName}</p>
                  </div>
                  <div className="text-cyan-400">→</div>
                  <div className="flex-1 text-center">
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">To</p>
                    <p className="text-sm font-semibold text-foreground">{toName}</p>
                  </div>
                </div>
              );
            })()}

            {/* Dual-lens: Analyst + Platform */}
            <div className="grid grid-cols-2 gap-6 mb-5">
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Analyst View</h3>
                <dl className="space-y-1.5 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Source</dt>
                    <dd>{selected.analyst_source || "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Sentiment</dt>
                    <dd>{selected.analyst_sentiment || "—"}</dd>
                  </div>
                </dl>
              </div>
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Platform Assessment</h3>
                <dl className="space-y-1.5 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Total Cost</dt>
                    <dd className="tabular-nums">{formatCurrency(totalCost(getPositions(selected.id)))}</dd>
                  </div>
                  {(() => {
                    const cash = getCashBalance(selected.portfolio_id);
                    const cost = totalCost(getPositions(selected.id));
                    const isBuy = selected.proposal_type !== "TRIM";
                    if (cash === undefined) return null;
                    const after = isBuy ? cash - cost : cash + cost;
                    return (
                      <>
                        <div className="flex justify-between">
                          <dt className="text-muted-foreground">Cash Available</dt>
                          <dd className="tabular-nums">{formatCurrency(cash)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-muted-foreground">Cash After</dt>
                          <dd className={cn("tabular-nums font-medium", after < 0 ? "text-loss" : "text-income")}>
                            {formatCurrency(after)}
                            {isBuy && after < 0 && " ⚠"}
                          </dd>
                        </div>
                      </>
                    );
                  })()}
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Est. Annual Income</dt>
                    <dd className="tabular-nums text-income">{formatCurrency(totalIncome(getPositions(selected.id)))}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Blended Yield</dt>
                    <dd className="tabular-nums text-income">
                      {totalCost(getPositions(selected.id)) > 0
                        ? formatPercent((totalIncome(getPositions(selected.id)) / totalCost(getPositions(selected.id))) * 100)
                        : "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Execution</dt>
                    <dd className={cn("text-xs", getAutoExecute(selected.portfolio_id) ? "text-amber-400" : "text-muted-foreground")}>
                      {getAutoExecute(selected.portfolio_id) ? "Auto" : "Manual"}
                    </dd>
                  </div>
                  {selected.risk_flags.length > 0 && (
                    <div>
                      <dt className="mb-1 text-muted-foreground">Risk Flags</dt>
                      <dd className="flex flex-wrap gap-1">
                        {selected.risk_flags.map((f) => (
                          <span key={f} className="rounded bg-red-400/10 px-1.5 py-0.5 text-[10px] font-medium text-red-400">{f}</span>
                        ))}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
            </div>

            {/* Impact summary when editing */}
            {editingId === selected.id && (costDelta(selected.id) !== null) && (
              <div className="mb-4 rounded-md border border-primary/30 bg-primary/5 px-4 py-2">
                <h4 className="text-xs font-semibold text-muted-foreground mb-1">Modification Impact</h4>
                <div className="flex gap-6 text-sm">
                  <div>
                    <span className="text-muted-foreground">Cost: </span>
                    <span className={cn("tabular-nums font-medium", (costDelta(selected.id) ?? 0) > 0 ? "text-loss" : "text-income")}>
                      {(costDelta(selected.id) ?? 0) >= 0 ? "+" : ""}{formatCurrency(costDelta(selected.id) ?? 0)}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Income: </span>
                    <span className={cn("tabular-nums font-medium", (incomeDelta(selected.id) ?? 0) >= 0 ? "text-income" : "text-loss")}>
                      {(incomeDelta(selected.id) ?? 0) >= 0 ? "+" : ""}{formatCurrency(incomeDelta(selected.id) ?? 0)}/yr
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Positions table */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Positions</h3>
                {selected.status === "PENDING" && editingId !== selected.id && (
                  <button
                    onClick={() => startEditing(selected.id)}
                    className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                  >
                    <Pencil className="h-3 w-3" /> Modify
                  </button>
                )}
                {editingId === selected.id && (
                  <button
                    onClick={cancelEditing}
                    className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                  >
                    <X className="h-3 w-3" /> Cancel Edit
                  </button>
                )}
              </div>

              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-secondary/50">
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Symbol</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Name</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Shares</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Entry Price</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Current</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Yield</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Score</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Cost</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Est. Income</th>
                      {editingId === selected.id && (
                        <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground w-8"></th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {getPositions(selected.id).map((pos, idx) => {
                      const posCost = Math.abs(pos.shares) * pos.entry_price;
                      const posIncome = posCost * (pos.yield_estimate / 100);
                      return (
                        <tr key={`${pos.symbol}-${idx}`} className="border-b border-border last:border-0">
                          <td className="px-3 py-2">
                            <TickerBadge symbol={pos.symbol} assetType={pos.asset_type} />
                          </td>
                          <td className="px-3 py-2 text-xs text-muted-foreground">{pos.name}</td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {editingId === selected.id ? (
                              <input
                                type="number"
                                value={pos.shares}
                                onChange={(e) => updatePosition(selected.id, idx, "shares", Number(e.target.value))}
                                className="w-20 rounded border border-border bg-secondary px-1.5 py-0.5 text-right text-xs tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
                              />
                            ) : (
                              <span className={pos.shares < 0 ? "text-red-400" : "text-income"}>
                                {pos.shares > 0 ? "+" : ""}{pos.shares}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {editingId === selected.id ? (
                              <input
                                type="number"
                                step="0.01"
                                value={pos.entry_price}
                                onChange={(e) => updatePosition(selected.id, idx, "entry_price", Number(e.target.value))}
                                className="w-20 rounded border border-border bg-secondary px-1.5 py-0.5 text-right text-xs tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
                              />
                            ) : (
                              formatCurrency(pos.entry_price)
                            )}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(pos.current_price)}</td>
                          <td className="px-3 py-2 text-right tabular-nums">{formatPercent(pos.yield_estimate)}</td>
                          <td className="px-3 py-2 text-right"><ScorePill score={pos.score} /></td>
                          <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(posCost)}</td>
                          <td className="px-3 py-2 text-right tabular-nums text-income">{formatCurrency(posIncome)}</td>
                          {editingId === selected.id && (
                            <td className="px-2 py-2 text-right">
                              <button
                                onClick={() => removePosition(selected.id, idx)}
                                className="rounded p-0.5 text-red-400 hover:bg-red-400/10 transition-colors"
                              >
                                <Minus className="h-3.5 w-3.5" />
                              </button>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr className="bg-secondary/30">
                      <td colSpan={7} className="px-3 py-2 text-xs font-medium text-muted-foreground text-right">Total</td>
                      <td className="px-3 py-2 text-right text-xs font-semibold tabular-nums">
                        {formatCurrency(totalCost(getPositions(selected.id)))}
                      </td>
                      <td className="px-3 py-2 text-right text-xs font-semibold tabular-nums text-income">
                        {formatCurrency(totalIncome(getPositions(selected.id)))}
                      </td>
                      {editingId === selected.id && <td></td>}
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>

            {/* Action bar */}
            {selected.status === "PENDING" && (
              <div className="flex gap-2 border-t border-border pt-4">
                <button
                  onClick={() => rejectProposal(selected.id)}
                  className="flex items-center gap-1.5 rounded-md bg-red-500/10 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-500/20 transition-colors"
                >
                  <X className="h-4 w-4" /> Reject
                </button>
                <button
                  onClick={() => acceptProposal(selected)}
                  disabled={executing}
                  className="flex items-center gap-1.5 rounded-md bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                >
                  {executing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                  {executing ? "Submitting…" : "Accept"}
                </button>
                <button
                  onClick={() => deferProposal(selected.id)}
                  className="flex items-center gap-1.5 rounded-md bg-secondary px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors ml-auto"
                >
                  <Clock className="h-4 w-4" /> Defer 7d
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center rounded-lg border border-border bg-card">
            <p className="text-sm text-muted-foreground">Select a proposal to view details</p>
          </div>
        )}
      </div>
    </div>
  );
}
