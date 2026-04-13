/**
 * Regression tests for useStreamLifecycle — Race A.
 *
 * Race A: between `beginStream()` (sets isStreaming=true) and
 * `trackOperation(subscription, operationId)` (records the cancellable
 * subscription + operationId), a call to `stopStreaming()` has no
 * subscription to unsubscribe and no operationId to cancel. The stream
 * continues running in the background even though the UI shows it stopped.
 *
 * Expected post-fix behavior:
 *   - After `beginStream()` -> `stopStreaming()` -> `trackOperation()`,
 *     the subscription MUST be unsubscribed (cancelled) exactly once.
 *   - `isStreaming` MUST be false after `stopStreaming()`.
 *
 * @vitest-environment jsdom
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useStreamLifecycle } from "./useStreamLifecycle";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const cancelOperationMock = vi.hoisted(() => vi.fn(async () => undefined));

vi.mock("@/lib/operationSubscribe", () => ({
  cancelOperation: cancelOperationMock,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeThinkingMock() {
  return {
    activeMessageId: null,
    activeToolCalls: [],
    lastToolCalls: [],
    reasoning: null,
    getThinkingForMessage: vi.fn(() => ({
      activeToolCalls: [],
      lastToolCalls: [],
      reasoning: null,
    })),
    setActiveMessage: vi.fn(),
    reset: vi.fn(),
    applyThinkingPayload: vi.fn(() => false),
    updateActiveFromBuffer: vi.fn(),
    updateReasoning: vi.fn(),
    finalizeToolCalls: vi.fn(),
  } as unknown as Parameters<typeof useStreamLifecycle>[0];
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useStreamLifecycle — Race A (beginStream / trackOperation gap)", () => {
  it("stopStreaming during beginStream/trackOperation gap cancels the late subscription", () => {
    // Arrange
    const thinking = makeThinkingMock();
    const onStreamingChange = vi.fn();
    const { result } = renderHook(() =>
      useStreamLifecycle(thinking, onStreamingChange),
    );

    const unsubscribe = vi.fn();
    const lateSubscription = { unsubscribe };
    const lateOperationId = "op-late-1";

    // 1. Start streaming (beginStream)
    act(() => {
      result.current.beginStream();
    });
    expect(result.current.isStreaming).toBe(true);

    // 2. User clicks Stop BEFORE streamChat resolves (gap window).
    act(() => {
      result.current.stopStreaming();
    });

    // 3. streamChat resolves late and calls trackOperation -- the late
    //    subscription arrives after stopStreaming.
    act(() => {
      result.current.trackOperation(lateSubscription, lateOperationId);
    });

    // Assert: after the full sequence, streaming must be off AND the late
    // subscription must have been cancelled exactly once (so it cannot
    // continue pumping events into the UI).
    expect(result.current.isStreaming).toBe(false);
    expect(unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("stopStreaming during the gap cancels the operation on the backend", () => {
    // When stopStreaming is called, cancelOperation MUST be invoked with
    // the operationId that eventually arrived via trackOperation.
    const thinking = makeThinkingMock();
    const { result } = renderHook(() => useStreamLifecycle(thinking));

    const unsubscribe = vi.fn();
    const lateOperationId = "op-late-2";

    act(() => {
      result.current.beginStream();
    });

    act(() => {
      result.current.stopStreaming();
    });

    act(() => {
      result.current.trackOperation({ unsubscribe }, lateOperationId);
    });

    // cancelOperation must have been called (either as part of stopStreaming
    // or as a deferred cancellation once the operationId arrived).
    expect(cancelOperationMock).toHaveBeenCalledTimes(1);
    expect(cancelOperationMock).toHaveBeenCalledWith(lateOperationId);
  });

  it("stopStreaming emits streaming=false via onStreamingChange even during the gap", () => {
    const thinking = makeThinkingMock();
    const onStreamingChange = vi.fn();
    const { result } = renderHook(() =>
      useStreamLifecycle(thinking, onStreamingChange),
    );

    act(() => {
      result.current.beginStream();
    });
    expect(onStreamingChange).toHaveBeenLastCalledWith(true);

    act(() => {
      result.current.stopStreaming();
    });

    expect(onStreamingChange).toHaveBeenLastCalledWith(false);
  });
});
