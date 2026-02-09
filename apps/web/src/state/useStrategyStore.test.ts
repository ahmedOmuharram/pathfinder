import { beforeEach, describe, expect, it } from "vitest";
import { useStrategyStore } from "./useStrategyStore";

describe("state/useStrategyStore", () => {
  beforeEach(() => {
    useStrategyStore.getState().clear();
  });

  it("builds a simple strategy and tracks rootStepId", () => {
    const { addStep } = useStrategyStore.getState();

    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    let state = useStrategyStore.getState();
    expect(state.strategy?.steps).toHaveLength(1);
    expect(state.strategy?.rootStepId).toBe("s1");

    addStep({
      id: "t1",
      displayName: "Transform",
      searchName: "transformStep",
      primaryInputStepId: "s1",
      recordType: "gene",
    });
    state = useStrategyStore.getState();
    expect(state.strategy?.steps).toHaveLength(2);
    expect(state.strategy?.rootStepId).toBe("t1");
  });

  it("preserves user-edited displayName when incoming update is fallback-like", () => {
    const { addStep } = useStrategyStore.getState();

    addStep({
      id: "s1",
      displayName: "My Custom Name",
      searchName: "geneById",
      recordType: "gene",
    });

    // Incoming AI update tries to overwrite the name with a generic fallback.
    addStep({
      id: "s1",
      displayName: "search",
      searchName: "geneById",
      recordType: "gene",
    });

    const step = useStrategyStore.getState().stepsById["s1"];
    expect(step.displayName).toBe("My Custom Name");
  });

  it("supports undo/redo over history", () => {
    const { addStep, updateStep, undo, redo, canUndo, canRedo } =
      useStrategyStore.getState();

    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    updateStep("s1", { displayName: "Renamed" });

    expect(canUndo()).toBe(true);
    expect(canRedo()).toBe(false);

    undo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("Search 1");
    expect(canRedo()).toBe(true);

    redo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("Renamed");
  });

  it("removeStep removes step and rebuilds strategy", () => {
    const { addStep, removeStep } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    addStep({
      id: "s2",
      displayName: "Search 2",
      searchName: "geneById",
      recordType: "gene",
    });
    removeStep("s1");
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]).toBeUndefined();
    expect(state.stepsById["s2"]).toBeDefined();
    expect(state.strategy?.steps).toHaveLength(1);
  });

  it("setStrategy clears when null", () => {
    const { addStep, setStrategy } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    setStrategy(null);
    const state = useStrategyStore.getState();
    expect(state.strategy).toBeNull();
    expect(Object.keys(state.stepsById)).toHaveLength(0);
  });

  it("setStrategy merges with existing steps preserving user edits", () => {
    const { addStep, setStrategy } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "My Custom Name",
      searchName: "geneById",
      recordType: "gene",
    });
    setStrategy({
      id: "draft",
      name: "Test",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [
        {
          id: "s1",
          displayName: "search",
          searchName: "geneById",
          recordType: "gene",
        },
      ],
      rootStepId: "s1",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.displayName).toBe("My Custom Name");
  });

  it("setStrategyMeta updates strategy metadata", () => {
    const { addStep, setStrategyMeta } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    setStrategyMeta({ name: "New Name", description: "New Desc" });
    const state = useStrategyStore.getState();
    expect(state.strategy?.name).toBe("New Name");
    expect(state.strategy?.description).toBe("New Desc");
  });

  it("setWdkInfo updates wdk metadata", () => {
    const { addStep, setWdkInfo } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    setWdkInfo(123, "http://example.com", "WDK Name", "WDK Desc");
    const state = useStrategyStore.getState();
    expect(state.strategy?.wdkStrategyId).toBe(123);
    expect(state.strategy?.wdkUrl).toBe("http://example.com");
    expect(state.strategy?.name).toBe("WDK Name");
    expect(state.strategy?.description).toBe("WDK Desc");
  });

  it("setStepValidationErrors updates validation errors", () => {
    const { addStep, setStepValidationErrors } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    setStepValidationErrors({ s1: "Error message" });
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.validationError).toBe("Error message");
  });

  it("setStepCounts updates step counts", () => {
    const { addStep, setStepCounts } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    setStepCounts({ s1: 42 });
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.resultCount).toBe(42);
  });

  it("buildPlan returns null for empty strategy", () => {
    const { buildPlan } = useStrategyStore.getState();
    expect(buildPlan()).toBeNull();
  });

  it("buildPlan returns plan for valid strategy", () => {
    const { addStep, buildPlan } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    const plan = buildPlan();
    expect(plan).not.toBeNull();
    expect(plan?.plan.root.id).toBe("s1");
    expect(plan?.plan.root.searchName).toBe("geneById");
  });

  it("preserves recordType when updating step without it", () => {
    const { addStep } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });
    addStep({
      id: "s1",
      displayName: "Search 1 Updated",
      searchName: "geneById",
    });
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.recordType).toBe("gene");
  });

  it("uses fallback displayName when none provided", () => {
    const { addStep } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "",
      searchName: "geneById",
      recordType: "gene",
    });
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.displayName).toBe("geneById");
  });
});
