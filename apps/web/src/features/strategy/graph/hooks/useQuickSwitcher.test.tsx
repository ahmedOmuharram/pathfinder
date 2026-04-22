// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import { useQuickSwitcher } from "./useQuickSwitcher";

describe("useQuickSwitcher", () => {
  afterEach(() => cleanup());

  it("starts closed", () => {
    const { result } = renderHook(() => useQuickSwitcher());
    expect(result.current.open).toBe(false);
  });

  it("setOpen(true) opens, setOpen(false) closes", () => {
    const { result } = renderHook(() => useQuickSwitcher());
    act(() => result.current.setOpen(true));
    expect(result.current.open).toBe(true);
    act(() => result.current.setOpen(false));
    expect(result.current.open).toBe(false);
  });

  it("toggle flips the open state", () => {
    const { result } = renderHook(() => useQuickSwitcher());
    act(() => result.current.toggle());
    expect(result.current.open).toBe(true);
    act(() => result.current.toggle());
    expect(result.current.open).toBe(false);
  });
});
