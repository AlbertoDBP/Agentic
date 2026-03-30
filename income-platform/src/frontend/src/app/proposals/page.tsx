"use client";

import { useState, useEffect, useCallback } from "react";
import { Check, X, Clock, RefreshCw, AlertTriangle, Loader2, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/utils";

// ── Types matching Agent 12 ProposalResponse ────────────────────────────────

interface Proposal {
  id: number;
  ticker: string;
  analyst_signal_id: number | null;
  analyst_id: number | null;
  platform_score: number | null;
  platform_alignment: string | null;
  veto_flags: unknown;
  divergence_notes: string | null;
  analyst_recommendation: string | null;
  analyst_sentiment: number | null;
  analyst_thesis_summary: string | null;
  analyst_yield_estimate: number | null;
  analyst_safety_grade: string | null;
  platform_yield_estimate: number | null;
  platform_safety_result: unknown;
  platform_income_grade: string | null;
  entry_price_low: number | null;
  entry_price_high: number | null;
  position_size_pct: number | null;
  recommended_account: string | null;
  sizing_rationale: string | null;
  status: string;
  trigger_mode: string | null;
  override_rationale: string | null;
  user_acknowledged_veto: boolean;
  decided_at: string | null;
  expires_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  entry_method: string | null;
}

// ── Status helpers ────────────────────────────────────────────────────────────

const PENDING_STATUSES = new Set(["pending", "PENDING"]);
const ACCEPTED_STATUSES = new Set(["executed_aligned", "executed_override"]);
const REJECTED_STATUSES = new Set(["rejected", "expired"]);

type Tab = "PENDING" | "ACCEPTED" | "REJECTED";

function tabMatch(status: string, tab: Tab): boolean {
  if (tab === "PENDING") return PENDING_STATUSES.has(status);
  if (tab === "ACCEPTED") return ACCEPTED_STATUSES.has(status);
  if (tab === "REJECTED") return REJECTED_STATUSES.has(status);
  return false;
}

function alignmentColor(alignment: string | null): string {
  if (!alignment) return "text-muted-foreground";
  const a = alignment.toLowerCase();
  if (a === "aligned") return "text-income";
  if (a === "partial") return "text-amber-400";
  if (a === "vetoed") return "text-loss";
  if (a === "divergent") return "text-amber-500";
  return "text-muted-foreground";
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("PENDING");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [actioning, setActioning] = useState<number | null>(null);

  const fetchProposals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/proposals?limit=200");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setProposals(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchProposals(); }, [fetchProposals]);

  const filtered = proposals.filter((p) => tabMatch(p.status, tab));
  const selected = proposals.find((p) => p.id === selectedId) ?? filtered[0] ?? null;

  // Auto-select first when switching tabs
  useEffect(() => {
    if (filtered.length > 0 && !filtered.find((p) => p.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [tab, filtered, selectedId]);

  const counts: Record<Tab, number> = {
    PENDING:  proposals.filter((p) => tabMatch(p.status, "PENDING")).length,
    ACCEPTED: proposals.filter((p) => tabMatch(p.status, "ACCEPTED")).length,
    REJECTED: proposals.filter((p) => tabMatch(p.status, "REJECTED")).length,
  };

  // ── Actions ──

  const executeProposal = async (proposal: Proposal) => {
    setActioning(proposal.id);
    try {
      const resp = await fetch(`/api/proposals/${proposal.id}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_acknowledged_veto: false }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Execute failed");
      setProposals((prev) => prev.map((p) => p.id === proposal.id ? data : p));
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      setActioning(null);
    }
  };

  const rejectProposal = async (proposal: Proposal) => {
    setActioning(proposal.id);
    try {
      const resp = await fetch(`/api/proposals/${proposal.id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Reject failed");
      setProposals((prev) => prev.map((p) => p.id === proposal.id ? data : p));
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      setActioning(null);
    }
  };

  // ── Render ──

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4 p-6 max-w-7xl mx-auto">
      {/* Left: proposal list */}
      <div className="flex w-72 shrink-0 flex-col gap-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Proposals</h1>
          <button
            onClick={fetchProposals}
            className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-secondary"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex rounded-lg border border-border bg-secondary/30 p-0.5 text-sm">
          {(["PENDING", "ACCEPTED", "REJECTED"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "flex-1 rounded-md px-2 py-1 text-xs font-medium transition-colors",
                tab === t
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {t.charAt(0) + t.slice(1).toLowerCase()} {counts[t] > 0 && `(${counts[t]})`}
            </button>
          ))}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto space-y-1.5">
          {loading && (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading…
            </div>
          )}
          {!loading && error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
          )}
          {!loading && !error && filtered.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              No {tab.toLowerCase()} proposals.<br />
              Run a scan and click <strong>Propose</strong> to create one.
            </div>
          )}
          {filtered.map((p) => (
            <button
              key={p.id}
              onClick={() => setSelectedId(p.id)}
              className={cn(
                "w-full rounded-lg border border-border p-3 text-left transition-colors",
                selected?.id === p.id
                  ? "bg-primary/10 border-primary/40"
                  : "bg-card hover:bg-secondary/50"
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-semibold">{p.ticker}</span>
                {p.platform_score != null && (
                  <span className="rounded-full bg-primary/15 px-2 py-0.5 text-xs font-semibold text-primary">{p.platform_score.toFixed(0)}</span>
                )}
              </div>
              <div className="mt-1 flex items-center justify-between">
                <span className={cn("text-xs font-medium", alignmentColor(p.platform_alignment))}>
                  {p.platform_alignment ?? "—"}
                </span>
                <span className="text-xs text-muted-foreground">
                  {p.created_at ? formatDateTime(p.created_at) : ""}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Right: detail panel */}
      <div className="flex-1 overflow-y-auto rounded-xl border border-border bg-card p-6">
        {!selected ? (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Select a proposal to review
          </div>
        ) : (
          <ProposalDetail
            proposal={selected}
            actioning={actioning === selected.id}
            onExecute={() => executeProposal(selected)}
            onReject={() => rejectProposal(selected)}
          />
        )}
      </div>
    </div>
  );
}

// ── Detail Panel ─────────────────────────────────────────────────────────────

function ProposalDetail({
  proposal: p,
  actioning,
  onExecute,
  onReject,
}: {
  proposal: Proposal;
  actioning: boolean;
  onExecute: () => void;
  onReject: () => void;
}) {
  const isPending = PENDING_STATUSES.has(p.status);
  const isVetoed = p.platform_alignment?.toLowerCase() === "vetoed";

  return (
    <div className="space-y-5">
      {/* Ticker + status row */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <span className="font-mono text-lg font-bold">{p.ticker}</span>
            <span className={cn("text-sm font-semibold", alignmentColor(p.platform_alignment))}>
              {p.platform_alignment ?? "—"}
            </span>
            {isVetoed && (
              <span className="flex items-center gap-1 text-xs text-loss">
                <AlertTriangle className="h-3 w-3" /> Vetoed
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Created {p.created_at ? formatDateTime(p.created_at) : "—"}
            {p.trigger_mode && ` · ${p.trigger_mode}`}
          </p>
        </div>

        {/* Actions */}
        {isPending && (
          <div className="flex gap-2">
            <button
              onClick={onReject}
              disabled={actioning}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground hover:border-loss hover:text-loss disabled:opacity-40"
            >
              {actioning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
              Reject
            </button>
            <button
              onClick={onExecute}
              disabled={actioning || isVetoed}
              title={isVetoed ? "Proposal is vetoed — cannot execute" : undefined}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
            >
              {actioning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
              Accept
            </button>
          </div>
        )}
        {!isPending && (
          <span className={cn(
            "rounded-full px-3 py-1 text-xs font-semibold",
            ACCEPTED_STATUSES.has(p.status) ? "bg-income/20 text-income" : "bg-muted text-muted-foreground"
          )}>
            {p.status.replace("_", " ").toUpperCase()}
          </span>
        )}
      </div>

      {/* Scores row */}
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Platform Score" value={p.platform_score != null ? p.platform_score.toFixed(1) : "—"} />
        <MetricCard label="Platform Grade" value={p.platform_income_grade ?? "—"} />
        <MetricCard
          label="Analyst Rec"
          value={p.analyst_recommendation ?? "—"}
          valueClass={p.analyst_recommendation?.includes("BUY") ? "text-income" : undefined}
        />
      </div>

      {/* Entry pricing */}
      {(p.entry_price_low != null || p.entry_price_high != null) && (
        <Section title="Entry Pricing">
          <div className="grid grid-cols-2 gap-3">
            <MetricCard label="Entry Low" value={p.entry_price_low != null ? `$${p.entry_price_low.toFixed(2)}` : "—"} />
            <MetricCard label="Entry High" value={p.entry_price_high != null ? `$${p.entry_price_high.toFixed(2)}` : "—"} />
          </div>
          {p.recommended_account && (
            <p className="text-sm text-muted-foreground">
              Recommended account: <span className="font-medium text-foreground">{p.recommended_account}</span>
            </p>
          )}
          {p.sizing_rationale && (
            <p className="text-sm text-muted-foreground">{p.sizing_rationale}</p>
          )}
        </Section>
      )}

      {/* Yield estimates */}
      {(p.analyst_yield_estimate != null || p.platform_yield_estimate != null) && (
        <Section title="Yield Estimates">
          <div className="grid grid-cols-2 gap-3">
            <MetricCard label="Analyst Yield" value={p.analyst_yield_estimate != null ? `${p.analyst_yield_estimate.toFixed(2)}%` : "—"} />
            <MetricCard label="Platform Yield" value={p.platform_yield_estimate != null ? `${p.platform_yield_estimate.toFixed(2)}%` : "—"} />
          </div>
        </Section>
      )}

      {/* Analyst thesis */}
      {p.analyst_thesis_summary && (
        <Section title="Analyst Thesis">
          <p className="text-sm leading-relaxed text-muted-foreground">{p.analyst_thesis_summary}</p>
          {p.analyst_safety_grade && (
            <p className="text-xs text-muted-foreground mt-1">
              Safety Grade: <span className="font-medium text-foreground">{p.analyst_safety_grade}</span>
            </p>
          )}
        </Section>
      )}

      {/* Veto / divergence notes */}
      {(p.veto_flags || p.divergence_notes) && (
        <Section title="Platform Notes">
          {p.divergence_notes && (
            <p className="text-sm text-muted-foreground">{p.divergence_notes}</p>
          )}
          {p.veto_flags && (
            <div className="rounded-md border border-loss/30 bg-loss/10 p-3 text-xs text-loss">
              {JSON.stringify(p.veto_flags)}
            </div>
          )}
        </Section>
      )}

      {/* Override rationale (if accepted via override) */}
      {p.override_rationale && (
        <Section title="Override Rationale">
          <p className="text-sm text-muted-foreground">{p.override_rationale}</p>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </div>
  );
}

function MetricCard({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="rounded-lg border border-border bg-secondary/30 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-base font-semibold", valueClass)}>{value}</p>
    </div>
  );
}
