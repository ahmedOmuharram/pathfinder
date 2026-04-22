// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { ReactFlowProvider, useStoreApi } from "@xyflow/react";
import { useCanvasIdle } from "./useCanvasIdle";

function Wrapper({ children }: { children: ReactNode }) {
  return <ReactFlowProvider>{children}</ReactFlowProvider>;
}

describe("useCanvasIdle", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("starts idle when there has been no activity", () => {
    const { result } = renderHook(() => useCanvasIdle({ idleMs: 1000 }), {
      wrapper: Wrapper,
    });
    expect(result.current).toBe(true);
  });

  it("flips to false on viewport change, then back to true after idleMs", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { result, rerender } = renderHook(
      () => {
        const idle = useCanvasIdle({ idleMs: 500 });
        const store = useStoreApi();
        return { idle, store };
      },
      { wrapper: Wrapper },
    );

    expect(result.current.idle).toBe(true);

    await act(async () => {
      result.current.store.setState({ transform: [100, 0, 1] });
    });
    rerender();
    expect(result.current.idle).toBe(false);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(600);
    });
    rerender();
    expect(result.current.idle).toBe(true);
  });
});
