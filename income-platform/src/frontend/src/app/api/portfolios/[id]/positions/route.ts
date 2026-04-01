import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? "dev-token";
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
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
}
