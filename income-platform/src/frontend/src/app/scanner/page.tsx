// src/frontend/src/app/scanner/page.tsx
"use client";

import { useState, useCallback } from "react";
import { ScanLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { InputPanel, type InputMode } from "@/components/scanner/input-panel";
import { FilterPanel, DEFAULT_FILTERS, type ScanFilters } from "@/components/scanner/filter-panel";
import { LensPicker, type ScannerLens } from "@/components/scanner/lens-picker";
import { ResultsTable } from "@/components/scanner/results-table";
import { ProposalModal } from "@/components/scanner/proposal-modal";
import { usePortfolios } from "@/lib/hooks/use-portfolios";
import type { ScanResult } from "@/lib/types";

export default function ScannerPage() {
  // Input mode
  const [mode, setMode] = useState<InputMode>("manual");
  const [manualTickers, setManualTickers] = useState("");
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);

  // Filters
  const [filters, setFilters] = useState<ScanFilters>(DEFAULT_FILTERS);

  // Portfolio lens (only active when portfolio mode)
  const [lens, setLens] = useState<ScannerLens>(null);

  // Scan state
  const [result, setResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selection + proposal
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

  const buildPayload = () => {
    const payload: Record<string, unknown> = {
      tickers: [],
      use_universe: mode === "universe",
      min_score: filters.min_score,
      quality_gate_only: filters.quality_gate_only,
      asset_classes: filters.asset_classes.length ? filters.asset_classes : null,
      min_yield: filters.min_yield,
      max_payout_ratio: filters.max_payout_ratio ? Number(filters.max_payout_ratio) : null,
      min_volume: filters.min_volume ? Number(filters.min_volume) : null,
      min_market_cap_m: filters.min_market_cap_m ? Number(filters.min_market_cap_m) : null,
      max_market_cap_m: filters.max_market_cap_m ? Number(filters.max_market_cap_m) : null,
      min_price: filters.min_price ? Number(filters.min_price) : null,
      max_price: filters.max_price ? Number(filters.max_price) : null,
      max_pe: filters.max_pe ? Number(filters.max_pe) : null,
      min_nav_discount_pct: filters.min_nav_discount_pct ? Number(filters.min_nav_discount_pct) : null,
    };

    if (mode === "manual") {
      payload.tickers = manualTickers
        .split(/[\n,]+/)
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);
    }

    if (mode === "portfolio" && selectedPortfolioId) {
      payload.portfolio_id = selectedPortfolioId;
      if (lens) payload.portfolio_lens = lens;
      // Scan portfolio positions: set use_universe=false, tickers=[]
      // The backend fetches positions when portfolio_id is set
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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ScanLine className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-semibold">Scanner</h1>
        </div>
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
        onModeChange={setMode}
        manualTickers={manualTickers}
        onManualTickersChange={setManualTickers}
        selectedPortfolioId={selectedPortfolioId}
        onPortfolioChange={setSelectedPortfolioId}
        portfolios={portfolios}
      />

      {/* Filters */}
      <FilterPanel filters={filters} onChange={setFilters} />

      {/* Lens picker — only when portfolio mode active */}
      {mode === "portfolio" && selectedPortfolioId && (
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
        defaultPortfolioId={mode === "portfolio" ? selectedPortfolioId : null}
        onSuccess={handleProposalSuccess}
      />
    </div>
  );
}
