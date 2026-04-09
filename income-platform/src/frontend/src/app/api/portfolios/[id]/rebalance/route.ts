/**
 * POST /api/portfolios/[id]/rebalance
 * Proxies to Agent 08 POST /rebalance/{id}?save=false
 */
import { NextRequest, NextResponse } from "next/server";

const AGENT08 = process.env.AGENT08_URL ?? "http://localhost:8008";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? "dev-token";
}

const headers = () => ({
  Authorization: `Bearer ${serviceToken()}`,
  "Content-Type": "application/json",
});

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: portfolioId } = await params;
  try {
    const body = await req.json().catch(() => ({}));
    const res = await fetch(
      `${AGENT08}/rebalance/${portfolioId}?save=false`,
      {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          include_tax_impact: true,
          max_proposals: 20,
          ...body,
        }),
        signal: AbortSignal.timeout(30_000),
      }
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
