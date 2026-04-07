// src/frontend/src/app/api/alerts/route.ts
/**
 * GET  /api/alerts?portfolio_id=<uuid>&status=ACTIVE
 *   → filters unified_alerts to symbols held in the portfolio
 *
 * POST /api/alerts/[id]/resolve is handled by the admin-panel middleware;
 *      this route only handles GET (list) to add portfolio filtering.
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://admin-panel:8100";

function serviceToken(): string {
  return process.env.SERVICE_TOKEN ?? process.env.SERVICE_JWT_TOKEN ?? "dev-token";
}

function authHeaders() {
  return {
    Authorization: `Bearer ${serviceToken()}`,
    "Content-Type": "application/json",
  };
}

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const portfolioId = searchParams.get("portfolio_id");

  try {
    // 1. Fetch all active alerts from agent-11 via admin panel
    const alertsRes = await fetch(`${ADMIN_PANEL}/api/alerts`, {
      headers: authHeaders(),
      signal: AbortSignal.timeout(8_000),
    });

    if (!alertsRes.ok) {
      return NextResponse.json({ alerts: [], _error: `alerts fetch ${alertsRes.status}` });
    }

    let alerts: Record<string, unknown>[] = await alertsRes.json();
    if (!Array.isArray(alerts)) {
      alerts = (alerts as { alerts?: Record<string, unknown>[] }).alerts ?? [];
    }

    // 2. If portfolio_id given, filter to symbols held in that portfolio
    if (portfolioId) {
      const posRes = await fetch(
        `${ADMIN_PANEL}/api/portfolios/${portfolioId}/positions`,
        { headers: authHeaders(), signal: AbortSignal.timeout(5_000) }
      ).catch(() => null);

      if (posRes && posRes.ok) {
        const posData = await posRes.json();
        const positions: { symbol: string }[] = Array.isArray(posData)
          ? posData
          : posData.positions ?? posData.items ?? [];
        const heldSymbols = new Set(positions.map((p) => p.symbol?.toUpperCase()));

        if (heldSymbols.size > 0) {
          alerts = alerts.filter((a) =>
            heldSymbols.has(String(a.symbol ?? "").toUpperCase())
          );
        }
      }
    }

    return NextResponse.json({ alerts });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ alerts: [], _error: msg });
  }
}
