import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? "dev-token";
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await req.json();

    const res = await fetch(`${ADMIN_PANEL_URL}/api/positions/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${serviceToken()}`,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10_000),
    });

    const data = res.status === 204 ? null : await res.json().catch(() => null);
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    const res = await fetch(`${ADMIN_PANEL_URL}/api/positions/${id}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${serviceToken()}`,
      },
      signal: AbortSignal.timeout(10_000),
    });

    return new NextResponse(null, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
