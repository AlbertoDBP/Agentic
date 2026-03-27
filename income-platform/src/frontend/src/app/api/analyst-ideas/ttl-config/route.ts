/**
 * GET + PUT /api/analyst-ideas/ttl-config
 * Both verbs proxy to ADMIN_PANEL/api/agent02/suggestions/ttl-config.
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
const UPSTREAM = `${ADMIN_PANEL}/api/agent02/suggestions/ttl-config`;

export async function GET() {
  try {
    const upstream = await fetch(UPSTREAM, { signal: AbortSignal.timeout(10_000) });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}

export async function PUT(req: NextRequest) {
  try {
    const body = await req.text();
    const upstream = await fetch(UPSTREAM, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body,
      signal: AbortSignal.timeout(10_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
