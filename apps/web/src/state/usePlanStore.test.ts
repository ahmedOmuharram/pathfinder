// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import type { PlanArtifact } from "@pathfinder/shared";

import { usePlanStore } from "./usePlanStore";

function makePlan(planId: string): PlanArtifact {
  return {
    planId,
    rationale: "test rationale",
    steps: [],
  };
}

beforeEach(() => {
  usePlanStore.getState().clearPlan();
});

describe("usePlanStore — carousel reducers", () => {
  it("starts with empty plans, focusedPlanIndex 0, no pending", () => {
    const s = usePlanStore.getState();
    expect(s.plans).toEqual([]);
    expect(s.focusedPlanIndex).toBe(0);
    expect(s.pendingApproval).toBeNull();
  });

  it("appendPlanArtifact appends and bumps focusedPlanIndex to last", () => {
    const s = usePlanStore.getState();
    s.appendPlanArtifact(makePlan("p1"));
    expect(usePlanStore.getState().plans).toHaveLength(1);
    expect(usePlanStore.getState().focusedPlanIndex).toBe(0);
    s.appendPlanArtifact(makePlan("p2"));
    expect(usePlanStore.getState().plans).toHaveLength(2);
    expect(usePlanStore.getState().focusedPlanIndex).toBe(1);
    s.appendPlanArtifact(makePlan("p3"));
    expect(usePlanStore.getState().plans).toHaveLength(3);
    expect(usePlanStore.getState().focusedPlanIndex).toBe(2);
  });

  it("setFocusedPlanIndex moves focus and clamps to bounds", () => {
    const s = usePlanStore.getState();
    s.appendPlanArtifact(makePlan("p1"));
    s.appendPlanArtifact(makePlan("p2"));
    s.appendPlanArtifact(makePlan("p3"));
    s.setFocusedPlanIndex(0);
    expect(usePlanStore.getState().focusedPlanIndex).toBe(0);
    s.setFocusedPlanIndex(99);
    expect(usePlanStore.getState().focusedPlanIndex).toBe(2);
    s.setFocusedPlanIndex(-5);
    expect(usePlanStore.getState().focusedPlanIndex).toBe(0);
  });

  it("setFocusedPlanIndex clamps to 0 when plans is empty", () => {
    const s = usePlanStore.getState();
    s.setFocusedPlanIndex(7);
    expect(usePlanStore.getState().focusedPlanIndex).toBe(0);
  });

  it("setPendingApproval / resolvePendingApproval round-trip", () => {
    const s = usePlanStore.getState();
    s.setPendingApproval({ id: "a1", planId: "p1", toolCallId: "t1" });
    expect(usePlanStore.getState().pendingApproval).toEqual({
      id: "a1",
      planId: "p1",
      toolCallId: "t1",
    });
    s.resolvePendingApproval();
    expect(usePlanStore.getState().pendingApproval).toBeNull();
  });

  it("clearPlan resets all carousel state", () => {
    const s = usePlanStore.getState();
    s.appendPlanArtifact(makePlan("p1"));
    s.appendPlanArtifact(makePlan("p2"));
    s.setFocusedPlanIndex(0);
    s.setPendingApproval({ id: "a1", planId: "p1", toolCallId: "t1" });
    s.clearPlan();
    const next = usePlanStore.getState();
    expect(next.plans).toEqual([]);
    expect(next.focusedPlanIndex).toBe(0);
    expect(next.pendingApproval).toBeNull();
  });

  it("sequence: create → submit → suggest → submit → approve mirrors carousel", () => {
    const s = usePlanStore.getState();
    s.appendPlanArtifact(makePlan("p1"));
    s.setPendingApproval({ id: "a1", planId: "p1", toolCallId: "t1" });

    // user denies, agent updates plan
    s.resolvePendingApproval();
    s.appendPlanArtifact(makePlan("p1"));

    // agent re-submits
    s.setPendingApproval({ id: "a2", planId: "p1", toolCallId: "t2" });

    // user approves
    s.resolvePendingApproval();

    const next = usePlanStore.getState();
    expect(next.plans).toHaveLength(2);
    expect(next.focusedPlanIndex).toBe(1);
    expect(next.pendingApproval).toBeNull();
  });
});
