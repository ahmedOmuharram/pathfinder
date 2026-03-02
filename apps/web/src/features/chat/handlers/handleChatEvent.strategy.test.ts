import { describe, expect, it, vi } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { makeCtx } from "./handleChatEvent.testUtils";

describe("handleChatEvent — strategy events", () => {
  it("strategy_update captures an undo snapshot and assistant_message persists it by message index", () => {
    const strategySnapshot = {
      id: "s1",
      name: "Draft",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      createdAt: "t",
      updatedAt: "t",
    };
    const session = new StreamingSession(strategySnapshot);
    const { ctx, state } = makeCtx({ session });

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

    expect(ctx.session.undoSnapshot).toBeTruthy();
    expect(ctx.session.snapshotApplied).toBe(true);

    // No streaming assistant active => assistant_message is appended; undo snapshot stored at index.
    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { messageId: "m1", content: "done" },
    } as any);

    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.content).toBe("done");
    expect(Object.keys(state.undoSnapshots)).toEqual(["0"]);
    expect(ctx.session.undoSnapshot).toBeNull();
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

  it("handles strategy_link (current strategy vs fetch) and strategy_meta/cleared", async () => {
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

    const { ctx } = makeCtx({
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

    const session = new StreamingSession(snapshot);
    const { ctx } = makeCtx({ session });

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
    expect(ctx.session.snapshotApplied).toBe(true);
    expect(ctx.session.undoSnapshot).toEqual(snapshot);
  });
});
