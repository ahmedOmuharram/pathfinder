/**
 * Route handler for /api/v1/experiments.
 *
 * - GET: plain JSON proxy (list experiments).
 * - POST: streaming SSE proxy (create experiment) — Next.js rewrites buffer
 *   SSE responses, so we pipe the ReadableStream directly.
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

function forwardHeaders(
  req: NextRequest,
  overrides?: Record<string, string>,
): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...overrides,
  };

  const auth = req.headers.get("authorization");
  if (auth) headers["Authorization"] = auth;

  const cookie = req.headers.get("cookie");
  if (cookie) headers["Cookie"] = cookie;

  return headers;
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const qs = searchParams.toString();
  const url = `${getUpstreamBase()}/api/v1/experiments${qs ? `?${qs}` : ""}`;

  try {
    const upstream = await fetch(url, {
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
      { detail: `Upstream API unreachable: ${message}` },
      { status: 502 },
    );
  }
}

export async function POST(req: NextRequest) {
  const body = await req.text();

  let upstream: Response;
  try {
    upstream = await fetch(`${getUpstreamBase()}/api/v1/experiments`, {
      method: "POST",
      headers: forwardHeaders(req, {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      }),
      body,
      // @ts-expect-error -- Node 18+ undici: disables response body buffering
      duplex: "half",
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { detail: `Upstream API unreachable: ${message}` },
      { status: 502 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const errorBody = await upstream.text();
    return new Response(errorBody, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") || "application/json",
      },
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

export async function DELETE(req: NextRequest) {
  const url = `${getUpstreamBase()}/api/v1/experiments`;
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
      { detail: `Upstream API unreachable: ${message}` },
      { status: 502 },
    );
  }
}
