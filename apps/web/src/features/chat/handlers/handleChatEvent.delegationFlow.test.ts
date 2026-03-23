/**
 * Integration tests for the mock delegation flow.
 *
 * These replicate the EXACT events emitted by mock_chat.py when the user
 * sends "delegation", exercising the real strategy store (not a mock
 * addStep). The goal is to isolate why the E2E "delegation creates
 * strategy with steps visible in graph" test intermittently fails.
 *
 * Chain under test:
 *   resolveTargetGraph → handleStrategyUpdateEvent → addStep (real store)
 *     → buildStrategy → useStableGraph → CompactStrategyView
 *
 * Suspected race:
 *   useUnifiedChatDataLoading.applyStrategy calling setStrategy(empty)
 *   after SSE events added steps.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { handleChatEvent } from "./handleChatEvent";
import type { ChatSSEEvent } from "@/lib/sse_events";
import type { Step } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { makeCtx } from "./handleChatEvent.testUtils";

/** Minimal Step with required boolean fields defaulted. */
function step(partial: Partial<Step> & { id: string; displayName: string }): Step {
  return { isBuilt: false, isFiltered: false, ...partial } as Step;
}

// ── Mock delegation events (matches mock_chat.py) ──

const STRATEGY_ID = "test-strat-delegation";

/**
 * The 3 strategy_update events the mock emits for a "delegation" message.
 * graphId and step.graphId both equal the strategy ID.
 */
function makeDelegationEvents(graphId: string): ChatSSEEvent[] {
  return [
    {
      type: "strategy_update",
      data: {
        graphId,
        step: {
          graphId,
          stepId: "mock_search_1",
          kind: "search",
          displayName: "Delegated search step",
          searchName: "mock_search",
          parameters: { q: "gametocyte", min: 10 },
          recordType: "gene",
          graphName: "Delegation-built strategy",
          description: "A deterministic delegated strategy for E2E.",
        },
      },
    } as ChatSSEEvent,
    {
      type: "strategy_update",
      data: {
        graphId,
        step: {
          graphId,
          stepId: "mock_transform_1",
          kind: "transform",
          displayName: "Delegated transform step",
          searchName: "mock_transform",
          primaryInputStepId: "mock_search_1",
          parameters: { insertBetween: true, species: "P. falciparum" },
          recordType: "gene",
        },
      },
    } as ChatSSEEvent,
    {
      type: "strategy_update",
      data: {
        graphId,
        step: {
          graphId,
          stepId: "mock_combine_1",
          kind: "combine",
          displayName: "Delegated combine step",
          operator: "UNION",
          primaryInputStepId: "mock_transform_1",
          secondaryInputStepId: "mock_search_1",
          parameters: {},
          recordType: "gene",
        },
      },
    } as ChatSSEEvent,
  ];
}

// ── Tests ──

describe("resolveTargetGraph logic (tested via handleChatEvent)", () => {
  it("accepts event when graphId matches strategyIdAtStart", () => {
    const { ctx } = makeCtx({ strategyIdAtStart: STRATEGY_ID });
    const events = makeDelegationEvents(STRATEGY_ID);

    handleChatEvent(ctx, events[0]!);
    expect(ctx.addStep).toHaveBeenCalledTimes(1);
  });

  it("rejects event when graphId does not match strategyIdAtStart", () => {
    const { ctx } = makeCtx({ strategyIdAtStart: "other-strategy" });
    const events = makeDelegationEvents(STRATEGY_ID);

    handleChatEvent(ctx, events[0]!);
    expect(ctx.addStep).not.toHaveBeenCalled();
  });

  it("accepts event when strategyIdAtStart is null (no active strategy)", () => {
    const { ctx } = makeCtx({ strategyIdAtStart: null });
    const events = makeDelegationEvents(STRATEGY_ID);

    handleChatEvent(ctx, events[0]!);
    expect(ctx.addStep).toHaveBeenCalledTimes(1);
  });

  it("rejects event when both graphId and strategyIdAtStart are null", () => {
    const { ctx } = makeCtx({ strategyIdAtStart: null });
    // Event with no graphId and no step.graphId
    handleChatEvent(ctx, {
      type: "strategy_update",
      data: { step: { stepId: "x", kind: "search", displayName: "X" } },
    } as ChatSSEEvent);
    expect(ctx.addStep).not.toHaveBeenCalled();
  });
});

