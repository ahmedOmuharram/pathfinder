// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePlanStore } from "./usePlanStore";

beforeEach(() => {
  usePlanStore.getState().clearPlan();
  usePlanStore.getState().clearThoughts();
});

describe("usePlanStore — phase + timing reducers", () => {
  it("setPhase records timing for a real phase and merges on re-entry", () => {
    const s = usePlanStore.getState();
    s.setPhase("planning", "started", { phaseStartedAt: "t0", durationMs: 100 });
    let st = usePlanStore.getState();
    expect(st.currentPhase).toBe("planning");
    expect(st.phaseStatus).toBe("started");
    expect(st.phaseTimings.planning?.durationMs).toBe(100);

    // Re-entering with a partial timing keeps prior values it doesn't override.
    s.setPhase("planning", "completed", { phaseCompletedAt: "t1" });
    st = usePlanStore.getState();
    expect(st.phaseTimings.planning?.phaseStartedAt).toBe("t0");
    expect(st.phaseTimings.planning?.phaseCompletedAt).toBe("t1");
    expect(st.phaseTimings.planning?.durationMs).toBe(100);
  });

  it("setPhase('completed') updates currentPhase without adding a timing entry", () => {
    const s = usePlanStore.getState();
    s.setPhase("completed", "completed");
    const st = usePlanStore.getState();
    expect(st.currentPhase).toBe("completed");
    expect(Object.keys(st.phaseTimings)).toHaveLength(0);
  });

  it("recordPhaseChange writes timing and ignores 'completed'", () => {
    const s = usePlanStore.getState();
    s.recordPhaseChange("discovery", "started", 50);
    expect(usePlanStore.getState().phaseTimings.discovery?.durationMs).toBe(50);
    s.recordPhaseChange("completed", "completed", null);
    expect(usePlanStore.getState().phaseTimings.discovery?.durationMs).toBe(50);
    expect(usePlanStore.getState().currentPhase).toBe("completed");
  });

  it("clearPhase and clearPhaseTimings reset their slices", () => {
    const s = usePlanStore.getState();
    s.setPhase("execution", "started");
    s.clearPhase();
    expect(usePlanStore.getState().currentPhase).toBeNull();
    expect(usePlanStore.getState().phaseStatus).toBeNull();
    s.clearPhaseTimings();
    expect(Object.keys(usePlanStore.getState().phaseTimings)).toHaveLength(0);
  });
});

describe("usePlanStore — trace, pinning, thoughts, approval", () => {
  it("setPlanTraceContext applies only the keys present", () => {
    const s = usePlanStore.getState();
    s.setPlanTraceContext({ traceId: "trace-1" });
    expect(usePlanStore.getState().activePlanTraceId).toBe("trace-1");
    s.setPlanTraceContext({ messageGroupId: "grp-1" });
    expect(usePlanStore.getState().activePlanMessageGroupId).toBe("grp-1");
    // An empty context leaves both untouched.
    s.setPlanTraceContext({});
    expect(usePlanStore.getState().activePlanTraceId).toBe("trace-1");
    expect(usePlanStore.getState().activePlanMessageGroupId).toBe("grp-1");
  });

  it("setPinned, addThought, clearThoughts", () => {
    const s = usePlanStore.getState();
    s.setPinned(true);
    expect(usePlanStore.getState().isPlanPinned).toBe(true);
    s.addThought("one");
    s.addThought("two");
    expect(usePlanStore.getState().planThoughts).toEqual(["one", "two"]);
    s.clearThoughts();
    expect(usePlanStore.getState().planThoughts).toEqual([]);
  });

  it("registers send-message and plan-action callbacks", () => {
    const s = usePlanStore.getState();
    const send = vi.fn();
    const action = vi.fn(async () => undefined);
    s.registerSendMessage(send);
    s.registerPlanAction(action);
    expect(usePlanStore.getState().sendMessage).toBe(send);
    expect(usePlanStore.getState().submitPlanAction).toBe(action);
  });

  it("set/resolve pending approval", () => {
    const s = usePlanStore.getState();
    s.setPendingApproval({ id: "i", planId: "p", toolCallId: "t" });
    expect(usePlanStore.getState().pendingApproval?.planId).toBe("p");
    s.resolvePendingApproval();
    expect(usePlanStore.getState().pendingApproval).toBeNull();
  });

  it("setFocusedPlanIndex clamps to the plan range", () => {
    const s = usePlanStore.getState();
    // No plans → index pinned to 0.
    s.setFocusedPlanIndex(5);
    expect(usePlanStore.getState().focusedPlanIndex).toBe(0);
    s.appendPlanArtifact({ planId: "a", rationale: "", steps: [] });
    s.appendPlanArtifact({ planId: "b", rationale: "", steps: [] });
    s.setFocusedPlanIndex(99); // clamps to last
    expect(usePlanStore.getState().focusedPlanIndex).toBe(1);
    s.setFocusedPlanIndex(-3); // clamps to 0
    expect(usePlanStore.getState().focusedPlanIndex).toBe(0);
  });

  it("updatePlan is a no-op while there is no active plan", () => {
    usePlanStore.getState().updatePlan({});
    expect(usePlanStore.getState().activePlan).toBeNull();
  });
});
