import { describe, expect, it, vi } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import { DELEGATION_EVENTS } from "./__fixtures__/realisticEvents";
import { makeCtx } from "./handleChatEvent.testUtils";

describe("handleChatEvent — realistic delegation (phase-agent) events", () => {
  it("routes tool call events and strategy updates correctly", () => {
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

    // Strategy initialized
    expect(ctx.setStrategyId).toHaveBeenCalledWith("strat-del");
    expect(ctx.loadGraph).toHaveBeenCalledWith("strat-del");

    // Tool calls tracked
    expect(thinking.updateActiveFromBuffer).toHaveBeenCalled();

    // Strategy update from delegation
    expect(ctx.addStep).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "step-d1",
        kind: "search",
        searchName: "GenesWithEpitopes",
      }),
    );

    // Final message
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.content).toBe("Delegation complete.");
  });
});
