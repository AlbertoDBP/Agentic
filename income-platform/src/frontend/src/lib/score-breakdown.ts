export type FactorEntry = { value: number | null; score: number; max: number };
export type Directionality = "Strong" | "Moderate" | "Weak" | "Critical";

export function directionality(score: number, max: number): Directionality {
  if (max <= 0) return "Weak";
  const ratio = score / max;
  if (ratio >= 0.85) return "Strong";
  if (ratio >= 0.65) return "Moderate";
  if (ratio >= 0.40) return "Weak";
  return "Critical";
}

export const DIRECTIONALITY_COLOR: Record<Directionality, string> = {
  Strong:   "text-green-400 bg-green-950/30",
  Moderate: "text-yellow-400 bg-yellow-950/30",
  Weak:     "text-amber-400 bg-amber-950/30",
  Critical: "text-red-400 bg-red-950/30",
};

export const DIRECTIONALITY_BAR: Record<Directionality, string> = {
  Strong:   "bg-green-500",
  Moderate: "bg-yellow-500",
  Weak:     "bg-amber-500",
  Critical: "bg-red-500",
};

export const FACTOR_LABEL: Record<string, string> = {
  payout_sustainability: "Payout Sustainability",
  yield_vs_market:       "Yield vs Market",
  fcf_coverage:          "FCF Coverage",
  debt_safety:           "Debt Safety",
  dividend_consistency:  "Dividend Consistency",
  volatility_score:      "Volatility",
  price_momentum:        "Price Momentum",
  price_range_position:  "52W Range Position",
};

export const FACTOR_PILLAR: Record<string, "INC" | "DUR" | "IES"> = {
  payout_sustainability: "INC",
  yield_vs_market:       "INC",
  fcf_coverage:          "INC",
  debt_safety:           "DUR",
  dividend_consistency:  "DUR",
  volatility_score:      "DUR",
  price_momentum:        "IES",
  price_range_position:  "IES",
};

export const PILLAR_FACTORS: Record<"INC" | "DUR" | "IES", string[]> = {
  INC: ["payout_sustainability", "yield_vs_market", "fcf_coverage"],
  DUR: ["debt_safety", "dividend_consistency", "volatility_score"],
  IES: ["price_momentum", "price_range_position"],
};

export const PILLAR_LABEL: Record<"INC" | "DUR" | "IES", string> = {
  INC: "Income Pillar",
  DUR: "Durability Pillar",
  IES: "IES Pillar (Technical)",
};
