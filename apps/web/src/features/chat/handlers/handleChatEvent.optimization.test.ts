import { describe, expect, it } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import { OPTIMIZATION_PROGRESS_EVENTS } from "./__fixtures__/realisticEvents";
import { makeCtx } from "./handleChatEvent.testUtils";

describe("handleChatEvent — optimization progress events", () => {
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

    // Final message should exist and carry persisted optimization payload
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.content).toBe("Optimization complete.");
    expect(state.messages[0]?.optimizationProgress).toBeDefined();
    expect(state.messages[0]?.optimizationProgress?.status).toBe("completed");
  });

  it("does not attach optimization_progress to previous assistant before current turn assistant exists", () => {
    const { ctx, state } = makeCtx();

    // Seed prior conversation history (outside current streaming turn).
    state.setMessages([
      {
        role: "assistant",
        content: "Previous answer.",
        timestamp: "2026-01-01T00:00:00.000Z",
      },
      {
        role: "user",
        content: "new question",
        timestamp: "2026-01-01T00:00:01.000Z",
      },
    ]);

    expect(ctx.streamState.streamingAssistantIndex).toBeNull();
    expect(state.messages).toHaveLength(2);

    handleChatEvent(ctx, {
      type: "optimization_progress",
      data: {
        optimizationId: "opt-test",
        status: "running",
        totalTrials: 5,
        currentTrial: 2,
        recentTrials: [
          {
            trialNumber: 1,
            parameters: {},
            score: 0.5,
            recall: 0.5,
            falsePositiveRate: 0.1,
            resultCount: 10,
          },
        ],
      },
    } as any);

    // Progress is live-only at this point; previous assistant must remain untouched.
    expect(state.messages[0]?.optimizationProgress).toBeUndefined();
  });

  it("attaches optimization_progress to current turn assistant only", () => {
    const { ctx, state } = makeCtx();

    // Seed prior conversation history (outside current streaming turn).
    state.setMessages([
      {
        role: "assistant",
        content: "Starting.",
        timestamp: "2026-01-01T00:00:00.000Z",
      },
      {
        role: "user",
        content: "optimize this",
        timestamp: "2026-01-01T00:00:01.000Z",
      },
    ]);

    // Live optimization arrives before assistant_delta for this turn.
    handleChatEvent(ctx, {
      type: "optimization_progress",
      data: {
        optimizationId: "opt-2",
        status: "completed",
        totalTrials: 3,
        currentTrial: 3,
      },
    } as any);

    // Current turn assistant starts streaming.
    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { messageId: "m2", delta: "Done." },
    } as ChatSSEEvent);
    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { messageId: "m2", content: "Done." },
    } as any);

    expect(state.messages).toHaveLength(3);
    // Previous assistant must stay clean.
    expect(state.messages[0]?.optimizationProgress).toBeUndefined();
    // Current assistant owns optimization for this turn.
    expect(state.messages[2]?.optimizationProgress?.status).toBe("completed");
  });
});
