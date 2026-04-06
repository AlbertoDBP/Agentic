// src/frontend/src/components/scanner/proposal-modal.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import type { ScanItem, ScanResult, PortfolioListItem } from "@/lib/types";

interface ProposalModalProps {
  open: boolean;
  onClose: () => void;
  selectedTickers: Set<string>;
  scanResult: ScanResult | null;
  portfolios: PortfolioListItem[];
  defaultPortfolioId?: string | null;
  onSuccess: (proposalId: string) => void;
  taxHoldings?: Array<{
    symbol: string;
    from_account: string;
    to_account: string;
    reason: string;
  }>;
}

export function ProposalModal({
  open,
  onClose,
  selectedTickers,
  scanResult,
  portfolios,
  defaultPortfolioId,
  onSuccess,
  taxHoldings,
}: ProposalModalProps) {
  const router = useRouter();
  const [targetPortfolioId, setTargetPortfolioId] = useState<string>(defaultPortfolioId ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedItems: ScanItem[] = (scanResult?.items ?? []).filter(
    (i) => selectedTickers.has(i.ticker)
  );
  // Show all portfolios — a proposal can target any portfolio, including new ones
  const activePortfolios = portfolios;

  const handleSubmit = async () => {
    if (!targetPortfolioId) return;
    setLoading(true);
    setError(null);
    try {
      let proposalId: string;
      if (taxHoldings && taxHoldings.length > 0) {
        // Tax rebalance path
        const resp = await fetch("/api/proposals/new", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            portfolio_id: targetPortfolioId,
            proposal_type: "TAX_REBALANCE",
            holdings: taxHoldings,
          }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail ?? "Failed to create proposal");
        proposalId = data.proposal_id;
      } else {
        // Existing scanner path — keep exactly as before
        if (!scanResult) return;
        // Step 1: Create the proposal draft in Agent 07
        const draftResp = await fetch("/api/scanner/propose", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            scan_id: scanResult.scan_id,
            selected_tickers: [...selectedTickers],
            target_portfolio_id: targetPortfolioId,
          }),
        });
        const draftData = await draftResp.json();
        if (!draftResp.ok) throw new Error(draftData.detail ?? "Failed to create proposal draft");

        // Step 2: Generate full proposals in Agent 12 for each selected ticker
        const tickers = [...selectedTickers];
        const genResp = await fetch("/api/proposals", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tickers,
            portfolio_id: targetPortfolioId,
            scan_id: scanResult.scan_id,
            trigger_mode: "on_demand",
          }),
        });
        if (!genResp.ok) {
          const genData = await genResp.json().catch(() => ({}));
          throw new Error(genData.detail ?? `Proposal generation failed (${genResp.status})`);
        }

        proposalId = draftData.proposal_id;
      }
      onSuccess(proposalId);
      onClose();
      router.push(`/proposals/${proposalId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Generate Proposal</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Selected tickers summary */}
          <div className="space-y-1">
            {taxHoldings && taxHoldings.length > 0 ? (
              <>
                <p className="text-sm font-medium">Holdings to rebalance ({taxHoldings.length})</p>
                <div className="rounded-md border border-border bg-muted/30 p-3 space-y-1.5 max-h-40 overflow-y-auto">
                  {taxHoldings.map((h) => (
                    <div key={h.symbol} className="flex justify-between text-sm">
                      <span className="font-mono font-medium">{h.symbol}</span>
                      <span className="text-muted-foreground text-xs">
                        {h.from_account} → {h.to_account}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <>
                <p className="text-sm font-medium">Selected ({selectedItems.length})</p>
                <div className="rounded-md border border-border bg-muted/30 p-3 space-y-1.5 max-h-40 overflow-y-auto">
                  {selectedItems.map((item) => (
                    <div key={item.ticker} className="flex justify-between text-sm">
                      <span className="font-mono font-medium">{item.ticker}</span>
                      <span className="text-muted-foreground">
                        Entry:{" "}
                        {item.entry_exit?.entry_limit != null
                          ? `$${item.entry_exit.entry_limit.toFixed(2)}`
                          : "—"}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Target portfolio */}
          <div className="space-y-2">
            <Label className="text-sm">Target Portfolio <span className="text-red-500">*</span></Label>
            <Select value={targetPortfolioId} onValueChange={(v) => setTargetPortfolioId(v ?? "")}>
              <SelectTrigger>
                {targetPortfolioId ? (
                  <span className="text-sm">{portfolios.find((p) => p.id === targetPortfolioId)?.name ?? "Portfolio"}</span>
                ) : (
                  <SelectValue placeholder="Select target portfolio..." />
                )}
              </SelectTrigger>
              <SelectContent>
                {activePortfolios.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}{p.broker ? ` · ${p.broker}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {error && (
            <p className="text-sm text-red-500">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={loading || !targetPortfolioId}
          >
            {loading ? "Generating…" : "Generate Proposal →"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
