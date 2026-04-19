import { describe, expect, it, vi, afterEach } from "vitest";

import type * as HttpModule from "./http";

const requestJsonMock = vi.hoisted(() => vi.fn());
vi.mock("./http", async (importOriginal) => {
  const actual = await importOriginal<typeof HttpModule>();
  return { ...actual, requestJson: requestJsonMock };
});

import { undoTurn } from "./conversationUndo";

afterEach(() => {
  requestJsonMock.mockReset();
});

describe("undoTurn", () => {
  it("POSTs to /api/v1/chat/{streamId}/undo with entryId", async () => {
    requestJsonMock.mockResolvedValue({
      messageCount: 2,
      strategy: { root: {} },
      wdkStrategyId: 123,
    });

    const result = await undoTurn("stream-abc", "1709234567890-0", "trace-123");

    expect(requestJsonMock).toHaveBeenCalledTimes(1);
    const [, path, args] = requestJsonMock.mock.calls[0] as [
      unknown,
      string,
      { method?: string; body?: unknown },
    ];
    expect(path).toBe("/api/v1/chat/stream-abc/undo");
    expect(args.method).toBe("POST");
    expect(args.body).toEqual({
      entryId: "1709234567890-0",
      traceId: "trace-123",
    });

    expect(result.messageCount).toBe(2);
    expect(result.strategy).toEqual({ root: {} });
    expect(result.wdkStrategyId).toBe(123);
  });

  it("returns null strategy when backend returns null", async () => {
    requestJsonMock.mockResolvedValue({
      messageCount: 0,
      strategy: null,
      wdkStrategyId: null,
    });

    const result = await undoTurn("stream-abc", "1234-0");

    expect(result.messageCount).toBe(0);
    expect(result.strategy).toBeNull();
    expect(result.wdkStrategyId).toBeNull();
  });

  it("omits traceId when none is provided", async () => {
    requestJsonMock.mockResolvedValue({
      messageCount: 0,
      strategy: null,
      wdkStrategyId: null,
    });

    await undoTurn("stream-abc", "1234-0");

    const [, , args] = requestJsonMock.mock.calls[0] as [
      unknown,
      string,
      { method?: string; body?: unknown },
    ];
    expect(args.body).toEqual({ entryId: "1234-0" });
  });
});
