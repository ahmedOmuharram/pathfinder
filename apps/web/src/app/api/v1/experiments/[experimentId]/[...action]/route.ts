/**
 * Catch-all route for /api/v1/experiments/:experimentId/:action
 * (e.g. cross-validate, enrich). Proxies POST to the upstream backend.
 */

import { type NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function getUpstreamBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
    /\/+$/,
    "",
  );
}

function forwardHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const auth = req.headers.get("authorization");
  if (auth) headers["Authorization"] = auth;
  const cookie = req.headers.get("cookie");
  if (cookie) headers["Cookie"] = cookie;
  return headers;
}

type Ctx = { params: Promise<{ experimentId: string; action: string[] }> };

export async function POST(req: NextRequest, ctx: Ctx) {
  const { experimentId, action } = await ctx.params;
  const actionPath = action.join("/");
  const url = `${getUpstreamBase()}/api/v1/experiments/${encodeURIComponent(experimentId)}/${actionPath}`;
  const body = await req.text();

  try {
    const upstream = await fetch(url, {
      method: "POST",
      headers: forwardHeaders(req),
      body,
    });
    const respBody = await upstream.text();
    return new Response(respBody, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") || "application/json",
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { detail: `Upstream unreachable: ${message}` },
      { status: 502 },
    );
  }
}
