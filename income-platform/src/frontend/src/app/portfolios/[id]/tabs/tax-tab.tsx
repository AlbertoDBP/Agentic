// src/frontend/src/app/portfolios/[id]/tabs/tax-tab.tsx
"use client";
import { useState, useEffect, useCallback } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { ColHeader } from "@/components/help-tooltip";
import { cn, scoreTextColor } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import type { PortfolioTaxAnalysis, TaxHolding } from "@/lib/types";

// ── Helper components ─────────────────────────────────────────────────────────

function DetailRow({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/80 mb-0.5">{label}</div>
      <div className={cn("text-sm font-semibold text-foreground", className)}>{value}</div>
    </div>
  );
}

function SectionTitle({ label }: { label: string }) {
  return (
    <div className="text-[10px] font-bold uppercase tracking-wider text-blue-400 mb-2 pb-1 border-b border-border/50">
      {label}
    </div>
  );
}

function AccountBadge({ account, mismatch }: { account: string; mismatch: boolean }) {
  const colors: Record<string, string> = {
    TAXABLE:  mismatch ? "bg-red-950/60 text-red-400 border-red-900/50" : "bg-slate-800 text-slate-400 border-slate-700",
    ROTH_IRA: "bg-green-950/60 text-green-400 border-green-900/50",
    TRAD_IRA: "bg-blue-950/60 text-blue-400 border-blue-900/50",
    HSA:      "bg-purple-950/60 text-purple-400 border-purple-900/50",
    "401K":   "bg-amber-950/60 text-amber-400 border-amber-900/50",
  };
  return (
    <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded border", colors[account] ?? "text-muted-foreground")}>
      {account.replace("_", " ")}
    </span>
  );
}

const TAX_PROFILE_HELP = {
  annual_income: "Your total gross annual income. Determines your federal bracket and NIIT eligibility (applies above $200k single / $250k joint).",
  filing_status: "Your IRS filing status. Determines which tax brackets and standard deduction apply.",
  state_code: "Your state of residence. Nine states have no income tax (AK, FL, NV, SD, TN, TX, WA, WY, NH on dividends).",
};

// ── Main component ────────────────────────────────────────────────────────────

interface TaxTabProps {
  portfolioId: string;
  refreshKey?: number;
  onTaxDataLoaded?: (data: PortfolioTaxAnalysis) => void;
}

