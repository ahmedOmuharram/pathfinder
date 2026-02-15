import { describe, expect, it, vi } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import type { Message, ToolCall } from "@pathfinder/shared";
import {
  EXECUTE_EPITOPE_SEARCH_EVENTS,
  PLAN_ARTIFACT_EVENTS,
  OPTIMIZATION_PROGRESS_EVENTS,
  DELEGATION_EVENTS,
} from "./__fixtures__/realisticEvents";

function makeStateSetters() {
  let messages: Message[] = [];
  let undoSnapshots: Record<number, any> = {};

  const setMessages = (updater: any) => {
    messages = typeof updater === "function" ? updater(messages) : updater;
  };
  const setUndoSnapshots = (updater: any) => {
    undoSnapshots = typeof updater === "function" ? updater(undoSnapshots) : updater;
  };
  return {
    get messages() {
      return messages;
    },
    get undoSnapshots() {
      return undoSnapshots;
    },
    setMessages,
    setUndoSnapshots,
  };
}

/**
 * Simulates React 18 batching: updaters are queued and executed later
 * (as happens when multiple SSE events arrive in a single chunk).
 */
function makeBatchingStateSetters() {
  let messages: Message[] = [];
  let undoSnapshots: Record<number, any> = {};
  const messageQueue: ((prev: Message[]) => Message[])[] = [];
  const snapshotQueue: ((prev: Record<number, any>) => Record<number, any>)[] = [];

  const setMessages = (updater: any) => {
    if (typeof updater === "function") messageQueue.push(updater);
    else messages = updater;
  };
  const setUndoSnapshots = (updater: any) => {
    if (typeof updater === "function") snapshotQueue.push(updater);
    else undoSnapshots = updater;
  };
  /** Flush queued updaters in order, simulating React's deferred flush. */
  function flush() {
    for (const fn of messageQueue) messages = fn(messages);
    messageQueue.length = 0;
    for (const fn of snapshotQueue) undoSnapshots = fn(undoSnapshots);
    snapshotQueue.length = 0;
  }
  return {
    get messages() {
      return messages;
    },
    get undoSnapshots() {
      return undoSnapshots;
    },
    setMessages,
    setUndoSnapshots,
    flush,
  };
}

