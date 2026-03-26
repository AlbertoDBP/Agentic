// src/frontend/src/components/scanner/input-panel.tsx
"use client";

import React from "react";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { PortfolioListItem } from "@/lib/types";

export type InputMode = "manual" | "portfolio" | "universe";

interface InputPanelProps {
  mode: InputMode;
  onModeChange: (mode: InputMode) => void;
  manualTickers: string;
  onManualTickersChange: (v: string) => void;
  selectedPortfolioId: string | null;
  onPortfolioChange: (id: string | null) => void;
  portfolios: PortfolioListItem[];
}

const TABS: { value: InputMode; label: string }[] = [
  { value: "manual", label: "Manual List" },
  { value: "portfolio", label: "Portfolio" },
  { value: "universe", label: "Full Universe" },
];

export function InputPanel({
  mode,
  onModeChange,
  manualTickers,
  onManualTickersChange,
  selectedPortfolioId,
  onPortfolioChange,
  portfolios,
}: InputPanelProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      {/* Mode tabs */}
      <div className="flex gap-1 rounded-md bg-muted p-1 w-fit">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => onModeChange(tab.value)}
            className={cn(
              "px-3 py-1.5 rounded text-sm font-medium transition-colors",
              mode === tab.value
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Input area */}
      {mode === "manual" && (
        <Textarea
          value={manualTickers}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => onManualTickersChange(e.target.value)}
          placeholder={"Enter tickers (comma or newline separated)\nMAIN, ARCC, O, JEPI, ..."}
          rows={4}
          className="font-mono text-sm resize-none"
        />
      )}

      {mode === "portfolio" && (
        <Select value={selectedPortfolioId ?? ""} onValueChange={onPortfolioChange}>
          <SelectTrigger className="w-full">
            <SelectValue>
              {(value: string | null) => {
                if (!value) return <span className="text-muted-foreground">Select a portfolio to scan...</span>;
                const p = portfolios.find((p) => p.id === value);
                return p ? `${p.name} (${p.holding_count} positions)` : value;
              }}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {portfolios.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name}
                <span className="ml-2 text-muted-foreground text-xs">
                  ({p.holding_count} positions)
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {mode === "universe" && (
        <p className="text-sm text-muted-foreground">
          Scans all active securities in the tracked universe. May take up to 2 minutes on a cold cache.
        </p>
      )}
    </div>
  );
}
