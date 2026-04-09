// src/frontend/src/components/chat/ToolCard.tsx
"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";
import { cn } from "@/lib/utils";

interface ToolCardProps {
  name: string;
  result?: Record<string, unknown>;
  pending?: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  create_proposal_draft: "Created ProposalDraft",
  get_position_details: "Position Details",
  get_score_breakdown: "Score Breakdown",
  get_scanner_results: "Scanner Results",
  get_analyst_signals: "Analyst Signals",
  save_memory: "Memory Saved",
  save_skill: "Skill Saved",
};

export function ToolCard({ name, result, pending = false }: ToolCardProps) {
  const [open, setOpen] = useState(false);
  const label = TOOL_LABELS[name] ?? name;

  return (
    <div className="my-1.5 rounded border border-border/40 bg-muted/20 text-xs overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-left text-muted-foreground hover:text-foreground transition-colors"
      >
        <Wrench className="w-3 h-3 shrink-0 text-blue-400" />
        <span className="flex-1 font-medium">{label}</span>
        {pending ? (
          <span className="text-[10px] text-muted-foreground animate-pulse">thinking…</span>
        ) : open ? (
          <ChevronDown className="w-3 h-3" />
        ) : (
          <ChevronRight className="w-3 h-3" />
        )}
      </button>
      {open && result && (
        <pre className="px-2.5 pb-2 text-[10px] text-muted-foreground whitespace-pre-wrap break-words border-t border-border/40 pt-1.5">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
      {!pending && typeof result?.link === "string" && (
        <div className="px-2.5 pb-1.5">
          <a href={result.link} className="text-blue-400 hover:underline text-[10px]">
            View in Proposals →
          </a>
        </div>
      )}
    </div>
  );
}
