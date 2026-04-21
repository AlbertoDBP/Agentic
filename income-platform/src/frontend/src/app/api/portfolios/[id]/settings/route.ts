// src/frontend/src/app/api/portfolios/[id]/settings/route.ts
/**
 * PATCH /api/portfolios/[id]/settings
 * Proxies to admin-panel PATCH /api/portfolios/{id}/settings
 * Accepts: { monthly_income_target, target_yield, benchmark_ticker, ... }
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL_URL =
  process.env.ADMIN_PANEL_URL ?? "http://admin-panel:8100";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token";
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: portfolioId } = await params;
  try {
    const body = await req.text();
    const r = await fetch(
      `${ADMIN_PANEL_URL}/api/portfolios/${portfolioId}/settings`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${serviceToken()}`,
          "Content-Type": "application/json",
        },
        body,
      }
    );
    const data = await r.json();
    return NextResponse.json(data, { status: r.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
