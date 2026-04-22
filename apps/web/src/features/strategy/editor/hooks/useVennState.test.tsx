/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useVennState } from "./useVennState";

describe("useVennState", () => {
  it("returns the current operator", () => {
    const { result } = renderHook(() => useVennState("INTERSECT"));
    expect(result.current.operator).toBe("INTERSECT");
  });

  it("syncs operator when prop changes", () => {
    const { result, rerender } = renderHook(
      ({ op }: { op: string }) => useVennState(op),
      { initialProps: { op: "INTERSECT" } },
    );
    expect(result.current.operator).toBe("INTERSECT");
    rerender({ op: "MINUS" });
    expect(result.current.operator).toBe("MINUS");
  });

  it("setOperator updates current value", () => {
    const { result } = renderHook(() => useVennState("INTERSECT"));
    act(() => {
      result.current.setOperator("MINUS");
    });
    expect(result.current.operator).toBe("MINUS");
  });

  it("swap toggles MINUS to RMINUS and labels", () => {
    const { result } = renderHook(() => useVennState("MINUS"));
    expect(result.current.swappedLabels).toBe(false);
    act(() => {
      result.current.swap();
    });
    expect(result.current.operator).toBe("RMINUS");
    expect(result.current.swappedLabels).toBe(true);
  });

  it("swap toggles RMINUS to MINUS", () => {
    const { result } = renderHook(() => useVennState("RMINUS"));
    act(() => {
      result.current.swap();
    });
    expect(result.current.operator).toBe("MINUS");
  });

  it("swap is no-op for INTERSECT (still flips labels)", () => {
    const { result } = renderHook(() => useVennState("INTERSECT"));
    act(() => {
      result.current.swap();
    });
    expect(result.current.operator).toBe("INTERSECT");
    expect(result.current.swappedLabels).toBe(true);
  });

  it("swap is no-op for UNION (still flips labels)", () => {
    const { result } = renderHook(() => useVennState("UNION"));
    act(() => {
      result.current.swap();
    });
    expect(result.current.operator).toBe("UNION");
    expect(result.current.swappedLabels).toBe(true);
  });

  it("swap toggles labels for COLOCATE without changing op", () => {
    const { result } = renderHook(() => useVennState("COLOCATE"));
    act(() => {
      result.current.swap();
    });
    expect(result.current.operator).toBe("COLOCATE");
    expect(result.current.swappedLabels).toBe(true);
  });

  it("double swap returns to original labels", () => {
    const { result } = renderHook(() => useVennState("MINUS"));
    act(() => {
      result.current.swap();
    });
    act(() => {
      result.current.swap();
    });
    expect(result.current.operator).toBe("MINUS");
    expect(result.current.swappedLabels).toBe(false);
  });
});
