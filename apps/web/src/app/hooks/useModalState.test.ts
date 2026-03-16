/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useModalState } from "./useModalState";

describe("useModalState", () => {
  it("starts with all modals closed", () => {
    const { result } = renderHook(() => useModalState());
    expect(result.current.showSettings).toBe(false);
    expect(result.current.graphEditing).toBe(false);
  });

  describe("settings modal", () => {
    it("opens and closes", () => {
      const { result } = renderHook(() => useModalState());
      act(() => result.current.openSettings());
      expect(result.current.showSettings).toBe(true);
      act(() => result.current.closeSettings());
      expect(result.current.showSettings).toBe(false);
    });
  });

  describe("graph editor modal", () => {
    it("opens and closes", () => {
      const { result } = renderHook(() => useModalState());
      act(() => result.current.openGraphEditor());
      expect(result.current.graphEditing).toBe(true);
      act(() => result.current.closeGraphEditor());
      expect(result.current.graphEditing).toBe(false);
    });
  });

  describe("modal independence", () => {
    it("opening settings does not affect graph editor", () => {
      const { result } = renderHook(() => useModalState());
      act(() => result.current.openSettings());
      expect(result.current.showSettings).toBe(true);
      expect(result.current.graphEditing).toBe(false);
    });

    it("opening graph editor does not affect settings", () => {
      const { result } = renderHook(() => useModalState());
      act(() => result.current.openGraphEditor());
      expect(result.current.showSettings).toBe(false);
      expect(result.current.graphEditing).toBe(true);
    });
  });

  describe("callback stability", () => {
    it("returns stable callback references across renders", () => {
      const { result, rerender } = renderHook(() => useModalState());
      const first = {
        openSettings: result.current.openSettings,
        closeSettings: result.current.closeSettings,
        openGraphEditor: result.current.openGraphEditor,
        closeGraphEditor: result.current.closeGraphEditor,
      };
      rerender();
      expect(result.current.openSettings).toBe(first.openSettings);
      expect(result.current.closeSettings).toBe(first.closeSettings);
      expect(result.current.openGraphEditor).toBe(first.openGraphEditor);
      expect(result.current.closeGraphEditor).toBe(first.closeGraphEditor);
    });
  });
});
