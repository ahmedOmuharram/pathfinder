/**
 * Regression tests for Issue 5, Part D: ``useOperationRecovery`` currently
 * initializes its per-stream ``streamState`` with ``currentPhase: null`` and
 * ``currentModelId: null``, ignoring the phase the backend has already
 * persisted on the :class:`ConversationState`. When a page reload recovers an
 * in-flight operation, downstream handlers (``handleChatEvent.messageHelpers``
 * etc.) rely on ``streamState.currentPhase`` to tag new assistant messages
 * with the active pipeline phase — without the seed, those messages come out
 * unphased until the next ``phase_change`` event arrives.
 *
 * These tests assert that the recovery hook accepts the REST-loaded
 * ``conversationState`` (either directly as a prop or via the ``currentStrategy``
 * argument) and seeds ``streamState`` so the first post-recovery event is
 * routed correctly. They currently FAIL — the literal ``null`` initializer is
 * still in place.
 *
 * @vitest-environment jsdom
 */

import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";
import { createTestWrapper } from "@/lib/query/testing";
import { useOperationRecovery } from "./useOperationRecovery";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const fetchActiveOperationsMock = vi.hoisted(() => vi.fn());
const subscribeToOperationMock = vi.hoisted(() => vi.fn());
const handleChatEventMock = vi.hoisted(() => vi.fn());

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
  handleChatEvent: handleChatEventMock,
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

function makeStrategyWithPhase(
  conversationState: Record<string, unknown>,
  pipeline: Record<string, unknown> | null = null,
): Strategy {
  return {
    id: "strategy-a",
    name: "Seeded Strategy",
    siteId: "plasmodb",
    steps: [],
    rootStepId: null,
    isSaved: false,
    recordType: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: [],
    conversationState,
    ...(pipeline !== null ? { pipeline } : {}),
  } as Strategy;
}

function makeArgs(
  overrides: Partial<Parameters<typeof useOperationRecovery>[0]> = {},
) {
  return {
    strategyId: "strategy-a" as string | null,
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
    currentStrategy: null as Strategy | null,
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

describe("useOperationRecovery — seeds streamState from REST conversationState", () => {
  let wrapper: ReturnType<typeof createTestWrapper>["Wrapper"];

  beforeEach(() => {
    wrapper = createTestWrapper().Wrapper;
  });

  it("seeds streamState.currentPhase from currentStrategy.conversationState before the first SSE event", async () => {
    const seededStrategy = makeStrategyWithPhase({
      currentPhase: "execution",
      phaseStatus: "started",
    });
    fetchActiveOperationsMock.mockResolvedValue([
      {
        operationId: "op-recovery",
        streamId: "strategy-a",
        type: "chat",
        status: "active",
      },
    ]);
    subscribeToOperationMock.mockImplementation(
      (_opId: string, opts: { onEvent?: (e: { type: string; data: string }) => void }) => {
        // Fire one delta event so handleChatEvent is invoked and we can
        // inspect the streamState passed down by the hook.
        opts.onEvent?.({
          type: "assistant_delta",
          data: JSON.stringify({ delta: "hi", messageId: "m1" }),
        });
        return { unsubscribe: vi.fn() };
      },
    );

    renderHook(
      () =>
        useOperationRecovery(
          makeArgs({
            strategyId: "strategy-a",
            currentStrategy: seededStrategy,
          }),
        ),
      { wrapper },
    );

    await waitFor(() => {
      expect(handleChatEventMock).toHaveBeenCalled();
    });

    const ctxArg = handleChatEventMock.mock.calls[0]?.[0] as
      | { streamState: { currentPhase: string | null } }
      | undefined;
    expect(ctxArg).toBeDefined();
    expect(ctxArg!.streamState.currentPhase).toBe("execution");
  });

  it("seeds streamState.pipeline from currentStrategy.pipeline so phase model IDs survive recovery", async () => {
    const seededStrategy = makeStrategyWithPhase(
      { currentPhase: "planning", phaseStatus: "started" },
      {
        scoping: { modelId: "gpt-5", reasoningEffort: "medium" },
        discovery: { modelId: "gpt-5", reasoningEffort: "medium" },
        planning: { modelId: "claude-4.5", reasoningEffort: "high" },
        execution: { modelId: "gpt-5", reasoningEffort: "medium" },
        verification: { modelId: "gpt-5", reasoningEffort: "medium" },
      },
    );
    fetchActiveOperationsMock.mockResolvedValue([
      {
        operationId: "op-pipeline",
        streamId: "strategy-a",
        type: "chat",
        status: "active",
      },
    ]);
    subscribeToOperationMock.mockImplementation(
      (_opId: string, opts: { onEvent?: (e: { type: string; data: string }) => void }) => {
        opts.onEvent?.({
          type: "assistant_delta",
          data: JSON.stringify({ delta: "x", messageId: "m2" }),
        });
        return { unsubscribe: vi.fn() };
      },
    );

    renderHook(
      () =>
        useOperationRecovery(
          makeArgs({
            strategyId: "strategy-a",
            currentStrategy: seededStrategy,
          }),
        ),
      { wrapper },
    );

    await waitFor(() => {
      expect(handleChatEventMock).toHaveBeenCalled();
    });

    const ctxArg = handleChatEventMock.mock.calls[0]?.[0] as
      | {
          streamState: {
            currentPhase: string | null;
            pipeline: Record<
              string,
              { modelId: string; reasoningEffort: string }
            > | null;
          };
        }
      | undefined;
    expect(ctxArg).toBeDefined();
    expect(ctxArg!.streamState.currentPhase).toBe("planning");
    expect(ctxArg!.streamState.pipeline).not.toBeNull();
    const pipeline = ctxArg!.streamState.pipeline;
    expect(pipeline).not.toBeNull();
    expect(pipeline!["planning"]?.modelId).toBe("claude-4.5");
    expect(pipeline!["execution"]?.modelId).toBe("gpt-5");
  });

  it("falls back to null when currentStrategy has no conversationState", async () => {
    // Establishes the baseline contract: when REST returned no phase state,
    // the recovery hook must leave the seed null instead of inventing one.
    const bareStrategy = {
      id: "strategy-a",
      name: "Bare",
      siteId: "plasmodb",
      steps: [],
      rootStepId: null,
      isSaved: false,
      recordType: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    } as Strategy;

    fetchActiveOperationsMock.mockResolvedValue([
      {
        operationId: "op-empty",
        streamId: "strategy-a",
        type: "chat",
        status: "active",
      },
    ]);
    subscribeToOperationMock.mockImplementation(
      (_opId: string, opts: { onEvent?: (e: { type: string; data: string }) => void }) => {
        opts.onEvent?.({
          type: "assistant_delta",
          data: JSON.stringify({ delta: "y", messageId: "m3" }),
        });
        return { unsubscribe: vi.fn() };
      },
    );

    renderHook(
      () =>
        useOperationRecovery(
          makeArgs({
            strategyId: "strategy-a",
            currentStrategy: bareStrategy,
          }),
        ),
      { wrapper },
    );

    await waitFor(() => {
      expect(handleChatEventMock).toHaveBeenCalled();
    });

    const ctxArg = handleChatEventMock.mock.calls[0]?.[0] as
      | {
          streamState: {
            currentPhase: string | null;
            pipeline: Record<string, unknown> | null;
          };
        }
      | undefined;
    expect(ctxArg).toBeDefined();
    expect(ctxArg!.streamState.currentPhase).toBeNull();
    expect(ctxArg!.streamState.pipeline).toBeNull();
  });
});
