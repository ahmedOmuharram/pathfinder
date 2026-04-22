/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

const awaitFlushMock = vi.hoisted(() => vi.fn(async () => {}));
vi.mock("./useStrategyAutoFlush", () => ({
  useStrategyAutoFlush: () => ({
    pending: false,
    awaitFlush: awaitFlushMock,
  }),
}));

import { useStrategyPopstateFlush } from "./useStrategyPopstateFlush";

beforeEach(() => {
  awaitFlushMock.mockReset();
  awaitFlushMock.mockImplementation(async () => {});
});

describe("useStrategyPopstateFlush", () => {
  it("calls awaitFlush when a popstate event fires", async () => {
    renderHook(() => useStrategyPopstateFlush());

    await act(async () => {
      window.dispatchEvent(new PopStateEvent("popstate"));
      // Allow the microtask queue to flush.
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(awaitFlushMock).toHaveBeenCalledTimes(1);
    });
  });

  it("does not invoke awaitFlush when popstate has not fired", () => {
    renderHook(() => useStrategyPopstateFlush());
    expect(awaitFlushMock).not.toHaveBeenCalled();
  });
});
