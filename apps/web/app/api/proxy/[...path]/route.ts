import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:4000/api";

export async function POST(req: NextRequest) {
  return proxy(req);
}

export async function GET(req: NextRequest) {
  return proxy(req);
}

async function proxy(req: NextRequest) {
  const path = req.nextUrl.pathname.replace("/api/proxy", "");
  const url = `${API_BASE_URL}${path}`;

  try {
    const headers = new Headers();
    headers.set("Content-Type", "application/json");

    let body: string | undefined;
    if (req.method === "POST") {
      body = await req.text();
    }

    const resp = await fetch(url, {
      method: req.method,
      headers,
      body,
    });

    const text = await resp.text();
    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      json = { success: false, error: { message: text || "Proxy error" } };
    }

    return NextResponse.json(json, { status: resp.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Backend unreachable";
    return NextResponse.json(
      { success: false, error: { message: `API 服务不可用: ${msg}` } },
      { status: 502 }
    );
  }
}
