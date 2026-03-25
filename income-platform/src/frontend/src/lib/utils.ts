import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number, compact = false): string {
  if (compact && Math.abs(value) >= 1000) {
    const abs = Math.abs(value);
    const sign = value < 0 ? "-" : "";
    if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
    return `${sign}$${(abs / 1000).toFixed(1)}K`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatDate(iso: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function severityColor(severity: string): string {
  switch (severity?.toUpperCase()) {
    case "CRITICAL":
      return "text-red-500 bg-red-500/10";
    case "HIGH":
      return "text-red-400 bg-red-400/10";
    case "MEDIUM":
      return "text-amber-400 bg-amber-400/10";
    case "LOW":
      return "text-blue-400 bg-blue-400/10";
    default:
      return "text-muted-foreground bg-muted";
  }
}

export function scoreColor(score: number): string {
  if (score >= 85) return "text-green-400 bg-green-400/10 border-green-400/30";
  if (score >= 70) return "text-lime-400 bg-lime-400/10 border-lime-400/30";
  if (score >= 50) return "text-amber-400 bg-amber-400/10 border-amber-400/30";
  return "text-red-400 bg-red-400/10 border-red-400/30";
}

/** Returns only the text color class for a score (traffic-light, no background). */
export function scoreTextColor(score: number | null | undefined): string {
  if (score == null) return "text-muted-foreground";
  if (score >= 85) return "text-green-400";
  if (score >= 70) return "text-lime-400";
  if (score >= 50) return "text-amber-400";
  return "text-red-400";
}

/** Returns text + background color classes for a score badge (traffic-light). */
export function scoreBadgeColor(score: number | null | undefined): string {
  if (score == null) return "text-muted-foreground bg-muted/30";
  if (score >= 85) return "text-green-400 bg-green-950/60";
  if (score >= 70) return "text-lime-400 bg-lime-950/60";
  if (score >= 50) return "text-amber-400 bg-amber-950/60";
  return "text-red-400 bg-red-950/60";
}

/** Color for 52-week range position (0–100% position in the range). */
export function rangePositionColor(positionPct: number | null | undefined): string {
  if (positionPct == null) return "text-muted-foreground";
  if (positionPct < 30) return "text-red-400";
  if (positionPct < 50) return "text-amber-400";
  if (positionPct < 70) return "text-blue-400";
  return "text-yellow-400";
}

/** Bar fill color for 52-week range position. */
export function rangeBarColor(positionPct: number | null | undefined): string {
  if (positionPct == null) return "bg-muted";
  if (positionPct < 30) return "bg-red-500";
  if (positionPct < 50) return "bg-amber-500";
  if (positionPct < 70) return "bg-blue-500";
  return "bg-yellow-500";
}
