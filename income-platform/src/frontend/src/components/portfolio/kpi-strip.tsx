"use client";
import { useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { HelpTooltip } from "@/components/help-tooltip";

interface KpiItem {
  label: string;
  value: string | number | null | undefined;
  helpText?: string;
  colorClass?: string;
  alert?: boolean;
  onClick?: () => void;
  title?: string;
  // Inline editing
  editing?: boolean;
  editValue?: string;
  onEditChange?: (v: string) => void;
  onEditSave?: () => void;
  onEditCancel?: () => void;
}

interface KpiStripProps {
  items: KpiItem[];
  className?: string;
}

export function KpiStrip({ items, className }: KpiStripProps) {
  return (
    <div className={cn(
      "grid gap-1.5 mb-3",
      "grid-cols-2 sm:grid-cols-4 lg:grid-cols-8",
      className
    )}>
      {items.map((item) => (
        <KpiTile key={item.label} item={item} />
      ))}
    </div>
  );
}

function KpiTile({ item }: { item: KpiItem }) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (item.editing) inputRef.current?.focus();
  }, [item.editing]);

  return (
    <div
      onClick={!item.editing ? item.onClick : undefined}
      title={!item.editing ? item.title : undefined}
      className={cn(
        "bg-card border rounded-lg px-2.5 py-1.5",
        item.alert && "border-red-900/50 bg-red-950/30",
        !item.editing && item.onClick && "cursor-pointer hover:border-border/80 hover:bg-card/80",
        item.editing && "border-primary/50 ring-1 ring-primary/30"
      )}
    >
      <div className="flex items-center gap-0.5 text-[0.625rem] font-bold uppercase text-muted-foreground tracking-wide">
        {item.label}
        {item.helpText && <HelpTooltip text={item.helpText} />}
      </div>
      {item.editing ? (
        <input
          ref={inputRef}
          className="w-full bg-transparent text-sm font-bold text-foreground border-none outline-none mt-0.5 tabular-nums"
          value={item.editValue ?? ""}
          onChange={(e) => item.onEditChange?.(e.target.value)}
          onBlur={item.onEditSave}
          onKeyDown={(e) => {
            if (e.key === "Enter") item.onEditSave?.();
            if (e.key === "Escape") item.onEditCancel?.();
          }}
        />
      ) : (
        <div className={cn("text-sm font-bold mt-0.5", item.colorClass ?? "text-foreground")}>
          {item.value ?? "—"}
        </div>
      )}
    </div>
  );
}
