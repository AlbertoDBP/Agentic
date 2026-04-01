import type { Position } from "./types";

/** Portfolio weight of a position as a percentage (0–100). Returns null if total value is 0. */
export function computePortfolioWeight(
  position: Position,
  positions: Position[]
): number | null {
  const total = positions.reduce((s, p) => s + (p.current_value ?? 0), 0);
  if (!total) return null;
  return ((position.current_value ?? 0) / total) * 100;
}

/** Sector weight of a position's sector as a percentage (0–100). Returns null if total value is 0. */
export function computeSectorWeight(
  position: Position,
  positions: Position[]
): number | null {
  if (!position.sector) return null;
  const total = positions.reduce((s, p) => s + (p.current_value ?? 0), 0);
  if (!total) return null;
  const sectorTotal = positions
    .filter((p) => p.sector === position.sector)
    .reduce((s, p) => s + (p.current_value ?? 0), 0);
  return (sectorTotal / total) * 100;
}

/** Income weight as a percentage (0–100). Returns null if total annual income is 0. */
export function computeIncomeWeight(
  position: Position,
  positions: Position[]
): number | null {
  const total = positions.reduce((s, p) => s + (p.annual_income ?? 0), 0);
  if (!total) return null;
  return ((position.annual_income ?? 0) / total) * 100;
}

/** 1-based rank among positions sorted by current_value descending. Returns null if position not found. */
export function computeRankByValue(
  position: Position,
  positions: Position[]
): number | null {
  const sorted = [...positions].sort(
    (a, b) => (b.current_value ?? 0) - (a.current_value ?? 0)
  );
  const idx = sorted.findIndex((p) => p.id === position.id);
  return idx === -1 ? null : idx + 1;
}

/** 1-based rank among positions sorted by annual_income descending. Returns null if position not found. */
export function computeRankByIncome(
  position: Position,
  positions: Position[]
): number | null {
  const sorted = [...positions].sort(
    (a, b) => (b.annual_income ?? 0) - (a.annual_income ?? 0)
  );
  const idx = sorted.findIndex((p) => p.id === position.id);
  return idx === -1 ? null : idx + 1;
}

/**
 * Format price deviation from SMA as "+2.1% ↑" or "−2.1% ↓".
 * Returns null if price or sma is null/zero.
 */
export function formatSmaDeviation(
  price: number | null | undefined,
  sma: number | null | undefined
): string | null {
  if (!price || !sma) return null;
  const pct = ((price - sma) / sma) * 100;
  const sign = pct >= 0 ? "+" : "−";
  const arrow = pct >= 0 ? "↑" : "↓";
  return `${sign}${Math.abs(pct).toFixed(1)}% ${arrow}`;
}

/** RSI label: < 30 → "oversold", > 70 → "overbought", else → "neutral". Returns null if rsi is null. */
export function rsiLabel(
  rsi: number | null | undefined
): "oversold" | "neutral" | "overbought" | null {
  if (rsi == null) return null;
  if (rsi < 30) return "oversold";
  if (rsi > 70) return "overbought";
  return "neutral";
}

// Re-export React context from portfolio-provider
export {
  PortfolioProvider,
  usePortfolio,
} from "./portfolio-provider";
