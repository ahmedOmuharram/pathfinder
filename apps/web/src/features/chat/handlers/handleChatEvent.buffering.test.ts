import { describe, expect, it, vi } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatEventContext } from "./handleChatEvent.types";
import type { ChatSSEEvent } from "@/lib/sse_events";
import type { Citation, PlanningArtifact, ToolCall } from "@pathfinder/shared";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { makeBatchingStateSetters, makeCtx } from "./handleChatEvent.testUtils";

describe("handleChatEvent — buffering & core events", () => {
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
    } as ChatSSEEvent);
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
    } as ChatSSEEvent);

    handleChatEvent(ctx, {
      type: "tool_call_start",
      data: { id: "t1", name: "tool", arguments: "{}" },
    } as ChatSSEEvent);
    handleChatEvent(ctx, {
      type: "tool_call_end",
      data: { id: "t1", result: '{"graphSnapshot":{"graphId":"g1","steps":[]}}' },
    } as ChatSSEEvent);
    expect(applyGraphSnapshot).toHaveBeenCalledWith({ graphId: "g1", steps: [] });

    // Final assistant message should attach everything and clear buffers.
    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { messageId: "m1", content: "hello!" },
    } as ChatSSEEvent);

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
    const batchState = makeBatchingStateSetters();
    const toolCallsBuffer: ToolCall[] = [];
    const citationsBuffer: Citation[] = [];
    const planningArtifactsBuffer: PlanningArtifact[] = [];
    const subKaniCallsBuffer: Record<string, ToolCall[]> = {};
    const subKaniStatusBuffer: Record<string, string> = {};
    const subKaniModelsBuffer: Record<string, string> = {};
    const subKaniTokenUsageBuffer: Record<
      string,
      import("@pathfinder/shared").SubKaniTokenUsage
    > = {};

    const ctx = {
      siteId: "plasmodb",
      strategyIdAtStart: "s1",
      toolCallsBuffer,
      citationsBuffer,
      planningArtifactsBuffer,
      subKaniCallsBuffer,
      subKaniStatusBuffer,
      subKaniModelsBuffer,
      subKaniTokenUsageBuffer,
      thinking: {
        activeToolCalls: [],
        lastToolCalls: [],
        subKaniCalls: {},
        subKaniStatus: {},
        subKaniModels: {},
        reasoning: null,
        subKaniActivity: undefined,
        reset: vi.fn(),
        applyThinkingPayload: vi.fn(() => false),
        updateActiveFromBuffer: vi.fn(),
        finalizeToolCalls: vi.fn(),
        updateReasoning: vi.fn(),
        snapshotSubKaniActivity: vi.fn(() => ({ calls: {}, status: {} })),
        subKaniTaskStart: vi.fn(),
        subKaniToolCallStart: vi.fn(),
        subKaniToolCallEnd: vi.fn(),
        subKaniTaskEnd: vi.fn(),
      } satisfies ChatEventContext["thinking"],
      setStrategyId: vi.fn(),
      addStrategy: vi.fn(),
      addExecutedStrategy: vi.fn(),
      setWdkInfo: vi.fn(),
      setStrategy: vi.fn(),
      setStrategyMeta: vi.fn(),
      clearStrategy: vi.fn(),
      addStep: vi.fn(),
      loadGraph: vi.fn(),
      session: new StreamingSession(null),
      currentStrategy: null,
      setMessages: batchState.setMessages,
      setUndoSnapshots: batchState.setUndoSnapshots,
      parseToolArguments: vi.fn(() => ({})),
      parseToolResult: vi.fn(() => null),
      applyGraphSnapshot: vi.fn(),
      getStrategy: vi.fn(),
      streamState: {
        streamingAssistantIndex: null,
        streamingAssistantMessageId: null,
        turnAssistantIndex: null,
        reasoning: null,
        optimizationProgress: null,
      },
      setOptimizationProgress: vi.fn(),
    };

    // Dispatch all events synchronously (as if they arrived in one SSE chunk).
    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { messageId: "m1", delta: "[mock] " },
    } as ChatSSEEvent);
    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { messageId: "m1", delta: "received: " },
    } as ChatSSEEvent);
    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { messageId: "m1", delta: "hello" },
    } as ChatSSEEvent);
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
    } as ChatSSEEvent);
    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { messageId: "m1", content: "[mock] received: hello" },
    } as ChatSSEEvent);

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
    expect(ctx.streamState.streamingAssistantIndex).toBeNull();
    expect(ctx.streamState.streamingAssistantMessageId).toBeNull();
  });

  it("appends assistant_message when no streaming delta exists", () => {
    const { ctx, state } = makeCtx();
    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { content: "hello" },
    } as ChatSSEEvent);
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.content).toBe("hello");
  });

  it("tool_call_end with unknown id does not crash and still parses result", () => {
    const { ctx, thinking, applyGraphSnapshot } = makeCtx({
      parseToolResult: vi.fn(() => ({ graphSnapshot: { graphId: "g3", steps: [] } })),
    });
    handleChatEvent(ctx, {
      type: "tool_call_end",
      data: { id: "missing", result: "{}" },
    } as ChatSSEEvent);
    expect(thinking.updateActiveFromBuffer).not.toHaveBeenCalled();
    expect(applyGraphSnapshot).toHaveBeenCalledWith({ graphId: "g3", steps: [] });
  });

  it("graph_snapshot delegates to applyGraphSnapshot", () => {
    const { ctx, applyGraphSnapshot } = makeCtx();
    handleChatEvent(ctx, {
      type: "graph_snapshot",
      data: { graphSnapshot: { name: "X", steps: [] } },
    } as ChatSSEEvent);
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
          isSaved: false,
          createdAt: "t",
          updatedAt: "t",
        },
      },
    } as ChatSSEEvent);
    expect(ctx.setStrategyId).toHaveBeenCalledWith("s99");
    expect(ctx.addStrategy).toHaveBeenCalled();
    expect(ctx.loadGraph).toHaveBeenCalledWith("s99");

    handleChatEvent(ctx, {
      type: "reasoning",
      data: { reasoning: "r" },
    } as ChatSSEEvent);
    expect(thinking.updateReasoning).toHaveBeenCalledWith("r");

    handleChatEvent(ctx, {
      type: "subkani_task_start",
      data: { task: "t" },
    } as ChatSSEEvent);
    handleChatEvent(ctx, {
      type: "subkani_tool_call_start",
      data: { task: "t", id: "1", name: "n", arguments: "{}" },
    } as ChatSSEEvent);
    handleChatEvent(ctx, {
      type: "subkani_tool_call_end",
      data: { task: "t", id: "1", result: "ok" },
    } as ChatSSEEvent);
    handleChatEvent(ctx, {
      type: "subkani_task_end",
      data: { task: "t", status: "done" },
    } as ChatSSEEvent);
    expect(thinking.subKaniTaskStart).toHaveBeenCalledWith("t", undefined);
    expect(thinking.subKaniTaskEnd).toHaveBeenCalledWith("t", "done");

    handleChatEvent(ctx, {
      type: "graph_snapshot",
      data: { graphSnapshot: { y: 2 } },
    } as ChatSSEEvent);
    expect(applyGraphSnapshot).toHaveBeenCalledWith({ y: 2 });
  });

  it("error event appends assistant error message", () => {
    const { ctx, state } = makeCtx();
    handleChatEvent(ctx, { type: "error", data: { error: "Boom" } } as ChatSSEEvent);
    expect(state.messages[state.messages.length - 1]?.content).toContain("Boom");
  });

  it("model_selected event calls setSelectedModelId", () => {
    const { ctx } = makeCtx();
    handleChatEvent(ctx, {
      type: "model_selected",
      data: { modelId: "claude-sonnet-4-20250514" },
    } as ChatSSEEvent);
    expect(ctx.setSelectedModelId).toHaveBeenCalledWith("claude-sonnet-4-20250514");
  });

  it("model_selected with empty modelId sets null", () => {
    const { ctx } = makeCtx();
    handleChatEvent(ctx, {
      type: "model_selected",
      data: { modelId: "" },
    } as ChatSSEEvent);
    expect(ctx.setSelectedModelId).toHaveBeenCalledWith(null);
  });

  it("message_end event does not crash and is handled (not unknown)", () => {
    const { ctx } = makeCtx();
    // message_end should be handled gracefully as a no-op.
    handleChatEvent(ctx, { type: "message_end", data: {} } as ChatSSEEvent);
    // If it fell through to "unknown", the handler would just break — no assertions,
    // but verify it doesn't throw.
  });
});
