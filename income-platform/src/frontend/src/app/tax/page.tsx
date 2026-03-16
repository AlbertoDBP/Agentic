"use client";

import { useState, useEffect } from "react";
import { Calculator, Leaf, TrendingDown, RefreshCw, DollarSign, Info, ArrowRight, FileText } from "lucide-react";
import { apiPost, apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { TickerBadge } from "@/components/ticker-badge";
import { usePortfolio } from "@/lib/portfolio-context";
import { useRouter } from "next/navigation";

// ── Types ─────────────────────────────────────────────────────────────────────

type Tab = "calculate" | "optimize" | "harvest";
type AccountType = "taxable" | "traditional_ira" | "roth_ira" | "401k";
type FilingStatus = "single" | "married_filing_jointly" | "married_filing_separately" | "head_of_household";

interface TaxCalcInput {
  symbol: string;
  annual_income: string;
  distribution_amount: string;
  account_type: AccountType;
  filing_status: FilingStatus;
  state_code: string;
}

interface TaxCalcResult {
  symbol: string;
  gross_distribution: number;
  federal_tax: number;
  state_tax: number;
  total_tax: number;
  net_distribution: number;
  effective_rate_pct: number;
  treatment_breakdown: {
    qualified_pct: number;
    ordinary_pct: number;
    return_of_capital_pct: number;
    long_term_gain_pct: number;
  };
}

interface HarvestOpportunity {
  symbol: string;
  asset_class: string;
  unrealized_loss: number;
  tax_savings_est: number;
  holding_days: number;
  wash_sale_risk: boolean;
  priority: "HIGH" | "MEDIUM" | "LOW";
}

// ── Mock data ─────────────────────────────────────────────────────────────────

const MOCK_TAX_RESULT: TaxCalcResult = {
  symbol: "GOF",
  gross_distribution: 1200,
  federal_tax: 312,
  state_tax: 96,
  total_tax: 408,
  net_distribution: 792,
  effective_rate_pct: 34.0,
  treatment_breakdown: {
    qualified_pct: 0,
    ordinary_pct: 75,
    return_of_capital_pct: 20,
    long_term_gain_pct: 5,
  },
};

const MOCK_HARVEST: HarvestOpportunity[] = [
  { symbol: "PDI",   asset_class: "CEF",  unrealized_loss: -2840, tax_savings_est: 624,  holding_days: 210, wash_sale_risk: false, priority: "HIGH" },
  { symbol: "GOF",   asset_class: "CEF",  unrealized_loss: -1650, tax_savings_est: 363,  holding_days: 185, wash_sale_risk: true,  priority: "HIGH" },
  { symbol: "NLY",   asset_class: "REIT", unrealized_loss: -980,  tax_savings_est: 216,  holding_days: 90,  wash_sale_risk: false, priority: "MEDIUM" },
  { symbol: "OXLC",  asset_class: "CEF",  unrealized_loss: -620,  tax_savings_est: 136,  holding_days: 310, wash_sale_risk: false, priority: "MEDIUM" },
  { symbol: "TPVG",  asset_class: "BDC",  unrealized_loss: -440,  tax_savings_est: 97,   holding_days: 45,  wash_sale_risk: true,  priority: "LOW" },
];

const MOCK_OPTIMIZE = [
  { action: "MOVE", symbol: "ARCC",  from: "taxable", to: "roth_ira",  reason: "High ordinary income (BDC) — Roth eliminates tax drag", savings_est: 1840 },
  { action: "MOVE", symbol: "PDI",   from: "taxable", to: "traditional_ira", reason: "CEF distributions are 100% ordinary income",        savings_est: 1260 },
  { action: "KEEP", symbol: "O",     from: "taxable", to: "taxable",   reason: "REIT qualified dividends benefit from 20% QBI deduction", savings_est: 0 },
  { action: "MOVE", symbol: "EPD",   from: "taxable", to: "taxable",   reason: "MLP — avoid UBTI in tax-advantaged accounts",             savings_est: 0 },
];

const PRIORITY_STYLES: Record<string, string> = {
  HIGH: "bg-red-400/10 text-red-400",
  MEDIUM: "bg-amber-400/10 text-amber-400",
  LOW: "bg-secondary text-muted-foreground",
};

const ACCOUNT_LABELS: Record<AccountType, string> = {
  taxable: "Taxable",
  traditional_ira: "Traditional IRA",
  roth_ira: "Roth IRA",
  "401k": "401(k)",
};

const FILING_LABELS: Record<FilingStatus, string> = {
  single: "Single",
  married_filing_jointly: "Married Filing Jointly",
  married_filing_separately: "Married Filing Separately",
  head_of_household: "Head of Household",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function matchPortfolioForAccount(portfolios: { id: string; name: string }[], accountType: string): string {
  const lower = accountType.toLowerCase();
  const match = portfolios.find((p) => {
    const name = p.name.toLowerCase();
    if (lower === "roth_ira") return name.includes("roth");
    if (lower === "traditional_ira") return (name.includes("traditional") || name.includes("ira")) && !name.includes("roth");
    if (lower === "401k") return name.includes("401");
    if (lower === "taxable") return name.includes("taxable") || name.includes("brokerage");
    return false;
  });
  return match?.id ?? portfolios[0]?.id ?? "";
}

interface TransferModal {
  symbol: string;
  assetType: string;
  fromAccount: string;
  toAccount: string;
  fromPortfolioId: string;
  toPortfolioId: string;
  reason: string;
  savings: number;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TaxPage() {
  const { portfolios } = usePortfolio();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("calculate");
  const [loading, setLoading] = useState(false);
  const [selectedHarvest, setSelectedHarvest] = useState<Set<string>>(new Set());
  const [harvestDialogOpen, setHarvestDialogOpen] = useState(false);
  const [harvestPortfolioId, setHarvestPortfolioId] = useState(portfolios[0]?.id ?? "p1");
  const [transferModal, setTransferModal] = useState<TransferModal | null>(null);

  // Calculate tab state
  const [calcInput, setCalcInput] = useState<TaxCalcInput>({
    symbol: "",
    annual_income: "150000",
    distribution_amount: "1200",
    account_type: "taxable",
    filing_status: "single",
    state_code: "",
  });
  const [calcResult, setCalcResult] = useState<TaxCalcResult | null>(null);

  // Optimize / Harvest tabs — start with mock, fetch live when available
  const [optimizeResults, setOptimizeResults] = useState(MOCK_OPTIMIZE);
  const [harvestResults, setHarvestResults] = useState(MOCK_HARVEST);
  const [optimizeLoading, setOptimizeLoading] = useState(false);
  const [harvestLoading, setHarvestLoading] = useState(false);

  const updCalc = (k: keyof TaxCalcInput, v: string) =>
    setCalcInput((c) => ({ ...c, [k]: v }));

  const runCalculate = async () => {
    if (!calcInput.symbol) return;
    setLoading(true);
    try {
      const data = await apiPost<TaxCalcResult>("/api/tax/calculate", {
        symbol: calcInput.symbol,
        annual_income: Number(calcInput.annual_income),
        distribution_amount: Number(calcInput.distribution_amount),
        account_type: calcInput.account_type,
        filing_status: calcInput.filing_status,
        state_code: calcInput.state_code || undefined,
      });
      setCalcResult(data);
    } catch (err) {
      console.error("Tax calculate failed:", err);
      // Fall back to mock during development
      setCalcResult({ ...MOCK_TAX_RESULT, symbol: calcInput.symbol.toUpperCase() });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "harvest") {
      setHarvestLoading(true);
      apiPost<{ opportunities: HarvestOpportunity[] }>("/api/tax/harvest", {})
        .then((data) => {
          if (data.opportunities?.length) setHarvestResults(data.opportunities);
        })
        .catch(() => { /* keep mock */ })
        .finally(() => setHarvestLoading(false));
    }
  }, [tab]);

  const createHarvestProposal = () => {
    const symbols = Array.from(selectedHarvest);
    const positions = symbols.map((sym) => {
      const row = harvestResults.find((r) => r.symbol === sym);
      return {
        symbol: sym,
        name: sym,
        asset_type: row?.asset_class ?? "ETF",
        shares: -1,
        entry_price: Math.abs(row?.unrealized_loss ?? 0),
        current_price: 0,
        yield_estimate: 0,
        score: 0,
      };
    });
    const proposal = {
      id: `harvest-${Date.now()}`,
      portfolio_id: harvestPortfolioId,
      proposal_type: "TRIM",
      summary: `Tax-loss harvest: sell ${symbols.join(", ")} to realize losses. Est. tax savings: $${harvestResults.filter(r => symbols.includes(r.symbol)).reduce((s, r) => s + r.tax_savings_est, 0).toLocaleString()}. Re-purchase equivalent positions after 30-day wash-sale window.`,
      status: "PENDING",
      created_at: new Date().toISOString(),
      analyst_source: "Tax Optimizer",
      analyst_sentiment: "Tax-driven",
      risk_flags: harvestResults.filter(r => symbols.includes(r.symbol) && r.wash_sale_risk).map(r => `${r.symbol} wash-sale risk`),
      positions,
    };
    try {
      const existing = JSON.parse(localStorage.getItem("pendingProposals") ?? "[]");
      localStorage.setItem("pendingProposals", JSON.stringify([...existing, proposal]));
    } catch { /* ignore */ }
    setHarvestDialogOpen(false);
    setSelectedHarvest(new Set());
    router.push("/proposals");
  };

  const createTransferProposal = () => {
    if (!transferModal) return;
    const fromPortfolio = portfolios.find((p) => p.id === transferModal.fromPortfolioId);
    const toPortfolio = portfolios.find((p) => p.id === transferModal.toPortfolioId);
    const fromName = fromPortfolio?.name ?? ACCOUNT_LABELS[transferModal.fromAccount as AccountType] ?? transferModal.fromAccount;
    const toName = toPortfolio?.name ?? ACCOUNT_LABELS[transferModal.toAccount as AccountType] ?? transferModal.toAccount;
    const proposal = {
      id: `transfer-${Date.now()}-${transferModal.symbol}`,
      portfolio_id: transferModal.fromPortfolioId,
      to_portfolio_id: transferModal.toPortfolioId,
      proposal_type: "TRANSFER",
      summary: `In-kind transfer: move ${transferModal.symbol} from ${fromName} → ${toName}. ${transferModal.reason}. Est. annual tax savings: $${transferModal.savings.toLocaleString()}.`,
      status: "PENDING",
      created_at: new Date().toISOString(),
      analyst_source: "Tax Optimizer",
      analyst_sentiment: "Tax-driven",
      risk_flags: [`From: ${fromName}`, `To: ${toName}`],
      positions: [{
        symbol: transferModal.symbol,
        name: transferModal.symbol,
        asset_type: transferModal.assetType,
        shares: 1,
        entry_price: 0,
        current_price: 0,
        yield_estimate: 0,
        score: 0,
      }],
    };
    try {
      const existing = JSON.parse(localStorage.getItem("pendingProposals") ?? "[]");
      localStorage.setItem("pendingProposals", JSON.stringify([...existing, proposal]));
    } catch { /* ignore */ }
    setTransferModal(null);
    router.push("/proposals");
  };

  return (
    <div className="space-y-4">
      {/* Harvest proposal dialog */}
      {harvestDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-xl space-y-4">
            <h2 className="text-base font-semibold">Create Tax-Loss Harvest Proposal</h2>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Positions to harvest ({selectedHarvest.size})</p>
              <div className="flex flex-wrap gap-1.5">
                {Array.from(selectedHarvest).map((t) => (
                  <span key={t} className="rounded bg-red-400/10 px-2 py-0.5 text-xs font-mono font-medium text-red-400">{t}</span>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Source Portfolio</label>
              <select
                value={harvestPortfolioId}
                onChange={(e) => setHarvestPortfolioId(e.target.value)}
                className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                {portfolios.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div className="rounded-md border border-emerald-400/30 bg-emerald-400/5 px-3 py-2">
              <p className="text-xs text-emerald-400 font-medium">
                Est. total tax savings: ${harvestResults.filter(r => selectedHarvest.has(r.symbol)).reduce((s, r) => s + r.tax_savings_est, 0).toLocaleString()}
              </p>
              <p className="mt-0.5 text-[10px] text-muted-foreground">A TRIM proposal will be created — re-purchase equivalent positions after the 30-day wash-sale window.</p>
            </div>
            <div className="flex gap-2 pt-1">
              <button onClick={() => setHarvestDialogOpen(false)} className="flex-1 rounded-md border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-secondary transition-colors">Cancel</button>
              <button onClick={createHarvestProposal} className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors">Create Proposal</button>
            </div>
          </div>
        </div>
      )}

      {/* Transfer proposal modal */}
      {transferModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-xl space-y-4">
            <h2 className="text-base font-semibold">Create Transfer Proposal</h2>
            <div className="rounded-md border border-border bg-secondary/50 px-3 py-2 space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-mono font-semibold text-sm">{transferModal.symbol}</span>
                <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">{transferModal.assetType}</span>
              </div>
              <p className="text-xs text-muted-foreground">{transferModal.reason}</p>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  From Portfolio <span className="text-[10px] normal-case">(recommended: {ACCOUNT_LABELS[transferModal.fromAccount as AccountType] ?? transferModal.fromAccount})</span>
                </label>
                <select
                  value={transferModal.fromPortfolioId}
                  onChange={(e) => setTransferModal({ ...transferModal, fromPortfolioId: e.target.value })}
                  className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {portfolios.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center justify-center text-muted-foreground">
                <ArrowRight className="h-4 w-4" />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  To Portfolio <span className="text-[10px] normal-case">(recommended: {ACCOUNT_LABELS[transferModal.toAccount as AccountType] ?? transferModal.toAccount})</span>
                </label>
                <select
                  value={transferModal.toPortfolioId}
                  onChange={(e) => setTransferModal({ ...transferModal, toPortfolioId: e.target.value })}
                  className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {portfolios.filter((p) => p.id !== transferModal.fromPortfolioId).map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
            </div>
            {transferModal.savings > 0 && (
              <div className="rounded-md border border-emerald-400/30 bg-emerald-400/5 px-3 py-2">
                <p className="text-xs text-emerald-400 font-medium">Est. annual tax savings: ${transferModal.savings.toLocaleString()}</p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">This is an in-kind or manual transfer — confirm with your broker.</p>
              </div>
            )}
            <div className="flex gap-2 pt-1">
              <button onClick={() => setTransferModal(null)} className="flex-1 rounded-md border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-secondary transition-colors">Cancel</button>
              <button
                onClick={createTransferProposal}
                disabled={!transferModal.fromPortfolioId || !transferModal.toPortfolioId || transferModal.fromPortfolioId === transferModal.toPortfolioId}
                className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                Create Transfer Proposal
              </button>
            </div>
          </div>
        </div>
      )}

      <div>
        <h1 className="text-xl font-semibold">Tax Optimizer</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Calculate after-tax income, optimize account placement, and identify harvest opportunities
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-border bg-secondary p-1 w-fit">
        {([
          { key: "calculate", label: "Calculate", icon: Calculator },
          { key: "optimize",  label: "Optimize",  icon: TrendingDown },
          { key: "harvest",   label: "Harvest",   icon: Leaf },
        ] as { key: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[]).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-4 py-1.5 text-xs font-medium transition-colors",
              tab === key ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* ── Calculate Tab ── */}
      {tab === "calculate" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Input form */}
          <div className="rounded-lg border border-border bg-card p-5 space-y-4">
            <h2 className="text-sm font-semibold">After-Tax Distribution Calculator</h2>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Ticker Symbol</label>
                <input
                  type="text"
                  placeholder="e.g. GOF, ARCC, PDI"
                  value={calcInput.symbol}
                  onChange={(e) => updCalc("symbol", e.target.value.toUpperCase())}
                  className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">Annual Income ($)</label>
                  <input
                    type="number"
                    value={calcInput.annual_income}
                    onChange={(e) => updCalc("annual_income", e.target.value)}
                    className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">Distribution Amount ($)</label>
                  <input
                    type="number"
                    value={calcInput.distribution_amount}
                    onChange={(e) => updCalc("distribution_amount", e.target.value)}
                    className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">Account Type</label>
                  <select
                    value={calcInput.account_type}
                    onChange={(e) => updCalc("account_type", e.target.value)}
                    className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    {Object.entries(ACCOUNT_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">Filing Status</label>
                  <select
                    value={calcInput.filing_status}
                    onChange={(e) => updCalc("filing_status", e.target.value)}
                    className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    {Object.entries(FILING_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">State Code (optional)</label>
                <input
                  type="text"
                  maxLength={2}
                  placeholder="e.g. CA, NY, TX"
                  value={calcInput.state_code}
                  onChange={(e) => updCalc("state_code", e.target.value.toUpperCase())}
                  className="w-32 rounded-md border border-border bg-secondary px-3 py-2 text-sm uppercase focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
            </div>

            <button
              onClick={runCalculate}
              disabled={!calcInput.symbol || loading}
              className={cn(
                "flex w-full items-center justify-center gap-2 rounded-md py-2 text-sm font-medium transition-colors",
                !calcInput.symbol || loading
                  ? "bg-primary/50 text-primary-foreground/50 cursor-not-allowed"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
            >
              {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Calculator className="h-4 w-4" />}
              {loading ? "Calculating..." : "Calculate After-Tax"}
            </button>
          </div>

          {/* Results */}
          <div className="rounded-lg border border-border bg-card p-5">
            {calcResult ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold">Results for {calcResult.symbol}</h2>
                  <span className={cn(
                    "rounded px-2 py-0.5 text-xs font-bold",
                    calcResult.effective_rate_pct > 30 ? "bg-red-400/10 text-red-400"
                    : calcResult.effective_rate_pct > 20 ? "bg-amber-400/10 text-amber-400"
                    : "bg-emerald-400/10 text-emerald-400"
                  )}>
                    {calcResult.effective_rate_pct.toFixed(1)}% eff. rate
                  </span>
                </div>

                {/* Summary cards */}
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: "Gross Dist.", value: formatCurrency(calcResult.gross_distribution), color: "" },
                    { label: "Total Tax",   value: formatCurrency(calcResult.total_tax),          color: "text-red-400" },
                    { label: "Net Dist.",   value: formatCurrency(calcResult.net_distribution),   color: "text-income" },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="rounded-md border border-border bg-secondary p-3 text-center">
                      <p className="text-[10px] text-muted-foreground mb-1">{label}</p>
                      <p className={cn("text-sm font-semibold tabular-nums", color)}>{value}</p>
                    </div>
                  ))}
                </div>

                {/* Tax breakdown */}
                <div className="space-y-2">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Tax Breakdown</h3>
                  {[
                    { label: "Federal Tax", value: calcResult.federal_tax },
                    { label: "State Tax",   value: calcResult.state_tax },
                  ].map(({ label, value }) => (
                    <div key={label} className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{label}</span>
                      <span className="tabular-nums text-red-400">{formatCurrency(value)}</span>
                    </div>
                  ))}
                </div>

                {/* Treatment breakdown */}
                <div className="space-y-2">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Distribution Treatment</h3>
                  {[
                    { label: "Ordinary Income",     pct: calcResult.treatment_breakdown.ordinary_pct,          color: "bg-red-400" },
                    { label: "Qualified Dividends", pct: calcResult.treatment_breakdown.qualified_pct,          color: "bg-emerald-400" },
                    { label: "Return of Capital",   pct: calcResult.treatment_breakdown.return_of_capital_pct,  color: "bg-blue-400" },
                    { label: "LT Capital Gain",     pct: calcResult.treatment_breakdown.long_term_gain_pct,     color: "bg-amber-400" },
                  ].map(({ label, pct, color }) => (
                    <div key={label} className="flex items-center gap-2 text-xs">
                      <div className={cn("h-2 rounded", color)} style={{ width: `${pct}%`, minWidth: pct > 0 ? "2px" : "0" }} />
                      <span className="text-muted-foreground w-36 shrink-0">{label}</span>
                      <span className="tabular-nums font-medium">{pct}%</span>
                    </div>
                  ))}
                </div>

                {calcInput.account_type !== "taxable" && (
                  <div className="flex items-start gap-2 rounded-md border border-emerald-400/30 bg-emerald-400/5 px-3 py-2">
                    <Info className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-emerald-400">
                      {calcInput.account_type === "roth_ira"
                        ? "Roth IRA: distributions grow and withdraw tax-free. No current tax drag."
                        : "Tax-advantaged account: distributions are tax-deferred until withdrawal."}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-2">
                <DollarSign className="h-8 w-8 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">Enter a ticker and click Calculate</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Optimize Tab ── */}
      {tab === "optimize" && (
        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <p className="text-xs text-muted-foreground">
              Account placement recommendations to minimize tax drag across your portfolios
            </p>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/50">
                <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Symbol</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Action</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">From</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">To</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Reason</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Est. Annual Savings</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Action</th>
              </tr>
            </thead>
            <tbody>
              {optimizeResults.map((row) => (
                <tr key={row.symbol} className="border-b border-border/50 hover:bg-secondary/20">
                  <td className="px-4 py-3">
                    <TickerBadge symbol={row.symbol} assetType="" />
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-bold",
                      row.action === "MOVE" ? "bg-blue-400/10 text-blue-400" : "bg-secondary text-muted-foreground"
                    )}>
                      {row.action}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-xs text-muted-foreground">{ACCOUNT_LABELS[row.from as AccountType] || row.from}</p>
                    {(() => {
                      const pid = matchPortfolioForAccount(portfolios, row.from);
                      const name = portfolios.find((p) => p.id === pid)?.name;
                      return name ? <p className="text-[10px] text-muted-foreground/60 mt-0.5">{name}</p> : null;
                    })()}
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-xs">{ACCOUNT_LABELS[row.to as AccountType] || row.to}</p>
                    {(() => {
                      const pid = matchPortfolioForAccount(portfolios, row.to);
                      const name = portfolios.find((p) => p.id === pid)?.name;
                      return name ? <p className="text-[10px] text-muted-foreground/60 mt-0.5">{name}</p> : null;
                    })()}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground max-w-xs">{row.reason}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-xs font-medium text-income">
                    {row.savings_est > 0 ? formatCurrency(row.savings_est) : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {row.action === "MOVE" && (
                      <button
                        onClick={() => setTransferModal({
                          symbol: row.symbol,
                          assetType: "",
                          fromAccount: row.from,
                          toAccount: row.to,
                          fromPortfolioId: matchPortfolioForAccount(portfolios, row.from),
                          toPortfolioId: matchPortfolioForAccount(portfolios, row.to),
                          reason: row.reason,
                          savings: row.savings_est,
                        })}
                        className="rounded-md border border-border px-2 py-1 text-[10px] font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                      >
                        Propose Transfer
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Harvest Tab ── */}
      {tab === "harvest" && (
        <div className="space-y-3">
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-start gap-2">
              <Leaf className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
              <p className="text-xs text-muted-foreground">
                Tax-loss harvesting opportunities identified in your taxable account.
                Wash-sale risk flagged — wait 30 days before re-purchasing the same security.
              </p>
            </div>
          </div>

          {selectedHarvest.size > 0 && (
            <div className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 flex items-center justify-between">
              <span className="text-sm font-medium">{selectedHarvest.size} position{selectedHarvest.size > 1 ? "s" : ""} selected · Est. savings: ${harvestResults.filter(r => selectedHarvest.has(r.symbol)).reduce((s, r) => s + r.tax_savings_est, 0).toLocaleString()}</span>
              <div className="flex gap-2">
                <button onClick={() => setSelectedHarvest(new Set())} className="text-xs text-muted-foreground hover:text-foreground">Clear</button>
                <button onClick={() => setHarvestDialogOpen(true)} className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors">Create Harvest Proposal →</button>
              </div>
            </div>
          )}

          <div className={cn("rounded-lg border border-border bg-card", harvestLoading && "opacity-50")}>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-secondary/50">
                  <th className="px-4 py-2 w-8">
                    <input type="checkbox" className="rounded"
                      checked={harvestResults.length > 0 && harvestResults.every(r => selectedHarvest.has(r.symbol))}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedHarvest(new Set(harvestResults.map(r => r.symbol)));
                        else setSelectedHarvest(new Set());
                      }}
                    />
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Symbol</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Class</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Unrealized Loss</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Est. Tax Savings</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Holding Days</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-muted-foreground">Wash Sale Risk</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-muted-foreground">Priority</th>
                </tr>
              </thead>
              <tbody>
                {harvestResults.map((row) => (
                  <tr key={row.symbol} className="border-b border-border/50 hover:bg-secondary/20">
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" className="rounded"
                        checked={selectedHarvest.has(row.symbol)}
                        onChange={(e) => {
                          const next = new Set(selectedHarvest);
                          if (e.target.checked) next.add(row.symbol);
                          else next.delete(row.symbol);
                          setSelectedHarvest(next);
                        }}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <TickerBadge symbol={row.symbol} assetType={row.asset_class} />
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{row.asset_class}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-red-400 font-medium">
                      {formatCurrency(row.unrealized_loss)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-income font-medium">
                      {formatCurrency(row.tax_savings_est)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-xs text-muted-foreground">
                      {row.holding_days}d
                    </td>
                    <td className="px-4 py-3 text-center">
                      {row.wash_sale_risk ? (
                        <span className="rounded bg-red-400/10 px-1.5 py-0.5 text-[10px] font-medium text-red-400">⚠ Risk</span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-bold", PRIORITY_STYLES[row.priority])}>
                        {row.priority}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-secondary/30">
                  <td colSpan={3} className="px-4 py-2 text-xs font-medium text-muted-foreground text-right">Total</td>
                  <td className="px-4 py-2 text-right tabular-nums text-sm font-semibold text-red-400">
                    {formatCurrency(harvestResults.reduce((s, r) => s + r.unrealized_loss, 0))}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-sm font-semibold text-income">
                    {formatCurrency(harvestResults.reduce((s, r) => s + r.tax_savings_est, 0))}
                  </td>
                  <td colSpan={4}></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
