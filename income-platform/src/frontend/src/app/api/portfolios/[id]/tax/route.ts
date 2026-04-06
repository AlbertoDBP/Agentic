// src/frontend/src/app/api/portfolios/[id]/tax/route.ts
/**
 * GET /api/portfolios/[id]/tax
 * Fetches user_preferences, calls tax service /tax/optimize/portfolio,
 * remaps holdings_analysis → holdings for the frontend.
 */
import { NextRequest, NextResponse } from "next/server";

const TAX_SERVICE = process.env.TAX_SERVICE_URL ?? "http://tax-optimization-service:8005";
const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
const SERVICE_TOKEN = process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: portfolioId } = await params;
  const authHeader = req.headers.get("authorization") ?? "";
  console.log(`[tax-route] GET /api/portfolios/${portfolioId}/tax — token: ${authHeader ? "present" : "missing"}`);

  try {
    // 1. Fetch user tax preferences
    const prefResp = await fetch(`${ADMIN_PANEL}/api/user/preferences`, {
      headers: { authorization: authHeader },
      signal: AbortSignal.timeout(5_000),
    });
    const prefs = prefResp.ok ? await prefResp.json() : {};
    console.log(`[tax-route] prefs status: ${prefResp.status}`);

    // 2. Call tax service optimize/portfolio (use service token — tax service
    //    uses its own JWT_SECRET, separate from the admin-panel user JWT)
    const taxResp = await fetch(`${TAX_SERVICE}/tax/optimize/portfolio`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        authorization: `Bearer ${SERVICE_TOKEN}`,
      },
      body: JSON.stringify({
        portfolio_id: portfolioId,
        annual_income: prefs.annual_income ?? 100000,
        filing_status: prefs.filing_status ?? "SINGLE",
        state_code: prefs.state_code ?? null,
      }),
      signal: AbortSignal.timeout(30_000),
    });
    console.log(`[tax-route] tax service status: ${taxResp.status} for portfolio ${portfolioId}`);

    if (!taxResp.ok) {
      const err = await taxResp.json().catch(() => ({}));
      const detail = (err as { detail?: string }).detail ?? "Tax service error";
      console.log(`[tax-route] tax service error: ${detail}`);
      return NextResponse.json({ detail }, { status: taxResp.status });
    }

    const taxData = await taxResp.json();

    // 3. Remap: holdings_analysis → holdings
    const response = {
      portfolio_gross_yield: (taxData as any).portfolio_gross_yield ?? 0,
      portfolio_nay: (taxData as any).portfolio_nay ?? 0,
      current_annual_tax_burden: (taxData as any).current_annual_tax_burden ?? 0,
      estimated_annual_savings: (taxData as any).estimated_annual_savings ?? 0,
      suboptimal_count: (taxData as any).suboptimal_count ?? 0,
      holdings: (taxData as any).holdings_analysis ?? [],
      tax_profile: {
        annual_income: (prefs as any).annual_income ?? 100000,
        filing_status: (prefs as any).filing_status ?? "SINGLE",
        state_code: (prefs as any).state_code ?? "",
      },
    };

    return NextResponse.json(response);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
