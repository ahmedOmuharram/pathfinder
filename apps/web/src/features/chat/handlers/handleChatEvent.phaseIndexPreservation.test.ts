/**
 * Regression tests for handlePhaseChangeEvent — Race B.
 *
 * Race B: When a `phase_change` event with `status === "started"` arrives,
 * the handler unconditionally resets `streamState.streamingAssistantIndex`
 * to `null`. But if `messageId` is the SAME as the currently-streaming
 * message, the index should be preserved (lookup-by-messageId is stable).
 *
 * Nulling the index forces a re-lookup on the next delta; if the lookup
 * fails (e.g. because the message hasn't been inserted yet or was filtered
 * out), a duplicate message may be appended.
 *
 * Expected post-fix behavior:
 *   - SAME messageId: streamingAssistantIndex is preserved.
 *   - DIFFERENT messageId: streamingAssistantIndex is reset to null.
 */

import { describe, expect, it, beforeEach } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatSSEEvent } from "@/lib/sse_events";
import { makeCtx } from "./handleChatEvent.testUtils";
import { usePlanStore } from "@/state/usePlanStore";

describe("handlePhaseChangeEvent — Race B (streamingAssistantIndex preservation)", () => {
  beforeEach(() => {
    // Reset plan store to a clean state so test ordering does not leak.
    usePlanStore.setState({
      activePlan: null,
      activePlanTraceId: null,
      activePlanMessageGroupId: null,
      isPlanPinned: false,
      planThoughts: [],
      sendMessage: null,
      submitPlanAction: null,
      currentPhase: null,
      phaseStatus: null,
      phaseTimings: {},
    });
  });

  it("phase_change with SAME messageId preserves streamingAssistantIndex", () => {
    const { ctx } = makeCtx();

    // Seed the stream state: assistant message "msg-1" already streaming at index 3.
    ctx.streamState.streamingAssistantMessageId = "msg-1";
    ctx.streamState.streamingAssistantIndex = 3;

    handleChatEvent(ctx, {
      type: "phase_change",
      data: {
        phase: "execution",
        status: "started",
        messageId: "msg-1",
      },
    } as ChatSSEEvent);

    // Expected post-fix: SAME messageId -> index is NOT reset.
    expect(ctx.streamState.streamingAssistantIndex).toBe(3);
    // Sanity: messageId is still the same.
    expect(ctx.streamState.streamingAssistantMessageId).toBe("msg-1");
  });

  it("phase_change with DIFFERENT messageId resets streamingAssistantIndex", () => {
    const { ctx } = makeCtx();

    // Seed: currently streaming msg-1 at index 3.
    ctx.streamState.streamingAssistantMessageId = "msg-1";
    ctx.streamState.streamingAssistantIndex = 3;

    handleChatEvent(ctx, {
      type: "phase_change",
      data: {
        phase: "execution",
        status: "started",
        messageId: "msg-2",
      },
    } as ChatSSEEvent);

    // New message id: index must be cleared so the next delta locates the
    // new message. This is the expected/correct reset path.
    expect(ctx.streamState.streamingAssistantIndex).toBeNull();
    expect(ctx.streamState.streamingAssistantMessageId).toBe("msg-2");
  });

  it("phase_change with SAME messageId keeps the messageId stable", () => {
    const { ctx } = makeCtx();

    ctx.streamState.streamingAssistantMessageId = "msg-x";
    ctx.streamState.streamingAssistantIndex = 0;

    handleChatEvent(ctx, {
      type: "phase_change",
      data: {
        phase: "discovery",
        status: "started",
        messageId: "msg-x",
      },
    } as ChatSSEEvent);

    expect(ctx.streamState.streamingAssistantMessageId).toBe("msg-x");
    expect(ctx.streamState.streamingAssistantIndex).toBe(0);
  });

  it("phase_change with status!=started does not reset streamingAssistantIndex", () => {
    const { ctx } = makeCtx();

    ctx.streamState.streamingAssistantMessageId = "msg-1";
    ctx.streamState.streamingAssistantIndex = 5;

    handleChatEvent(ctx, {
      type: "phase_change",
      data: {
        phase: "execution",
        status: "completed",
        messageId: "msg-1",
      },
    } as ChatSSEEvent);

    expect(ctx.streamState.streamingAssistantIndex).toBe(5);
    expect(ctx.streamState.streamingAssistantMessageId).toBe("msg-1");
  });
});
