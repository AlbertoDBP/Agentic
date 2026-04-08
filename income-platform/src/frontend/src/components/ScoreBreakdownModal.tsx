"use client";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import {
  directionality,
  DIRECTIONALITY_COLOR,
  DIRECTIONALITY_BAR,
  FACTOR_LABEL,
  PILLAR_FACTORS,
  PILLAR_LABEL,
  type FactorEntry,
} from "@/lib/score-breakdown";

export interface ScoreBreakdownModalProps {
  ticker: string;
  factorDetails: Record<string, FactorEntry> | null | undefined;
  hhsScore?: number | null;
  iesScore?: number | null;
  hhsStatus?: string | null;
  iesCalculated?: boolean;
  iesBlockedReason?: string | null;
  onClose: () => void;
}

function FactorBar({ factorKey, entry }: { factorKey: string; entry: FactorEntry }) {
  const pct = entry.max > 0 ? Math.min(100, (entry.score / entry.max) * 100) : 0;
  const dir = directionality(entry.score, entry.max);
  return (
    <div className="flex items-center gap-2">
      <div className="w-36 shrink-0 text-xs text-muted-foreground truncate">
        {FACTOR_LABEL[factorKey] ?? factorKey.replace(/_/g, " ")}
      </div>
      <div className="flex-1 bg-muted/30 rounded-full h-1.5 overflow-hidden">
        <div
          className={cn("h-full rounded-full", DIRECTIONALITY_BAR[dir])}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded min-w-[52px] text-center", DIRECTIONALITY_COLOR[dir])}>
        {dir}
      </div>
      <div className="text-xs tabular-nums text-muted-foreground w-14 text-right">
        {entry.score.toFixed(1)}/{entry.max.toFixed(1)}
      </div>
    </div>
  );
}

function PillarSection({
  pillar,
  factorDetails,
}: {
  pillar: "INC" | "DUR" | "IES";
  factorDetails: Record<string, FactorEntry>;
}) {
  const factors = PILLAR_FACTORS[pillar].filter((k) => factorDetails[k]);
  if (factors.length === 0) return null;
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-2 pb-1 border-b border-border/40">
        {PILLAR_LABEL[pillar]}
      </div>
      <div className="space-y-2.5">
        {factors.map((k) => (
          <FactorBar key={k} factorKey={k} entry={factorDetails[k]} />
        ))}
      </div>
    </div>
  );
}

export function ScoreBreakdownModal({
  ticker,
  factorDetails,
  hhsScore,
  iesScore,
  hhsStatus,
  iesCalculated,
  iesBlockedReason,
  onClose,
}: ScoreBreakdownModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6 space-y-5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-lg font-bold">{ticker}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Score Factor Breakdown</div>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* HHS + IES summary */}
        <div className="flex gap-3">
          <div className="flex-1 bg-muted/20 rounded-lg p-3 text-center">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1.5">
              HHS Score
            </div>
            {hhsScore != null ? (
              <HhsBadge status={hhsStatus} score={hhsScore} />
            ) : (
              <div className="text-muted-foreground text-sm">—</div>
            )}
          </div>
          <div className="flex-1 bg-muted/20 rounded-lg p-3 text-center">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1.5">
              IES Score
            </div>
            {iesCalculated && iesScore != null ? (
              <div className="text-xl font-bold tabular-nums text-blue-400">
                {iesScore.toFixed(0)}
              </div>
            ) : (
              <div className="text-muted-foreground text-xs">{iesBlockedReason ?? "—"}</div>
            )}
          </div>
        </div>

        {/* Factor bars */}
        {factorDetails && Object.keys(factorDetails).some((k) => PILLAR_FACTORS.INC.includes(k) || PILLAR_FACTORS.DUR.includes(k) || PILLAR_FACTORS.IES.includes(k)) ? (
          <div className="space-y-5">
            <PillarSection pillar="INC" factorDetails={factorDetails} />
            <PillarSection pillar="DUR" factorDetails={factorDetails} />
            <PillarSection pillar="IES" factorDetails={factorDetails} />
          </div>
        ) : (
          <div className="text-muted-foreground text-sm text-center py-6">
            Detailed breakdown not available for this score
          </div>
        )}
      </div>
    </div>
  );
}
