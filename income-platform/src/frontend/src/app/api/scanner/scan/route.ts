/**
 * Route Handler for POST /api/scanner/scan
 *
 * Replaces the Next.js rewrite for this endpoint to avoid the ~30s proxy
 * timeout. Scans over the full 73-symbol universe can take up to 90 seconds
 * on a cold cache (first run of the day); this handler waits up to 120 s.
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function POST(req: NextRequest) {
  let body: string;
  try {
    body = await req.text();
  } catch {
    return NextResponse.json({ detail: "Failed to read request body" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${ADMIN_PANEL}/api/scanner/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      signal: AbortSignal.timeout(120_000),
    });

    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const isTimeout = msg.includes("TimeoutError") || msg.includes("AbortError") || msg.includes("timed out");
    return NextResponse.json(
      { detail: isTimeout ? "Scan timed out — try again (market data is now cached)" : msg },
      { status: isTimeout ? 504 : 502 }
    );
  }
}
