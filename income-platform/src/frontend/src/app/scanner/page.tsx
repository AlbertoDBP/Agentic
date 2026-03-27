// src/frontend/src/app/scanner/page.tsx
"use client";

import { useState, useCallback } from "react";
import { ScanLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { InputPanel, type InputMode } from "@/components/scanner/input-panel";
import { FilterPanel, DEFAULT_FILTERS, type ScanFilters } from "@/components/scanner/filter-panel";
import { LensPicker, type ScannerLens } from "@/components/scanner/lens-picker";
import { ResultsTable } from "@/components/scanner/results-table";
import { ProposalModal } from "@/components/scanner/proposal-modal";
import { AnalystIdeasTab } from "@/components/scanner/analyst-ideas-tab";
import { usePortfolios } from "@/lib/hooks/use-portfolios";
import type { ScanResult } from "@/lib/types";

type ScannerTab = "manual" | "portfolio" | "universe" | "analyst_ideas";

const TABS: { value: ScannerTab; label: string }[] = [
  { value: "manual",        label: "Manual List" },
  { value: "portfolio",     label: "Portfolio" },
  { value: "universe",      label: "Full Universe" },
  { value: "analyst_ideas", label: "Analyst Ideas" },
];

const TAB_TO_MODE: Record<ScannerTab, InputMode | null> = {
  manual:        "manual",
  portfolio:     "portfolio",
  universe:      "universe",
  analyst_ideas: null,
};

export default function ScannerPage() {
  const [activeTab, setActiveTab] = useState<ScannerTab>("manual");

  const [manualTickers, setManualTickers] = useState("");
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);

  const [filters, setFilters] = useState<ScanFilters>(DEFAULT_FILTERS);
  const [lens, setLens] = useState<ScannerLens>(null);

  const [result, setResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [proposalOpen, setProposalOpen] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const { data: portfolios = [] } = usePortfolios();

  const handleToggleTicker = useCallback((ticker: string) => {
    setSelectedTickers((prev) => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  }, []);

  const mode: InputMode = (TAB_TO_MODE[activeTab] ?? "manual") as InputMode;

  const buildPayload = () => {
    const payload: Record<string, unknown> = {
      tickers: [],
      use_universe: activeTab === "universe",
      min_score: filters.min_score,
      quality_gate_only: filters.quality_gate_only,
      asset_classes: filters.asset_classes.length ? filters.asset_classes : null,
      min_yield: filters.min_yield ? Number(filters.min_yield) : 0,
      max_payout_ratio: filters.max_payout_ratio ? Number(filters.max_payout_ratio) : null,
      min_volume: filters.min_volume ? Number(filters.min_volume) : null,
      min_market_cap_m: filters.min_market_cap_m ? Number(filters.min_market_cap_m) : null,
      max_market_cap_m: filters.max_market_cap_m ? Number(filters.max_market_cap_m) : null,
      min_price: filters.min_price ? Number(filters.min_price) : null,
      max_price: filters.max_price ? Number(filters.max_price) : null,
      max_pe: filters.max_pe ? Number(filters.max_pe) : null,
      min_nav_discount_pct: filters.min_nav_discount_pct ? Number(filters.min_nav_discount_pct) : null,
    };

    if (activeTab === "manual") {
      payload.tickers = manualTickers
        .split(/[\n,]+/)
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);
    }

    if (activeTab === "portfolio" && selectedPortfolioId) {
      payload.portfolio_id = selectedPortfolioId;
      if (lens) payload.portfolio_lens = lens;
      payload.use_universe = false;
      payload.tickers = [];
    }

    return payload;
  };

  const handleScan = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedTickers(new Set());
    setSuccessMsg(null);

    try {
      const resp = await fetch("/api/scanner/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Scan failed");
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleProposalSuccess = (proposalId: string) => {
    setSuccessMsg(`Proposal ${proposalId} created.`);
    setSelectedTickers(new Set());
  };

  return (
    <div className="space-y-4 p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-2">
        <ScanLine className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-semibold">Scanner</h1>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-border">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveTab(tab.value)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px",
              activeTab === tab.value
                ? "border-violet-500 text-violet-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Analyst Ideas Tab ── */}
      {activeTab === "analyst_ideas" && (
        <AnalystIdeasTab
          portfolios={portfolios}
          onSuccess={handleProposalSuccess}
        />
      )}

      {/* ── Standard scan tabs (Manual / Portfolio / Universe) ── */}
      {activeTab !== "analyst_ideas" && (
        <>
          {/* Action bar */}
          <div className="flex items-center justify-between">
            <div />
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setProposalOpen(true)}
                disabled={selectedTickers.size === 0}
              >
                Generate Proposal → {selectedTickers.size > 0 ? `(${selectedTickers.size})` : ""}
              </Button>
              <Button onClick={handleScan} disabled={loading} size="sm">
                {loading ? "Scanning…" : "Run Scan"}
              </Button>
            </div>
          </div>

          {/* Input */}
          <InputPanel
            mode={mode}
            onModeChange={(m) => {
              const tab = (Object.entries(TAB_TO_MODE).find(([, v]) => v === m)?.[0] ?? "manual") as ScannerTab;
              setActiveTab(tab);
            }}
            manualTickers={manualTickers}
            onManualTickersChange={setManualTickers}
            selectedPortfolioId={selectedPortfolioId}
            onPortfolioChange={setSelectedPortfolioId}
            portfolios={portfolios}
            hideTabs
          />

          {/* Filters */}
          <FilterPanel filters={filters} onChange={setFilters} />

          {/* Lens picker */}
          {activeTab === "portfolio" && selectedPortfolioId && (
            <LensPicker lens={lens} onChange={setLens} />
          )}

          {/* Error */}
          {error && (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Success */}
          {successMsg && (
            <div className="rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
              {successMsg}
            </div>
          )}

          {/* Results */}
          <ResultsTable
            result={result}
            selectedTickers={selectedTickers}
            onToggleTicker={handleToggleTicker}
            loading={loading}
          />

          {/* Proposal modal */}
          <ProposalModal
            open={proposalOpen}
            onClose={() => setProposalOpen(false)}
            selectedTickers={selectedTickers}
            scanResult={result}
            portfolios={portfolios}
            defaultPortfolioId={activeTab === "portfolio" ? selectedPortfolioId : null}
            onSuccess={handleProposalSuccess}
          />
        </>
      )}
    </div>
  );
}
