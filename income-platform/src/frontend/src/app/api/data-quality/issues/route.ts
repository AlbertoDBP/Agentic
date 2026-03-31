// src/frontend/src/app/api/data-quality/issues/route.ts
import { NextRequest, NextResponse } from "next/server";

const AGENT14 = process.env.AGENT14_URL ?? "http://localhost:8014";
const TOKEN = process.env.SERVICE_JWT_TOKEN ?? "dev-token";

export async function GET(req: NextRequest) {
  try {
    const qs = req.nextUrl.search;
    const upstream = await fetch(`${AGENT14}/data-quality/issues${qs}`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
      signal: AbortSignal.timeout(10_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    return NextResponse.json({ detail: String(err) }, { status: 502 });
  }
}
