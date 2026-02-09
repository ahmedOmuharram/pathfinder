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
});
