import { NextRequest, NextResponse } from "next/server";
const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
function svcToken() { return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token"; }
const hdrs = () => ({ Authorization: `Bearer ${svcToken()}`, "Content-Type": "application/json" });

export async function GET() {
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/skills`, { headers: hdrs() });
  return NextResponse.json(await r.json(), { status: r.status });
}
export async function POST(req: NextRequest) {
  const body = await req.json();
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/skills`, {
    method: "POST", headers: hdrs(), body: JSON.stringify(body),
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
