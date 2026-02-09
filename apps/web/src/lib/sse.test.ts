import { describe, expect, it, vi, afterEach } from "vitest";
import { streamSSE } from "./sse";

function makeHeaders(init: Record<string, string>) {
  const normalized = new Map<string, string>();
  for (const [k, v] of Object.entries(init)) normalized.set(k.toLowerCase(), v);
  return {
    get(name: string) {
      return normalized.get(name.toLowerCase()) ?? null;
    },
  } as Headers;
}

function streamFromStrings(parts: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const p of parts) controller.enqueue(encoder.encode(p));
      controller.close();
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("lib/sse", () => {
  it("parses SSE chunks into events with type + data", async () => {
    const events: Array<{ type: string; data: string }> = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          headers: makeHeaders({ "content-type": "text/event-stream" }),
          body: streamFromStrings([
            // event with explicit type
            'event: message_start\ndata: {"ok":true}\n\n',
            // multiline data, implicit type defaults to "message"
            "data: line1\ndata: line2\n\n",
            // keep-alive (no data) should be ignored
            "event: ping\n\n",
          ]),
        } as unknown as Response;
      }),
    );

    await streamSSE(
      "/api/v1/chat",
      { method: "POST", body: { x: 1 } },
      {
        onEvent: (evt) => events.push(evt),
      },
    );

    expect(events).toEqual([
      { type: "message_start", data: '{"ok":true}' },
      { type: "message", data: "line1\nline2" },
    ]);
  });

  it("retries once when maxRetries=1", async () => {
    const fetchSpy = vi.fn();
    let call = 0;
    fetchSpy.mockImplementation(async () => {
      call += 1;
      if (call === 1) {
        return {
          ok: false,
          status: 500,
          statusText: "Internal Server Error",
          headers: makeHeaders({}),
          body: null,
        } as unknown as Response;
      }
      return {
        ok: true,
        status: 200,
        statusText: "OK",
        headers: makeHeaders({ "content-type": "text/event-stream" }),
        body: streamFromStrings(['data: {"ok":true}\n\n']),
      } as unknown as Response;
    });
    vi.stubGlobal("fetch", fetchSpy);

    const onError = vi.fn();
    const onComplete = vi.fn();
    await streamSSE(
      "/api/v1/chat",
      { method: "POST", body: { x: 1 } },
      {
        onEvent: () => {},
        onError,
        onComplete,
        maxRetries: 1,
        retryDelay: 0,
      },
    );

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("throws when response body is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          headers: makeHeaders({ "content-type": "text/event-stream" }),
          body: null,
        } as unknown as Response;
      }),
    );

    await expect(
      streamSSE(
        "/api/v1/chat",
        { method: "POST", body: { x: 1 } },
        { onEvent: () => {} },
      ),
    ).rejects.toBeInstanceOf(Error);
  });
});
