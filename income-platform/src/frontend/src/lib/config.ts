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

export const ASSET_CLASS_COLORS: Record<string, string> = {
  "Common Stock":     "#3b82f6",   // blue
  Preferred:          "#ec4899",   // pink  (was purple — now clearly distinct)
  BDC:                "#06b6d4",   // cyan
  CEF:                "#f59e0b",   // amber
  MLP:                "#10b981",   // emerald
  ETF:                "#8b5cf6",   // violet
  "Covered Call ETF": "#a78bfa",   // light purple
  Bond:               "#f97316",   // orange  (was light-purple — clearly distinct now)
  REIT:               "#84cc16",   // lime
  "Mortgage REIT":    "#facc15",   // yellow
};
