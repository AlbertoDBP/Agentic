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
  dividend_frequency?: string;
  price_updated_at: string | null;
  updated_at: string | null;
}

export default function TickerDetailPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = use(params);

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
    fetch(`${API_BASE_URL}/api/positions/${symbol.toUpperCase()}`, { credentials: "include" })
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
    const cost_basis = Number(editForm.cost_basis ?? position.cost_basis);
    const current_value = Number(editForm.current_value ?? position.current_value);
    const annual_income = Number(editForm.annual_income ?? position.annual_income);
    const avg_cost_basis = shares > 0 ? cost_basis / shares : 0;
    const cur_price = shares > 0 ? current_value / shares : 0;
    const yoc = cost_basis > 0 ? (annual_income / cost_basis) * 100 : 0;

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
              <label className="text-[10px] text-muted-foreground">Shares</label>
              <input type="number" step="1" value={editForm.shares ?? ""}
                onChange={(e) => {
                  const shares = Number(e.target.value);
                  const avgCost = (position.shares > 0) ? (editForm.cost_basis ?? position.cost_basis) / (editForm.shares ?? position.shares) : 0;
                  const curP = (position.shares > 0) ? (editForm.current_value ?? position.current_value) / (editForm.shares ?? position.shares) : 0;
                  setEditForm({ ...editForm, shares, cost_basis: shares * avgCost, current_value: shares * curP });
                }}
                className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Cost Basis (total)</label>
              <input type="number" step="0.01" value={editForm.cost_basis ?? ""}
                onChange={(e) => setEditForm({ ...editForm, cost_basis: Number(e.target.value) })}
                className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Current Value</label>
              <input type="number" step="0.01" value={editForm.current_value ?? ""}
                onChange={(e) => setEditForm({ ...editForm, current_value: Number(e.target.value) })}
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
              const cb = Number(editForm.cost_basis ?? 0);
              const cv = Number(editForm.current_value ?? 0);
              const ai = Number(editForm.annual_income ?? 0);
              const avg = sh > 0 ? cb / sh : 0;
              const cp = sh > 0 ? cv / sh : 0;
              const yoc = cb > 0 ? (ai / cb) * 100 : 0;
              return (<>
                <span>Avg Cost: <strong className="text-foreground">{formatCurrency(avg)}</strong></span>
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
              ["Asset Type", position.asset_type],
              ["Sector", position.sector || "—"],
              ["Frequency", position.dividend_frequency || "—"],
              ["Last Updated", position.price_updated_at
                ? new Date(position.price_updated_at).toLocaleDateString()
                : "—"],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between">
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

        {/* Analysis & Ratings */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Analysis</h2>
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Income Score</dt>
              <dd>{position.score > 0 ? <ScorePill score={position.score} /> : <span className="text-muted-foreground">—</span>}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Grade</dt>
              <dd className={cn("font-medium",
                position.grade === "A" && "text-income",
                position.grade === "B" && "text-blue-400",
                position.grade === "C" && "text-yellow-400",
                position.grade === "D" && "text-orange-400",
                position.grade === "F" && "text-loss",
              )}>{position.grade || "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Current Yield</dt>
              <dd className="tabular-nums font-medium">{formatPercent(position.current_yield)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Yield on Cost</dt>
              <dd className="tabular-nums font-medium">{formatPercent(position.yield_on_cost)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Annual Income</dt>
              <dd className="tabular-nums font-medium text-income">{formatCurrency(position.annual_income)}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
