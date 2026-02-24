/**
 * Route handler for /api/v1/experiments/:experimentId.
 *
 * Proxies GET, DELETE, and POST (sub-actions like cross-validate, enrich)
 * to the upstream FastAPI backend.
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

type Ctx = { params: Promise<{ experimentId: string }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  const { experimentId } = await ctx.params;
  const url = `${getUpstreamBase()}/api/v1/experiments/${encodeURIComponent(experimentId)}`;

  try {
    const upstream = await fetch(url, { headers: forwardHeaders(req) });
    const body = await upstream.text();
    return new Response(body, {
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

export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { experimentId } = await ctx.params;
  const url = `${getUpstreamBase()}/api/v1/experiments/${encodeURIComponent(experimentId)}`;

  try {
    const upstream = await fetch(url, {
      method: "DELETE",
      headers: forwardHeaders(req),
    });
    const body = await upstream.text();
    return new Response(body, {
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

export async function POST(req: NextRequest, ctx: Ctx) {
  const { experimentId } = await ctx.params;
  const { pathname } = new URL(req.url);
  const suffix = pathname.split(`/experiments/${experimentId}`)[1] || "";
  const url = `${getUpstreamBase()}/api/v1/experiments/${encodeURIComponent(experimentId)}${suffix}`;
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
