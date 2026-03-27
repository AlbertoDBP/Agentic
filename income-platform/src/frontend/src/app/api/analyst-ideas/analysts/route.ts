/**
 * GET /api/analyst-ideas/analysts
 * Proxies to ADMIN_PANEL/api/agent02/suggestions/analysts
 * Returns analysts with ≥1 active non-expired suggestion — used for filter dropdown.
 */
import { NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function GET() {
  try {
    const upstream = await fetch(`${ADMIN_PANEL}/api/agent02/suggestions/analysts`, {
      signal: AbortSignal.timeout(10_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
