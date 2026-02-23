/**
 * Streaming SSE proxy for the /api/v1/experiments/ai-assist endpoint.
 *
 * Same buffering workaround as the experiment creation proxy — see
 * ../route.ts for the full explanation.
 */

import { type NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function getUpstreamUrl(): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
    /\/+$/,
    "",
  );
  return `${base}/api/v1/experiments/ai-assist`;
}

function forwardHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };

  const auth = req.headers.get("authorization");
  if (auth) headers["Authorization"] = auth;

  const cookie = req.headers.get("cookie");
  if (cookie) headers["Cookie"] = cookie;

  return headers;
}

export async function POST(req: NextRequest) {
  const body = await req.text();

  let upstream: Response;
  try {
    upstream = await fetch(getUpstreamUrl(), {
      method: "POST",
      headers: forwardHeaders(req),
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
