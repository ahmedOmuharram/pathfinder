import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import {
  subscribeToOperation,
  fetchActiveOperations,
  type SubscribeOptions,
} from "./operationSubscribe";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api/http", () => ({
  buildUrl: vi.fn((path: string) => `http://localhost${path}`),
  getAuthHeaders: vi.fn(() => ({})),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a ReadableStream from an array of strings (each encoded to bytes). */
function streamFromStrings(parts: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const p of parts) controller.enqueue(encoder.encode(p));
      controller.close();
    },
  });
}

/** Build a ReadableStream that emits parts with an async delay between each. */
function streamFromStringsAsync(
  parts: string[],
  delayMs = 5,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const p of parts) {
        await new Promise((r) => setTimeout(r, delayMs));
        controller.enqueue(encoder.encode(p));
      }
      controller.close();
    },
  });
}

/** Helper to create a mock ok Response with an SSE body. */
function okSSEResponse(body: ReadableStream<Uint8Array>): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: new Headers({ "content-type": "text/event-stream" }),
    body,
  } as unknown as Response;
}

/** Flush micro-task and timer queues so the async connect() loop progresses. */
async function flush(ms = 0): Promise<void> {
  await vi.advanceTimersByTimeAsync(ms);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("subscribeToOperation", () => {
  it("receives and parses SSE events with explicit and default types", async () => {
    const events: Array<{ type: string; data: unknown }> = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        okSSEResponse(
          streamFromStrings([
            'event: step_start\ndata: {"step":1}\n\n',
            'data: {"step":2}\n\n',
            'event: message_end\ndata: {"done":true}\n\n',
          ]),
        ),
      ),
    );

    const onComplete = vi.fn();
    subscribeToOperation("op-1", {
      onEvent: (evt) => events.push(evt),
      onComplete,
    });

    // Let the async connect() run
    await flush();

    expect(events).toEqual([
      { type: "step_start", data: { step: 1 } },
      { type: "message", data: { step: 2 } },
      { type: "message_end", data: { done: true } },
    ]);
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("triggers onComplete when an end event type is received", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        okSSEResponse(
          streamFromStrings(['event: experiment_end\ndata: {"ok":true}\n\n']),
        ),
      ),
    );

    const onComplete = vi.fn();
    subscribeToOperation("op-2", {
      onEvent: () => {},
      onComplete,
    });

    await flush();

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("supports custom endEventTypes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        okSSEResponse(streamFromStrings(['event: custom_done\ndata: {"ok":true}\n\n'])),
      ),
    );

    const onComplete = vi.fn();
    subscribeToOperation("op-3", {
      onEvent: () => {},
      onComplete,
      endEventTypes: new Set(["custom_done"]),
    });

    await flush();

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("unsubscribe() stops the connection", async () => {
    const events: Array<{ type: string; data: unknown }> = [];

    // Stream that delivers events asynchronously with delays
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        okSSEResponse(
          streamFromStringsAsync(
            [
              'event: step\ndata: {"n":1}\n\n',
              'event: step\ndata: {"n":2}\n\n',
              'event: step\ndata: {"n":3}\n\n',
            ],
            50,
          ),
        ),
      ),
    );

    const sub = subscribeToOperation("op-4", {
      onEvent: (evt) => events.push(evt),
    });

    // Let the first event arrive
    await flush(60);

    // Unsubscribe before the rest arrive
    sub.unsubscribe();

    // Advance past when remaining events would have arrived
    await flush(200);

    // We should have received at most the first event (possibly more depending
    // on timing, but definitely fewer than all 3 since we unsubscribed).
    expect(events.length).toBeLessThanOrEqual(2);
  });

  it("calls onError for a 404 response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 404,
        statusText: "Not Found",
        body: null,
      })),
    );

    const onError = vi.fn();
    subscribeToOperation("op-missing", {
      onEvent: () => {},
      onError,
    });

    await flush();

    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0][0].message).toContain("not found");
  });

  it("auto-reconnects on network failure then succeeds", async () => {
    const events: Array<{ type: string; data: unknown }> = [];
    let callCount = 0;

    const fetchMock = vi.fn(async () => {
      callCount++;
      if (callCount === 1) {
        throw new Error("Network failure");
      }
      return okSSEResponse(
        streamFromStrings(['event: message_end\ndata: {"recovered":true}\n\n']),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const onComplete = vi.fn();
    const onError = vi.fn();
    subscribeToOperation("op-reconnect", {
      onEvent: (evt) => events.push(evt),
      onComplete,
      onError,
      maxReconnects: 3,
    });

    // First call throws immediately. Then there's a 1s backoff before retry.
    await flush(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Advance past the 1s backoff
    await flush(1500);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(events).toEqual([{ type: "message_end", data: { recovered: true } }]);
    expect(onComplete).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("calls onError after exhausting max reconnect attempts", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("Persistent failure");
    });
    vi.stubGlobal("fetch", fetchMock);

    const onError = vi.fn();
    subscribeToOperation("op-exhaust", {
      onEvent: () => {},
      onError,
      maxReconnects: 2,
    });

    // Attempt 1 (initial): immediate
    await flush(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Attempt 2 (reconnect 1): 1s backoff
    await flush(1500);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // Attempt 3 (reconnect 2): 2s backoff
    await flush(2500);
    expect(fetchMock).toHaveBeenCalledTimes(3);

    // All 2 reconnects exhausted, onError should have been called
    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0][0].message).toBe("Persistent failure");
  });

  it("handles response with no body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        body: null,
      })),
    );

    const onError = vi.fn();
    subscribeToOperation("op-nobody", {
      onEvent: () => {},
      onError,
      maxReconnects: 0,
    });

    await flush();

    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0][0].message).toContain("No response body");
  });

  it("skips events with invalid JSON and continues", async () => {
    const events: Array<{ type: string; data: unknown }> = [];
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        okSSEResponse(
          streamFromStrings([
            "event: step\ndata: not-json\n\n",
            'event: message_end\ndata: {"ok":true}\n\n',
          ]),
        ),
      ),
    );

    const onComplete = vi.fn();
    subscribeToOperation("op-bad-json", {
      onEvent: (evt) => events.push(evt),
      onComplete,
    });

    await flush();

    // The invalid-JSON event should have been skipped
    expect(events).toEqual([{ type: "message_end", data: { ok: true } }]);
    expect(onComplete).toHaveBeenCalledOnce();
    expect(warnSpy).toHaveBeenCalledOnce();
  });
});

describe("fetchActiveOperations", () => {
  it("returns parsed results from the API", async () => {
    const mockData = [
      {
        operationId: "op-1",
        streamId: "stream-1",
        type: "chat",
        status: "active",
        createdAt: "2026-03-01T00:00:00Z",
      },
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => mockData,
      })),
    );

    const result = await fetchActiveOperations();

    expect(result).toEqual(mockData);
    expect(global.fetch).toHaveBeenCalledOnce();
    // Should have been called with the active operations URL (no query param)
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "http://localhost/api/v1/operations/active",
    );
  });

  it("passes the type query parameter when specified", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => [],
      })),
    );

    await fetchActiveOperations({ type: "experiment" });

    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "http://localhost/api/v1/operations/active?type=experiment",
    );
  });

  it("returns empty array on error response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 500,
      })),
    );

    const result = await fetchActiveOperations();

    expect(result).toEqual([]);
  });

  it("returns empty array when fetch throws", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("Network error");
      }),
    );

    // Network errors are caught and return [] instead of crashing callers.
    const result = await fetchActiveOperations();
    expect(result).toEqual([]);
  });
});
