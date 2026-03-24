import { describe, expect, it, vi, afterEach } from "vitest";

const subscribeToOperationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/operationSubscribe", () => ({
  subscribeToOperation: subscribeToOperationMock,
}));

const requestJsonMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/http", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/http")>();
  return { ...actual, requestJson: requestJsonMock };
});

import { streamChat } from "./stream";

afterEach(() => {
  vi.unstubAllGlobals();
  subscribeToOperationMock.mockReset();
  requestJsonMock.mockReset();
});

describe("features/chat/stream", () => {
  it("POSTs to /api/v1/chat and subscribes to the operation", async () => {
    requestJsonMock.mockResolvedValue({
      operationId: "op-1",
      strategyId: "s-1",
    });

    const unsubscribe = vi.fn();
    subscribeToOperationMock.mockImplementation(
      (
        _opId: string,
        opts: {
          onEvent: (e: { type: string; data: unknown }) => void;
          onComplete?: () => void;
        },
      ) => {
        // Simulate an event followed by completion.
        opts.onEvent({
          type: "assistant_message",
          data: { content: "hello" },
        });
        opts.onComplete?.();
        return { unsubscribe };
      },
    );

    const onMessage = vi.fn();
    const onComplete = vi.fn();

    const result = await streamChat(
      "hello",
      "plasmodb",
      { onMessage, onComplete },
      { strategyId: "s1" },
    );

    // requestJson was called with correct params
    expect(requestJsonMock).toHaveBeenCalledTimes(1);
    const [, path, args] = requestJsonMock.mock.calls[0] as [unknown, string, { body?: unknown }];
    expect(path).toBe("/api/v1/chat");
    expect(args.body).toMatchObject({
      message: "hello",
      siteId: "plasmodb",
      strategyId: "s1",
    });

    // subscribeToOperation was called with the operationId
    expect(subscribeToOperationMock).toHaveBeenCalledTimes(1);
    expect(subscribeToOperationMock.mock.calls[0]?.[0]).toBe("op-1");

    // onMessage received a parsed ChatSSEEvent
    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onMessage.mock.calls[0]?.[0]).toMatchObject({
      type: "assistant_message",
      data: { content: "hello" },
    });

    // onComplete was called
    expect(onComplete).toHaveBeenCalledTimes(1);

    // Result contains operationId, strategyId, and subscription
    expect(result.operationId).toBe("op-1");
    expect(result.strategyId).toBe("s-1");
    expect(result.subscription).toEqual({ unsubscribe });
  });
});
