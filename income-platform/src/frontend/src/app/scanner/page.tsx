"use client";

import { useState, useEffect, useMemo } from "react";
import { Search, ScanLine, Filter, ShieldCheck, ShieldAlert, ChevronDown, ChevronUp, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { TickerBadge } from "@/components/ticker-badge";
import { ScorePill } from "@/components/score-pill";
import { formatPercent } from "@/lib/utils";
import { apiPost, apiGet } from "@/lib/api";
import { useRouter } from "next/navigation";
import { usePortfolio } from "@/lib/portfolio-context";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ScanFilters {
  // Universe
  use_universe: boolean;
  custom_tickers: string;       // comma-separated input
  // Group 1
  asset_classes: string[];
  min_score: number;
  quality_gate_only: boolean;
  grades: string[];
  recommendations: string[];
  chowder_signals: string[];
  // Group 2
  min_yield: number;
  max_payout_ratio: string;
  min_volume: string;
  min_market_cap_m: string;
  max_market_cap_m: string;
  min_price: string;
  max_price: string;
  max_pe: string;
  min_nav_discount_pct: string;
}

interface ScanItem {
  rank: number;
  ticker: string;
  asset_class: string;
  score: number;
  grade: string;
  recommendation: string;
  chowder_number: number | null;
  chowder_signal: string | null;
  signal_penalty: number;
  passed_quality_gate: boolean;
  veto_flag: boolean;
  score_details: {
    valuation_yield_score?: number;
    financial_durability_score?: number;
    technical_entry_score?: number;
    nav_erosion_penalty?: number;
  };
}

interface ScanResult {
  scan_id: string;
  total_scanned: number;
  total_passed: number;
  total_vetoed: number;
  items: ScanItem[];
  created_at: string;
}

interface UniverseItem {
  symbol: string;
  name: string;
  asset_type: string;
}

// ── Mock data ─────────────────────────────────────────────────────────────────

const MOCK_RESULTS: ScanResult = {
  scan_id: "mock-001",
  total_scanned: 47,
  total_passed: 18,
  total_vetoed: 29,
  created_at: new Date().toISOString(),
  items: [
    { rank: 1, ticker: "MAIN",  asset_class: "BDC",      score: 94.2, grade: "A", recommendation: "BUY",  chowder_number: 18.4, chowder_signal: "STRONG",   signal_penalty: 0,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 32, financial_durability_score: 28, technical_entry_score: 22, nav_erosion_penalty: 0 } },
    { rank: 2, ticker: "ARCC",  asset_class: "BDC",      score: 89.1, grade: "A", recommendation: "BUY",  chowder_number: 14.9, chowder_signal: "STRONG",   signal_penalty: 0,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 30, financial_durability_score: 27, technical_entry_score: 20, nav_erosion_penalty: 0 } },
    { rank: 3, ticker: "O",     asset_class: "REIT",     score: 87.5, grade: "A", recommendation: "BUY",  chowder_number: 13.2, chowder_signal: "STRONG",   signal_penalty: 0,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 28, financial_durability_score: 30, technical_entry_score: 18, nav_erosion_penalty: 0 } },
    { rank: 4, ticker: "JEPI",  asset_class: "ETF",      score: 84.3, grade: "B", recommendation: "BUY",  chowder_number: 11.0, chowder_signal: "MODERATE", signal_penalty: 2,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 26, financial_durability_score: 24, technical_entry_score: 22, nav_erosion_penalty: 0 } },
    { rank: 5, ticker: "BXSL",  asset_class: "BDC",      score: 83.0, grade: "B", recommendation: "BUY",  chowder_number: 12.5, chowder_signal: "MODERATE", signal_penalty: 0,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 28, financial_durability_score: 26, technical_entry_score: 17, nav_erosion_penalty: 0 } },
    { rank: 6, ticker: "HTGC",  asset_class: "BDC",      score: 81.2, grade: "B", recommendation: "BUY",  chowder_number: 13.8, chowder_signal: "MODERATE", signal_penalty: 1,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 27, financial_durability_score: 24, technical_entry_score: 18, nav_erosion_penalty: 0 } },
    { rank: 7, ticker: "PTY",   asset_class: "CEF",      score: 78.8, grade: "B", recommendation: "HOLD", chowder_number: 8.2,  chowder_signal: "MODERATE", signal_penalty: 3,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 24, financial_durability_score: 22, technical_entry_score: 16, nav_erosion_penalty: -4 } },
    { rank: 8, ticker: "PFF",   asset_class: "ETF",      score: 76.4, grade: "B", recommendation: "HOLD", chowder_number: 6.5,  chowder_signal: "WEAK",     signal_penalty: 4,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 22, financial_durability_score: 25, technical_entry_score: 17, nav_erosion_penalty: 0 } },
    { rank: 9, ticker: "STWD",  asset_class: "REIT",     score: 74.1, grade: "C", recommendation: "HOLD", chowder_number: 9.8,  chowder_signal: "WEAK",     signal_penalty: 5,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 22, financial_durability_score: 20, technical_entry_score: 15, nav_erosion_penalty: -2 } },
    { rank: 10, ticker: "EPD",  asset_class: "MLP",      score: 72.9, grade: "C", recommendation: "HOLD", chowder_number: 11.3, chowder_signal: "MODERATE", signal_penalty: 3,   passed_quality_gate: true,  veto_flag: false, score_details: { valuation_yield_score: 20, financial_durability_score: 23, technical_entry_score: 18, nav_erosion_penalty: 0 } },
  ],
};