export function TaxTab({ portfolioId, refreshKey = 0, onTaxDataLoaded }: TaxTabProps) {
  const [taxData, setTaxData] = useState<PortfolioTaxAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TaxHolding | null>(null);
  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [showSettings, setShowSettings] = useState(false);
  const [settingsForm, setSettingsForm] = useState({ annual_income: "", filing_status: "SINGLE", state_code: "" });
  const [savingSettings, setSavingSettings] = useState(false);

  const load = useCallback(() => {
    if (!portfolioId) return;
    setLoading(true);
    setError(null);
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    fetch(`${API_BASE_URL}/api/portfolios/${portfolioId}/tax`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data: PortfolioTaxAnalysis) => {
        setTaxData(data);
        setSettingsForm({
          annual_income: String(data.tax_profile.annual_income),
          filing_status: data.tax_profile.filing_status,
          state_code: data.tax_profile.state_code ?? "",
        });
        onTaxDataLoaded?.(data);
        setLoading(false);
      })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [portfolioId, refreshKey, onTaxDataLoaded]);

  useEffect(() => { load(); }, [load]);

  const saveSettings = async () => {
    setSavingSettings(true);
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    await fetch(`${API_BASE_URL}/api/user/preferences`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      credentials: "include",
      body: JSON.stringify({
        annual_income: Number(settingsForm.annual_income),
        filing_status: settingsForm.filing_status,
        state_code: settingsForm.state_code || null,
      }),
    });
    setSavingSettings(false);
    setShowSettings(false);
    load();
  };

  const columns: ColumnDef<TaxHolding>[] = [
    {
      id: "select",
      header: "",
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selectedTickers.has(row.original.symbol)}
          onChange={(e) => {
            setSelectedTickers((prev) => {
              const next = new Set(prev);
              e.target.checked ? next.add(row.original.symbol) : next.delete(row.original.symbol);
              return next;
            });
          }}
          className="w-3.5 h-3.5"
        />
      ),
      size: 28,
    },
    {
      accessorKey: "symbol",
      header: () => <ColHeader label="Ticker" help="Ticker symbol" />,
      meta: { label: "Ticker" },
      cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_class} />,
    },
    {
      accessorKey: "asset_class",
      header: () => <ColHeader label="Class" help="Asset classification" />,
      meta: { label: "Class" },
    },
    {
      accessorKey: "current_account",
      header: () => <ColHeader label="Account" help="Current account type for this holding" />,
      meta: { label: "Account" },
      cell: ({ row }) => (
        <AccountBadge account={row.original.current_account} mismatch={row.original.placement_mismatch} />
      ),
    },
    {
      accessorKey: "treatment",
      header: () => <ColHeader label="Treatment" help="Primary tax treatment of distributions" />,
      meta: { label: "Tax Treatment" },
      cell: ({ getValue }) => (
        <span className={cn("text-xs", (getValue() as string) === "ORDINARY_INCOME" ? "text-red-400" : "text-green-400")}>
          {(getValue() as string).replace(/_/g, " ")}
        </span>
      ),
    },
    {
      accessorKey: "gross_yield",
      header: () => <ColHeader label="Gross Yield" help="Annual income / current market value, before tax and fees" />,
      meta: { label: "Gross Yield" },
      cell: ({ getValue }) => <span className="tabular-nums">{((getValue() as number) * 100).toFixed(2)}%</span>,
    },
    {
      accessorKey: "effective_tax_rate",
      header: () => <ColHeader label="Tax Rate" help="Combined effective rate: federal + state + NIIT" />,
      meta: { label: "Effective Tax Rate" },
      cell: ({ getValue }) => {
        const v = (getValue() as number) * 100;
        return <span className={cn("tabular-nums", v > 40 ? "text-red-400" : v > 20 ? "text-amber-400" : "text-green-400")}>{v.toFixed(1)}%</span>;
      },
    },
    {
      accessorKey: "after_tax_yield",
      header: () => <ColHeader label="After-Tax" help="Gross yield minus tax drag" />,
      meta: { label: "After-Tax Yield" },
      cell: ({ getValue }) => <span className="tabular-nums">{((getValue() as number) * 100).toFixed(2)}%</span>,
    },
    {
      accessorKey: "nay",
      header: () => <ColHeader label="NAA Yield" help="Net After-All Yield: gross yield minus tax drag minus expense ratio. The yield you actually keep." />,
      meta: { label: "NAA Yield" },
      cell: ({ getValue }) => {
        const v = (getValue() as number) * 100;
        return <span className={cn("font-bold tabular-nums", scoreTextColor(v / 0.1))}>{v.toFixed(2)}%</span>;
      },
    },
    {
      accessorKey: "recommended_account",
      header: () => <ColHeader label="Rec." help="Recommended account for tax optimization" />,
      meta: { label: "Placement Rec." },
      cell: ({ row }) => {
        const h = row.original;
        if (!h.placement_mismatch) return <span className="text-green-400 text-xs">✓ Optimal</span>;
        return <span className="text-amber-400 text-xs font-medium">→ {h.recommended_account.replace("_", " ")} ⚠</span>;
      },
    },
    {
      accessorKey: "estimated_annual_tax_savings",
      header: () => <ColHeader label="Savings/yr" help="Estimated annual tax savings if moved to recommended account" />,
      meta: { label: "Est. Savings/yr" },
      cell: ({ getValue }) => {
        const v = getValue() as number;
        return v > 0 ? <span className="text-green-400 tabular-nums text-xs">${v.toFixed(0)}</span> : <span className="text-muted-foreground">—</span>;
      },
    },
    // Hidden by default
    {
      accessorKey: "expense_ratio",
      header: "Expense Ratio",
      meta: { defaultHidden: true, label: "Expense Ratio" },
      cell: ({ getValue }) => {
        const v = getValue() as number | null;
        return v != null ? `${(v * 100).toFixed(2)}%` : "—";
      },
    },
    {
      accessorKey: "expense_drag_amount",
      header: "Expense Drag $",
      meta: { defaultHidden: true, label: "Annual Expense Drag" },
      cell: ({ getValue }) => {
        const v = getValue() as number;
        return v > 0 ? `$${v.toFixed(0)}` : "—";
      },
    },
  ];

  if (loading) return <div className="text-muted-foreground text-sm p-4">Loading tax analysis...</div>;
  if (error) return <div className="text-red-400 text-sm p-4 bg-red-950/30 border border-red-900/50 rounded">{error}</div>;
  if (!taxData) return null;

  const profile = taxData.tax_profile;
  const fmt = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

  return (
    <div className="flex flex-col gap-3">

      {/* BANNER */}
      <div className="flex items-center gap-3 flex-wrap px-1">
        <div className="flex gap-3 flex-1">
          <div className="bg-card border border-border rounded-lg px-4 py-2.5 min-w-[120px]">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Est. Tax Drag / yr</div>
            <div className="text-lg font-bold text-red-400">{fmt(taxData.current_annual_tax_burden)}</div>
          </div>
          <div className="bg-card border border-border rounded-lg px-4 py-2.5 min-w-[120px]">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Suboptimal Holdings</div>
            <div className="text-lg font-bold text-amber-400">
              {taxData.suboptimal_count} <span className="text-sm text-muted-foreground font-normal">of {taxData.holdings.length}</span>
            </div>
          </div>
          <div className="bg-card border border-border rounded-lg px-4 py-2.5 min-w-[120px]">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Potential Savings / yr</div>
            <div className="text-lg font-bold text-green-400">{fmt(taxData.estimated_annual_savings)}</div>
          </div>
          <div className="bg-card border border-border rounded-lg px-4 py-2.5 min-w-[120px]">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Portfolio NAA Yield</div>
            <div className="text-lg font-bold text-blue-400">{(taxData.portfolio_nay * 100).toFixed(2)}%</div>
          </div>
        </div>

        {/* Tax profile pill */}
        <div className="flex items-center gap-2 bg-card border border-border rounded-lg px-3 py-2 text-xs text-muted-foreground">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground/60">Tax Profile</span>
          <span className="bg-muted px-2 py-0.5 rounded" title={TAX_PROFILE_HELP.annual_income}>
            ${(profile.annual_income / 1000).toFixed(0)}k ⓘ
          </span>
          <span className="text-muted-foreground/40">·</span>
          <span className="bg-muted px-2 py-0.5 rounded" title={TAX_PROFILE_HELP.filing_status}>
            {profile.filing_status.replace("_", " ")} ⓘ
          </span>
          {profile.state_code && (
            <>
              <span className="text-muted-foreground/40">·</span>
              <span className="bg-muted px-2 py-0.5 rounded" title={TAX_PROFILE_HELP.state_code}>
                {profile.state_code} ⓘ
              </span>
            </>
          )}
          <button
            onClick={() => setShowSettings(true)}
            className="text-blue-400 hover:text-blue-300 border border-blue-900/50 px-2 py-0.5 rounded text-[10px]"
          >
            Edit ✎
          </button>
        </div>
      </div>

      {/* ACTION BAR */}
      {selectedTickers.size > 0 && (
        <div className="flex items-center gap-3 px-1 py-2 bg-blue-950/30 border border-blue-900/40 rounded-lg">
          <span className="text-blue-400 text-xs font-medium">{selectedTickers.size} selected</span>
          <button
            className="bg-blue-700 hover:bg-blue-600 text-white text-xs font-semibold px-3 py-1.5 rounded"
            onClick={() => {
              // Opens proposal modal — scanner ProposalModal handles this
              // Emit event or use router to navigate with selected tickers
              // Implementation: store selectedTickers in URL params or session
              // TODO(Task 12): wire ProposalModal — pre-populate selectedTickers
              alert(`Open ProposalModal for: ${[...selectedTickers].join(", ")} — see Task 12`);
            }}
          >
            ⚡ Generate Rebalance Proposal
          </button>
          <span className="text-muted-foreground text-xs">Proposes sell + buy to move to recommended accounts</span>
          <button
            onClick={() => setSelectedTickers(new Set())}
            className="ml-auto text-muted-foreground text-xs hover:text-foreground"
          >
            Clear
          </button>
        </div>
      )}

      {/* TABLE + DETAIL PANEL */}
      <div className="flex gap-3">
        <div className="flex-1 min-w-0">
          <DataTable
            columns={columns}
            data={taxData.holdings}
            storageKey={`tax-tab-${portfolioId}`}
            onRowClick={(row) => setSelected((s) => s?.symbol === row.symbol ? null : row)}
          />
        </div>

        {/* DETAIL PANEL */}
        {selected && (
          <div className="w-80 shrink-0 bg-card border border-border rounded-lg p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-260px)]">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-bold text-base">{selected.symbol}</span>
                <div className="text-xs text-muted-foreground mt-0.5">{selected.asset_class}</div>
              </div>
              <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground text-sm px-1">✕</button>
            </div>

            {/* Tax waterfall */}
            <section>
              <SectionTitle label="Tax Breakdown" />
              <div className="space-y-1.5">
                <DetailRow label="Gross Yield" value={`${(selected.gross_yield * 100).toFixed(2)}%`} />
                <DetailRow label="Treatment" value={selected.treatment.replace(/_/g, " ")} />
                <div className="border-t border-border/40 pt-1.5 space-y-1">
                  <DetailRow label="Federal Tax" value={`−${((selected.effective_tax_rate - 0) * 100 * 0.7).toFixed(1)}%`} className="text-red-400" />
                  <DetailRow label="State Tax" value={`−${((selected.effective_tax_rate) * 100 * 0.25).toFixed(1)}%`} className="text-red-400" />
                  {selected.effective_tax_rate > 0.50 && (
                    <DetailRow label="NIIT (3.8%)" value="−3.8%" className="text-red-400" />
                  )}
                  <DetailRow label="After-Tax Yield" value={`${(selected.after_tax_yield * 100).toFixed(2)}%`} />
                </div>
                {selected.expense_ratio != null && selected.expense_ratio > 0 && (
                  <div className="border-t border-border/40 pt-1.5">
                    <DetailRow
                      label={`Expense Ratio (${(selected.expense_ratio * 100).toFixed(2)}%)`}
                      value={`−$${selected.expense_drag_amount.toFixed(0)}/yr`}
                      className="text-amber-400"
                    />
                  </div>
                )}
                <div className="border-t border-border/40 pt-1.5">
                  <DetailRow label="NAA Yield" value={`${(selected.nay * 100).toFixed(2)}%`} className="text-green-400 text-base" />
                  <DetailRow label="Net Annual Income" value={`$${selected.net_annual_income.toFixed(0)}`} />
                </div>
              </div>
            </section>

            {/* Placement recommendation */}
            {selected.placement_mismatch && (
              <section>
                <SectionTitle label="Account Recommendation" />
                <div className="bg-amber-950/30 border border-amber-900/40 rounded p-2.5 space-y-2">
                  <div className="text-amber-400 font-semibold text-sm">→ {selected.recommended_account.replace("_", " ")}</div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{selected.reason}</p>
                  <div className="flex justify-between text-xs pt-1 border-t border-border/30">
                    <span className="text-muted-foreground">Est. savings if moved</span>
                    <span className="text-green-400 font-semibold">${selected.estimated_annual_tax_savings.toFixed(0)}/yr</span>
                  </div>
                </div>
                <button
                  className="w-full mt-3 bg-blue-700 hover:bg-blue-600 text-white text-xs font-semibold py-2 rounded"
                  onClick={() => alert(`TODO(Task 12): ProposalModal for ${selected.symbol}`)}
                >
                  ⚡ Propose Account Transfer
                </button>
                <p className="text-center text-[9px] text-muted-foreground/60 mt-1">
                  Generates sell + buy proposal in Proposals tab
                </p>
              </section>
            )}
          </div>
        )}
      </div>

      {/* SETTINGS MODAL */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-sm space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-semibold">Tax Profile Settings</h3>
              <button onClick={() => setShowSettings(false)} className="text-muted-foreground hover:text-foreground">✕</button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  Annual Income
                  <span className="cursor-help text-muted-foreground/50" title={TAX_PROFILE_HELP.annual_income}>ⓘ</span>
                </label>
                <input
                  type="number"
                  value={settingsForm.annual_income}
                  onChange={(e) => setSettingsForm((s) => ({ ...s, annual_income: e.target.value }))}
                  className="mt-1 w-full bg-muted border border-border rounded px-3 py-1.5 text-sm"
                  placeholder="150000"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  Filing Status
                  <span className="cursor-help text-muted-foreground/50" title={TAX_PROFILE_HELP.filing_status}>ⓘ</span>
                </label>
                <select
                  value={settingsForm.filing_status}
                  onChange={(e) => setSettingsForm((s) => ({ ...s, filing_status: e.target.value }))}
                  className="mt-1 w-full bg-muted border border-border rounded px-3 py-1.5 text-sm"
                >
                  <option value="SINGLE">Single</option>
                  <option value="MARRIED_JOINT">Married Filing Jointly</option>
                  <option value="MARRIED_SEPARATE">Married Filing Separately</option>
                  <option value="HEAD_OF_HOUSEHOLD">Head of Household</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  State
                  <span className="cursor-help text-muted-foreground/50" title={TAX_PROFILE_HELP.state_code}>ⓘ</span>
                </label>
                <input
                  type="text"
                  value={settingsForm.state_code}
                  onChange={(e) => setSettingsForm((s) => ({ ...s, state_code: e.target.value.toUpperCase().slice(0, 2) }))}
                  className="mt-1 w-full bg-muted border border-border rounded px-3 py-1.5 text-sm uppercase"
                  placeholder="CA"
                  maxLength={2}
                />
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button onClick={() => setShowSettings(false)} className="flex-1 bg-muted hover:bg-muted/80 text-sm py-2 rounded border border-border">
                Cancel
              </button>
              <button
                onClick={saveSettings}
                disabled={savingSettings}
                className="flex-1 bg-blue-700 hover:bg-blue-600 text-white text-sm py-2 rounded font-semibold"
              >
                {savingSettings ? "Saving…" : "Save & Recalculate"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
