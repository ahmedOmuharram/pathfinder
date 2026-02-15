/**
 * Streaming SSE proxy for the /api/v1/chat endpoint.
 *
 * Next.js rewrites (`next.config.js`) proxy API requests to the backend, but
 * the built-in rewrite proxy can buffer the response body, which breaks the
 * real-time delivery of Server-Sent Events (tool calls, deltas, etc.).
 *
 * This route handler replaces the rewrite for /api/v1/chat only.  It forwards
 * the request to the backend and pipes the response body back as a raw
 * ReadableStream, which Next.js route handlers deliver chunk-by-chunk without
 * buffering.
 */

import { type NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
// Streaming responses must not be statically cached.
export const dynamic = "force-dynamic";

function getUpstreamUrl(): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
    /\/+$/,
    "",
  );
  return `${base}/api/v1/chat`;
}

/** Headers we forward from the incoming browser request to the upstream API. */
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
  const upstreamUrl = getUpstreamUrl();
  const body = await req.text();

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: "POST",
      headers: forwardHeaders(req),
      body,
      // @ts-expect-error -- Node 18+ undici option: disables response body buffering
      duplex: "half",
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { detail: `Upstream API unreachable: ${message}` },
      { status: 502 },
    );
  }

  // Non-success: forward the upstream error body as-is.
  if (!upstream.ok || !upstream.body) {
    const errorBody = await upstream.text();
    return new Response(errorBody, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") || "application/json",
      },
    });
  }

  // Stream the SSE body through without buffering.
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
