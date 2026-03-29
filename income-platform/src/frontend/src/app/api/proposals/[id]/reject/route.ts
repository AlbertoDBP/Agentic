/**
 * POST /api/proposals/[id]/reject — reject a proposal via Agent 12
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await req.json().catch(() => ({}));
    const upstream = await fetch(
      `${ADMIN_PANEL}/api/proposals/${params.id}/reject`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(15_000),
      }
    );
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
