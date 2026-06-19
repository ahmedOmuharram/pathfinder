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

vi.mock("next/server", () => ({
  NextResponse: {
    json: vi.fn((body: unknown, init?: { status?: number }) => ({
      body: JSON.stringify(body),
      status: init?.status ?? 200,
    })),
  },
}));

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

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("SSE proxy streaming behavior", () => {
  it("pipes each upstream chunk individually (no batching)", async () => {
    const sseEvent1 = 'event: delta\ndata: {"token":"Hello"}\n\n';
    const sseEvent2 = 'event: delta\ndata: {"token":" world"}\n\n';
    const sseEvent3 = 'event: message_end\ndata: {"done":true}\n\n';

    const upstreamBody = streamFromChunksAsync([sseEvent1, sseEvent2, sseEvent3], 20);

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "text/event-stream" }),
        body: upstreamBody,
      })),
    );

    const { proxySSEGet } = await import("@/app/api/v1/_proxy");

    const mockReq = {
      headers: new Headers({ authorization: "Bearer test" }),
      url: "http://localhost:3000/api/v1/conversations/c-1/tasks/t-1/events",
    } as unknown as NextRequest;

    const response = await proxySSEGet(
      mockReq,
      "/api/v1/conversations/c-1/tasks/t-1/events",
    );

    expect(response.status).toBe(200);

    const chunks = await collectChunks(response.body!);

    expect(chunks).toEqual([sseEvent1, sseEvent2, sseEvent3]);
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

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ cache: "no-store" }),
    );
  });
});

describe("JSON proxy behavior", () => {
  it("forwards upstream set-cookie headers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response('{"ok":true}', {
            status: 200,
            headers: {
              "content-type": "application/json",
              "set-cookie": "pathfinder-auth=test; Path=/; HttpOnly",
            },
          }),
      ),
    );

    const { proxyJsonRequest } = await import("@/app/api/v1/_proxy");

    const mockReq = {
      headers: new Headers({}),
      method: "POST",
      url: "http://localhost:3000/api/v1/dev/login",
    } as unknown as NextRequest;

    const response = await proxyJsonRequest(mockReq, "/api/v1/dev/login");

    expect(response.headers.get("set-cookie")).toContain("pathfinder-auth=test");
  });
});

describe("Next.js config for SSE", () => {
  it("has compression disabled to prevent SSE buffering", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");

    const configPath = path.resolve(__dirname, "../..", "next.config.ts");
    expect(fs.existsSync(configPath)).toBe(true);
    const configContent = fs.readFileSync(configPath, "utf-8");

    expect(configContent).toContain("compress");
    expect(configContent).toMatch(/compress\s*:\s*false/);
  });
});
