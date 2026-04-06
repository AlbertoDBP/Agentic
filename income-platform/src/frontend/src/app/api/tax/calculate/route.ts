import { NextRequest, NextResponse } from "next/server";

const TAX_SERVICE = process.env.TAX_SERVICE_URL ?? "http://tax-optimization-service:8005";
const SERVICE_TOKEN = process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(`${TAX_SERVICE}/tax/calculate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${SERVICE_TOKEN}`,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15_000),
    });
    const data = await res.json().catch(() => null);
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
