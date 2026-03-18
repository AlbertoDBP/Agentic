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
  "Common Stock": "#3b82f6",
  Preferred: "#8b5cf6",
  BDC: "#06b6d4",
  CEF: "#f59e0b",
  MLP: "#10b981",
  ETF: "#64748b",
  Bond: "#a78bfa",
};
