// src/frontend/src/app/api/portfolios/[id]/income-by-month/route.ts
/**
 * GET /api/portfolios/[id]/income-by-month
 *
 * Proxies to admin-panel's /api/portfolios/{id}/income-by-month which returns:
 *   { portfolio_id, monthly_totals, positions, annual_total }
 *
 * The admin panel computes monthly distribution from positions using
 * dividend_frequency, ex_div_date, and pay_date — everything the calendar needs.
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL_URL =
  process.env.ADMIN_PANEL_URL ?? "http://admin-panel:8100";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token";
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: portfolioId } = await params;

  try {
    const r = await fetch(
      `${ADMIN_PANEL_URL}/api/portfolios/${portfolioId}/income-by-month`,
      {
        headers: { Authorization: `Bearer ${serviceToken()}` },
        signal: AbortSignal.timeout(10_000),
      }
    );

    if (!r.ok) {
      return NextResponse.json(
        { portfolio_id: portfolioId, monthly_totals: [], positions: [], annual_total: 0 },
        { status: 200 }
      );
    }

    const data = await r.json();
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { portfolio_id: portfolioId, monthly_totals: [], positions: [], annual_total: 0, _error: msg },
      { status: 200 }
    );
  }
}
