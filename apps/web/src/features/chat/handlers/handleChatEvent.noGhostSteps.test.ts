/**
 * Regression tests for Issue 2: Ghost steps during planning phase.
 *
 * The backend emits two distinct SSE events:
 *   - graph_plan     -> proposed plan payload (planning phase)
 *   - graph_snapshot -> real WDK-executed graph (execution phase)
 *
 * Both events share a similar shape. The bug was that `graph_plan`
 * was being handled like `graph_snapshot` and was calling
 * `applyGraphSnapshot`, which mounted planned steps as real WDK
 * steps in the strategy graph (ghost steps).
 *
 * The fix: `handleGraphPlanEvent` at
 *   apps/web/src/features/chat/handlers/handleChatEvent.strategyEvents.ts
 * only calls `setStrategyMeta` — it does NOT call `applyGraphSnapshot`.
 * Only `handleGraphSnapshotEvent` may call `applyGraphSnapshot`.
 *
 * These tests guard against regressing that fix.
 */
import { describe, expect, it } from "vitest";
import type { ChatSSEEvent } from "@/lib/sse_events";
import { handleChatEvent } from "./handleChatEvent";
import {
  handleGraphPlanEvent,
  handleGraphSnapshotEvent,
} from "./handleChatEvent.strategyEvents";
import { makeCtx } from "./handleChatEvent.testUtils";

