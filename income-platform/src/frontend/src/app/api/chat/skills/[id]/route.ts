import { NextRequest, NextResponse } from "next/server";
const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
function svcToken() { return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token"; }

export async function DELETE(_: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/skills/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${svcToken()}` },
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