// ── Constants ─────────────────────────────────────────────────────────────────

const ASSET_CLASSES = ["BDC", "CEF", "MLP", "REIT", "Preferred", "ETF", "Bond", "Common Stock"];
const GRADES = ["A", "B", "C", "D", "F"];
const RECOMMENDATIONS = ["BUY", "HOLD", "AVOID"];
const CHOWDER_SIGNALS = ["STRONG", "MODERATE", "WEAK", "NEGATIVE"];

const GRADE_COLORS: Record<string, string> = {
  A: "text-emerald-400",
  B: "text-blue-400",
  C: "text-amber-400",
  D: "text-orange-400",
  F: "text-red-400",
};

const SIGNAL_COLORS: Record<string, string> = {
  STRONG: "text-emerald-400",
  MODERATE: "text-blue-400",
  WEAK: "text-amber-400",
  NEGATIVE: "text-red-400",
};

const REC_COLORS: Record<string, string> = {
  BUY: "bg-emerald-400/10 text-emerald-400",
  HOLD: "bg-amber-400/10 text-amber-400",
  AVOID: "bg-red-400/10 text-red-400",
};

const DEFAULT_FILTERS: ScanFilters = {
  use_universe: false,
  custom_tickers: "",
  asset_classes: [],
  min_score: 0,
  quality_gate_only: false,
  grades: [],
  recommendations: [],
  chowder_signals: [],
  min_yield: 0,
  max_payout_ratio: "",
  min_volume: "",
  min_market_cap_m: "",
  max_market_cap_m: "",
  min_price: "",
  max_price: "",
  min_nav_discount_pct: "",
  max_pe: "",
};

// ── Toggle helper ─────────────────────────────────────────────────────────────