describe("regression: graph_plan must NOT mount planned steps as WDK steps", () => {
  it("handleGraphPlanEvent does NOT call applyGraphSnapshot", () => {
    const { ctx, applyGraphSnapshot } = makeCtx();

    handleGraphPlanEvent(ctx, {
      graphId: "s1",
      plan: {
        recordType: "transcript",
        root: {
          searchName: "GenesByTaxon",
          displayName: "Genes by taxon",
          parameters: { organism: '["Plasmodium falciparum 3D7"]' },
        },
      },
      name: "My planned strategy",
      description: "A plan we proposed",
      recordType: "transcript",
    });

    // THE CORE REGRESSION CHECK: applyGraphSnapshot must never fire
    // for a graph_plan event. If it does, planned steps appear as
    // real WDK steps (ghost steps).
    expect(applyGraphSnapshot).toHaveBeenCalledTimes(0);

    // Metadata is the only side effect — name/description/recordType.
    expect(ctx.setStrategyMeta).toHaveBeenCalledTimes(1);
    expect(ctx.setStrategyMeta).toHaveBeenCalledWith({
      name: "My planned strategy",
      description: "A plan we proposed",
      recordType: "transcript",
    });

    // Steps must not be mutated via other strategy-store paths either.
    expect(ctx.addStep).toHaveBeenCalledTimes(0);
    expect(ctx.setStrategy).toHaveBeenCalledTimes(0);
    expect(ctx.addStrategy).toHaveBeenCalledTimes(0);
    expect(ctx.setWdkInfo).toHaveBeenCalledTimes(0);
  });

  it("handleGraphPlanEvent ignored when graphId does not match strategyIdAtStart", () => {
    const { ctx, applyGraphSnapshot } = makeCtx();

    handleGraphPlanEvent(ctx, {
      graphId: "different-strategy-id",
      plan: {
        recordType: "transcript",
        root: { searchName: "GenesByTaxon" },
      },
      name: "Other plan",
    });

    // Mismatched graphId: skip entirely — no store writes at all.
    expect(applyGraphSnapshot).toHaveBeenCalledTimes(0);
    expect(ctx.setStrategyMeta).toHaveBeenCalledTimes(0);
    expect(ctx.addStep).toHaveBeenCalledTimes(0);
  });

  it("handleGraphSnapshotEvent IS the only handler that calls applyGraphSnapshot", () => {
    const { ctx, applyGraphSnapshot } = makeCtx();

    const snapshot = {
      graphId: "s1",
      name: "Real strategy",
      steps: [
        { id: "step-1", kind: "search", displayName: "step 1" },
      ],
    };

    handleGraphSnapshotEvent(ctx, { graphSnapshot: snapshot });

    // handleGraphSnapshotEvent is explicitly allowed to call applyGraphSnapshot.
    expect(applyGraphSnapshot).toHaveBeenCalledTimes(1);
    expect(applyGraphSnapshot).toHaveBeenCalledWith(snapshot);
  });

  it("full SSE dispatcher: graph_plan event does not touch strategy steps", () => {
    const { ctx, applyGraphSnapshot } = makeCtx();

    handleChatEvent(ctx, {
      type: "graph_plan",
      data: {
        graphId: "s1",
        plan: {
          recordType: "transcript",
          root: {
            searchName: "GenesByTaxon",
            displayName: "Genes by taxon",
            parameters: { organism: '["Plasmodium falciparum 3D7"]' },
            primaryInput: {
              searchName: "GenesByLocation",
              displayName: "Genes by location",
              parameters: {},
            },
          },
        },
        name: "Dispatcher plan",
        description: "Routed via handleChatEvent",
        recordType: "transcript",
      },
    } as ChatSSEEvent);

    // Ghost-step regression: dispatcher must not apply the plan as a graph.
    expect(applyGraphSnapshot).toHaveBeenCalledTimes(0);

    // Dispatcher must not create steps or assign a real strategy id.
    expect(ctx.addStep).toHaveBeenCalledTimes(0);
    expect(ctx.setStrategy).toHaveBeenCalledTimes(0);
    expect(ctx.setStrategyId).toHaveBeenCalledTimes(0);
    expect(ctx.setWdkInfo).toHaveBeenCalledTimes(0);
    expect(ctx.loadGraph).toHaveBeenCalledTimes(0);

    // Only metadata propagates.
    expect(ctx.setStrategyMeta).toHaveBeenCalledTimes(1);
    expect(ctx.setStrategyMeta).toHaveBeenCalledWith({
      name: "Dispatcher plan",
      description: "Routed via handleChatEvent",
      recordType: "transcript",
    });
  });

  it("full SSE dispatcher: graph_snapshot is the ONLY path that mounts steps", () => {
    const { ctx, applyGraphSnapshot } = makeCtx();

    const realSnapshot = {
      graphId: "s1",
      name: "Executed strategy",
      steps: [
        { id: "real-step-1", kind: "search", displayName: "Real step 1" },
        { id: "real-step-2", kind: "search", displayName: "Real step 2" },
      ],
    };

    handleChatEvent(ctx, {
      type: "graph_snapshot",
      data: { graphSnapshot: realSnapshot },
    } as ChatSSEEvent);

    // graph_snapshot is the sole allowed caller of applyGraphSnapshot.
    expect(applyGraphSnapshot).toHaveBeenCalledTimes(1);
    expect(applyGraphSnapshot).toHaveBeenCalledWith(realSnapshot);
  });

  it("regression scenario: planning-phase event stream does not create ghost steps", () => {
    // Simulates the real backend event sequence during planning:
    // plan_presented + graph_plan. If the old bug were present,
    // graph_plan would call applyGraphSnapshot and ghost steps
    // would appear on the graph.
    const { ctx, applyGraphSnapshot } = makeCtx();

    handleChatEvent(ctx, {
      type: "plan_presented",
      data: {
        plan: {
          id: "plan_abc123",
          title: "Find malaria drug targets",
          description: "Intersect two gene sets",
          steps: [],
          connections: [],
        },
      },
    } as ChatSSEEvent);

    handleChatEvent(ctx, {
      type: "graph_plan",
      data: {
        graphId: "s1",
        plan: {
          recordType: "transcript",
          root: {
            searchName: "__combine__",
            displayName: "Intersect",
            parameters: {},
            primaryInput: {
              searchName: "GenesByTaxon",
              displayName: "Genes by taxon",
              parameters: { organism: '["Plasmodium falciparum 3D7"]' },
            },
            secondaryInput: {
              searchName: "GenesByLocation",
              displayName: "Genes by location",
              parameters: {},
            },
          },
        },
        name: "Find malaria drug targets",
        description: "Intersect two gene sets",
        recordType: "transcript",
      },
    } as ChatSSEEvent);

    // After a full planning event stream: zero ghost steps.
    expect(applyGraphSnapshot).toHaveBeenCalledTimes(0);
    expect(ctx.addStep).toHaveBeenCalledTimes(0);
    expect(ctx.setStrategy).toHaveBeenCalledTimes(0);
    expect(ctx.setWdkInfo).toHaveBeenCalledTimes(0);
  });
});
