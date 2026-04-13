/**
 * Regression tests for useOperationRecovery — Race C.
 *
 * Race C: The first query (`operation-recovery`) is gated by
 * `!isStreaming`, but the second query (`operation-recovery-stream`) is
 * gated only by `activeOp != null && strategyId != null`. If the user
 * sends a new chat message while the first query is in-flight,
 * `isStreaming` flips to true BEFORE the second query evaluates its
 * `enabled` condition. Today, the second query still fires and
 * subscribes to the stale `activeOp.operationId`, creating a duplicate
 * subscription alongside the fresh chat stream.
 *
 * Expected post-fix behavior:
 *   - When isStreaming=true by the time the recovery subscription would
 *     fire, `subscribeToOperation` MUST NOT be invoked.
 *
 * @vitest-environment jsdom
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";
import { createTestWrapper } from "@/lib/query/testing";
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

vi.mock("@/features/chat/streaming/StreamingSession", () => ({
  StreamingSession: class MockStreamingSession {
    latestStrategy = null;
    snapshotApplied = false;
    consumeUndoSnapshot = vi.fn();
  },
}));

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: (selector: (s: { authRefreshed: boolean }) => unknown) =>
    selector({ authRefreshed: true }),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function flushPromises(): Promise<void> {
  await act(async () => {
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

describe("useOperationRecovery — Race C (duplicate subscription)", () => {
  let wrapper: ReturnType<typeof createTestWrapper>["Wrapper"];

  beforeEach(() => {
    wrapper = createTestWrapper().Wrapper;
  });

  it("does not subscribe when isStreaming flips to true before second query fires", async () => {
    // The first query returns an active operation.
    fetchActiveOperationsMock.mockResolvedValue([
      { operationId: "stale-op-1", streamId: "strategy-a", type: "chat", status: "active" },
    ]);
    subscribeToOperationMock.mockReturnValue({ unsubscribe: vi.fn() });

    const args = makeArgs({ strategyId: "strategy-a", isStreaming: false });

    const { rerender } = renderHook(
      (props: Parameters<typeof useOperationRecovery>[0]) => useOperationRecovery(props),
      { initialProps: args, wrapper },
    );

    // User sends a new chat message -- isStreaming flips to true BEFORE the
    // second query evaluates its `enabled` expression. Re-render with the new
    // prop immediately so the effect runs with isStreaming=true.
    rerender(makeArgs({ strategyId: "strategy-a", isStreaming: true }));

    await flushPromises();
    await flushPromises();

    // Assert: the stale recovery subscription must NOT fire. The caller's
    // active chat stream is the only legitimate subscription.
    expect(subscribeToOperationMock).toHaveBeenCalledTimes(0);
  });

  it("does not subscribe when a new stream starts mid-recovery-lookup", async () => {
    // First query is slow -- pretend the fetch is pending while the user
    // initiates a new chat stream which sets isStreaming=true.
    let resolveFetch: ((ops: Array<{ operationId: string; streamId: string; type: string; status: string }>) => void) | undefined;
    fetchActiveOperationsMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );
    subscribeToOperationMock.mockReturnValue({ unsubscribe: vi.fn() });

    const args = makeArgs({ strategyId: "strategy-a", isStreaming: false });

    const { rerender } = renderHook(
      (props: Parameters<typeof useOperationRecovery>[0]) => useOperationRecovery(props),
      { initialProps: args, wrapper },
    );

    // User sends message: isStreaming flips to true.
    rerender(makeArgs({ strategyId: "strategy-a", isStreaming: true }));

    // Now the slow recovery fetch resolves with an active op.
    await act(async () => {
      resolveFetch!([
        { operationId: "stale-op-2", streamId: "strategy-a", type: "chat", status: "active" },
      ]);
    });

    await flushPromises();
    await flushPromises();

    // Because isStreaming is true, the second query must not subscribe.
    expect(subscribeToOperationMock).toHaveBeenCalledTimes(0);
  });
});
