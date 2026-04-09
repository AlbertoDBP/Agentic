import { NextRequest, NextResponse } from "next/server";
const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
function svcToken() { return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token"; }

export async function GET() {
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads`,
    { headers: { Authorization: `Bearer ${svcToken()}` } });
  return NextResponse.json(await r.json(), { status: r.status });
}
export async function POST(req: NextRequest) {
  const body = await req.json();
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads`, {
    method: "POST",
    headers: { Authorization: `Bearer ${svcToken()}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
