/**
 * Route Handler for POST /api/scanner/propose
 * Proxies to ADMIN_PANEL/api/scanner/scan/{scan_id}/propose
 * Quick operation — uses 15 s timeout.
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function POST(req: NextRequest) {
  const { scan_id, selected_tickers, target_portfolio_id, position_overrides } = await req.json();

  if (!scan_id || !target_portfolio_id || !selected_tickers?.length) {
    return NextResponse.json({ detail: "scan_id, target_portfolio_id and selected_tickers are required" }, { status: 422 });
  }

  try {
    const upstream = await fetch(`${ADMIN_PANEL}/api/scanner/scan/${scan_id}/propose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_tickers, target_portfolio_id, position_overrides }),
      signal: AbortSignal.timeout(15_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
