/**
 * Tests for the SSE proxy streaming behavior.
 *
 * Key requirements:
 * 1. Each upstream SSE event must be flushed immediately to the client
 *    (not batched/buffered).
 * 2. Response headers must disable caching and compression.
 * 3. The proxy must not accumulate multiple events before sending.
 */

import type { NextRequest } from "next/server";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";

// We can't directly import the pipeStream function since it's not exported,
// so we test through proxySSEGet. We mock fetch to control the upstream.

// Since _proxy.ts uses next/server imports, we need to mock those.
vi.mock("next/server", () => ({
  NextResponse: {
    json: vi.fn((body: unknown, init?: { status?: number }) => ({
      body: JSON.stringify(body),
      status: init?.status ?? 200,
    })),
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a ReadableStream that emits chunks with async delay between each. */
function streamFromChunksAsync(
  chunks: string[],
  delayMs = 10,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const chunk of chunks) {
        await new Promise((r) => setTimeout(r, delayMs));
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

/** Read all chunks from a ReadableStream, recording arrival order/timing. */
async function collectChunks(stream: ReadableStream<Uint8Array>): Promise<string[]> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  const chunks: string[] = [];

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(decoder.decode(value, { stream: true }));
  }

  return chunks;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("SSE proxy streaming behavior", () => {
  it("pipes each upstream chunk individually (no batching)", async () => {
    // Simulate 3 SSE events arriving one at a time from upstream
    const sseEvent1 = 'event: delta\ndata: {"token":"Hello"}\n\n';
    const sseEvent2 = 'event: delta\ndata: {"token":" world"}\n\n';
    const sseEvent3 = 'event: message_end\ndata: {"done":true}\n\n';

    const upstreamBody = streamFromChunksAsync([sseEvent1, sseEvent2, sseEvent3], 20);

    // Mock fetch to return our streaming body
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "text/event-stream" }),
        body: upstreamBody,
      })),
    );

    // Dynamically import proxySSEGet
    const { proxySSEGet } = await import("@/app/api/v1/_proxy");

    const mockReq = {
      headers: new Headers({ authorization: "Bearer test" }),
      url: "http://localhost:3000/api/v1/operations/op-1/subscribe",
    } as unknown as NextRequest;

    const response = await proxySSEGet(mockReq, "/api/v1/operations/op-1/subscribe");

    expect(response.status).toBe(200);
    expect(response.body).toBeTruthy();

    // Collect chunks from the piped stream
    const chunks = await collectChunks(response.body!);

    // CRITICAL: Each upstream event should arrive as a separate chunk.
    // If the proxy buffers, all events would arrive in one or two chunks.
    expect(chunks.length).toBeGreaterThanOrEqual(3);
    expect(chunks[0]).toContain("Hello");
    expect(chunks[1]).toContain("world");
    expect(chunks[2]).toContain("done");
  });

  it("response headers disable caching and buffering", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "text/event-stream" }),
        body: streamFromChunksAsync(["data: {}\n\n"]),
      })),
    );

    const { proxySSEGet } = await import("@/app/api/v1/_proxy");

    const mockReq = {
      headers: new Headers({}),
      url: "http://localhost:3000/test",
    } as unknown as NextRequest;

    const response = await proxySSEGet(mockReq, "/test");

    // Verify SSE-critical headers
    expect(response.headers.get("Content-Type")).toBe("text/event-stream");
    expect(response.headers.get("Cache-Control")).toContain("no-cache");
    expect(response.headers.get("Cache-Control")).toContain("no-transform");
    expect(response.headers.get("X-Accel-Buffering")).toBe("no");
    expect(response.headers.get("Connection")).toBe("keep-alive");
  });

  it("proxySSEGet fetch includes cache: no-store to prevent Node.js caching", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "text/event-stream" }),
      body: streamFromChunksAsync(["data: {}\n\n"]),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { proxySSEGet } = await import("@/app/api/v1/_proxy");

    const mockReq = {
      headers: new Headers({}),
      url: "http://localhost:3000/test",
    } as unknown as NextRequest;

    await proxySSEGet(mockReq, "/test");

    // Verify fetch was called with cache: 'no-store'
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ cache: "no-store" }),
    );
  });
});

describe("Next.js config for SSE", () => {
  it("has compression disabled to prevent SSE buffering", async () => {
    // Read the next.config.js and verify compress: false
    // This is critical: Next.js default compress: true uses gzip which
    // buffers the response, breaking token-by-token SSE delivery.
    const fs = await import("node:fs");
    const path = await import("node:path");

    // Walk up from src/lib to find next.config.js at the web app root
    let dir = path.resolve(__dirname, "..");
    let configPath = "";
    for (let i = 0; i < 5; i++) {
      const candidate = path.join(dir, "next.config.js");
      if (fs.existsSync(candidate)) {
        configPath = candidate;
        break;
      }
      dir = path.dirname(dir);
    }

    expect(configPath).not.toBe(""); // must find the config
    const configContent = fs.readFileSync(configPath, "utf-8");

    // The config must explicitly set compress: false
    expect(configContent).toContain("compress");
    expect(configContent).toMatch(/compress\s*:\s*false/);
  });
});
