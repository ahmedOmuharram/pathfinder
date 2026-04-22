import { beforeEach, describe, expect, it } from "vitest";
import type { Step } from "@pathfinder/shared";
import { useStrategyStore } from "./strategy/store";

/** Minimal Step with required boolean fields defaulted. */
function step(partial: Partial<Step> & { id: string; displayName: string }): Step {
  return { isBuilt: false, isFiltered: false, ...partial } as Step;
}

function findStep(id: string): Step | undefined {
  return useStrategyStore.getState().strategy?.steps.find((s) => s.id === id);
}

describe("state/useStrategyStore", () => {
  beforeEach(() => {
    useStrategyStore.getState().clear();
  });

  it("builds a simple strategy and tracks rootStepId", () => {
    const { addStep } = useStrategyStore.getState();

    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    let state = useStrategyStore.getState();
    expect(state.strategy?.steps).toHaveLength(1);
    expect(state.strategy?.rootStepId).toBe("s1");

    addStep(
      step({
        id: "t1",
        displayName: "Transform",
        searchName: "transformStep",
        primaryInputStepId: "s1",
        recordType: "gene",
      }),
    );
    state = useStrategyStore.getState();
    expect(state.strategy?.steps).toHaveLength(2);
    expect(state.strategy?.rootStepId).toBe("t1");
  });

  it("preserves user-edited displayName when incoming update is fallback-like", () => {
    const { addStep } = useStrategyStore.getState();

    addStep(
      step({
        id: "s1",
        displayName: "My Custom Name",
        searchName: "geneById",
        recordType: "gene",
      }),
    );

    addStep(
      step({
        id: "s1",
        displayName: "search",
        searchName: "geneById",
        recordType: "gene",
      }),
    );

    expect(findStep("s1")?.displayName).toBe("My Custom Name");
  });

  it("removeStep removes step and rebuilds strategy", () => {
    const { addStep, removeStep } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    addStep(
      step({
        id: "s2",
        displayName: "Search 2",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    removeStep("s1");
    const state = useStrategyStore.getState();
    expect(findStep("s1")).toBeUndefined();
    expect(findStep("s2")).toBeDefined();
    expect(state.strategy?.steps).toHaveLength(1);
  });

  it("setStrategy clears when null", () => {
    const { addStep, setStrategy } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    setStrategy(null);
    const state = useStrategyStore.getState();
    expect(state.strategy).toBeNull();
  });

  it("setStrategy is a full replace (no display-name preservation)", () => {
    const { addStep, setStrategy } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "My Custom Name",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    setStrategy({
      id: "draft",
      name: "Test",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [
        step({
          id: "s1",
          displayName: "Server canonical name",
          searchName: "geneById",
          recordType: "gene",
        }),
      ],
      rootStepId: "s1",
      isSaved: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
    expect(findStep("s1")?.displayName).toBe("Server canonical name");
  });

  it("setStrategyMeta updates strategy metadata (name + description only)", () => {
    const { addStep, setStrategyMeta } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    setStrategyMeta({ name: "New Name", description: "New Desc" });
    const state = useStrategyStore.getState();
    expect(state.strategy?.name).toBe("New Name");
    expect(state.strategy?.description).toBe("New Desc");
  });

  it("setStrategyMeta accepts wdkStrategyId and wdkUrl updates", () => {
    const { addStep, setStrategyMeta } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "S1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    setStrategyMeta({ wdkStrategyId: 42, wdkUrl: "http://example" });
    const state = useStrategyStore.getState();
    expect(state.strategy?.wdkStrategyId).toBe(42);
    expect(state.strategy?.wdkUrl).toBe("http://example");
  });

  it("setWdkInfo updates wdk metadata", () => {
    const { addStep, setWdkInfo } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    setWdkInfo(123, "http://example.com", "WDK Name", "WDK Desc");
    const state = useStrategyStore.getState();
    expect(state.strategy?.wdkStrategyId).toBe(123);
    expect(state.strategy?.wdkUrl).toBe("http://example.com");
    expect(state.strategy?.name).toBe("WDK Name");
    expect(state.strategy?.description).toBe("WDK Desc");
  });

  it("applyStepValidationErrors records validation errors in the lifecycle machine", () => {
    const { addStep, applyStepValidationErrors } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    applyStepValidationErrors({ s1: "Error message" });
    const snapshot = useStrategyStore.getState().getStepLifecycle("s1");
    expect(snapshot?.value).toBe("invalid");
    expect(snapshot?.context.validationErrors?.general?.[0]).toBe("Error message");
  });

  it("applyStepCounts records estimatedSize in the lifecycle machine", () => {
    const { addStep, dispatchStepEvent, applyStepCounts } =
      useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    // Counts only flow from `valid` (or further) per the step machine.
    dispatchStepEvent("s1", { type: "VALIDATE" });
    dispatchStepEvent("s1", { type: "VALIDATION_SUCCESS" });
    applyStepCounts({ s1: 42 });
    const snapshot = useStrategyStore.getState().getStepLifecycle("s1");
    expect(snapshot?.value).toBe("complete");
    expect(snapshot?.context.estimatedSize).toBe(42);
  });

  it("preserves recordType when updating step without it", () => {
    const { addStep } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    addStep(
      step({
        id: "s1",
        displayName: "Search 1 Updated",
        searchName: "geneById",
      }),
    );
    expect(findStep("s1")?.recordType).toBe("gene");
  });

  it("uses fallback displayName when none provided", () => {
    const { addStep } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    expect(findStep("s1")?.displayName).toBe("geneById");
  });
});
