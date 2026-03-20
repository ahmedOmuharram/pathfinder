import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import {
  forwardHeaders,
  getUpstreamBase,
  proxyJsonRequest,
  proxySSEGet,
  proxySSEPost,
} from "./_proxy";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeNextRequest(
  url: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> },
): NextRequest {
  return new NextRequest(new URL(url, "http://localhost:3000"), init);
}

function fakeHeaders(h: Record<string, string>): Headers {
  return new Headers(h);
}

function fakeUpstreamResponse(args: {
  ok?: boolean;
  status?: number;
  body?: string | null;
  headers?: Record<string, string>;
}): Response {
  const status = args.status ?? (args.ok === false ? 500 : 200);
  const ok = args.ok ?? status < 400;
  const bodyStr = args.body ?? "";
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    headers: fakeHeaders(args.headers ?? { "content-type": "application/json" }),
    text: vi.fn(async () => bodyStr),
    body: null,
  } as unknown as Response;
}

function fakeSSEUpstreamResponse(args?: {
  ok?: boolean;
  status?: number;
  headers?: Record<string, string>;
}): Response {
  const ok = args?.ok ?? true;
  const status = args?.status ?? 200;

  // Create a simple readable stream for SSE
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode("data: hello\n\n"));
      controller.close();
    },
  });

  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    headers: fakeHeaders(args?.headers ?? { "content-type": "text/event-stream" }),
    body: ok ? stream : null,
    text: vi.fn(async () => "upstream error body"),
  } as unknown as Response;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("_proxy", () => {
  const ORIGINAL_ENV = { ...process.env };

  beforeEach(() => {
    process.env = { ...ORIGINAL_ENV };
    process.env["NEXT_PUBLIC_API_URL"] = "http://api:8000";
  });

  afterEach(() => {
    process.env = { ...ORIGINAL_ENV };
    vi.unstubAllGlobals();
  });

  // -----------------------------------------------------------------------
  // getUpstreamBase
  // -----------------------------------------------------------------------

  describe("getUpstreamBase", () => {
    it("returns NEXT_PUBLIC_API_URL with trailing slashes stripped", () => {
      process.env["NEXT_PUBLIC_API_URL"] = "http://backend:9000///";
      expect(getUpstreamBase()).toBe("http://backend:9000");
    });

    it("falls back to localhost:8000 when env is unset", () => {
      delete process.env["NEXT_PUBLIC_API_URL"];
      expect(getUpstreamBase()).toBe("http://localhost:8000");
    });
  });

  // -----------------------------------------------------------------------
  // forwardHeaders
  // -----------------------------------------------------------------------

  describe("forwardHeaders", () => {
    it("forwards Authorization and Cookie from the incoming request", () => {
      const req = makeNextRequest("/api/v1/test", {
        headers: {
          authorization: "Bearer tok123",
          cookie: "session=abc",
        },
      });
      const result = forwardHeaders(req);
      expect(result["Authorization"]).toBe("Bearer tok123");
      expect(result["Cookie"]).toBe("session=abc");
    });

    it("omits Authorization and Cookie when absent", () => {
      const req = makeNextRequest("/api/v1/test");
      const result = forwardHeaders(req);
      expect(result["Authorization"]).toBeUndefined();
      expect(result["Cookie"]).toBeUndefined();
    });

    it("merges override headers", () => {
      const req = makeNextRequest("/api/v1/test");
      const result = forwardHeaders(req, {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      });
      expect(result["Content-Type"]).toBe("application/json");
      expect(result["Accept"]).toBe("text/event-stream");
    });
  });

  // -----------------------------------------------------------------------
  // proxyJsonRequest
  // -----------------------------------------------------------------------

  describe("proxyJsonRequest", () => {
    it("proxies GET request to the upstream and returns the response", async () => {
      const fetchMock = vi.fn(async () =>
        fakeUpstreamResponse({
          ok: true,
          body: '{"items":[]}',
          headers: { "content-type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/experiments");
      const resp = await proxyJsonRequest(req, "/api/v1/experiments");

      expect(fetchMock).toHaveBeenCalledOnce();
      const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
      expect(url).toBe("http://api:8000/api/v1/experiments");
      expect(init.method).toBe("GET");

      expect(resp.status).toBe(200);
      const text = await resp.text();
      expect(text).toBe('{"items":[]}');
      expect(resp.headers.get("Content-Type")).toBe("application/json");
    });

    it("uses overridden method when specified", async () => {
      const fetchMock = vi.fn(async () =>
        fakeUpstreamResponse({ ok: true, body: "{}" }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/experiments", { method: "GET" });
      await proxyJsonRequest(req, "/api/v1/experiments", { method: "DELETE" });

      const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
      expect(init.method).toBe("DELETE");
    });

    it("includes request body when includeBody is true", async () => {
      const fetchMock = vi.fn(async () =>
        fakeUpstreamResponse({ ok: true, body: '{"id":"123"}' }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/experiments", {
        method: "POST",
        body: '{"name":"test"}',
        headers: { "content-type": "application/json" },
      });
      await proxyJsonRequest(req, "/api/v1/experiments", { includeBody: true });

      const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
      expect(init.body).toBe('{"name":"test"}');
    });

    it("forwards upstream error status codes", async () => {
      const fetchMock = vi.fn(async () =>
        fakeUpstreamResponse({
          ok: false,
          status: 404,
          body: '{"detail":"Not found"}',
          headers: { "content-type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/experiments/xyz");
      const resp = await proxyJsonRequest(req, "/api/v1/experiments/xyz");

      expect(resp.status).toBe(404);
      const text = await resp.text();
      expect(text).toBe('{"detail":"Not found"}');
    });

    it("returns 502 when upstream is unreachable", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => {
          throw new Error("ECONNREFUSED");
        }),
      );

      const req = makeNextRequest("/api/v1/experiments");
      const resp = await proxyJsonRequest(req, "/api/v1/experiments");

      expect(resp.status).toBe(502);
      const json = await resp.json();
      expect(json.detail).toContain("Upstream API unreachable");
      expect(json.detail).toContain("ECONNREFUSED");
    });

    it("forwards auth headers from the incoming request", async () => {
      const fetchMock = vi.fn(async () =>
        fakeUpstreamResponse({ ok: true, body: "{}" }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/experiments", {
        headers: {
          authorization: "Bearer mytoken",
          cookie: "session=xyz",
        },
      });
      await proxyJsonRequest(req, "/api/v1/experiments");

      const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers["Authorization"]).toBe("Bearer mytoken");
      expect(headers["Cookie"]).toBe("session=xyz");
    });
  });

  // -----------------------------------------------------------------------
  // proxySSEGet
  // -----------------------------------------------------------------------

  describe("proxySSEGet", () => {
    it("pipes SSE stream with correct headers on success", async () => {
      const fetchMock = vi.fn(async () => fakeSSEUpstreamResponse());
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/operations/123/subscribe");
      const resp = await proxySSEGet(req, "/api/v1/operations/123/subscribe");

      expect(resp.status).toBe(200);
      expect(resp.headers.get("Content-Type")).toBe("text/event-stream");
      expect(resp.headers.get("Cache-Control")).toBe("no-cache, no-transform");
      expect(resp.headers.get("X-Accel-Buffering")).toBe("no");

      // Verify the stream is readable
      const reader = resp.body!.getReader();
      const { value } = await reader.read();
      const decoded = new TextDecoder().decode(value);
      expect(decoded).toBe("data: hello\n\n");
    });

    it("returns upstream error when upstream responds with non-OK", async () => {
      const fetchMock = vi.fn(async () =>
        fakeSSEUpstreamResponse({ ok: false, status: 404 }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/operations/bad/subscribe");
      const resp = await proxySSEGet(req, "/api/v1/operations/bad/subscribe");

      expect(resp.status).toBe(404);
      const text = await resp.text();
      expect(text).toBe("upstream error body");
    });

    it("returns 502 when upstream is unreachable", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => {
          throw new TypeError("fetch failed");
        }),
      );

      const req = makeNextRequest("/api/v1/operations/123/subscribe");
      const resp = await proxySSEGet(req, "/api/v1/operations/123/subscribe");

      expect(resp.status).toBe(502);
      const json = await resp.json();
      expect(json.detail).toContain("Upstream API unreachable");
      expect(json.detail).toContain("fetch failed");
    });

    it("sends Accept: text/event-stream header upstream", async () => {
      const fetchMock = vi.fn(async () => fakeSSEUpstreamResponse());
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/operations/123/subscribe");
      await proxySSEGet(req, "/api/v1/operations/123/subscribe");

      const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers["Accept"]).toBe("text/event-stream");
    });
  });

  // -----------------------------------------------------------------------
  // proxySSEPost
  // -----------------------------------------------------------------------

  describe("proxySSEPost", () => {
    it("pipes SSE stream with correct headers on success", async () => {
      const fetchMock = vi.fn(async () => fakeSSEUpstreamResponse());
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/chat", {
        method: "POST",
        body: '{"prompt":"hello"}',
        headers: { "content-type": "application/json" },
      });
      const resp = await proxySSEPost(req, "/api/v1/chat");

      expect(resp.status).toBe(200);
      expect(resp.headers.get("Content-Type")).toBe("text/event-stream");
      expect(resp.headers.get("Cache-Control")).toBe("no-cache, no-transform");
    });

    it("forwards the request body to upstream", async () => {
      const fetchMock = vi.fn(async () => fakeSSEUpstreamResponse());
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/chat", {
        method: "POST",
        body: '{"prompt":"hello"}',
        headers: { "content-type": "application/json" },
      });
      await proxySSEPost(req, "/api/v1/chat");

      const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
      expect(init.body).toBe('{"prompt":"hello"}');
      expect(init.method).toBe("POST");
    });

    it("returns upstream error when upstream responds with non-OK", async () => {
      const fetchMock = vi.fn(async () =>
        fakeSSEUpstreamResponse({ ok: false, status: 422 }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const req = makeNextRequest("/api/v1/chat", {
        method: "POST",
        body: "{}",
        headers: { "content-type": "application/json" },
      });
      const resp = await proxySSEPost(req, "/api/v1/chat");

      expect(resp.status).toBe(422);
    });

    it("returns 502 when upstream is unreachable", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => {
          throw new Error("connection refused");
        }),
      );

      const req = makeNextRequest("/api/v1/chat", {
        method: "POST",
        body: "{}",
        headers: { "content-type": "application/json" },
      });
      const resp = await proxySSEPost(req, "/api/v1/chat");

      expect(resp.status).toBe(502);
      const json = await resp.json();
      expect(json.detail).toContain("Upstream API unreachable");
    });
  });
});
