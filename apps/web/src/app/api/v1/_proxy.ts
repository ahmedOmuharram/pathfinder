/**
 * Shared proxy utilities for Next.js API route handlers.
 *
 * Next.js rewrites can buffer SSE response bodies, breaking real-time
 * delivery. These helpers forward requests to the upstream API and pipe
 * SSE streams through without buffering.
 */

import { type NextRequest, NextResponse } from "next/server";

export function getUpstreamBase(): string {
  return (process.env["NEXT_PUBLIC_API_URL"] ?? "http://localhost:8000").replace(
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
  if (auth !== null) headers["Authorization"] = auth;

  const cookie = req.headers.get("cookie");
  if (cookie !== null) headers["Cookie"] = cookie;

  return headers;
}

/**
 * Create a new ReadableStream that pipes from an upstream reader chunk by
 * chunk.  Passing `upstream.body` directly to `new Response()` can cause
 * Node.js / Next.js to buffer the entire body before forwarding to the
 * client.  This explicit pipe ensures each SSE event is flushed immediately.
 */
function pipeStream(upstream: ReadableStream<Uint8Array>): ReadableStream<Uint8Array> {
  const reader = upstream.getReader();
  return new ReadableStream<Uint8Array>({
    async pull(controller) {
      try {
        const { done, value } = await reader.read();
        if (done) {
          controller.close();
          return;
        }
        controller.enqueue(value);
      } catch (err) {
        controller.error(err);
      }
    },
    cancel() {
      void reader.cancel();
    },
  });
}

const SSE_RESPONSE_HEADERS = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache, no-transform",
  "Content-Encoding": "identity",
  Connection: "keep-alive",
  "X-Accel-Buffering": "no",
} as const;

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
    const fetchOptions: RequestInit & { duplex: string } = {
      method: "POST",
      headers: forwardHeaders(req, {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      }),
      body,
      duplex: "half",
    };
    upstream = await fetch(url, fetchOptions);
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
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  }

  return new Response(pipeStream(upstream.body), {
    status: 200,
    headers: SSE_RESPONSE_HEADERS,
  });
}

/**
 * Proxy a GET request as an SSE stream to the upstream API.
 */
export async function proxySSEGet(
  req: NextRequest,
  upstreamPath: string,
): Promise<Response> {
  const url = `${getUpstreamBase()}${upstreamPath}`;

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: "GET",
      headers: forwardHeaders(req, {
        Accept: "text/event-stream",
      }),
      // Prevent Node.js / Next.js from caching or buffering the response.
      cache: "no-store",
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
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  }

  return new Response(pipeStream(upstream.body), {
    status: 200,
    headers: SSE_RESPONSE_HEADERS,
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
      headers: forwardHeaders(req, {
        Accept: "application/json",
        ...(options?.includeBody === true
          ? { "Content-Type": "application/json" }
          : {}),
      }),
      ...(options?.includeBody === true ? { body: await req.text() } : {}),
    });
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
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