describe("features/chat/handlers/handleChatEvent", () => {
  function makeCtx(overrides?: Partial<any>) {
    const toolCallsBuffer: ToolCall[] = [];
    const citationsBuffer: any[] = [];
    const planningArtifactsBuffer: any[] = [];
    const state = makeStateSetters();
    const applyGraphSnapshot = vi.fn();
    const thinking = {
      updateActiveFromBuffer: vi.fn(),
      updateReasoning: vi.fn(),
      snapshotSubKaniActivity: vi.fn(() => ({ calls: {}, status: {} })),
      subKaniTaskStart: vi.fn(),
      subKaniToolCallStart: vi.fn(),
      subKaniToolCallEnd: vi.fn(),
      subKaniTaskEnd: vi.fn(),
    } as any;

    const base = {
      siteId: "plasmodb",
      strategyIdAtStart: "s1",
      toolCallsBuffer,
      citationsBuffer,
      planningArtifactsBuffer,
      thinking,
      setStrategyId: vi.fn(),
      addStrategy: vi.fn(),
      addExecutedStrategy: vi.fn(),
      setWdkInfo: vi.fn(),
      setStrategy: vi.fn(),
      setStrategyMeta: vi.fn(),
      clearStrategy: vi.fn(),
      addStep: vi.fn(),
      loadGraph: vi.fn(),
      pendingUndoSnapshotRef: { current: null as any },
      appliedSnapshotRef: { current: false },
      strategyRef: { current: null as any },
      currentStrategy: null,
      setMessages: state.setMessages,
      setUndoSnapshots: state.setUndoSnapshots,
      parseToolArguments: vi.fn(() => ({ a: 1 })),
      parseToolResult: vi.fn(() => ({ graphSnapshot: { x: 1 } })),
      applyGraphSnapshot,
      getStrategy: vi.fn(),
      streamingAssistantIndexRef: { current: null as number | null },
      streamingAssistantMessageIdRef: { current: null as string | null },
      setOptimizationProgress: vi.fn(),
      reasoningRef: { current: null as string | null },
      optimizationProgressRef: { current: null as any },
    };

    const ctx = { ...base, ...(overrides ?? {}) };
    return {
      ctx,
      state,
      toolCallsBuffer,
      citationsBuffer,
      planningArtifactsBuffer,
      thinking,
      applyGraphSnapshot,
    };
  }

  it("buffers tool calls/citations/artifacts and attaches them on assistant_message", () => {
    const {
      ctx,
      state,
      toolCallsBuffer,
      citationsBuffer,
      planningArtifactsBuffer,
      applyGraphSnapshot,
    } = makeCtx();

    // Start streaming assistant message via delta.
    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { messageId: "m1", delta: "hel" },
    } as ChatSSEEvent);
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.content).toBe("hel");

    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { messageId: "m1", delta: "lo" },
    } as ChatSSEEvent);
    expect(state.messages[0]?.content).toBe("hello");

    // Buffer citations + artifacts + tool calls.
    handleChatEvent(ctx, {
      type: "citations",
      data: { citations: [{ id: "c1", title: "t", source: "web" }] },
    } as any);
    handleChatEvent(ctx, {
      type: "planning_artifact",
      data: {
        planningArtifact: {
          id: "a1",
          title: "Artifact",
          summaryMarkdown: "s",
          assumptions: [],
          parameters: {},
          createdAt: new Date().toISOString(),
        },
      },
    } as any);

    handleChatEvent(ctx, {
      type: "tool_call_start",
      data: { id: "t1", name: "tool", arguments: "{}" },
    } as any);
    handleChatEvent(ctx, {
      type: "tool_call_end",
      data: { id: "t1", result: '{"graphSnapshot":{"x":1}}' },
    } as any);
    expect(applyGraphSnapshot).toHaveBeenCalledWith({ x: 1 });

    // Final assistant message should attach everything and clear buffers.
    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { messageId: "m1", content: "hello!" },
    } as any);

    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.content).toBe("hello!");
    expect(state.messages[0]?.toolCalls?.[0]?.id).toBe("t1");
    expect(state.messages[0]?.citations?.[0]?.id).toBe("c1");
    expect(state.messages[0]?.planningArtifacts?.[0]?.id).toBe("a1");
    expect(toolCallsBuffer).toHaveLength(0);
    expect(citationsBuffer).toHaveLength(0);
    expect(planningArtifactsBuffer).toHaveLength(0);
  });

  it("handles batched SSE events (deltas + artifact + finalize in one synchronous chunk)", () => {
    // Simulate React 18 batching: all setMessages updaters are queued, not
    // executed, until flush(). This mirrors the real browser behavior when the
    // SSE client receives multiple events in a single reader.read() chunk.
    const batchState = makeBatchingStateSetters();
    const toolCallsBuffer: ToolCall[] = [];
    const citationsBuffer: any[] = [];
    const planningArtifactsBuffer: any[] = [];

    const ctx = {
      siteId: "plasmodb",
      strategyIdAtStart: "s1",
      toolCallsBuffer,
      citationsBuffer,
      planningArtifactsBuffer,
      thinking: {
        updateActiveFromBuffer: vi.fn(),
        updateReasoning: vi.fn(),
        snapshotSubKaniActivity: vi.fn(() => ({ calls: {}, status: {} })),
        subKaniTaskStart: vi.fn(),
        subKaniToolCallStart: vi.fn(),
        subKaniToolCallEnd: vi.fn(),
        subKaniTaskEnd: vi.fn(),
      } as any,
      setStrategyId: vi.fn(),
      addStrategy: vi.fn(),
      addExecutedStrategy: vi.fn(),
      setWdkInfo: vi.fn(),
      setStrategy: vi.fn(),
      setStrategyMeta: vi.fn(),
      clearStrategy: vi.fn(),
      addStep: vi.fn(),
      loadGraph: vi.fn(),
      pendingUndoSnapshotRef: { current: null as any },
      appliedSnapshotRef: { current: false },
      strategyRef: { current: null as any },
      currentStrategy: null,
      setMessages: batchState.setMessages,
      setUndoSnapshots: batchState.setUndoSnapshots,
      parseToolArguments: vi.fn(() => ({})),
      parseToolResult: vi.fn(() => null),
      applyGraphSnapshot: vi.fn(),
      getStrategy: vi.fn(),
      streamingAssistantIndexRef: { current: null as number | null },
      streamingAssistantMessageIdRef: { current: null as string | null },
      setOptimizationProgress: vi.fn(),
      reasoningRef: { current: null as string | null },
      optimizationProgressRef: { current: null as any },
    };

    // Dispatch all events synchronously (as if they arrived in one SSE chunk).
    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { messageId: "m1", delta: "[mock] " },
    } as any);
    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { messageId: "m1", delta: "received: " },
    } as any);
    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { messageId: "m1", delta: "hello" },
    } as any);
    handleChatEvent(ctx, {
      type: "planning_artifact",
      data: {
        planningArtifact: {
          id: "a1",
          title: "Art",
          summaryMarkdown: "s",
          assumptions: [],
          parameters: {},
          createdAt: new Date().toISOString(),
        },
      },
    } as any);
    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { messageId: "m1", content: "[mock] received: hello" },
    } as any);

    // Before React flush, messages array is still empty (queued only).
    expect(batchState.messages).toHaveLength(0);

    // Simulate React flushing all batched state updates.
    batchState.flush();

    // After flush: exactly ONE assistant message with final content + artifacts.
    expect(batchState.messages).toHaveLength(1);
    expect(batchState.messages[0]?.role).toBe("assistant");
    expect(batchState.messages[0]?.content).toBe("[mock] received: hello");
    expect(batchState.messages[0]?.planningArtifacts).toHaveLength(1);
    expect(batchState.messages[0]?.planningArtifacts?.[0]?.id).toBe("a1");

    // Refs are cleaned up.
    expect(ctx.streamingAssistantIndexRef.current).toBeNull();
    expect(ctx.streamingAssistantMessageIdRef.current).toBeNull();
  });

  it("strategy_update captures an undo snapshot and assistant_message persists it by message index", () => {
    const { ctx, state } = makeCtx({
      strategyRef: {
        current: {
          id: "s1",
          name: "Draft",
          siteId: "plasmodb",
          recordType: "gene",
          steps: [],
          rootStepId: null,
          createdAt: "t",
          updatedAt: "t",
        },
      },
    });

    handleChatEvent(ctx, {
      type: "strategy_update",
      data: {
        graphId: "s1",
        step: {
          stepId: "a",
          kind: "search",
          displayName: "A",
        },
      },
    } as any);

    expect(ctx.pendingUndoSnapshotRef.current).toBeTruthy();
    expect(ctx.appliedSnapshotRef.current).toBe(true);

    // No streaming assistant active => assistant_message is appended; undo snapshot stored at index.
    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { messageId: "m1", content: "done" },
    } as any);

    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.content).toBe("done");
    expect(Object.keys(state.undoSnapshots)).toEqual(["0"]);
    expect(ctx.pendingUndoSnapshotRef.current).toBeNull();
  });

  it("strategy_update maps step inputs and updates strategy meta", () => {
    const { ctx } = makeCtx();
    handleChatEvent(ctx, {
      type: "strategy_update",
      data: {
        graphId: "s1",
        step: {
          stepId: "c",
          kind: "combine",
          displayName: "Combine",
          primaryInputStepId: "a",
          secondaryInputStepId: "b",
          graphName: "New name",
          description: "Desc",
          recordType: "gene",
        },
      },
    } as any);

    expect(ctx.setStrategyMeta).toHaveBeenCalledWith({
      name: "New name",
      description: "Desc",
      recordType: "gene",
    });
    expect(ctx.addStep).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "c",
        kind: "combine",
        primaryInputStepId: "a",
        secondaryInputStepId: "b",
      }),
    );
  });

  it("graph_snapshot delegates to applyGraphSnapshot", () => {
    const { ctx, applyGraphSnapshot } = makeCtx();
    handleChatEvent(ctx, {
      type: "graph_snapshot",
      data: { graphSnapshot: { name: "X", steps: [] } },
    } as any);
    expect(applyGraphSnapshot).toHaveBeenCalledWith({ name: "X", steps: [] });
  });

  it("handles message_start + reasoning + subkani + graph_snapshot branches", () => {
    const { ctx, thinking, applyGraphSnapshot } = makeCtx();

    handleChatEvent(ctx, {
      type: "message_start",
      data: {
        strategyId: "s99",
        strategy: {
          id: "s99",
          name: "X",
          siteId: "plasmodb",
          recordType: null,
          steps: [],
          rootStepId: null,
          createdAt: "t",
          updatedAt: "t",
        },
      },
    } as any);
    expect(ctx.setStrategyId).toHaveBeenCalledWith("s99");
    expect(ctx.addStrategy).toHaveBeenCalled();
    expect(ctx.loadGraph).toHaveBeenCalledWith("s99");

    handleChatEvent(ctx, { type: "reasoning", data: { reasoning: "r" } } as any);
    expect(thinking.updateReasoning).toHaveBeenCalledWith("r");

    handleChatEvent(ctx, { type: "subkani_task_start", data: { task: "t" } } as any);
    handleChatEvent(ctx, {
      type: "subkani_tool_call_start",
      data: { task: "t", id: "1", name: "n", arguments: "{}" },
    } as any);
    handleChatEvent(ctx, {
      type: "subkani_tool_call_end",
      data: { task: "t", id: "1", result: "ok" },
    } as any);
    handleChatEvent(ctx, {
      type: "subkani_task_end",
      data: { task: "t", status: "done" },
    } as any);
    expect(thinking.subKaniTaskStart).toHaveBeenCalledWith("t");
    expect(thinking.subKaniTaskEnd).toHaveBeenCalledWith("t", "done");

    handleChatEvent(ctx, {
      type: "graph_snapshot",
      data: { graphSnapshot: { y: 2 } },
    } as any);
    expect(applyGraphSnapshot).toHaveBeenCalledWith({ y: 2 });
  });

  it("appends assistant_message when no streaming delta exists", () => {
    const { ctx, state } = makeCtx();
    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { content: "hello" },
    } as any);
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.content).toBe("hello");
  });

  it("tool_call_end with unknown id does not crash and still parses result", () => {
    const { ctx, thinking, applyGraphSnapshot } = makeCtx({
      parseToolResult: vi.fn(() => ({ graphSnapshot: { z: 3 } })),
    });
    handleChatEvent(ctx, {
      type: "tool_call_end",
      data: { id: "missing", result: "{}" },
    } as any);
    expect(thinking.updateActiveFromBuffer).not.toHaveBeenCalled();
    expect(applyGraphSnapshot).toHaveBeenCalledWith({ z: 3 });
  });

  it("handles strategy_link (current strategy vs fetch) and strategy_meta/cleared/error", async () => {
    const currentStrategy = {
      id: "s1",
      name: "Draft",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      createdAt: "t",
      updatedAt: "t",
    };

    const getStrategy = vi.fn(async () => ({
      ...currentStrategy,
      id: "s2",
      name: "Fetched",
    }));

    const { ctx, state } = makeCtx({
      currentStrategy,
      getStrategy,
    });

    // strategy_link with active currentStrategy updates executed list immediately.
    handleChatEvent(ctx, {
      type: "strategy_link",
      data: {
        graphId: "s1",
        wdkStrategyId: 123,
        wdkUrl: "u",
        name: "N",
        description: "D",
      },
    } as any);
    expect(ctx.addExecutedStrategy).toHaveBeenCalled();
    expect(ctx.setWdkInfo).toHaveBeenCalledWith(123, "u", "N", "D");
    expect(ctx.setStrategyMeta).toHaveBeenCalled();

    // strategy_link when no currentStrategy triggers fetch path.
    const { ctx: ctx2 } = makeCtx({
      strategyIdAtStart: null,
      currentStrategy: null,
      getStrategy,
    });
    handleChatEvent(ctx2, { type: "strategy_link", data: { graphId: "s2" } } as any);
    // resolve microtask for then()
    await Promise.resolve();
    expect(getStrategy).toHaveBeenCalledWith("s2");

    // strategy_meta sets meta when targetGraphId matches.
    handleChatEvent(ctx, {
      type: "strategy_meta",
      data: {
        graphId: "s1",
        name: "NewName",
        description: "NewDesc",
        recordType: "gene",
      },
    } as any);
    expect(ctx.setStrategyMeta).toHaveBeenCalledWith({
      name: "NewName",
      description: "NewDesc",
      recordType: "gene",
    });

    // strategy_cleared clears when id matches.
    handleChatEvent(ctx, { type: "strategy_cleared", data: { graphId: "s1" } } as any);
    expect(ctx.clearStrategy).toHaveBeenCalled();

    // error event appends assistant error message.
    handleChatEvent(ctx, { type: "error", data: { error: "Boom" } } as any);
    expect(state.messages[state.messages.length - 1]?.content).toContain("Boom");
  });

  it("handles strategy_update guards and applies step updates", () => {
    const snapshot = {
      id: "s1",
      name: "Snap",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      createdAt: "t",
      updatedAt: "t",
    };

    const { ctx } = makeCtx({
      strategyRef: { current: snapshot },
      pendingUndoSnapshotRef: { current: null },
      appliedSnapshotRef: { current: false },
    });

    // Guard: mismatched graphId should do nothing when strategyIdAtStart is set.
    handleChatEvent(ctx, {
      type: "strategy_update",
      data: {
        graphId: "other",
        step: { stepId: "x", kind: "search", displayName: "X", recordType: "gene" },
      },
    } as any);
    expect(ctx.addStep).not.toHaveBeenCalled();

    // Matching graph id applies update and captures undo snapshot.
    handleChatEvent(ctx, {
      type: "strategy_update",
      data: {
        graphId: "s1",
        step: {
          stepId: "a",
          kind: "search",
          displayName: "A",
          searchName: "q",
          recordType: "gene",
          name: "StrategyName",
          description: "Desc",
        },
      },
    } as any);
    expect(ctx.addStep).toHaveBeenCalledWith(
      expect.objectContaining({ id: "a", displayName: "A", searchName: "q" }),
    );
    expect(ctx.setStrategyMeta).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "StrategyName",
        description: "Desc",
        recordType: "gene",
      }),
    );
    expect(ctx.appliedSnapshotRef.current).toBe(true);
    expect(ctx.pendingUndoSnapshotRef.current).toEqual(snapshot);
  });

  // Realistic event sequences — replay full SSE streams from backend scenarios

  describe("realistic execute mode: epitope search + build", () => {
    it("processes full event stream without errors and produces correct state", () => {
      const currentStrategy = {
        id: "strat-001",
        name: "Draft Strategy",
        siteId: "plasmodb",
        recordType: null as string | null,
        steps: [],
        rootStepId: null,
        createdAt: "2025-02-15T00:00:00Z",
        updatedAt: "2025-02-15T00:00:00Z",
      };
      const { ctx, state, toolCallsBuffer, applyGraphSnapshot, thinking } = makeCtx({
        strategyIdAtStart: "strat-001",
        currentStrategy,
        strategyRef: { current: currentStrategy },
        getStrategy: vi.fn(async () => currentStrategy),
      });

      for (const event of EXECUTE_EPITOPE_SEARCH_EVENTS) {
        handleChatEvent(ctx, event as ChatSSEEvent);
      }

      // ── Strategy initialization ──
      expect(ctx.setStrategyId).toHaveBeenCalledWith("strat-001");
      expect(ctx.addStrategy).toHaveBeenCalled();
      expect(ctx.loadGraph).toHaveBeenCalledWith("strat-001");

      // ── Tool calls processed ──
      // search_for_searches + create_step + build_strategy = 3 tool calls completed
      expect(toolCallsBuffer).toHaveLength(0); // cleared after assistant_message

      // ── Strategy updates applied ──
      expect(ctx.addStep).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "step-001",
          kind: "search",
          searchName: "GenesWithEpitopes",
        }),
      );
      expect(ctx.setStrategyMeta).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Epitope vaccine targets",
          recordType: "transcript",
        }),
      );

      // ── WDK link applied ──
      expect(ctx.addExecutedStrategy).toHaveBeenCalled();
      expect(ctx.setWdkInfo).toHaveBeenCalledWith(
        987654,
        "https://plasmodb.org/plasmo/app/workspace/strategies/987654",
        "Epitope vaccine targets",
        undefined,
      );

      // ── Final assistant message ──
      expect(state.messages).toHaveLength(1);
      const msg = state.messages[0]!;
      expect(msg.role).toBe("assistant");
      expect(msg.content).toBe(
        "I've built a strategy for P. falciparum genes with high or medium epitope evidence.",
      );
      // Tool calls should be attached to the message
      expect(msg.toolCalls).toBeDefined();
      expect(msg.toolCalls!.length).toBeGreaterThanOrEqual(3);
      expect(msg.toolCalls!.map((tc: ToolCall) => tc.name)).toEqual(
        expect.arrayContaining([
          "search_for_searches",
          "create_step",
          "build_strategy",
        ]),
      );

      // ── Refs cleaned up ──
      expect(ctx.streamingAssistantIndexRef.current).toBeNull();
      expect(ctx.streamingAssistantMessageIdRef.current).toBeNull();
    });

    it("handles batched delivery (React 18 batching) of realistic events", () => {
      const batchState = makeBatchingStateSetters();
      const toolCallsBuffer: ToolCall[] = [];
      const citationsBuffer: any[] = [];
      const planningArtifactsBuffer: any[] = [];

      const ctx = {
        siteId: "plasmodb",
        strategyIdAtStart: "strat-001" as string | null,
        toolCallsBuffer,
        citationsBuffer,
        planningArtifactsBuffer,
        thinking: {
          updateActiveFromBuffer: vi.fn(),
          updateReasoning: vi.fn(),
          snapshotSubKaniActivity: vi.fn(() => ({ calls: {}, status: {} })),
          subKaniTaskStart: vi.fn(),
          subKaniToolCallStart: vi.fn(),
          subKaniToolCallEnd: vi.fn(),
          subKaniTaskEnd: vi.fn(),
        } as any,
        setStrategyId: vi.fn(),
        addStrategy: vi.fn(),
        addExecutedStrategy: vi.fn(),
        setWdkInfo: vi.fn(),
        setStrategy: vi.fn(),
        setStrategyMeta: vi.fn(),
        clearStrategy: vi.fn(),
        addStep: vi.fn(),
        loadGraph: vi.fn(),
        pendingUndoSnapshotRef: { current: null as any },
        appliedSnapshotRef: { current: false },
        strategyRef: { current: null as any },
        currentStrategy: null,
        setMessages: batchState.setMessages,
        setUndoSnapshots: batchState.setUndoSnapshots,
        parseToolArguments: vi.fn(() => ({})),
        parseToolResult: vi.fn(() => null),
        applyGraphSnapshot: vi.fn(),
        getStrategy: vi.fn(async () => ({
          id: "strat-001",
          name: "Epitope vaccine targets",
          siteId: "plasmodb",
          recordType: "gene",
          steps: [],
          rootStepId: null,
          createdAt: "t",
          updatedAt: "t",
        })),
        streamingAssistantIndexRef: { current: null as number | null },
        streamingAssistantMessageIdRef: { current: null as string | null },
        setOptimizationProgress: vi.fn(),
        reasoningRef: { current: null as string | null },
        optimizationProgressRef: { current: null as any },
      };

      // Dispatch all events synchronously (simulating chunk delivery)
      for (const event of EXECUTE_EPITOPE_SEARCH_EVENTS) {
        handleChatEvent(ctx, event as ChatSSEEvent);
      }

      // Before flush, messages are queued
      expect(batchState.messages).toHaveLength(0);

      batchState.flush();

      // After flush: one assistant message with correct content
      expect(batchState.messages).toHaveLength(1);
      expect(batchState.messages[0]?.role).toBe("assistant");
      expect(batchState.messages[0]?.content).toContain("epitope evidence");
    });
  });

  describe("realistic plan mode: artifact + executor request", () => {
    it("processes planning events and fires callbacks", () => {
      const onPlanSessionId = vi.fn();
      const onPlanningArtifactUpdate = vi.fn();
      const onExecutorBuildRequest = vi.fn();

      const { ctx, state, planningArtifactsBuffer } = makeCtx({
        onPlanSessionId,
        onPlanningArtifactUpdate,
        onExecutorBuildRequest,
      });

      for (const event of PLAN_ARTIFACT_EVENTS) {
        handleChatEvent(ctx, event as ChatSSEEvent);
      }

      // ── Artifact should be buffered then attached ──
      expect(state.messages).toHaveLength(1);
      const msg = state.messages[0]!;
      expect(msg.planningArtifacts).toBeDefined();
      if (msg.planningArtifacts && msg.planningArtifacts.length > 0) {
        expect(msg.planningArtifacts[0]?.title).toBe("Vaccine target search plan");
      }

      // ── Callbacks fired ──
      if (onPlanningArtifactUpdate.mock.calls.length > 0) {
        expect(onPlanningArtifactUpdate).toHaveBeenCalledWith(
          expect.objectContaining({ id: "artifact-001" }),
        );
      }

      if (onExecutorBuildRequest.mock.calls.length > 0) {
        expect(onExecutorBuildRequest).toHaveBeenCalled();
      }

      // Refs cleaned up
      expect(ctx.streamingAssistantIndexRef.current).toBeNull();
    });
  });

  describe("realistic optimization progress events", () => {
    it("updates optimization progress through started → trials → completed", () => {
      const { ctx, state } = makeCtx();

      for (const event of OPTIMIZATION_PROGRESS_EVENTS) {
        handleChatEvent(ctx, event as ChatSSEEvent);
      }

      // setOptimizationProgress should have been called multiple times
      expect(ctx.setOptimizationProgress).toHaveBeenCalled();
      const calls = ctx.setOptimizationProgress.mock.calls;
      // At least 5 calls: started + 3 trials + completed
      expect(calls.length).toBeGreaterThanOrEqual(5);

      // Final message should exist
      expect(state.messages).toHaveLength(1);
      expect(state.messages[0]?.content).toBe("Optimization complete.");
    });
  });

  describe("realistic delegation (sub-kani) events", () => {
    it("routes sub-kani lifecycle events to thinking tracker", () => {
      const { ctx, state, thinking } = makeCtx({
        strategyIdAtStart: "strat-del",
        getStrategy: vi.fn(async () => ({
          id: "strat-del",
          name: "Delegation strategy",
          siteId: "plasmodb",
          recordType: "gene",
          steps: [],
          rootStepId: null,
          createdAt: "t",
          updatedAt: "t",
        })),
      });

      for (const event of DELEGATION_EVENTS) {
        handleChatEvent(ctx, event as ChatSSEEvent);
      }

      // ── Strategy initialized ──
      expect(ctx.setStrategyId).toHaveBeenCalledWith("strat-del");
      expect(ctx.loadGraph).toHaveBeenCalledWith("strat-del");

      // ── Sub-kani lifecycle ──
      expect(thinking.subKaniTaskStart).toHaveBeenCalledWith("delegate:build-step-1");
      expect(thinking.subKaniToolCallStart).toHaveBeenCalledTimes(2);
      expect(thinking.subKaniToolCallEnd).toHaveBeenCalledTimes(2);
      expect(thinking.subKaniTaskEnd).toHaveBeenCalledWith(
        "delegate:build-step-1",
        "done",
      );

      // ── Strategy update from delegation ──
      expect(ctx.addStep).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "step-d1",
          kind: "search",
          searchName: "GenesWithEpitopes",
        }),
      );

      // ── Final message ──
      expect(state.messages).toHaveLength(1);
      expect(state.messages[0]?.content).toBe("Delegation complete.");
    });
  });
});
