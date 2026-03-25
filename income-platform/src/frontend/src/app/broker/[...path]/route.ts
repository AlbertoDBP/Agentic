import { NextRequest, NextResponse } from "next/server";

const BROKER_URL = process.env.BROKER_URL || "http://localhost:8013";
const SERVICE_TOKEN = process.env.SERVICE_TOKEN || "";

async function handler(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const url = `${BROKER_URL}/broker/${path.join("/")}`;
  const qs = req.nextUrl.search;
  const fullUrl = qs ? url + qs : url;

  const res = await fetch(fullUrl, {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${SERVICE_TOKEN}`,
    },
    body: req.method !== "GET" && req.method !== "HEAD" ? await req.text() : undefined,
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
