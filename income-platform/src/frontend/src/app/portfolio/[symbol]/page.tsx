"use client";

import { use, useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, TrendingUp, DollarSign, Activity, Loader2, Pencil, Check, X } from "lucide-react";
import { MetricCard } from "@/components/metric-card";
import { ScorePill } from "@/components/score-pill";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { ASSET_CLASS_COLORS, API_BASE_URL } from "@/lib/config";

const ASSET_TYPES = ["Common Stock", "BDC", "CEF", "MLP", "ETF", "Preferred", "Bond"];
const FREQUENCIES = ["Monthly", "Quarterly", "Semi-Annual", "Annual"];

interface Position {
  id: string;
  portfolio_id: string;
  symbol: string;
  name: string;
  asset_type: string;
  sector: string;
  industry?: string;
  shares: number;
  cost_basis: number;
  current_value: number;
  market_price: number;
  avg_cost: number;
  annual_income: number;
  yield_on_cost: number;   // returned as percentage
  current_yield: number;   // returned as percentage
  score: number;
  grade: string;
  recommendation: string;
  valuation_yield_score: number;
  financial_durability_score: number;
  technical_entry_score: number;
  nav_erosion_penalty: number;
  signal_penalty: number;
  factor_details: Record<string, { value: number; score: number; weight: number }> | null;
  nav_erosion_details: { prob_erosion_gt_5pct?: number; median_annual_nav_change_pct?: number; risk_classification?: string; penalty_applied?: number } | null;
  dividend_frequency?: string;
  price_updated_at: string | null;
  updated_at: string | null;
  // Market intelligence
  daily_change_pct?: number | null;
  week52_high?: number | null;
  week52_low?: number | null;
  market_cap?: number | null;
  pe_ratio?: number | null;
  eps?: number | null;
  payout_ratio?: number | null;
  beta?: number | null;
  nav_value?: number | null;
  nav_discount_pct?: number | null;
  ex_div_date?: string | null;
  pay_date?: string | null;
  avg_volume?: number | null;
  dividend_growth_5y?: number | null;
}

