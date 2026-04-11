// src/frontend/src/app/api/broker/portfolios/[id]/summary/route.ts
import { NextRequest, NextResponse } from "next/server";

const BROKER_URL = process.env.BROKER_URL ?? "http://broker-service:8013";

function serviceToken() {
  return process.env.SERVICE_TOKEN ?? "";
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const res = await fetch(`${BROKER_URL}/broker/portfolios/${id}/summary`, {
      headers: { Authorization: `Bearer ${serviceToken()}` },
      signal: AbortSignal.timeout(10_000),
    });
    const data = await res.json().catch(() => null);
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
