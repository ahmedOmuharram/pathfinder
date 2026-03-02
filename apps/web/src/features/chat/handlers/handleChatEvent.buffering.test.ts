import { describe, expect, it, vi } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import type { ToolCall } from "@pathfinder/shared";
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
    const batchState = makeBatchingStateSetters();
    const toolCallsBuffer: ToolCall[] = [];
    const citationsBuffer: any[] = [];
    const planningArtifactsBuffer: any[] = [];
    const subKaniCallsBuffer: Record<string, ToolCall[]> = {};
    const subKaniStatusBuffer: Record<string, string> = {};

    const ctx = {
      siteId: "plasmodb",
      strategyIdAtStart: "s1",
      toolCallsBuffer,
      citationsBuffer,
      planningArtifactsBuffer,
      subKaniCallsBuffer,
      subKaniStatusBuffer,
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
    expect(ctx.streamState.streamingAssistantIndex).toBeNull();
    expect(ctx.streamState.streamingAssistantMessageId).toBeNull();
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

  it("error event appends assistant error message", () => {
    const { ctx, state } = makeCtx();
    handleChatEvent(ctx, { type: "error", data: { error: "Boom" } } as any);
    expect(state.messages[state.messages.length - 1]?.content).toContain("Boom");
  });
});