describe("mock delegation → real strategy store", () => {
  beforeEach(() => {
    useStrategyStore.getState().clear();
  });

  it("3 strategy_update events produce valid strategy with rootStepId", () => {
    const store = useStrategyStore.getState();
    const session = new StreamingSession(null);
    const { ctx } = makeCtx({
      strategyIdAtStart: STRATEGY_ID,
      session,
      // Wire addStep to the REAL store instead of a mock
      addStep: store.addStep,
      setStrategyMeta: store.setStrategyMeta,
    });

    const events = makeDelegationEvents(STRATEGY_ID);
    for (const event of events) {
      handleChatEvent(ctx, event);
    }

    const state = useStrategyStore.getState();
    expect(state.strategy).not.toBeNull();
    expect(state.strategy!.steps).toHaveLength(3);
    expect(state.strategy!.rootStepId).toBe("mock_combine_1");
    expect(session.snapshotApplied).toBe(true);
  });

  it("each step is correctly added with proper input references", () => {
    const store = useStrategyStore.getState();
    const session = new StreamingSession(null);
    const { ctx } = makeCtx({
      strategyIdAtStart: STRATEGY_ID,
      session,
      addStep: store.addStep,
      setStrategyMeta: store.setStrategyMeta,
    });

    const events = makeDelegationEvents(STRATEGY_ID);
    for (const event of events) {
      handleChatEvent(ctx, event);
    }

    const state = useStrategyStore.getState();
    const search = state.stepsById["mock_search_1"];
    const transform = state.stepsById["mock_transform_1"];
    const combine = state.stepsById["mock_combine_1"];

    expect(search).toBeDefined();
    expect(search!.primaryInputStepId).toBeUndefined();

    expect(transform).toBeDefined();
    expect(transform!.primaryInputStepId).toBe("mock_search_1");

    expect(combine).toBeDefined();
    expect(combine!.primaryInputStepId).toBe("mock_transform_1");
    expect(combine!.secondaryInputStepId).toBe("mock_search_1");
    expect(combine!.operator).toBe("UNION");
  });
});

