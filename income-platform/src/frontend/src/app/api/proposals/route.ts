/**
 * /api/proposals
 *   GET  — list proposals from Agent 12
 *   POST — generate proposal(s) via Agent 12
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function GET(req: NextRequest) {
  const query = req.nextUrl.searchParams.toString();
  const url = `${ADMIN_PANEL}/api/proposals${query ? `?${query}` : ""}`;
  try {
    const upstream = await fetch(url, { signal: AbortSignal.timeout(15_000) });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const upstream = await fetch(`${ADMIN_PANEL}/api/proposals/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
