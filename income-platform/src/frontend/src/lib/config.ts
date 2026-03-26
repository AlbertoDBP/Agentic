// API calls go through Next.js rewrites (/api/* → admin panel).
// Use empty string so all fetch() calls use relative paths (same origin).
// For local dev without Docker, set NEXT_PUBLIC_API_BASE to override.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE ?? "";

export const POLLING = {
  dashboard: 60_000,
  alerts: 30_000,
  proposals: 30_000,
  portfolio: 300_000,
} as const;

export const DESIGN_TOKENS = {
  // HHS status colors — traffic-light: STRONG=green, GOOD=lime, WATCH=amber, CONCERN/UNSAFE=red
  HHS_STATUS_COLORS: {
    STRONG:       "text-green-400",
    GOOD:         "text-lime-400",
    WATCH:        "text-amber-400",
    CONCERN:      "text-red-400",
    UNSAFE:       "text-red-400",
    INSUFFICIENT: "text-slate-500",
  } as Record<string, string>,

  // Asset-class colors for concentration bars (matches spec §6.1)
  ASSET_CLASS_COLORS: {
    BDC:                "bg-purple-400",
    EQUITY_REIT:        "bg-blue-500",
    MORTGAGE_REIT:      "bg-blue-400",
    COVERED_CALL_ETF:   "bg-amber-400",
    MLP:                "bg-teal-400",
    DIVIDEND_STOCK:     "bg-green-500",
    BOND:               "bg-yellow-200",
    PREFERRED_STOCK:    "bg-pink-400",
    UNKNOWN:            "bg-slate-600",
    // Sectors
    "Financial Services":     "bg-blue-500",
    "Real Estate":            "bg-green-500",
    "Energy":                 "bg-orange-400",
    "Utilities":              "bg-yellow-400",
    "Healthcare":             "bg-red-400",
    "Technology":             "bg-purple-400",
    "Consumer Defensive":     "bg-teal-400",
    "Consumer Cyclical":      "bg-pink-400",
    "Industrials":            "bg-slate-400",
    "Communication Services": "bg-cyan-400",
    "Other":                  "bg-slate-600",
  } as Record<string, string>,
} as const;

export const ASSET_CLASS_COLORS: Record<string, string> = {
  // Human-readable labels (used in edit dropdowns / older DB entries)
  "Common Stock": "#3b82f6",
  Preferred:      "#ec4899",
  BDC:            "#06b6d4",
  CEF:            "#f59e0b",
  MLP:            "#10b981",
  ETF:            "#8b5cf6",
  Bond:           "#f97316",
  // Taxonomy enum values stored by classification service
  DIVIDEND_STOCK:   "#3b82f6",
  PREFERRED_STOCK:  "#ec4899",
  COVERED_CALL_ETF: "#a78bfa",
  BOND:             "#f97316",
  EQUITY_REIT:      "#84cc16",
  MORTGAGE_REIT:    "#facc15",
};
