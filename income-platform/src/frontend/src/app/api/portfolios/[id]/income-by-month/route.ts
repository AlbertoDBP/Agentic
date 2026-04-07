// src/frontend/src/app/api/portfolios/[id]/income-by-month/route.ts
/**
 * GET /api/portfolios/[id]/income-by-month
 *
 * Returns monthly income projection in the shape the frontend expects:
 *   { portfolio_id, monthly_totals: [{month, month_num, total}], annual_total }
 *
 * Strategy:
 *   1. Try GET /projection/{id}/latest from the income-projection-service.
 *   2. If no stored projection (404), trigger POST /projection/{id} to generate one.
 *   3. Transform monthly_cashflow [{month: 1, projected_income: X}] → named months.
 *   4. Fallback: if the projection service is down or has no data, return zeros.
 */
import { NextRequest, NextResponse } from "next/server";

const PROJECTION_URL =
  process.env.PROJECTION_SERVICE_URL ?? "http://income-projection-service:8009";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token";
}

function authHeaders() {
  return {
    Authorization: `Bearer ${serviceToken()}`,
    "Content-Type": "application/json",
  };
}

/** Normalise the monthly_cashflow array from the projection service. */
function toMonthlyTotals(
  cashflow: { month: number; projected_income: number }[] | null | undefined
): { month: string; month_num: number; total: number }[] {
  if (!cashflow || cashflow.length === 0) return [];
  return cashflow
    .filter((cf) => cf.month >= 1 && cf.month <= 12)
    .map((cf) => ({
      month: MONTH_NAMES[cf.month - 1],
      month_num: cf.month,
      total: Math.round((cf.projected_income ?? 0) * 100) / 100,
    }))
    .sort((a, b) => a.month_num - b.month_num);
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: portfolioId } = await params;

  try {
    // 1. Try stored projection first
    let projection: Record<string, unknown> | null = null;

    const latestRes = await fetch(
      `${PROJECTION_URL}/projection/${portfolioId}/latest`,
      { headers: authHeaders(), signal: AbortSignal.timeout(8_000) }
    );

    if (latestRes.ok) {
      projection = await latestRes.json() as Record<string, unknown>;
    } else if (latestRes.status === 404) {
      // 2. No stored projection — generate one now
      const postRes = await fetch(
        `${PROJECTION_URL}/projection/${portfolioId}?horizon_months=12&yield_source=forward`,
        { method: "POST", headers: authHeaders(), signal: AbortSignal.timeout(20_000) }
      );
      if (postRes.ok) {
        projection = await postRes.json() as Record<string, unknown>;
      }
    }

    if (!projection) {
      // Service unavailable or portfolio has no positions — return empty shape
      return NextResponse.json({
        portfolio_id: portfolioId,
        monthly_totals: [],
        annual_total: 0,
      });
    }

    const cashflow = (
      (projection.monthly_cashflow as { month: number; projected_income: number }[]) ??
      ((projection.metadata_ as Record<string, unknown>)?.monthly_cashflow as
        | { month: number; projected_income: number }[]
        | undefined)
    );

    const monthlyTotals = toMonthlyTotals(cashflow);
    const annualTotal =
      typeof projection.total_projected_annual === "number"
        ? projection.total_projected_annual
        : monthlyTotals.reduce((s, m) => s + m.total, 0) * (12 / (monthlyTotals.length || 12));

    return NextResponse.json({
      portfolio_id: portfolioId,
      monthly_totals: monthlyTotals,
      annual_total: Math.round(annualTotal * 100) / 100,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    // Return empty rather than 502 so the UI shows "no data" instead of broken
    return NextResponse.json(
      { portfolio_id: portfolioId, monthly_totals: [], annual_total: 0, _error: msg },
      { status: 200 }
    );
  }
}
