// src/frontend/src/app/api/tax/summary/route.ts
/**
 * GET /api/tax/summary
 * Aggregates NAA Yield across all active portfolios for the dashboard.
 */
import { NextRequest, NextResponse } from "next/server";

const TAX_SERVICE = process.env.TAX_SERVICE_URL ?? "http://tax-optimization-service:8005";
const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get("authorization") ?? "";

  try {
    // 1. Fetch user preferences and all portfolios in parallel
    const [prefResp, portfoliosResp] = await Promise.all([
      fetch(`${ADMIN_PANEL}/api/user/preferences`, {
        headers: { authorization: authHeader },
        signal: AbortSignal.timeout(5_000),
      }),
      fetch(`${ADMIN_PANEL}/api/portfolios`, {
        headers: { authorization: authHeader },
        signal: AbortSignal.timeout(10_000),
      }),
    ]);

    const prefs = prefResp.ok ? await prefResp.json() : {};
    const portfolios: { id: string }[] = portfoliosResp.ok
      ? await portfoliosResp.json()
      : [];

    if (!portfolios.length) {
      return NextResponse.json({
        aggregate_nay: null,
        aggregate_gross_yield: null,
        total_tax_drag: 0,
        total_expense_drag: 0,
        portfolio_count: 0,
      });
    }

    // 2. Call tax service for each portfolio in parallel
    const results = await Promise.allSettled(
      portfolios.map((p) =>
        fetch(`${TAX_SERVICE}/tax/optimize/portfolio`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            authorization: authHeader,
          },
          body: JSON.stringify({
            portfolio_id: p.id,
            annual_income: (prefs as any).annual_income ?? 100000,
            filing_status: (prefs as any).filing_status ?? "SINGLE",
            state_code: (prefs as any).state_code ?? null,
          }),
          signal: AbortSignal.timeout(30_000),
        }).then((r) => (r.ok ? r.json() : null))
      )
    );

    // 3. Aggregate across portfolios using portfolio-level values
    let sumValue = 0;
    let sumNay = 0;
    let sumGross = 0;
    let totalTaxDrag = 0;
    let totalExpenseDrag = 0;
    let portfolioCount = 0;

    for (const result of results) {
      if (result.status !== "fulfilled" || !result.value) continue;
      const data = result.value as any;
      const v = data.total_portfolio_value ?? 0;
      if (v <= 0) continue;
      sumValue += v;
      sumNay += (data.portfolio_nay ?? 0) * v;
      sumGross += (data.portfolio_gross_yield ?? 0) * v;
      totalTaxDrag += data.current_annual_tax_burden ?? 0;
      totalExpenseDrag += (data.holdings_analysis ?? []).reduce(
        (acc: number, h: any) => acc + (h.expense_drag_amount ?? 0),
        0
      );
      portfolioCount++;
    }

    return NextResponse.json({
      aggregate_nay: sumValue > 0 ? sumNay / sumValue : null,
      aggregate_gross_yield: sumValue > 0 ? sumGross / sumValue : null,
      total_tax_drag: Math.round(totalTaxDrag * 100) / 100,
      total_expense_drag: Math.round(totalExpenseDrag * 100) / 100,
      portfolio_count: portfolioCount,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