export default function TickerDetailPage({ params }: { params: Promise<{ symbol: string }> }) {
  // params.symbol may still be URL-encoded (e.g. "BRK%2FB") in some Next.js versions
  const { symbol: rawSymbol } = use(params);
  const symbol = decodeURIComponent(rawSymbol);

  const [position, setPosition] = useState<Position | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit state
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editForm, setEditForm] = useState<Partial<Position>>({});
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE_URL}/api/positions/${encodeURIComponent(symbol.toUpperCase())}`, { credentials: "include" })
      .then((res) => {
        if (!res.ok) throw new Error(`Position not found: ${symbol.toUpperCase()}`);
        return res.json() as Promise<Position>;
      })
      .then((pos) => { setPosition(pos); setEditForm(pos); })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [symbol]);

  const startEdit = () => {
    if (position) setEditForm({ ...position });
    setEditing(true);
  };

  const cancelEdit = () => { setEditing(false); setSaveMsg(null); };

  const saveEdit = async () => {
    if (!position || !editForm) return;
    setSaving(true);
    const shares = Number(editForm.shares ?? position.shares);
    const avg_cost_basis = Number(editForm.avg_cost ?? position.avg_cost);
    const cost_basis = shares * avg_cost_basis;
    const cur_price = position.shares > 0 ? position.current_value / position.shares : avg_cost_basis;
    const annual_income = Number(editForm.annual_income ?? position.annual_income);
    const yoc = cost_basis > 0 ? (annual_income / cost_basis) * 100 : 0;
    const current_value = shares * cur_price;

    try {
      const res = await fetch(`${API_BASE_URL}/api/positions/${position.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quantity: shares,
          avg_cost_basis,
          current_price: cur_price,
          annual_income,
          yield_on_cost: yoc,
          sector: editForm.sector ?? "",
          dividend_frequency: editForm.dividend_frequency ?? "",
        }),
      });
      if (!res.ok) throw new Error("Save failed");
      const updated: Position = {
        ...position,
        ...editForm,
        shares, cost_basis, current_value, annual_income,
        avg_cost: avg_cost_basis,
        market_price: cur_price,
        yield_on_cost: yoc,
      };
      setPosition(updated);
      setEditing(false);
      setSaveMsg("Saved");
      setTimeout(() => setSaveMsg(null), 3000);
    } catch {
      setSaveMsg("Save failed — try again");
    } finally {
      setSaving(false);
    }
  };

  const backLink = (
    <Link href="/portfolio" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="h-4 w-4" /> Back to Portfolio
    </Link>
  );

  if (loading) return (
    <div className="space-y-4">
      {backLink}
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading {symbol.toUpperCase()}…</span>
      </div>
    </div>
  );

  if (error || !position) return (
    <div className="space-y-4">
      {backLink}
      <p className="text-muted-foreground">{error ?? `Position not found: ${symbol}`}</p>
    </div>
  );

  const gain = position.current_value - position.cost_basis;
  const gainPct = position.cost_basis > 0 ? (gain / position.cost_basis) * 100 : 0;
  const color = ASSET_CLASS_COLORS[position.asset_type] || "#64748b";
  const currentPrice = position.market_price || (position.shares > 0 ? position.current_value / position.shares : 0);
  const avgCostPerShare = position.avg_cost || (position.shares > 0 ? position.cost_basis / position.shares : 0);
  const monthlyAmt = position.annual_income / 12;
  const monthlyIncome = Array(12).fill(monthlyAmt);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        {backLink}
        <div className="flex items-center gap-3 mt-3">
          <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
          <h1 className="text-2xl font-semibold">{position.symbol}</h1>
          <span className="rounded bg-secondary px-2 py-0.5 text-xs font-medium">{position.asset_type}</span>
          {position.score > 0 && <ScorePill score={position.score} />}
          <div className="ml-auto flex items-center gap-2">
            {saveMsg && (
              <span className={cn("text-xs", saveMsg === "Saved" ? "text-income" : "text-loss")}>{saveMsg}</span>
            )}
            {!editing ? (
              <button onClick={startEdit}
                className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors">
                <Pencil className="h-3.5 w-3.5" /> Edit Position
              </button>
            ) : (
              <div className="flex gap-2">
                <button onClick={saveEdit} disabled={saving}
                  className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors">
                  <Check className="h-3.5 w-3.5" /> {saving ? "Saving…" : "Save"}
                </button>
                <button onClick={cancelEdit}
                  className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-secondary transition-colors">
                  <X className="h-3.5 w-3.5" /> Cancel
                </button>
              </div>
            )}
          </div>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {position.name}
          {position.sector ? ` · ${position.sector}` : ""}
          {position.grade ? ` · Grade ${position.grade}` : ""}
          {position.dividend_frequency ? ` · ${position.dividend_frequency}` : ""}
        </p>
      </div>

      {/* Edit form */}
      {editing && (
        <div className="rounded-lg border border-primary/30 bg-card p-4 space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Edit Position</h3>
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Quantity</label>
              <input type="number" step="1" value={editForm.shares ?? ""}
                onChange={(e) => setEditForm({ ...editForm, shares: Number(e.target.value) })}
                className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Cost/Share</label>
              <input type="number" step="0.01" value={editForm.avg_cost ?? ""}
                onChange={(e) => setEditForm({ ...editForm, avg_cost: Number(e.target.value) })}
                className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Annual Income</label>
              <input type="number" step="0.01" value={editForm.annual_income ?? ""}
                onChange={(e) => setEditForm({ ...editForm, annual_income: Number(e.target.value) })}
                className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Sector</label>
              <input type="text" value={editForm.sector ?? ""}
                onChange={(e) => setEditForm({ ...editForm, sector: e.target.value })}
                className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Frequency</label>
              <select value={editForm.dividend_frequency ?? "Quarterly"}
                onChange={(e) => setEditForm({ ...editForm, dividend_frequency: e.target.value })}
                className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm">
                {FREQUENCIES.map((f) => <option key={f}>{f}</option>)}
              </select>
            </div>
          </div>
          {/* Calculated preview */}
          <div className="flex gap-6 text-xs text-muted-foreground border-t border-border pt-2">
            {(() => {
              const sh = Number(editForm.shares ?? 0);
              const avg = Number(editForm.avg_cost ?? 0);
              const cb = sh * avg;
              const ai = Number(editForm.annual_income ?? 0);
              const cp = position.shares > 0 ? position.current_value / position.shares : avg;
              const yoc = cb > 0 ? (ai / cb) * 100 : 0;
              return (<>
                <span>Cost Basis: <strong className="text-foreground">{formatCurrency(cb)}</strong></span>
                <span>Curr Price: <strong className="text-foreground">{formatCurrency(cp)}</strong></span>
                <span>YoC: <strong className="text-foreground">{yoc.toFixed(2)}%</strong></span>
                <span>Monthly: <strong className="text-income">{formatCurrency(ai / 12)}</strong></span>
              </>);
            })()}
          </div>
        </div>
      )}

      {/* KPI strip */}
      <div className="grid grid-cols-6 gap-3">
        <MetricCard label="Current Value" value={formatCurrency(position.current_value)} icon={DollarSign} />
        <MetricCard label="Cost Basis" value={formatCurrency(position.cost_basis)} />
        <MetricCard
          label="Gain/Loss"
          value={`${gain >= 0 ? "+" : ""}${formatCurrency(gain)}`}
          delta={`${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(1)}%`}
          deltaType={gain >= 0 ? "positive" : "negative"}
          icon={TrendingUp}
        />
        <MetricCard label="Annual Income" value={formatCurrency(position.annual_income)} icon={DollarSign} />
        <MetricCard label="Yield on Cost" value={formatPercent(position.yield_on_cost)} icon={Activity} />
        <MetricCard label="Current Yield" value={formatPercent(position.current_yield)} />
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Position Details */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Position Details</h2>
          <dl className="space-y-2.5 text-sm">
            {[
              ["Shares", position.shares.toLocaleString()],
              ["Avg Cost/Share", formatCurrency(avgCostPerShare)],
              ["Current Price", formatCurrency(currentPrice)],
              ["Daily Change", position.daily_change_pct != null
                ? <span className={cn("tabular-nums", position.daily_change_pct >= 0 ? "text-income" : "text-loss")}>
                    {position.daily_change_pct >= 0 ? "+" : ""}{position.daily_change_pct.toFixed(2)}%
                  </span>
                : "—"],
              ["Asset Type", position.asset_type],
              ["Sector", position.sector || "—"],
              ["Industry", position.industry || "—"],
              ["Frequency", position.dividend_frequency || "—"],
              ["Ex-Div Date", position.ex_div_date ? new Date(position.ex_div_date).toLocaleDateString() : "—"],
              ["Pay Date", position.pay_date ? new Date(position.pay_date).toLocaleDateString() : "—"],
              ["Last Updated", position.price_updated_at
                ? new Date(position.price_updated_at).toLocaleDateString()
                : "—"],
            ].map(([label, value]) => (
              <div key={String(label)} className="flex justify-between">
                <dt className="text-muted-foreground">{label}</dt>
                <dd className="tabular-nums font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Income Breakdown */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Monthly Income (Est.)</h2>
          <div className="flex items-end gap-1 h-32">
            {["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"].map((month, i) => {
              const val = monthlyIncome[i];
              const max = Math.max(...monthlyIncome, 1);
              const h = (val / max) * 100;
              return (
                <div key={month} className="flex flex-1 flex-col items-center gap-1">
                  <div className="w-full flex flex-col justify-end" style={{ height: 100 }}>
                    <div className="w-full rounded-t" style={{
                      height: `${h}%`,
                      backgroundColor: val > 0 ? "#10b981" : "#252d3d",
                      minHeight: val > 0 ? 4 : 1,
                    }} />
                  </div>
                  <span className="text-[9px] text-muted-foreground">{month}</span>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex justify-between text-xs">
            <span className="text-muted-foreground">Annual</span>
            <span className="tabular-nums font-medium text-income">{formatCurrency(position.annual_income)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Monthly Avg</span>
            <span className="tabular-nums font-medium">{formatCurrency(position.annual_income / 12)}</span>
          </div>
        </div>

        {/* Score Breakdown */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-muted-foreground">Income Score</h2>
            <div className="flex items-center gap-2">
              {position.score > 0 && <ScorePill score={position.score} />}
              {position.grade && (
                <span className={cn("text-sm font-bold",
                  position.grade.startsWith("A") && "text-income",
                  position.grade.startsWith("B") && "text-blue-400",
                  position.grade.startsWith("C") && "text-yellow-400",
                  position.grade.startsWith("D") && "text-orange-400",
                  position.grade === "F" && "text-loss",
                )}>{position.grade}</span>
              )}
            </div>
          </div>
          {position.score > 0 ? (
            <div className="space-y-2.5">
              {[
                { label: "Valuation/Yield", value: position.valuation_yield_score, max: 40, color: "#3b82f6" },
                { label: "Financial Durability", value: position.financial_durability_score, max: 40, color: "#10b981" },
                { label: "Technical Entry", value: position.technical_entry_score, max: 20, color: "#a78bfa" },
              ].map(({ label, value, max, color }) => (
                <div key={label}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="tabular-nums font-medium">{value.toFixed(1)}<span className="text-muted-foreground">/{max}</span></span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-secondary">
                    <div className="h-1.5 rounded-full transition-all" style={{ width: `${(value / max) * 100}%`, backgroundColor: color }} />
                  </div>
                </div>
              ))}
              {(position.nav_erosion_penalty > 0 || position.signal_penalty > 0) && (
                <div className="border-t border-border pt-2 mt-2 space-y-1">
                  {position.nav_erosion_penalty > 0 && (
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">NAV Erosion Penalty</span>
                      <span className="text-loss tabular-nums">−{position.nav_erosion_penalty.toFixed(1)}</span>
                    </div>
                  )}
                  {position.signal_penalty > 0 && (
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">Signal Penalty</span>
                      <span className="text-loss tabular-nums">−{position.signal_penalty.toFixed(1)}</span>
                    </div>
                  )}
                </div>
              )}
              {position.recommendation && (
                <div className="flex justify-between text-xs pt-1">
                  <span className="text-muted-foreground">Recommendation</span>
                  <span className={cn("font-medium",
                    position.recommendation === "AGGRESSIVE_BUY" && "text-income",
                    position.recommendation === "ACCUMULATE" && "text-blue-400",
                    position.recommendation === "WATCH" && "text-yellow-400",
                  )}>{position.recommendation.replace(/_/g, " ")}</span>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No score data — run scoring batch from Admin Panel</p>
          )}
        </div>
      </div>

      {/* Market Intelligence */}
      {(position.pe_ratio != null || position.beta != null || position.nav_value != null ||
        position.week52_high != null || position.market_cap != null) && (
        <div className="grid grid-cols-2 gap-4">
          {/* Valuation Metrics */}
          <div className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">Valuation Metrics</h2>
            <dl className="space-y-2.5 text-sm">
              {[
                ["Market Cap", position.market_cap != null
                  ? position.market_cap >= 1000
                    ? `$${(position.market_cap / 1000).toFixed(1)}B`
                    : `$${position.market_cap.toFixed(0)}M`
                  : null],
                ["P/E Ratio", position.pe_ratio != null ? position.pe_ratio.toFixed(1) : null],
                ["EPS", position.eps != null ? formatCurrency(position.eps) : null],
                ["Payout Ratio", position.payout_ratio != null
                  ? <span className={cn("tabular-nums",
                      position.payout_ratio > 100 ? "text-loss" : position.payout_ratio > 90 ? "text-warning" : "")}>
                      {position.payout_ratio.toFixed(1)}%
                    </span>
                  : null],
                ["5Y Div Growth", position.dividend_growth_5y != null
                  ? <span className={cn("tabular-nums", position.dividend_growth_5y >= 0 ? "text-income" : "text-loss")}>
                      {position.dividend_growth_5y >= 0 ? "+" : ""}{position.dividend_growth_5y.toFixed(1)}%
                    </span>
                  : null],
                ["Beta", position.beta != null ? position.beta.toFixed(2) : null],
                ["Avg Volume", position.avg_volume != null
                  ? position.avg_volume >= 1_000_000
                    ? `${(position.avg_volume / 1_000_000).toFixed(1)}M`
                    : `${(position.avg_volume / 1_000).toFixed(0)}K`
                  : null],
              ].filter(([, v]) => v != null).map(([label, value]) => (
                <div key={String(label)} className="flex justify-between">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="tabular-nums font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Price Range & NAV */}
          <div className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">Price Range & NAV</h2>
            <dl className="space-y-2.5 text-sm">
              {/* 52-week range with visual bar */}
              {position.week52_low != null && position.week52_high != null && (() => {
                const range = position.week52_high! - position.week52_low!;
                const pct = range > 0 ? ((currentPrice - position.week52_low!) / range) * 100 : 0;
                return (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>52W Range</span>
                      <span className="tabular-nums">
                        {formatCurrency(position.week52_low!)} — {formatCurrency(position.week52_high!)}
                      </span>
                    </div>
                    <div className="relative h-2 rounded-full bg-secondary">
                      <div className="absolute h-2 rounded-full bg-primary/60 transition-all"
                        style={{ width: `${Math.min(Math.max(pct, 2), 100)}%` }} />
                      <div className="absolute h-3 w-0.5 -top-0.5 rounded-full bg-primary"
                        style={{ left: `${Math.min(Math.max(pct, 1), 99)}%` }} />
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                      <span>52W Low</span>
                      <span className="font-medium text-foreground">{pct.toFixed(0)}% of range</span>
                      <span>52W High</span>
                    </div>
                  </div>
                );
              })()}

              {position.nav_value != null && (
                <>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">NAV / Share</dt>
                    <dd className="tabular-nums font-medium">{formatCurrency(position.nav_value!)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Prem / Disc</dt>
                    <dd className={cn("tabular-nums font-medium",
                      position.nav_discount_pct != null && position.nav_discount_pct > 0
                        ? "text-warning" : "text-income")}>
                      {position.nav_discount_pct != null
                        ? `${position.nav_discount_pct >= 0 ? "+" : ""}${position.nav_discount_pct.toFixed(2)}%`
                        : "—"}
                    </dd>
                  </div>
                </>
              )}

              {position.nav_value == null && position.week52_low == null && (
                <p className="text-xs text-muted-foreground">No range data available — refresh market data to populate.</p>
              )}
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}