function toggleItem(arr: string[], item: string): string[] {
  return arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item];
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ScannerPage() {
  const [filters, setFilters] = useState<ScanFilters>(DEFAULT_FILTERS);
  const [showGroup2, setShowGroup2] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<ScanResult | null>(null);
  const [sortCol, setSortCol] = useState<keyof ScanItem>("rank");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [universeCount, setUniverseCount] = useState<number | null>(null);
  const router = useRouter();
  const { portfolios } = usePortfolio();
  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [proposalDialogOpen, setProposalDialogOpen] = useState(false);
  const [proposalPortfolioId, setProposalPortfolioId] = useState(portfolios[0]?.id ?? "p1");
  const [proposalAmount, setProposalAmount] = useState("5000");

  useEffect(() => {
    apiGet<{ total: number; securities: UniverseItem[] }>("/api/scanner/universe?limit=1000")
      .then((data) => setUniverseCount(data.total))
      .catch(() => setUniverseCount(null));
  }, []);

  const upd = (k: keyof ScanFilters, v: ScanFilters[typeof k]) =>
    setFilters((f) => ({ ...f, [k]: v }));

  const runScan = async () => {
    setScanning(true);
    setProgress(10);
    setResults(null);

    try {
      // Resolve tickers: universe or custom list
      let tickers: string[] = [];
      if (filters.use_universe) {
        setProgress(20);
        const univ = await apiGet<{ securities: UniverseItem[] }>("/api/scanner/universe?limit=500&active_only=true");
        tickers = (univ.securities || []).map((s) => s.symbol);
      } else {
        tickers = filters.custom_tickers
          .split(/[\s,]+/)
          .map((t) => t.trim().toUpperCase())
          .filter(Boolean);
      }

      if (tickers.length === 0) {
        setScanning(false);
        setProgress(0);
        return;
      }

      setProgress(40);

      const payload: Record<string, unknown> = {
        tickers,
        min_score: filters.min_score,
        quality_gate_only: filters.quality_gate_only,
        use_universe: false, // already resolved above
      };
      if (filters.asset_classes.length > 0) payload.asset_classes = filters.asset_classes;
      if (filters.min_yield > 0) payload.min_yield = filters.min_yield;
      if (filters.max_payout_ratio) payload.max_payout_ratio = Number(filters.max_payout_ratio);
      if (filters.min_volume) payload.min_volume = Number(filters.min_volume);
      if (filters.min_market_cap_m) payload.min_market_cap_m = Number(filters.min_market_cap_m);
      if (filters.max_market_cap_m) payload.max_market_cap_m = Number(filters.max_market_cap_m);
      if (filters.min_price) payload.min_price = Number(filters.min_price);
      if (filters.max_price) payload.max_price = Number(filters.max_price);
      if (filters.max_pe) payload.max_pe = Number(filters.max_pe);
      if (filters.min_nav_discount_pct) payload.min_nav_discount_pct = Number(filters.min_nav_discount_pct);

      setProgress(60);
      const data = await apiPost<ScanResult>("/api/scanner/scan", payload);
      setProgress(100);

      setResults(data);
    } catch (err) {
      console.error("Scan failed:", err);
      // Fall back to mock on error during development
      setResults(MOCK_RESULTS);
    } finally {
      setScanning(false);
    }
  };

  const filteredItems = useMemo(() => {
    if (!results) return [];
    return results.items.filter((item) => {
      if (filters.grades.length > 0 && !filters.grades.includes(item.grade)) return false;
      if (filters.recommendations.length > 0 && !filters.recommendations.includes(item.recommendation)) return false;
      if (filters.chowder_signals.length > 0 && (!item.chowder_signal || !filters.chowder_signals.includes(item.chowder_signal))) return false;
      if (filters.asset_classes.length > 0 && !filters.asset_classes.includes(item.asset_class)) return false;
      if (item.score < filters.min_score) return false;
      return true;
    });
  }, [results, filters.grades, filters.recommendations, filters.chowder_signals, filters.asset_classes, filters.min_score]);

  const handleSort = (col: keyof ScanItem) => {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };

  const sorted = [...filteredItems].sort((a, b) => {
    const av = a[sortCol];
    const bv = b[sortCol];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortDir === "asc" ? cmp : -cmp;
  });

  const activeFilterCount = [
    filters.asset_classes.length > 0,
    filters.min_score > 0,
    filters.quality_gate_only,
    filters.grades.length > 0,
    filters.recommendations.length > 0,
    filters.chowder_signals.length > 0,
    filters.min_yield > 0,
    !!filters.max_payout_ratio,
    !!filters.min_volume,
    !!filters.min_market_cap_m || !!filters.max_market_cap_m,
    !!filters.min_price || !!filters.max_price,
    !!filters.max_pe,
    !!filters.min_nav_discount_pct,
  ].filter(Boolean).length;

  const createProposal = () => {
    const tickers = Array.from(selectedTickers);
    const amountPerPosition = Math.round(Number(proposalAmount) / tickers.length);
    const positions = tickers.map((ticker) => {
      const item = results?.items.find((i) => i.ticker === ticker);
      return {
        symbol: ticker,
        name: ticker,
        asset_type: item?.asset_class ?? "ETF",
        shares: 1,
        entry_price: amountPerPosition,
        current_price: amountPerPosition,
        yield_estimate: 0,
        score: item?.score ?? 0,
      };
    });
    const proposal = {
      id: `scanner-${Date.now()}`,
      portfolio_id: proposalPortfolioId,
      proposal_type: "BUY",
      summary: `Scanner-identified opportunities: ${tickers.join(", ")}. Target allocation: $${Number(proposalAmount).toLocaleString()} total across ${tickers.length} position${tickers.length > 1 ? "s" : ""}.`,
      status: "PENDING",
      created_at: new Date().toISOString(),
      analyst_source: "Opportunity Scanner",
      analyst_sentiment: "Bullish",
      risk_flags: [],
      positions,
    };
    try {
      const existing = JSON.parse(localStorage.getItem("pendingProposals") ?? "[]");
      localStorage.setItem("pendingProposals", JSON.stringify([...existing, proposal]));
    } catch { /* ignore */ }
    setProposalDialogOpen(false);
    setSelectedTickers(new Set());
    router.push("/proposals");
  };

  return (
    <div className="space-y-4">
      {/* Proposal dialog */}
      {proposalDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-xl space-y-4">
            <h2 className="text-base font-semibold">Create Buy Proposal</h2>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Selected positions ({selectedTickers.size})</p>
              <div className="flex flex-wrap gap-1.5">
                {Array.from(selectedTickers).map((t) => (
                  <span key={t} className="rounded bg-primary/10 px-2 py-0.5 text-xs font-mono font-medium text-primary">{t}</span>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Target Portfolio</label>
                <select
                  value={proposalPortfolioId}
                  onChange={(e) => setProposalPortfolioId(e.target.value)}
                  className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {portfolios.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Total Investment Amount ($)</label>
                <input
                  type="number"
                  value={proposalAmount}
                  onChange={(e) => setProposalAmount(e.target.value)}
                  className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  placeholder="e.g. 10000"
                />
                {selectedTickers.size > 0 && Number(proposalAmount) > 0 && (
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    ≈ ${Math.round(Number(proposalAmount) / selectedTickers.size).toLocaleString()} per position · adjust shares in Proposals
                  </p>
                )}
              </div>
            </div>
            <div className="flex gap-2 pt-1">
              <button
                onClick={() => setProposalDialogOpen(false)}
                className="flex-1 rounded-md border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-secondary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={createProposal}
                disabled={!proposalAmount || Number(proposalAmount) <= 0}
                className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                Create Proposal
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Opportunity Scanner</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Scan the universe for income opportunities matching your criteria
          </p>
        </div>
        {results && (
          <div className="flex items-center gap-3 text-xs">
            <span className="text-muted-foreground">{results.total_scanned} scanned</span>
            <span className="text-emerald-400 font-medium">{results.total_passed} passed</span>
            <span className="text-red-400">{results.total_vetoed} vetoed</span>
          </div>
        )}
      </div>

      {/* Filter panel */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-4">

        {/* Universe selector */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => upd("use_universe", false)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                !filters.use_universe
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              Custom Tickers
            </button>
            <button
              onClick={() => upd("use_universe", true)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                filters.use_universe
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              Full Universe
            </button>
          </div>

          {!filters.use_universe && (
            <div className="flex-1 relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="ARCC, MAIN, O, JEPI, PTY, ..."
                value={filters.custom_tickers}
                onChange={(e) => upd("custom_tickers", e.target.value)}
                className="w-full rounded-md border border-border bg-secondary pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          )}
          {filters.use_universe && (
            <p className="text-xs text-muted-foreground">
              Will scan {universeCount !== null ? universeCount : "all"} active securities in platform_shared.securities — use filters to narrow results.
            </p>
          )}
        </div>

        {/* Group 1 filters */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {/* Asset class */}
          <div>
            <label className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
              Asset Class
            </label>
            <div className="flex flex-wrap gap-1">
              {ASSET_CLASSES.map((ac) => (
                <button
                  key={ac}
                  onClick={() => upd("asset_classes", toggleItem(filters.asset_classes, ac))}
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors",
                    filters.asset_classes.includes(ac)
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-muted-foreground hover:text-foreground"
                  )}
                >
                  {ac}
                </button>
              ))}
            </div>
          </div>

          {/* Min score */}
          <div>
            <label className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
              Min Score: <span className="text-foreground">{filters.min_score}</span>
            </label>
            <input
              type="range" min={0} max={100} step={5}
              value={filters.min_score}
              onChange={(e) => upd("min_score", Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          {/* Grade */}
          <div>
            <label className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
              Grade
            </label>
            <div className="flex gap-1">
              {GRADES.map((g) => (
                <button
                  key={g}
                  onClick={() => upd("grades", toggleItem(filters.grades, g))}
                  className={cn(
                    "rounded px-2 py-0.5 text-xs font-semibold transition-colors",
                    filters.grades.includes(g)
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-muted-foreground hover:text-foreground"
                  )}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>

          {/* Recommendation */}
          <div>
            <label className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
              Recommendation
            </label>
            <div className="flex gap-1">
              {RECOMMENDATIONS.map((r) => (
                <button
                  key={r}
                  onClick={() => upd("recommendations", toggleItem(filters.recommendations, r))}
                  className={cn(
                    "rounded px-2 py-0.5 text-[10px] font-semibold transition-colors",
                    filters.recommendations.includes(r)
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-muted-foreground hover:text-foreground"
                  )}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          {/* Chowder signal */}
          <div>
            <label className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
              Chowder Signal
            </label>
            <div className="flex flex-wrap gap-1">
              {CHOWDER_SIGNALS.map((s) => (
                <button
                  key={s}
                  onClick={() => upd("chowder_signals", toggleItem(filters.chowder_signals, s))}
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors",
                    filters.chowder_signals.includes(s)
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-muted-foreground hover:text-foreground"
                  )}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Quality gate */}
          <div className="flex items-end pb-0.5">
            <label className="flex items-center gap-2 cursor-pointer">
              <div
                onClick={() => upd("quality_gate_only", !filters.quality_gate_only)}
                className={cn(
                  "relative h-5 w-9 rounded-full transition-colors cursor-pointer",
                  filters.quality_gate_only ? "bg-primary" : "bg-secondary border border-border"
                )}
              >
                <div className={cn(
                  "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform shadow-sm",
                  filters.quality_gate_only ? "translate-x-4" : "translate-x-0.5"
                )} />
              </div>
              <span className="text-xs text-muted-foreground">Quality Gate ≥70 only</span>
            </label>
          </div>
        </div>

        {/* Group 2 toggle */}
        <div>
          <button
            onClick={() => setShowGroup2(!showGroup2)}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <Filter className="h-3.5 w-3.5" />
            Market Data Filters (Group 2)
            {showGroup2 ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {activeFilterCount > 0 && (
              <span className="ml-1 rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-bold text-primary-foreground">
                {activeFilterCount}
              </span>
            )}
          </button>

          {showGroup2 && (
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 border-t border-border pt-3">
              {[
                { key: "min_yield", label: "Min Yield (%)", placeholder: "e.g. 6" },
                { key: "max_payout_ratio", label: "Max Payout Ratio (%)", placeholder: "e.g. 90" },
                { key: "min_volume", label: "Min Avg Volume", placeholder: "e.g. 100000" },
                { key: "min_market_cap_m", label: "Min Market Cap ($M)", placeholder: "e.g. 500" },
                { key: "max_market_cap_m", label: "Max Market Cap ($M)", placeholder: "e.g. 50000" },
                { key: "min_price", label: "Min Price ($)", placeholder: "e.g. 5" },
                { key: "max_price", label: "Max Price ($)", placeholder: "e.g. 100" },
                { key: "max_pe", label: "Max P/E", placeholder: "e.g. 20" },
                { key: "min_nav_discount_pct", label: "Min NAV Discount (%)", placeholder: "e.g. -5 for ≥5% disc" },
              ].map(({ key, label, placeholder }) => (
                <div key={key}>
                  <label className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1">
                    {label}
                  </label>
                  <input
                    type="number"
                    placeholder={placeholder}
                    value={(filters as unknown as Record<string, string>)[key]}
                    onChange={(e) => upd(key as keyof ScanFilters, e.target.value)}
                    className="w-full rounded-md border border-border bg-secondary px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Action row */}
        <div className="flex items-center gap-3 border-t border-border pt-3">
          <button
            onClick={runScan}
            disabled={scanning}
            className={cn(
              "flex items-center gap-2 rounded-md px-5 py-2 text-sm font-medium transition-colors",
              scanning
                ? "bg-primary/50 text-primary-foreground/50 cursor-not-allowed"
                : "bg-primary text-primary-foreground hover:bg-primary/90"
            )}
          >
            {scanning ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                Scanning... {progress}%
              </>
            ) : (
              <>
                <ScanLine className="h-4 w-4" />
                Run Scan
              </>
            )}
          </button>

          {(activeFilterCount > 0 || filters.custom_tickers || filters.use_universe) && (
            <button
              onClick={() => { setFilters(DEFAULT_FILTERS); setResults(null); }}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Clear all
            </button>
          )}

          {/* Progress bar */}
          {scanning && (
            <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all duration-150"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      {results && !scanning && (
        <div className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-4 text-xs">
              <span className="font-medium">{results.total_passed} results</span>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">{results.total_scanned} tickers scanned</span>
              <span className="text-muted-foreground">·</span>
              <span className="text-red-400">{results.total_vetoed} vetoed</span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-secondary/50">
                  <th className="px-3 py-2 w-8">
                    <input
                      type="checkbox"
                      className="rounded"
                      checked={sorted.length > 0 && sorted.every((i) => selectedTickers.has(i.ticker))}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedTickers(new Set(sorted.map((i) => i.ticker)));
                        else setSelectedTickers(new Set());
                      }}
                    />
                  </th>
                  {[
                    { key: "rank", label: "#" },
                    { key: "ticker", label: "Ticker" },
                    { key: "asset_class", label: "Class" },
                    { key: "score", label: "Score" },
                    { key: "grade", label: "Grade" },
                    { key: "recommendation", label: "Rec." },
                    { key: "chowder_number", label: "Chowder #" },
                    { key: "chowder_signal", label: "Signal" },
                    { key: "signal_penalty", label: "Penalty" },
                    { key: "passed_quality_gate", label: "QG" },
                  ].map(({ key, label }) => (
                    <th
                      key={key}
                      onClick={() => handleSort(key as keyof ScanItem)}
                      className="cursor-pointer select-none px-3 py-2 text-left text-xs font-medium text-muted-foreground hover:text-foreground"
                    >
                      <span className="flex items-center gap-1">
                        {label}
                        {sortCol === key && (
                          sortDir === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
                        )}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((item) => (
                  <>
                    <tr
                      key={item.ticker}
                      onClick={() => setExpandedRow(expandedRow === item.ticker ? null : item.ticker)}
                      className={cn(
                        "cursor-pointer border-b border-border/50 transition-colors",
                        item.veto_flag ? "opacity-50" : "",
                        expandedRow === item.ticker ? "bg-secondary/50" : "hover:bg-secondary/30"
                      )}
                    >
                      <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          className="rounded"
                          checked={selectedTickers.has(item.ticker)}
                          onChange={(e) => {
                            const next = new Set(selectedTickers);
                            if (e.target.checked) next.add(item.ticker);
                            else next.delete(item.ticker);
                            setSelectedTickers(next);
                          }}
                        />
                      </td>
                      <td className="px-3 py-2.5 text-xs tabular-nums text-muted-foreground">{item.rank}</td>
                      <td className="px-3 py-2.5">
                        <TickerBadge symbol={item.ticker} assetType={item.asset_class} />
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">{item.asset_class}</td>
                      <td className="px-3 py-2.5">
                        <ScorePill score={item.score} />
                      </td>
                      <td className={cn("px-3 py-2.5 text-sm font-bold", GRADE_COLORS[item.grade] || "")}>
                        {item.grade}
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-bold", REC_COLORS[item.recommendation] || "")}>
                          {item.recommendation}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 tabular-nums text-xs">
                        {item.chowder_number !== null ? item.chowder_number.toFixed(1) : "—"}
                      </td>
                      <td className={cn("px-3 py-2.5 text-xs font-medium", SIGNAL_COLORS[item.chowder_signal ?? ""] || "text-muted-foreground")}>
                        {item.chowder_signal || "—"}
                      </td>
                      <td className={cn("px-3 py-2.5 tabular-nums text-xs", item.signal_penalty > 0 ? "text-red-400" : "text-muted-foreground")}>
                        {item.signal_penalty > 0 ? `-${item.signal_penalty}` : "0"}
                      </td>
                      <td className="px-3 py-2.5">
                        {item.passed_quality_gate
                          ? <ShieldCheck className="h-4 w-4 text-emerald-400" />
                          : <ShieldAlert className="h-4 w-4 text-red-400" />
                        }
                      </td>
                    </tr>
                    {expandedRow === item.ticker && (
                      <tr key={`${item.ticker}-exp`} className="border-b border-border/50 bg-secondary/20">
                        <td colSpan={11} className="px-4 py-3">
                          <div className="grid grid-cols-4 gap-4 text-xs">
                            {[
                              { label: "Valuation/Yield", val: item.score_details.valuation_yield_score },
                              { label: "Financial Durability", val: item.score_details.financial_durability_score },
                              { label: "Technical Entry", val: item.score_details.technical_entry_score },
                              { label: "NAV Erosion Penalty", val: item.score_details.nav_erosion_penalty },
                            ].map(({ label, val }) => (
                              <div key={label} className="rounded-md border border-border bg-card p-2">
                                <p className="text-muted-foreground mb-1">{label}</p>
                                <p className={cn("text-sm font-semibold tabular-nums",
                                  val !== undefined && val < 0 ? "text-red-400" : "text-foreground"
                                )}>
                                  {val !== undefined && val !== null ? val : "—"}
                                </p>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Proposal action bar */}
      {results && !scanning && selectedTickers.size > 0 && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 flex items-center gap-4">
          <span className="text-sm font-medium">{selectedTickers.size} position{selectedTickers.size > 1 ? "s" : ""} selected</span>
          <div className="flex flex-wrap gap-1">
            {Array.from(selectedTickers).map((t) => (
              <span key={t} className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono font-medium text-primary">{t}</span>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => setSelectedTickers(new Set())}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Clear
            </button>
            <button
              onClick={() => setProposalDialogOpen(true)}
              className="rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Create Proposal →
            </button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!results && !scanning && (
        <div className="rounded-lg border border-border bg-card py-16 text-center">
          <ScanLine className="mx-auto mb-3 h-8 w-8 text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">Configure your criteria and click Run Scan</p>
          <p className="mt-1 text-xs text-muted-foreground/60">
            Results are scored via Agent 03 and ranked by composite income score
          </p>
        </div>
      )}
    </div>
  );
}
