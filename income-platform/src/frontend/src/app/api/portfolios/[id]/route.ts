// src/frontend/src/app/api/portfolios/[id]/route.ts
/**
 * GET /api/portfolios/[id]  — data quality health from agent-14
 * PATCH /api/portfolios/[id] — update portfolio fields (proxied to admin panel)
 */
import { NextRequest, NextResponse } from "next/server";

const AGENT14 = process.env.AGENT14_URL ?? "http://localhost:8014";
const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? "dev-token";
}

const headers = () => ({
  Authorization: `Bearer ${serviceToken()}`,
  "Content-Type": "application/json",
});

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: portfolioId } = await params;

  try {
    const [gateRes, refreshRes] = await Promise.allSettled([
      fetch(`${AGENT14}/data-quality/gate/${portfolioId}`, {
        headers: headers(),
        signal: AbortSignal.timeout(5_000),
      }),
      fetch(`${AGENT14}/data-quality/refresh-log/${portfolioId}`, {
        headers: headers(),
        signal: AbortSignal.timeout(5_000),
      }),
    ]);

    const gate =
      gateRes.status === "fulfilled" && gateRes.value.ok
        ? await gateRes.value.json()
        : null;

    const refreshLog =
      refreshRes.status === "fulfilled" && refreshRes.value.ok
        ? await refreshRes.value.json()
        : null;

    return NextResponse.json({ gate, refresh_log: refreshLog });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: portfolioId } = await params;
  try {
    const body = await req.text();
    const res = await fetch(`${ADMIN_PANEL}/api/portfolios/${portfolioId}`, {
      method: "PATCH",
      headers: headers(),
      body,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
