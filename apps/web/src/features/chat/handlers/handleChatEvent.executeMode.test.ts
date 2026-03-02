import { describe, expect, it, vi } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import type { ToolCall } from "@pathfinder/shared";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { EXECUTE_EPITOPE_SEARCH_EVENTS } from "./__fixtures__/realisticEvents";
import { makeBatchingStateSetters, makeCtx } from "./handleChatEvent.testUtils";

describe("handleChatEvent — realistic execute mode", () => {
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
    const { ctx, state, toolCallsBuffer } = makeCtx({
      strategyIdAtStart: "strat-001",
      currentStrategy,
      session: new StreamingSession(currentStrategy),
      getStrategy: vi.fn(async () => currentStrategy),
    });

    for (const event of EXECUTE_EPITOPE_SEARCH_EVENTS) {
      handleChatEvent(ctx, event as ChatSSEEvent);
    }

    // ── Strategy initialization (callbacks are the component interface) ──
    expect(ctx.setStrategyId).toHaveBeenCalledWith("strat-001");
    expect(ctx.addStrategy).toHaveBeenCalled();
    expect(ctx.loadGraph).toHaveBeenCalledWith("strat-001");

    // ── Tool calls processed ──
    expect(toolCallsBuffer).toHaveLength(0); // cleared after assistant_message

    // ── Strategy updates applied (callbacks are the component interface) ──
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

    // ── WDK link applied (callbacks are the component interface) ──
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
    expect(msg.toolCalls).toBeDefined();
    expect(msg.toolCalls!.length).toBeGreaterThanOrEqual(3);
    expect(msg.toolCalls!.map((tc: ToolCall) => tc.name)).toEqual(
      expect.arrayContaining(["search_for_searches", "create_step", "build_strategy"]),
    );

    // ── Refs cleaned up ──
    expect(ctx.streamState.streamingAssistantIndex).toBeNull();
    expect(ctx.streamState.streamingAssistantMessageId).toBeNull();
  });

  it("handles batched delivery (React 18 batching) of realistic events", () => {
    const batchState = makeBatchingStateSetters();
    const toolCallsBuffer: ToolCall[] = [];
    const citationsBuffer: any[] = [];
    const planningArtifactsBuffer: any[] = [];
    const subKaniCallsBuffer: Record<string, ToolCall[]> = {};
    const subKaniStatusBuffer: Record<string, string> = {};

    const ctx = {
      siteId: "plasmodb",
      strategyIdAtStart: "strat-001" as string | null,
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
      streamState: {
        streamingAssistantIndex: null,
        streamingAssistantMessageId: null,
        turnAssistantIndex: null,
        reasoning: null,
        optimizationProgress: null,
      },
      setOptimizationProgress: vi.fn(),
    };

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
