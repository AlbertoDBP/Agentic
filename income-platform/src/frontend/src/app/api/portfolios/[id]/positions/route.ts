import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

function serviceToken(): string {
  return process.env.SERVICE_TOKEN ?? "";
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: portfolioId } = await params;
    const authHeader = req.headers.get("authorization") ?? `Bearer ${serviceToken()}`;

    const res = await fetch(
      `${ADMIN_PANEL_URL}/api/portfolios/${portfolioId}/positions`,
      {
        headers: { Authorization: authHeader },
        signal: AbortSignal.timeout(10_000),
      }
    );

    const data = await res.json().catch(() => null);
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: portfolioId } = await params;
    const body = await req.json();

    const res = await fetch(
      `${ADMIN_PANEL_URL}/api/portfolios/${portfolioId}/positions`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${serviceToken()}`,
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(10_000),
      }
    );

    const data = res.status === 204 ? null : await res.json().catch(() => null);
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
