import { describe, expect, it, vi } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatSSEEvent } from "@/lib/sse_events";
import { DELEGATION_EVENTS } from "./__fixtures__/realisticEvents";
import { makeCtx } from "./handleChatEvent.testUtils";

describe("handleChatEvent — realistic delegation (sub-kani) events", () => {
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
        isSaved: false,
        createdAt: "t",
        updatedAt: "t",
      })),
    });

    for (const event of DELEGATION_EVENTS) {
      handleChatEvent(ctx, event);
    }

    // ── Strategy initialized ──
    expect(ctx.setStrategyId).toHaveBeenCalledWith("strat-del");
    expect(ctx.loadGraph).toHaveBeenCalledWith("strat-del");

    // ── Sub-kani lifecycle ──
    expect(thinking.subKaniTaskStart).toHaveBeenCalledWith(
      "delegate:build-step-1",
      undefined,
    );
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
