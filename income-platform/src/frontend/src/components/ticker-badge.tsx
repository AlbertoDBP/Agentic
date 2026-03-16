import { ASSET_CLASS_COLORS } from "@/lib/config";

interface TickerBadgeProps {
  symbol: string;
  assetType?: string;
}

export function TickerBadge({ symbol, assetType }: TickerBadgeProps) {
  const color = assetType ? ASSET_CLASS_COLORS[assetType] || "#64748b" : "#64748b";

  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-sm font-medium">
      <span
        className="h-2 w-2 rounded-full"
        style={{ backgroundColor: color }}
      />
      {symbol}
    </span>
  );
}
