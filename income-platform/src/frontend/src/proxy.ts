/**
 * Next.js Middleware — runs before routing.
 *
 * Strategy: all /api/* requests go here first.
 * - If the path matches a compiled Route Handler → pass through (next())
 * - Otherwise → proxy to admin panel
 *
 * This replaces the unreliable next.config.ts fallback rewrite which does NOT
 * consistently respect Route Handlers in Next.js 15/16 standalone mode.
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

/**
 * Paths served by Next.js Route Handlers — do NOT proxy these.
 * Use exact strings or patterns (checked with startsWith / regex).
 */
const NEXTJS_API_PREFIXES = [
  "/api/portfolios/",       // covers /api/portfolios/[id], /api/portfolios/[id]/tax, /api/portfolios/[id]/positions
  "/api/positions/",        // /api/positions/[id]
  "/api/proposals",         // /api/proposals and /api/proposals/[id]/...
  "/api/scanner/",          // /api/scanner/scan, /api/scanner/propose
  "/api/data-quality/",     // /api/data-quality/issues and /api/data-quality/issues/[id]/[action]
  "/api/analyst-ideas/",    // /api/analyst-ideas/analysts, /api/analyst-ideas/ttl-config
  "/api/tax/",              // /api/tax/summary, /api/tax/calculate, /api/tax/harvest, /api/tax/optimize/portfolio
];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Only intercept /api/* paths
  if (!pathname.startsWith("/api/")) return NextResponse.next();

  // If this path has a Route Handler — let Next.js handle it
  for (const prefix of NEXTJS_API_PREFIXES) {
    if (pathname.startsWith(prefix)) return NextResponse.next();
  }

  // Everything else → proxy to admin panel
  const targetUrl = new URL(pathname + request.nextUrl.search, ADMIN_PANEL);
  return NextResponse.rewrite(targetUrl);
}

export const config = {
  matcher: "/api/:path*",
};
