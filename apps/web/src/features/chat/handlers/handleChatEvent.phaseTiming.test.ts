import { beforeEach, describe, expect, it } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatSSEEvent } from "@/lib/sse_events";
import { makeCtx } from "./handleChatEvent.testUtils";
import { usePlanStore } from "@/state/usePlanStore";

describe("handleChatEvent phase timing", () => {
  beforeEach(() => {
    usePlanStore.setState({
      activePlan: null,
      isPlanPinned: false,
      planThoughts: [],
      sendMessage: null,
      submitPlanAction: null,
      currentPhase: null,
      phaseStatus: null,
      phaseTimings: {},
    });
  });

  it("stores phase timing metadata from phase_change events", () => {
    const { ctx } = makeCtx();

    handleChatEvent(ctx, {
      type: "phase_change",
      data: {
        phase: "planning",
        status: "completed",
        messageId: "plan-msg",
        emittedAt: "2026-04-10T21:44:00Z",
        phaseStartedAt: "2026-04-10T21:43:30Z",
        phaseCompletedAt: "2026-04-10T21:44:00Z",
        durationMs: 30000,
      },
    } as ChatSSEEvent);

    const timing = usePlanStore.getState().phaseTimings.planning;
    expect(timing).toBeDefined();
    expect(timing?.status).toBe("completed");
    expect(timing?.phaseStartedAt).toBe("2026-04-10T21:43:30Z");
    expect(timing?.phaseCompletedAt).toBe("2026-04-10T21:44:00Z");
    expect(timing?.durationMs).toBe(30000);
  });

  it("clears phase timings when a new user message arrives", () => {
    usePlanStore.setState({
      phaseTimings: {
        planning: {
          phase: "planning",
          status: "completed",
          emittedAt: "2026-04-10T21:44:00Z",
          phaseStartedAt: "2026-04-10T21:43:30Z",
          phaseCompletedAt: "2026-04-10T21:44:00Z",
          durationMs: 30000,
        },
      },
      planThoughts: ["Old thinking"],
      currentPhase: "planning",
      phaseStatus: "completed",
    });
    const { ctx } = makeCtx();

    handleChatEvent(ctx, {
      type: "user_message",
      data: { content: "new question" },
    } as ChatSSEEvent);

    expect(usePlanStore.getState().phaseTimings).toEqual({});
    expect(usePlanStore.getState().planThoughts).toEqual([]);
    expect(usePlanStore.getState().currentPhase).toBeNull();
    expect(usePlanStore.getState().phaseStatus).toBeNull();
  });
});
