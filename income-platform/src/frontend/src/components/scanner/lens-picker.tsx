// src/frontend/src/components/scanner/lens-picker.tsx
import { cn } from "@/lib/utils";

export type ScannerLens = "gap" | "replacement" | "concentration" | null;

const LENSES: { value: ScannerLens; label: string; description: string }[] = [
  { value: "gap", label: "Gap Finder", description: "New opportunities not in portfolio" },
  { value: "replacement", label: "Replacement", description: "Better alternatives to underperformers" },
  { value: "concentration", label: "Concentration", description: "Picks that improve diversification" },
];

interface LensPickerProps {
  lens: ScannerLens;
  onChange: (lens: ScannerLens) => void;
}

export function LensPicker({ lens, onChange }: LensPickerProps) {
  return (
    <div className="flex gap-2 flex-wrap">
      {LENSES.map((l) => (
        <button
          key={String(l.value)}
          onClick={() => onChange(lens === l.value ? null : l.value)}
          title={l.description}
          className={cn(
            "px-3 py-1.5 rounded-full text-xs font-medium border transition-colors",
            lens === l.value
              ? "bg-primary text-primary-foreground border-primary"
              : "border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
          )}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
