"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
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
  yield_on_cost: number;
  current_yield: number;
  score: number;
  grade: string;
  recommendation: string;
  valuation_yield_score: number;
  financial_durability_score: number;
  technical_entry_score: number;
  nav_erosion_penalty: number;
  signal_penalty: number;
  factor_details: Record<string, { value: number; score: number; weight: number }> | null;
  nav_erosion_details: {
    prob_erosion_gt_5pct?: number;
    median_annual_nav_change_pct?: number;
    risk_classification?: string;
    penalty_applied?: number;
  } | null;
  dividend_frequency?: string;
  price_updated_at: string | null;
  updated_at: string | null;
  // New v2 fields
  dca_stage?: number | null;
  drip_enabled?: boolean | null;
  acquired_date?: string | null;
  total_dividends_received?: number | null;
  annual_fee_drag?: number | null;
  estimated_tax_drag?: number | null;
  net_annual_income?: number | null;
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

function DL({ items }: { items: [string, React.ReactNode, string?][] }) {
  return (
    <dl className="space-y-2 text-sm">
      {items.map(([label, value, cls]) => (
        <div key={label} className="flex justify-between">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className={cn("tabular-nums font-medium", cls)}>{value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

const FACTOR_LABELS: Record<string, string> = {
  dividend_yield:        "Dividend Yield",
  yield_vs_5yr_avg:     "Yield vs 5Y Avg",
  chowder_number:       "Chowder Number",
  payout_ratio:         "Payout Ratio",
  consecutive_yrs:      "Consecutive Growth Yrs",
  div_cagr_3yr:         "Div CAGR 3Y",
  interest_coverage:    "Interest Coverage",
  net_debt_ebitda:      "Net Debt/EBITDA",
  fcf_yield:            "FCF Yield",
  credit_rating:        "Credit Rating",
  rsi:                  "RSI (14d)",
  sma_signal:           "SMA Signal",
  price_vs_support:     "Price vs Support",
};

export default function TickerDetailPage() {
  const params = useParams();
  const rawSymbol = params.symbol as string;
  const symbol = decodeURIComponent(rawSymbol);

  const [position, setPosition] = useState<Position | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const startEdit = () => { if (position) setEditForm({ ...position }); setEditing(true); };
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
          dca_stage: editForm.dca_stage ?? null,
          drip_enabled: editForm.drip_enabled ?? false,
          acquired_date: editForm.acquired_date ?? null,
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

  // Net income computations (fallback if server hasn't computed yet)
  const feeDrag = position.annual_fee_drag ?? 0;
  const taxDrag = position.estimated_tax_drag ?? 0;
  const netIncome = position.net_annual_income ?? (position.annual_income - feeDrag - taxDrag);
  const hasNetData = feeDrag > 0 || taxDrag > 0;

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
          {position.dca_stage != null && (
            <span className="rounded bg-blue-500/15 text-blue-400 px-2 py-0.5 text-[11px] font-medium">
              DCA Stage {position.dca_stage}
            </span>
          )}
          {position.drip_enabled && (
            <span className="rounded bg-emerald-500/15 text-emerald-400 px-2 py-0.5 text-[11px] font-medium">DRIP</span>
          )}
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
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">DCA Stage (1–4)</label>
              <select value={editForm.dca_stage ?? 1}
                onChange={(e) => setEditForm({ ...editForm, dca_stage: Number(e.target.value) })}
                className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm">
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>Stage {n}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Entry Date</label>
              <input type="date" value={editForm.acquired_date?.slice(0, 10) ?? ""}
                onChange={(e) => setEditForm({ ...editForm, acquired_date: e.target.value })}
                className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="space-y-1 flex flex-col justify-end">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={editForm.drip_enabled ?? false}
                  onChange={(e) => setEditForm({ ...editForm, drip_enabled: e.target.checked })}
                  className="rounded border-border" />
                <span className="text-xs text-muted-foreground">DRIP Enabled</span>
              </label>
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

      {/* Main 3-card grid */}
      <div className="grid grid-cols-3 gap-4">
        {/* Position Details */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Position Details</h2>
          <DL items={[
            ["Shares", position.shares.toLocaleString()],
            ["Avg Cost/Share", formatCurrency(avgCostPerShare)],
            ["Current Price", formatCurrency(currentPrice)],
            ["Asset Type", position.asset_type],
            ["Sector", position.sector || null],
            ["Industry", position.industry || null],
            ["Frequency", position.dividend_frequency || null],
            ["Entry Date", position.acquired_date ? new Date(position.acquired_date).toLocaleDateString() : null],
            ["Total Divs Received", position.total_dividends_received != null ? formatCurrency(position.total_dividends_received) : null, "text-income"],
            ["DCA Stage", position.dca_stage != null ? `Stage ${position.dca_stage} / 4` : null],
            ["DRIP", position.drip_enabled != null ? (position.drip_enabled ? "Enabled" : "Disabled") : null],
            ["Ex-Div Date", position.ex_div_date ? new Date(position.ex_div_date).toLocaleDateString() : null],
            ["Pay Date", position.pay_date ? new Date(position.pay_date).toLocaleDateString() : null],
            ["Last Updated", position.price_updated_at ? new Date(position.price_updated_at).toLocaleDateString() : null],
          ]} />
          {position.daily_change_pct != null && (
            <div className="flex justify-between mt-2 text-sm">
              <dt className="text-muted-foreground">Daily Change</dt>
              <dd className={cn("tabular-nums font-medium",
                position.daily_change_pct >= 0 ? "text-income" : "text-loss")}>
                {position.daily_change_pct >= 0 ? "+" : ""}{position.daily_change_pct.toFixed(2)}%
              </dd>
            </div>
          )}
        </div>

        {/* Monthly Income */}
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
            <span className="text-muted-foreground">Annual Gross</span>
            <span className="tabular-nums font-medium text-income">{formatCurrency(position.annual_income)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Monthly Avg</span>
            <span className="tabular-nums font-medium">{formatCurrency(position.annual_income / 12)}</span>
          </div>

          {/* Net income waterfall */}
          {hasNetData && (
            <div className="mt-3 border-t border-border pt-3 space-y-1.5">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Net Efficiency</p>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Gross Income</span>
                <span className="tabular-nums font-medium">{formatCurrency(position.annual_income)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">− Fee Drag</span>
                <span className="tabular-nums font-medium text-loss">−{formatCurrency(feeDrag)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">− Tax Drag</span>
                <span className="tabular-nums font-medium text-loss">−{formatCurrency(taxDrag)}</span>
              </div>
              <div className="flex justify-between text-xs border-t border-border pt-1.5">
                <span className="font-medium">Net Annual Income</span>
                <span className="tabular-nums font-semibold text-income">{formatCurrency(netIncome)}</span>
              </div>
              {position.annual_income > 0 && (
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Retention Rate</span>
                  <span className="tabular-nums text-muted-foreground">{((netIncome / position.annual_income) * 100).toFixed(0)}%</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Score Summary */}
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
                    <span className="tabular-nums font-medium">{(value ?? 0).toFixed(1)}<span className="text-muted-foreground">/{max}</span></span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-secondary">
                    <div className="h-1.5 rounded-full transition-all" style={{ width: `${((value ?? 0) / max) * 100}%`, backgroundColor: color }} />
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
              <a href="#score" className="block text-center text-[10px] text-muted-foreground hover:text-foreground mt-2 underline underline-offset-2">
                Why this score? ↓
              </a>
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
              {position.market_cap != null && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Market Cap</dt>
                  <dd className="tabular-nums font-medium">
                    {position.market_cap >= 1000 ? `$${(position.market_cap / 1000).toFixed(1)}B` : `$${position.market_cap.toFixed(0)}M`}
                  </dd>
                </div>
              )}
              {position.pe_ratio != null && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">P/E Ratio</dt>
                  <dd className="tabular-nums font-medium">{position.pe_ratio.toFixed(1)}</dd>
                </div>
              )}
              {position.eps != null && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">EPS</dt>
                  <dd className="tabular-nums font-medium">{formatCurrency(position.eps)}</dd>
                </div>
              )}
              {position.payout_ratio != null && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Payout Ratio</dt>
                  <dd className={cn("tabular-nums font-medium",
                    position.payout_ratio > 100 ? "text-loss" : position.payout_ratio > 90 ? "text-warning" : "")}>
                    {position.payout_ratio.toFixed(1)}%
                  </dd>
                </div>
              )}
              {position.dividend_growth_5y != null && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">5Y Div Growth</dt>
                  <dd className={cn("tabular-nums font-medium", position.dividend_growth_5y >= 0 ? "text-income" : "text-loss")}>
                    {position.dividend_growth_5y >= 0 ? "+" : ""}{position.dividend_growth_5y.toFixed(1)}%
                  </dd>
                </div>
              )}
              {position.beta != null && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Beta</dt>
                  <dd className="tabular-nums font-medium">{position.beta.toFixed(2)}</dd>
                </div>
              )}
              {position.avg_volume != null && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Avg Volume</dt>
                  <dd className="tabular-nums font-medium">
                    {position.avg_volume >= 1_000_000 ? `${(position.avg_volume / 1_000_000).toFixed(1)}M` : `${(position.avg_volume / 1_000).toFixed(0)}K`}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Price Range & NAV */}
          <div className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">Price Range & NAV</h2>
            <dl className="space-y-2.5 text-sm">
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

      {/* ── Why This Score? ──────────────────────────────────────────────────── */}
      {position.score > 0 && (
        <div id="score" className="rounded-lg border border-border bg-card scroll-mt-6">
          <div className="border-b border-border px-4 py-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold">Why This Score?</h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">Factor-by-factor breakdown of the {position.score.toFixed(1)}/100 score</p>
            </div>
            <div className="flex items-center gap-2">
              <ScorePill score={position.score} />
              {position.grade && (
                <span className={cn("text-base font-bold",
                  position.grade.startsWith("A") && "text-income",
                  position.grade.startsWith("B") && "text-blue-400",
                  position.grade.startsWith("C") && "text-yellow-400",
                  position.grade.startsWith("D") && "text-orange-400",
                  position.grade === "F" && "text-loss",
                )}>{position.grade}</span>
              )}
            </div>
          </div>

          {/* Component bars */}
          <div className="grid grid-cols-3 gap-4 px-4 py-4 border-b border-border">
            {[
              { label: "Valuation & Yield", value: position.valuation_yield_score, max: 40, color: "#3b82f6" },
              { label: "Financial Durability", value: position.financial_durability_score, max: 40, color: "#10b981" },
              { label: "Technical Entry", value: position.technical_entry_score, max: 20, color: "#a78bfa" },
            ].map(({ label, value, max, color }) => (
              <div key={label} className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="tabular-nums font-semibold">{(value ?? 0).toFixed(1)}<span className="text-muted-foreground font-normal">/{max}</span></span>
                </div>
                <div className="h-2 w-full rounded-full bg-secondary">
                  <div className="h-2 rounded-full" style={{ width: `${(value / max) * 100}%`, backgroundColor: color }} />
                </div>
                <p className="text-[10px] text-muted-foreground">{((value / max) * 100).toFixed(0)}% of max</p>
              </div>
            ))}
          </div>

          {/* Factor details table */}
          {position.factor_details && Object.keys(position.factor_details).length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-secondary/30">
                    <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Factor</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Raw Value</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Points</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Max</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Weight</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Score Bar</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(position.factor_details).map(([key, detail]) => {
                    const maxPts = detail.weight;
                    const pct = maxPts > 0 ? Math.min((detail.score / maxPts) * 100, 100) : 0;
                    const label = FACTOR_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                    return (
                      <tr key={key} className="border-b border-border/40 hover:bg-secondary/10">
                        <td className="px-4 py-2.5 text-xs font-medium">{label}</td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-xs text-muted-foreground">
                          {typeof detail.value === "number"
                            ? (Math.abs(detail.value) > 1000 ? formatCurrency(detail.value) : detail.value.toFixed(2))
                            : String(detail.value)}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-xs font-semibold">
                          {detail.score.toFixed(1)}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-xs text-muted-foreground">
                          {maxPts.toFixed(1)}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-xs text-muted-foreground">
                          {(detail.weight * 100).toFixed(0)}%
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="w-24 h-1.5 rounded-full bg-secondary overflow-hidden">
                              <div className="h-full rounded-full transition-all"
                                style={{
                                  width: `${pct}%`,
                                  backgroundColor: pct >= 70 ? "#10b981" : pct >= 40 ? "#f59e0b" : "#f87171",
                                }} />
                            </div>
                            <span className="text-[10px] text-muted-foreground">{pct.toFixed(0)}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Penalties */}
          {(position.nav_erosion_penalty > 0 || position.signal_penalty > 0) && (
            <div className="px-4 py-3 border-t border-border space-y-3">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Penalties Applied</h3>

              {position.nav_erosion_penalty > 0 && (
                <div className="rounded-md border border-red-500/20 bg-red-500/5 p-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-medium text-red-400">NAV Erosion Penalty</p>
                      {position.nav_erosion_details && (
                        <p className="text-[11px] text-muted-foreground mt-1">
                          {position.nav_erosion_details.risk_classification
                            ? `Risk: ${position.nav_erosion_details.risk_classification}`
                            : ""}
                          {position.nav_erosion_details.median_annual_nav_change_pct != null
                            ? ` · Median NAV Δ: ${position.nav_erosion_details.median_annual_nav_change_pct.toFixed(1)}%/yr`
                            : ""}
                          {position.nav_erosion_details.prob_erosion_gt_5pct != null
                            ? ` · P(>5% erosion): ${(position.nav_erosion_details.prob_erosion_gt_5pct * 100).toFixed(0)}%`
                            : ""}
                        </p>
                      )}
                    </div>
                    <span className="text-sm font-semibold text-loss tabular-nums">
                      −{position.nav_erosion_penalty.toFixed(1)} pts
                    </span>
                  </div>
                </div>
              )}

              {position.signal_penalty > 0 && (
                <div className="rounded-md border border-yellow-500/20 bg-yellow-500/5 p-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-medium text-yellow-400">Technical Signal Penalty</p>
                      <p className="text-[11px] text-muted-foreground mt-1">
                        Applied when price is below key moving averages or RSI signals weakness
                      </p>
                    </div>
                    <span className="text-sm font-semibold text-loss tabular-nums">
                      −{position.signal_penalty.toFixed(1)} pts
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Final tally */}
          <div className="px-4 py-3 border-t border-border flex items-center justify-between bg-secondary/20">
            <div className="flex items-center gap-6 text-xs">
              <span className="text-muted-foreground">
                Component total: <strong className="text-foreground">
                  {(position.valuation_yield_score + position.financial_durability_score + position.technical_entry_score).toFixed(1)}
                </strong>
              </span>
              {(position.nav_erosion_penalty + position.signal_penalty) > 0 && (
                <span className="text-muted-foreground">
                  Penalties: <strong className="text-loss">−{(position.nav_erosion_penalty + position.signal_penalty).toFixed(1)}</strong>
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Final Score</span>
              <ScorePill score={position.score} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
