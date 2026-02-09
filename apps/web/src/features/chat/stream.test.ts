import { describe, expect, it, vi, afterEach } from "vitest";

const streamSSEMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/sse", () => ({
  streamSSE: streamSSEMock,
}));

import { streamChat } from "./stream";

afterEach(() => {
  vi.unstubAllGlobals();
  streamSSEMock.mockReset();
});

describe("features/chat/stream", () => {
  it("reports error via onError when API health check is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
      })),
    );

    const onError = vi.fn();
    await streamChat("hi", "plasmodb", { onMessage: () => {}, onError });
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it("streams chat via streamSSE and parses events before invoking onMessage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true })),
    );

    const onMessage = vi.fn();

    streamSSEMock.mockImplementation(
      async (_path: string, _args: unknown, options: unknown) => {
        const opts = options as {
          onEvent: (evt: { type: string; data: string }) => void;
          onComplete?: () => void;
        };
        opts.onEvent({
          type: "assistant_message",
          data: JSON.stringify({ content: "hello" }),
        });
        opts.onComplete?.();
      },
    );

    await streamChat(
      "hello",
      "plasmodb",
      {
        onMessage,
      },
      { strategyId: "s1" },
      "execute",
    );

    expect(streamSSEMock).toHaveBeenCalledTimes(1);
    const [path, args] = streamSSEMock.mock.calls[0] as [string, { body?: unknown }];
    expect(path).toBe("/api/v1/chat");
    expect(args.body).toMatchObject({
      message: "hello",
      siteId: "plasmodb",
      strategyId: "s1",
      mode: "execute",
    });

    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onMessage.mock.calls[0]?.[0]).toMatchObject({
      type: "assistant_message",
      data: { content: "hello" },
    });
  });
});
