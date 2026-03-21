/**
 * Tests for useResetOnStrategyChange — conversation switch reset logic.
 *
 * These tests verify whether the hook properly resets chat state when
 * the user switches between conversations.  Tests that FAIL indicate
 * a confirmed bug in the current codebase.
 *
 * @vitest-environment jsdom
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useResetOnStrategyChange } from "./useResetOnStrategyChange";
import { useSessionStore } from "@/state/useSessionStore";

function makeMocks() {
  return {
    resetThinking: vi.fn(),
    setIsStreaming: vi.fn(),
    setMessages: vi.fn(),
    setUndoSnapshots: vi.fn(),
    sessionRef: { current: null } as { current: null },
    stopStreaming: vi.fn(),
  };
}

describe("useResetOnStrategyChange", () => {
  beforeEach(() => {
    useSessionStore.setState({ chatIsStreaming: false });
  });

  // ── Normal path: not streaming ────────────────────────────────────

  it("resets all state when strategy changes and not streaming", () => {
    const fns = makeMocks();
    const { rerender } = renderHook(
      ({ strategyId, prevId }: { strategyId: string | null; prevId: string | null }) =>
        useResetOnStrategyChange({
          strategyId,
          previousStrategyId: prevId,
          ...fns,
        }),
      { initialProps: { strategyId: "A", prevId: "A" } },
    );

    rerender({ strategyId: "B", prevId: "A" });

    expect(fns.stopStreaming).toHaveBeenCalled();
    expect(fns.setIsStreaming).toHaveBeenCalledWith(false);
    expect(fns.resetThinking).toHaveBeenCalled();
    expect(fns.setMessages).toHaveBeenCalled();
    expect(fns.setUndoSnapshots).toHaveBeenCalled();
  });

  it("does NOT reset when strategyId is unchanged", () => {
    const fns = makeMocks();
    const { rerender } = renderHook(
      ({ strategyId, prevId }: { strategyId: string | null; prevId: string | null }) =>
        useResetOnStrategyChange({
          strategyId,
          previousStrategyId: prevId,
          ...fns,
        }),
      { initialProps: { strategyId: "A", prevId: "A" } },
    );

    rerender({ strategyId: "A", prevId: "A" });

    expect(fns.stopStreaming).not.toHaveBeenCalled();
    expect(fns.setMessages).not.toHaveBeenCalled();
  });

  it("does NOT reset when previousStrategyId is null (first load)", () => {
    const fns = makeMocks();
    renderHook(() =>
      useResetOnStrategyChange({
        strategyId: "A",
        previousStrategyId: null,
        ...fns,
      }),
    );

    expect(fns.stopStreaming).not.toHaveBeenCalled();
    expect(fns.setMessages).not.toHaveBeenCalled();
  });

  // ── Bug 2: Reset skipped when chatIsStreaming is true ─────────────
  //
  // useResetOnStrategyChange (line 36) checks:
  //   if (useSessionStore.getState().chatIsStreaming) return;
  //
  // This guard was added for the auto-create flow (stream creates a new
  // strategy mid-stream). But it also blocks resets for USER-INITIATED
  // conversation switches.  The comment says "sidebar navigation stops
  // streaming BEFORE setting the new strategyId," but handleSelect in
  // useConversationSidebarActions does NOT call stopStreaming before
  // setStrategyId.
  //
  // If these tests FAIL, the bug is confirmed: user-initiated switches
  // while streaming leave the old stream running and don't clear state.

  it("resets state when strategy changes even if chatIsStreaming is true", () => {
    useSessionStore.setState({ chatIsStreaming: true });

    const fns = makeMocks();
    const { rerender } = renderHook(
      ({ strategyId, prevId }: { strategyId: string | null; prevId: string | null }) =>
        useResetOnStrategyChange({
          strategyId,
          previousStrategyId: prevId,
          ...fns,
        }),
      { initialProps: { strategyId: "A", prevId: "A" } },
    );

    rerender({ strategyId: "B", prevId: "A" });

    // A user-initiated conversation switch should ALWAYS stop the
    // old stream and reset state, regardless of chatIsStreaming.
    expect(fns.stopStreaming).toHaveBeenCalled();
    expect(fns.setIsStreaming).toHaveBeenCalledWith(false);
    expect(fns.setMessages).toHaveBeenCalled();
  });

  it("clears messages on switch so old conversation content is not visible", () => {
    useSessionStore.setState({ chatIsStreaming: true });

    const fns = makeMocks();
    const { rerender } = renderHook(
      ({ strategyId, prevId }: { strategyId: string | null; prevId: string | null }) =>
        useResetOnStrategyChange({
          strategyId,
          previousStrategyId: prevId,
          ...fns,
        }),
      { initialProps: { strategyId: "A", prevId: "A" } },
    );

    rerender({ strategyId: "B", prevId: "A" });

    // Without clearing messages, mergeMessages in useUnifiedChatDataLoading
    // will merge the NEW conversation's messages on top of the OLD ones,
    // showing the wrong content briefly.
    expect(fns.setMessages).toHaveBeenCalledWith([]);
  });
});
