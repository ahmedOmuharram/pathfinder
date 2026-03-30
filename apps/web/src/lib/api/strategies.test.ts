import { describe, expect, it, vi, afterEach } from "vitest";

const requestJsonMock = vi.hoisted(() => vi.fn());
vi.mock("./http", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./http")>();
  return { ...actual, requestJson: requestJsonMock };
});

import { undoTurn } from "./strategies";

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

    const result = await undoTurn("stream-abc", "1709234567890-0");

    expect(requestJsonMock).toHaveBeenCalledTimes(1);
    const [, path, args] = requestJsonMock.mock.calls[0] as [
      unknown,
      string,
      { method?: string; body?: unknown },
    ];
    expect(path).toBe("/api/v1/chat/stream-abc/undo");
    expect(args.method).toBe("POST");
    expect(args.body).toEqual({ entryId: "1709234567890-0" });

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
});
