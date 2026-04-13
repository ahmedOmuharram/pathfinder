/**
 * Regression tests for modelId / pipeline restore during operation recovery.
 *
 * Scenario: the backend emits `model_selected` once, early in the stream.
 * When the user refreshes AFTER that event was already consumed, the
 * recovery subscription starts from a Redis cursor AFTER the event — so
 * neither `streamState.pipeline` nor `streamState.currentModelId` gets
 * populated during this re-subscription.
 *
 * Consequence: new `assistant_delta` events during recovery create
 * messages WITHOUT a modelId, the model name/icon disappears, and the
 * retroactive stamping in `handleModelSelectedEvent` does nothing
 * because that event never fires.
 *
 * Expected fix: seed `streamState.pipeline` / `currentModelId` from the
 * REST-loaded `strategy.pipeline` payload when the recovery subscription
 * is initialized.  These tests describe the expected seeding behavior
 * and will fail on the unfixed hook (see useOperationRecovery.ts:171-182
 * — everything is initialized to null without consulting REST data).
 *
 * @vitest-environment jsdom
 */

import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
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
  parseChatSSEEvent: vi.fn((raw: { type: string; data: unknown }) => ({
    type: raw.type,
    data: raw.data,
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

function makeStrategyWithPipeline(): Strategy {
  return {
    id: "strategy-a",
    name: "s",
    title: "s",
    siteId: "plasmodb",
    recordType: "transcript",
    steps: [],
    rootStepId: null,
    stepCount: 0,
    isSaved: false,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    pipeline: {
      scoping: { modelId: "gpt-4", reasoningEffort: "low" },
      discovery: { modelId: "gpt-4", reasoningEffort: "medium" },
      planning: { modelId: "gpt-4", reasoningEffort: "high" },
      execution: { modelId: "gpt-4", reasoningEffort: "medium" },
      verification: { modelId: "gpt-4", reasoningEffort: "low" },
    },
  } as Strategy;
}

function makeArgs(
  overrides: Partial<Parameters<typeof useOperationRecovery>[0]> = {},
) {
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
    setSelectedModelId: vi.fn(),
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

describe("useOperationRecovery — modelId / pipeline restore from REST", () => {
  it(
    "seeds streamState.pipeline from currentStrategy.pipeline so that " +
      "assistant_delta events during recovery know the modelId",
    async () => {
      const { Wrapper } = createTestWrapper();

      fetchActiveOperationsMock.mockResolvedValue([
        {
          operationId: "op-resume",
          streamId: "strategy-a",
          type: "chat",
          status: "active",
        },
      ]);

      // Capture the context passed to handleChatEvent so we can inspect
      // streamState.pipeline / streamState.currentModelId at event time.
      let capturedOnEvent:
        | ((e: { type: string; data: unknown }) => void)
        | undefined;
      subscribeToOperationMock.mockImplementation(
        (
          _opId: string,
          opts: {
            onEvent: (e: { type: string; data: unknown }) => void;
          },
        ) => {
          capturedOnEvent = opts.onEvent;
          return { unsubscribe: vi.fn() };
        },
      );

      const strategy = makeStrategyWithPipeline();

      renderHook(
        () =>
          useOperationRecovery(
            makeArgs({
              strategyId: "strategy-a",
              currentStrategy: strategy,
            }),
          ),
        { wrapper: Wrapper },
      );

      await waitFor(() => {
        expect(capturedOnEvent).toBeDefined();
      });

      // Simulate an assistant_delta arriving AFTER the model_selected
      // event was already consumed on the backend.  The recovery
      // subscription will NEVER see a model_selected.
      capturedOnEvent!({
        type: "assistant_delta",
        data: { delta: "hello", messageId: "m1" },
      });

      expect(handleChatEventMock).toHaveBeenCalled();
      const lastCall =
        handleChatEventMock.mock.calls[
          handleChatEventMock.mock.calls.length - 1
        ];
      const ctx = lastCall?.[0] as
        | { streamState: { pipeline: unknown; currentModelId: string | null } }
        | undefined;
      expect(ctx).toBeDefined();

      // EXPECTED after fix: the hook reads strategy.pipeline from REST
      // and seeds streamState.pipeline + streamState.currentModelId
      // before dispatching any recovery events.
      // This assertion FAILS today — the hook hard-codes both to null.
      expect(ctx!.streamState.pipeline).not.toBeNull();
      expect(ctx!.streamState.currentModelId).toBe("gpt-4");
    },
  );

  it(
    "calls setSelectedModelId with strategy.pipeline.planning.modelId on " +
      "recovery when the SSE stream never emits model_selected",
    async () => {
      const { Wrapper } = createTestWrapper();

      fetchActiveOperationsMock.mockResolvedValue([
        {
          operationId: "op-resume",
          streamId: "strategy-a",
          type: "chat",
          status: "active",
        },
      ]);

      subscribeToOperationMock.mockReturnValue({ unsubscribe: vi.fn() });

      const strategy = makeStrategyWithPipeline();
      const setSelectedModelId = vi.fn();

      renderHook(
        () =>
          useOperationRecovery(
            makeArgs({
              strategyId: "strategy-a",
              currentStrategy: strategy,
              setSelectedModelId,
            }),
          ),
        { wrapper: Wrapper },
      );

      await waitFor(() => {
        expect(subscribeToOperationMock).toHaveBeenCalled();
      });

      // EXPECTED after fix: recovery flow calls setSelectedModelId("gpt-4")
      // because the REST-loaded strategy.pipeline is authoritative when
      // the SSE stream is past the model_selected event.
      // This FAILS today.
      expect(setSelectedModelId).toHaveBeenCalledWith("gpt-4");
    },
  );
});