describe("setStrategy race condition with delegation flow", () => {
  beforeEach(() => {
    useStrategyStore.getState().clear();
  });

  it("setStrategy(emptyStrategy) AFTER addStep×3 wipes all steps", () => {
    // This demonstrates the MECHANISM of the race: setStrategy replaces
    // stepsById with only the incoming strategy's steps.
    const { addStep, setStrategy } = useStrategyStore.getState();

    // Simulate SSE events adding 3 delegation steps
    addStep(
      step({
        id: "mock_search_1",
        displayName: "Search",
        searchName: "mock_search",
        recordType: "gene",
      }),
    );
    addStep(
      step({
        id: "mock_transform_1",
        displayName: "Transform",
        searchName: "mock_transform",
        primaryInputStepId: "mock_search_1",
        recordType: "gene",
      }),
    );
    addStep(
      step({
        id: "mock_combine_1",
        displayName: "Combine",
        operator: "UNION" as const,
        primaryInputStepId: "mock_transform_1",
        secondaryInputStepId: "mock_search_1",
        recordType: "gene",
      }),
    );

    let state = useStrategyStore.getState();
    expect(state.strategy!.steps).toHaveLength(3);
    expect(state.strategy!.rootStepId).toBe("mock_combine_1");

    // Simulate useUnifiedChatDataLoading.applyStrategy calling setStrategy
    // with the server-side strategy (which has 0 steps because mock
    // delegation events don't persist to DB).
    setStrategy({
      id: STRATEGY_ID,
      name: "New Conversation",
      siteId: "plasmodb",
      recordType: null,
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    state = useStrategyStore.getState();
    // BUG: setStrategy(empty) wipes all steps!
    expect(state.strategy?.steps).toHaveLength(0);
    expect(state.strategy?.rootStepId).toBeNull();
  });

  it("setStrategy(emptyStrategy) BEFORE addStep×3 does not prevent steps", () => {
    const { addStep, setStrategy } = useStrategyStore.getState();

    // applyStrategy fires before SSE events arrive
    setStrategy({
      id: STRATEGY_ID,
      name: "New Conversation",
      siteId: "plasmodb",
      recordType: null,
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    // SSE events arrive after
    addStep(
      step({
        id: "mock_search_1",
        displayName: "Search",
        searchName: "mock_search",
        recordType: "gene",
      }),
    );
    addStep(
      step({
        id: "mock_transform_1",
        displayName: "Transform",
        searchName: "mock_transform",
        primaryInputStepId: "mock_search_1",
        recordType: "gene",
      }),
    );
    addStep(
      step({
        id: "mock_combine_1",
        displayName: "Combine",
        operator: "UNION" as const,
        primaryInputStepId: "mock_transform_1",
        secondaryInputStepId: "mock_search_1",
        recordType: "gene",
      }),
    );

    const state = useStrategyStore.getState();
    expect(state.strategy!.steps).toHaveLength(3);
    expect(state.strategy!.rootStepId).toBe("mock_combine_1");
  });

  it("snapshotApplied guard protects against late setStrategy wipe", () => {
    // This simulates the CORRECT path where the guard prevents the wipe.
    // The guard is in useUnifiedChatDataLoading.applyStrategy:
    //   if (strategy.id && !sessionRef.current?.snapshotApplied) { setStrategy(...) }
    const { addStep, setStrategy } = useStrategyStore.getState();
    const session = new StreamingSession(null);

    // SSE events add steps and mark snapshot applied
    addStep(
      step({
        id: "mock_search_1",
        displayName: "Search",
        searchName: "mock_search",
        recordType: "gene",
      }),
    );
    session.markSnapshotApplied();

    addStep(
      step({
        id: "mock_transform_1",
        displayName: "Transform",
        searchName: "mock_transform",
        primaryInputStepId: "mock_search_1",
        recordType: "gene",
      }),
    );
    addStep(
      step({
        id: "mock_combine_1",
        displayName: "Combine",
        operator: "UNION" as const,
        primaryInputStepId: "mock_transform_1",
        secondaryInputStepId: "mock_search_1",
        recordType: "gene",
      }),
    );

    // Guard check (simulates applyStrategy logic)
    const shouldApply = !session.snapshotApplied;
    expect(shouldApply).toBe(false); // guard blocks

    // If guard didn't block, this would wipe:
    if (shouldApply) {
      setStrategy({
        id: STRATEGY_ID,
        name: "New Conversation",
        siteId: "plasmodb",
        recordType: null,
        steps: [],
        rootStepId: null,
        isSaved: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });
    }

    const state = useStrategyStore.getState();
    expect(state.strategy!.steps).toHaveLength(3);
    expect(state.strategy!.rootStepId).toBe("mock_combine_1");
  });

  it("guard FAILS when session exists but snapshotApplied is still false", () => {
    // This is the dangerous timing: getStrategy resolves after the stream
    // session is created but BEFORE any strategy_update events arrive.
    // The session exists (snapshotApplied = false), so the guard passes.
    // But the store is empty at this point, so the wipe is harmless.
    const session = new StreamingSession(null);
    const { setStrategy, addStep } = useStrategyStore.getState();

    // Guard check when store is empty
    const shouldApply = !session.snapshotApplied;
    expect(shouldApply).toBe(true); // guard allows

    // setStrategy on empty store — harmless
    if (shouldApply) {
      setStrategy({
        id: STRATEGY_ID,
        name: "New Conversation",
        siteId: "plasmodb",
        recordType: null,
        steps: [],
        rootStepId: null,
        isSaved: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });
    }

    // SSE events arrive AFTER — steps still get added
    addStep(
      step({
        id: "mock_search_1",
        displayName: "Search",
        searchName: "mock_search",
        recordType: "gene",
      }),
    );

    const state = useStrategyStore.getState();
    expect(state.strategy!.steps).toHaveLength(1);
  });
});
