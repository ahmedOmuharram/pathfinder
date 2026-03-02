/**
 * Shared proxy utilities for Next.js API route handlers.
 *
 * Next.js rewrites can buffer SSE response bodies, breaking real-time
 * delivery. These helpers forward requests to the upstream API and pipe
 * SSE streams through without buffering.
 */

import { type NextRequest, NextResponse } from "next/server";

export function getUpstreamBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
    /\/+$/,
    "",
  );
}

export function forwardHeaders(
  req: NextRequest,
  overrides?: Record<string, string>,
): Record<string, string> {
  const headers: Record<string, string> = { ...overrides };

  const auth = req.headers.get("authorization");
  if (auth) headers["Authorization"] = auth;

  const cookie = req.headers.get("cookie");
  if (cookie) headers["Cookie"] = cookie;

  return headers;
}

/**
 * Proxy a POST request as an SSE stream to the upstream API.
 *
 * Reads the request body, forwards it to `upstreamPath`, and pipes
 * the response back as a raw ReadableStream (no buffering).
 */
export async function proxySSEPost(
  req: NextRequest,
  upstreamPath: string,
): Promise<Response> {
  const url = `${getUpstreamBase()}${upstreamPath}`;
  const body = await req.text();

  let upstream: Response;
  try {
    upstream = await fetch(url, {
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

/**
 * Proxy a plain JSON request (GET, DELETE, etc.) to the upstream API.
 */
export async function proxyJsonRequest(
  req: NextRequest,
  upstreamPath: string,
  options?: { method?: string; includeBody?: boolean },
): Promise<Response> {
  const url = `${getUpstreamBase()}${upstreamPath}`;
  const method = options?.method ?? req.method;

  try {
    const upstream = await fetch(url, {
      method,
      headers: forwardHeaders(req, { Accept: "application/json" }),
      ...(options?.includeBody ? { body: await req.text() } : {}),
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
