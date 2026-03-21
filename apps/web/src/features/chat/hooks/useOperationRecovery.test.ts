/**
 * Tests for useOperationRecovery — verifies that operation recovery
 * correctly handles strategy switches and re-subscribes when needed.
 *
 * Key scenario: switching A → B → A must trigger recovery on the return
 * to A if an operation is still active.
 *
 * @vitest-environment jsdom
 */

import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";
import { useOperationRecovery } from "./useOperationRecovery";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const fetchActiveOperationsMock = vi.hoisted(() => vi.fn());
const subscribeToOperationMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/operationSubscribe", () => ({
  fetchActiveOperations: fetchActiveOperationsMock,
  subscribeToOperation: subscribeToOperationMock,
}));

vi.mock("@/lib/sse_events", () => ({
  parseChatSSEEvent: vi.fn((raw: { type: string; data: string }) => ({
    type: raw.type,
    data: JSON.parse(raw.data),
  })),
}));

vi.mock("@/features/chat/handlers/handleChatEvent", () => ({
  handleChatEvent: vi.fn(),
}));

vi.mock("@/features/chat/handlers/handleChatEvent.messageEvents", () => ({
  snapshotSubKaniActivityFromBuffers: vi.fn(() => undefined),
}));

vi.mock("@/features/chat/streaming/StreamingSession", () => ({
  StreamingSession: class MockStreamingSession {
    latestStrategy = null;
    snapshotApplied = false;
    consumeUndoSnapshot = vi.fn();
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Flush pending promises and effects. */
async function flushPromises(): Promise<void> {
  await act(async () => {
    // Flush microtask queue
    await new Promise<void>((r) => setTimeout(r, 0));
  });
}

function makeArgs(overrides: Partial<Parameters<typeof useOperationRecovery>[0]> = {}) {
  return {
    strategyId: null as string | null,
    siteId: "test-site",
    isStreaming: false,
    setIsStreaming: vi.fn(),
    setMessages: vi.fn(),
    setUndoSnapshots: vi.fn(),
    thinking: {
      reset: vi.fn(),
      applyThinkingPayload: vi.fn(),
      finalizeToolCalls: vi.fn(),
      thinkingLabel: null,
      toolCalls: [],
      isThinking: false,
      subKaniActivity: null,
    } as unknown as Parameters<typeof useOperationRecovery>[0]["thinking"],
    currentStrategy: null,
    setStrategyId: vi.fn(),
    addStrategy: vi.fn(),
    addExecutedStrategy: vi.fn(),
    setWdkInfo: vi.fn(),
    setStrategy: vi.fn(),
    setStrategyMeta: vi.fn(),
    clearStrategy: vi.fn(),
    addStep: vi.fn(),
    loadGraph: vi.fn(),
    parseToolArguments: vi.fn(),
    parseToolResult: vi.fn(),
    applyGraphSnapshot: vi.fn(),
    getStrategy: vi.fn(async (): Promise<Strategy> => null as unknown as Strategy),
    attachThinkingToLastAssistant: vi.fn(),
    onApiError: vi.fn(),
    setOptimizationProgress: vi.fn(),
    ...overrides,
  };
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

describe("useOperationRecovery", () => {
  it("does not attempt recovery when strategyId is null", async () => {
    renderHook(() => useOperationRecovery(makeArgs({ strategyId: null })));
    await flushPromises();
    expect(fetchActiveOperationsMock).not.toHaveBeenCalled();
  });

  it("attempts recovery when strategyId is set", async () => {
    fetchActiveOperationsMock.mockResolvedValue([]);

    renderHook(() => useOperationRecovery(makeArgs({ strategyId: "strategy-a" })));

    await flushPromises();

    expect(fetchActiveOperationsMock).toHaveBeenCalledTimes(1);
    expect(fetchActiveOperationsMock).toHaveBeenCalledWith({
      type: "chat",
      streamId: "strategy-a",
    });
  });

  it("subscribes to active operation when found", async () => {
    const unsubscribe = vi.fn();
    fetchActiveOperationsMock.mockResolvedValue([
      { operationId: "op-1", streamId: "strategy-a", type: "chat", status: "active" },
    ]);
    subscribeToOperationMock.mockReturnValue({ unsubscribe });

    const setIsStreaming = vi.fn();
    renderHook(() =>
      useOperationRecovery(makeArgs({ strategyId: "strategy-a", setIsStreaming })),
    );

    // Wait for the nested async .then() chain to complete
    await waitFor(() => {
      expect(subscribeToOperationMock).toHaveBeenCalledTimes(1);
    });

    expect(setIsStreaming).toHaveBeenCalledWith(true);
    expect(subscribeToOperationMock).toHaveBeenCalledWith(
      "op-1",
      expect.objectContaining({
        endEventTypes: new Set(["message_end"]),
      }),
    );
  });

  it("does not attempt recovery when isStreaming is true", async () => {
    fetchActiveOperationsMock.mockResolvedValue([]);

    renderHook(() =>
      useOperationRecovery(makeArgs({ strategyId: "strategy-a", isStreaming: true })),
    );

    await flushPromises();
    expect(fetchActiveOperationsMock).not.toHaveBeenCalled();
  });

  it("re-attempts recovery after switching strategies A → B → A", async () => {
    fetchActiveOperationsMock.mockResolvedValue([]);

    const args = makeArgs({ strategyId: "strategy-a" });
    const { rerender } = renderHook(
      (props: Parameters<typeof useOperationRecovery>[0]) =>
        useOperationRecovery(props),
      { initialProps: args },
    );

    await flushPromises();
    expect(fetchActiveOperationsMock).toHaveBeenCalledTimes(1);
    expect(fetchActiveOperationsMock).toHaveBeenCalledWith({
      type: "chat",
      streamId: "strategy-a",
    });

    // Switch to strategy-b
    rerender(makeArgs({ strategyId: "strategy-b" }));
    await flushPromises();

    expect(fetchActiveOperationsMock).toHaveBeenCalledTimes(2);
    expect(fetchActiveOperationsMock).toHaveBeenLastCalledWith({
      type: "chat",
      streamId: "strategy-b",
    });

    // Switch BACK to strategy-a
    fetchActiveOperationsMock.mockClear();
    rerender(makeArgs({ strategyId: "strategy-a" }));
    await flushPromises();

    expect(fetchActiveOperationsMock).toHaveBeenCalledTimes(1);
    expect(fetchActiveOperationsMock).toHaveBeenCalledWith({
      type: "chat",
      streamId: "strategy-a",
    });
  });

  // ── Bug 1: Stale operation → isStreaming stuck true ───────────────
  //
  // When the backend has a stale "active" operation (producer died
  // without cleanup), the SSE endpoint loops forever. The frontend's
  // subscribeToOperation never calls onComplete or onError because
  // the connection stays open (keepalive comments aren't events).
  //
  // In this scenario, isStreaming is set to true and NEVER reset.
  // The chat UI is locked in "streaming" state indefinitely.

  it("resets isStreaming when subscription completes normally", async () => {
    fetchActiveOperationsMock.mockResolvedValue([
      { operationId: "op-ok", streamId: "strategy-a", type: "chat", status: "active" },
    ]);

    let capturedOnComplete: (() => void) | undefined;
    subscribeToOperationMock.mockImplementation(
      (_opId: string, opts: { onComplete?: () => void }) => {
        capturedOnComplete = opts.onComplete;
        return { unsubscribe: vi.fn() };
      },
    );

    const setIsStreaming = vi.fn();
    renderHook(() =>
      useOperationRecovery(makeArgs({ strategyId: "strategy-a", setIsStreaming })),
    );

    await waitFor(() => {
      expect(capturedOnComplete).toBeDefined();
    });

    // Simulate message_end arriving
    act(() => capturedOnComplete!());

    expect(setIsStreaming).toHaveBeenCalledWith(false);
  });

  it("resets isStreaming when subscription errors (e.g., 404 stale op)", async () => {
    fetchActiveOperationsMock.mockResolvedValue([
      { operationId: "op-stale", streamId: "strategy-a", type: "chat", status: "active" },
    ]);

    let capturedOnError: (() => void) | undefined;
    subscribeToOperationMock.mockImplementation(
      (_opId: string, opts: { onError?: () => void }) => {
        capturedOnError = opts.onError;
        return { unsubscribe: vi.fn() };
      },
    );

    const setIsStreaming = vi.fn();
    renderHook(() =>
      useOperationRecovery(makeArgs({ strategyId: "strategy-a", setIsStreaming })),
    );

    await waitFor(() => {
      expect(capturedOnError).toBeDefined();
    });

    act(() => capturedOnError!());

    expect(setIsStreaming).toHaveBeenCalledWith(false);
  });

  it("isStreaming stays true when subscription never completes (stale op)", async () => {
    // This test documents the behavior when a stale "active" operation
    // causes the SSE connection to hang indefinitely. The subscription
    // never fires onComplete or onError, so isStreaming stays true.
    // A proper fix would add a timeout or heartbeat mechanism.
    fetchActiveOperationsMock.mockResolvedValue([
      { operationId: "op-orphaned", streamId: "strategy-a", type: "chat", status: "active" },
    ]);

    // Subscription that never fires any callbacks (simulates hanging SSE)
    subscribeToOperationMock.mockReturnValue({ unsubscribe: vi.fn() });

    const setIsStreaming = vi.fn();
    renderHook(() =>
      useOperationRecovery(makeArgs({ strategyId: "strategy-a", setIsStreaming })),
    );

    await waitFor(() => {
      expect(setIsStreaming).toHaveBeenCalledWith(true);
    });

    // Verify setIsStreaming(false) was NEVER called — confirming stuck state.
    // This test passes, documenting the existing gap: there's no timeout.
    const falseCallCount = (setIsStreaming.mock.calls as boolean[][]).filter(
      (call) => call[0] === false,
    ).length;
    expect(falseCallCount).toBe(0);
  });

  it("unsubscribes from previous operation when strategy changes", async () => {
    const unsubscribe = vi.fn();
    fetchActiveOperationsMock.mockResolvedValue([
      { operationId: "op-a", streamId: "strategy-a", type: "chat", status: "active" },
    ]);
    subscribeToOperationMock.mockReturnValue({ unsubscribe });

    const args = makeArgs({ strategyId: "strategy-a" });
    const { rerender } = renderHook(
      (props: Parameters<typeof useOperationRecovery>[0]) =>
        useOperationRecovery(props),
      { initialProps: args },
    );

    // Wait for the nested subscription to be established
    await waitFor(() => {
      expect(subscribeToOperationMock).toHaveBeenCalledTimes(1);
    });

    // Switch to strategy-b — cleanup should unsubscribe
    fetchActiveOperationsMock.mockResolvedValue([]);
    rerender(makeArgs({ strategyId: "strategy-b" }));
    await flushPromises();

    expect(unsubscribe).toHaveBeenCalledTimes(1);
  });
});
