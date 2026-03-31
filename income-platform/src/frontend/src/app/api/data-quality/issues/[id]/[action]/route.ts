// src/frontend/src/app/api/data-quality/issues/[id]/[action]/route.ts
import { NextRequest, NextResponse } from "next/server";

const AGENT14 = process.env.AGENT14_URL ?? "http://localhost:8014";
const TOKEN = process.env.SERVICE_JWT_TOKEN ?? "dev-token";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string; action: string }> }
) {
  try {
    const { id, action } = await params;
    const ALLOWED_ACTIONS = new Set(["retry", "mark-na", "reclassify"]);
    if (!ALLOWED_ACTIONS.has(action)) {
      return NextResponse.json({ detail: "Invalid action" }, { status: 400 });
    }
    const upstream = await fetch(
      `${AGENT14}/data-quality/issues/${id}/${action}`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${TOKEN}` },
        signal: AbortSignal.timeout(10_000),
      }
    );
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    return NextResponse.json({ detail: String(err) }, { status: 502 });
  }
}
