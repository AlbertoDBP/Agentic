"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { usePortfolio } from "@/lib/portfolio-context";
import { ScoreBreakdownModal, type ScoreBreakdownModalProps } from "@/components/ScoreBreakdownModal";

// ── Types (mirrors Agent 08 RebalanceResponse) ────────────────────────────────

interface TaxImpact {
  unrealized_gain_loss: number;
  estimated_tax_savings: number;
  long_term: boolean;
  wash_sale_risk: boolean;
  action: string;
}

interface RebalanceProposal {
  symbol: string;
  action: string;
  priority: number;
  reason: string;
  violation_type: string | null;
  current_value: number;
  current_weight_pct: number;
  proposed_weight_pct: number | null;
  estimated_trade_value: number;
  income_score: number | null;
  income_grade: string | null;
  hhs_score: number | null;
  hhs_status: string | null;
  unsafe_flag: boolean | null;
  ies_score: number | null;
  ies_calculated: boolean | null;
  income_contribution_est: number | null;
  tax_impact: TaxImpact | null;
}

interface RebalanceResult {
  portfolio_id: string;
  portfolio_value: number;
  actual_income_annual: number | null;
  target_income_annual: number | null;
  income_gap_annual: number | null;
  violations_count: number;
  violations_summary: {
    count: number;
    unsafe?: number;
    veto?: number;
    overweight?: number;
    below_grade?: number;
    hhs_tiers?: Record<string, number>;
  };
  proposals: RebalanceProposal[];
  tax_impact_total_savings: number | null;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const ACTION_COLOR: Record<string, string> = {
  SELL: "text-red-400",
  TRIM: "text-amber-400",
  ADD:  "text-green-400",
};

const VIOLATION_BADGE: Record<string, string> = {
  UNSAFE:        "bg-red-950/50 text-red-400 border border-red-900/50",
  VETO:          "bg-orange-950/50 text-orange-400 border border-orange-900/50",
  OVERWEIGHT:    "bg-amber-950/50 text-amber-400 border border-amber-900/50",
  BELOW_GRADE:   "bg-yellow-950/50 text-yellow-400 border border-yellow-900/50",
  DEPLOY_CAPITAL:"bg-green-950/50 text-green-400 border border-green-900/50",
};

function fmt$(n: number | null): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

// ── Component ─────────────────────────────────────────────────────────────────

interface RebalanceCardProps {
  defaultPortfolioId?: string;
}

export function RebalanceCard({ defaultPortfolioId }: RebalanceCardProps) {
  const { portfolios } = usePortfolio();
  const [collapsed, setCollapsed] = useState(true);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>(
    defaultPortfolioId ?? portfolios[0]?.id ?? ""
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RebalanceResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modalProps, setModalProps] = useState<Omit<ScoreBreakdownModalProps, "onClose"> | null>(null);

  async function runAnalysis() {
    if (!selectedPortfolioId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`/api/portfolios/${selectedPortfolioId}/rebalance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail ?? `HTTP ${res.status}`);
      }
      setResult(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const vs = result?.violations_summary;
  const tiers = vs?.hhs_tiers ?? {};

  return (
    <div className="border border-border rounded-lg bg-card/50 overflow-hidden">
      {/* Header */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/20 transition-colors"
        onClick={() => setCollapsed((c) => !c)}
      >
        <div className="flex items-center gap-2">
          {collapsed ? <ChevronRight size={14} className="text-muted-foreground" /> : <ChevronDown size={14} className="text-muted-foreground" />}
          <span className="text-sm font-semibold">Portfolio Health Check</span>
          {result && (
            <span className="text-xs text-muted-foreground ml-1">
              · {result.violations_count} violation{result.violations_count !== 1 ? "s" : ""}
              {result.tax_impact_total_savings ? ` · ${fmt$(result.tax_impact_total_savings)} tax savings avail.` : ""}
            </span>
          )}
        </div>
        {result && (
          <span className="text-[10px] text-emerald-400 font-medium">Analysis ready</span>
        )}
      </button>

      {!collapsed && (
        <div className="border-t border-border px-4 py-4 space-y-4">
          {/* Controls */}
          <div className="flex items-center gap-3">
            {portfolios.length > 1 && (
              <select
                className="text-sm bg-muted/30 border border-border rounded px-2 py-1 text-foreground"
                value={selectedPortfolioId}
                onChange={(e) => { setSelectedPortfolioId(e.target.value); setResult(null); }}
              >
                {portfolios.map((p) => (
                  <option key={p.id} value={p.id}>{p.name ?? p.id.slice(0, 8)}</option>
                ))}
              </select>
            )}
            <button
              onClick={runAnalysis}
              disabled={loading || !selectedPortfolioId}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-white transition-colors"
            >
              {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              {loading ? "Analyzing…" : result ? "Re-run" : "Run Analysis"}
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/40 rounded px-3 py-2">
              {error}
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-3">
              {/* Violation counts */}
              <div className="flex flex-wrap gap-2 text-xs">
                {(vs?.unsafe ?? 0) > 0 && <span className={cn("px-2 py-0.5 rounded", VIOLATION_BADGE.UNSAFE)}>UNSAFE ×{vs!.unsafe}</span>}
                {(vs?.veto ?? 0) > 0 && <span className={cn("px-2 py-0.5 rounded", VIOLATION_BADGE.VETO)}>VETO ×{vs!.veto}</span>}
                {(vs?.overweight ?? 0) > 0 && <span className={cn("px-2 py-0.5 rounded", VIOLATION_BADGE.OVERWEIGHT)}>OVERWEIGHT ×{vs!.overweight}</span>}
                {(vs?.below_grade ?? 0) > 0 && <span className={cn("px-2 py-0.5 rounded", VIOLATION_BADGE.BELOW_GRADE)}>BELOW GRADE ×{vs!.below_grade}</span>}
              </div>

              {/* HHS tiers */}
              {Object.keys(tiers).some((k) => tiers[k] > 0) && (
                <div className="text-xs text-muted-foreground">
                  HHS tiers:{" "}
                  {Object.entries(tiers)
                    .filter(([, n]) => n > 0)
                    .map(([status, n]) => `${n} ${status}`)
                    .join(" · ")}
                </div>
              )}

              {/* Proposals table */}
              {result.proposals.length > 0 ? (
                <div className="space-y-1">
                  {result.proposals.map((p, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 py-2 border-b border-border/30 last:border-0"
                    >
                      {/* Violation badge */}
                      <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 mt-0.5", VIOLATION_BADGE[p.violation_type ?? ""] ?? "bg-muted/40 text-muted-foreground")}>
                        {p.violation_type?.replace("_", " ") ?? "—"}
                      </span>
                      {/* Ticker + action */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold">{p.symbol}</span>
                          <span className={cn("text-xs font-semibold", ACTION_COLOR[p.action] ?? "text-muted-foreground")}>
                            {p.action}
                          </span>
                          <span className="text-xs text-muted-foreground tabular-nums">
                            {p.estimated_trade_value >= 0 ? "+" : ""}{fmt$(p.estimated_trade_value)}
                          </span>
                          {/* Score breakdown button */}
                          <button
                            onClick={() => setModalProps({
                              ticker: p.symbol,
                              factorDetails: null,
                              hhsScore: p.hhs_score,
                              iesScore: p.ies_score,
                              hhsStatus: p.hhs_status,
                              iesCalculated: p.ies_calculated ?? false,
                              iesBlockedReason: null,
                            })}
                            className="text-[10px] text-blue-400 hover:text-blue-300 ml-auto shrink-0"
                          >
                            ↗ score
                          </button>
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5 truncate">{p.reason}</div>
                        {p.tax_impact && p.tax_impact.estimated_tax_savings > 0 && (
                          <div className="text-[10px] text-emerald-400 mt-0.5">
                            Est. {fmt$(p.tax_impact.estimated_tax_savings)} tax savings
                            {p.tax_impact.long_term ? " · Long-term" : ""}
                            {p.tax_impact.wash_sale_risk ? " · ⚠ Wash-sale risk" : ""}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground text-center py-3">
                  No violations or opportunities found for this portfolio.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Score breakdown modal */}
      {modalProps && (
        <ScoreBreakdownModal {...modalProps} onClose={() => setModalProps(null)} />
      )}
    </div>
  );
}
