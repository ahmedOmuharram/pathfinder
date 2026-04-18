import { beforeEach, describe, expect, it } from "vitest";
import type { Step } from "@pathfinder/shared";
import { useStrategyStore } from "./store";

function step(partial: Partial<Step> & { id: string; displayName: string }): Step {
  return { isBuilt: false, isFiltered: false, ...partial } as Step;
}

describe("state/strategy/historySlice (Immer patches)", () => {
  beforeEach(() => {
    useStrategyStore.getState().clear();
  });

  it("stores patch arrays in undoStack, not full strategy snapshots", () => {
    const { addStep, updateStep } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "Search 1", searchName: "geneById", recordType: "gene" }));
    updateStep("s1", { displayName: "Renamed" });

    const { undoStack, redoStack } = useStrategyStore.getState();
    expect(undoStack).toHaveLength(1);
    expect(redoStack).toHaveLength(0);

    const patches = undoStack[0];
    if (!patches) throw new Error("expected patches");
    expect(Array.isArray(patches)).toBe(true);
    expect(patches.length).toBeGreaterThan(0);
    const firstPatch = patches[0];
    if (!firstPatch) throw new Error("expected first patch");
    expect(typeof firstPatch.op).toBe("string");
    expect(Array.isArray(firstPatch.path)).toBe(true);
  });

  it("redo restores forward patches after undo", () => {
    const { addStep, updateStep, undo, redo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "Search 1", searchName: "geneById", recordType: "gene" }));
    updateStep("s1", { displayName: "Renamed" });

    undo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("Search 1");
    expect(useStrategyStore.getState().redoStack).toHaveLength(1);
    expect(useStrategyStore.getState().undoStack).toHaveLength(0);

    redo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("Renamed");
    expect(useStrategyStore.getState().undoStack).toHaveLength(1);
    expect(useStrategyStore.getState().redoStack).toHaveLength(0);
  });

  it("new mutation after undo clears redoStack", () => {
    const { addStep, updateStep, undo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "Search 1", searchName: "geneById", recordType: "gene" }));
    updateStep("s1", { displayName: "Renamed" });
    undo();
    expect(useStrategyStore.getState().redoStack).toHaveLength(1);

    updateStep("s1", { displayName: "Fresh" });
    expect(useStrategyStore.getState().redoStack).toHaveLength(0);
    expect(useStrategyStore.getState().undoStack).toHaveLength(1);
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("Fresh");
  });

  it("undo/redo restores step removal", () => {
    const { addStep, removeStep, undo, redo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    addStep(step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }));
    removeStep("s1");

    expect(useStrategyStore.getState().stepsById["s1"]).toBeUndefined();
    undo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("S1");
    redo();
    expect(useStrategyStore.getState().stepsById["s1"]).toBeUndefined();
  });

  it("caps undoStack at MAX_HISTORY (50)", () => {
    const { addStep, updateStep } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "init", searchName: "geneById", recordType: "gene" }));
    // 60 mutations after initial — only 50 should be retained.
    for (let i = 0; i < 60; i += 1) {
      updateStep("s1", { displayName: `name-${i}` });
    }
    const { undoStack } = useStrategyStore.getState();
    expect(undoStack.length).toBeLessThanOrEqual(50);
    expect(undoStack.length).toBe(50);
  });

  it("canUndo is false after first mutation from null strategy", () => {
    const { addStep, canUndo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    expect(canUndo()).toBe(false);
  });

  it("clear empties both stacks", () => {
    const { addStep, updateStep, clear } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    updateStep("s1", { displayName: "R" });
    clear();
    const state = useStrategyStore.getState();
    expect(state.undoStack).toHaveLength(0);
    expect(state.redoStack).toHaveLength(0);
    expect(state.strategy).toBeNull();
  });

  it("undo is a no-op when undoStack is empty", () => {
    const { undo } = useStrategyStore.getState();
    undo();
    const state = useStrategyStore.getState();
    expect(state.strategy).toBeNull();
    expect(state.undoStack).toHaveLength(0);
  });

  it("redo is a no-op when redoStack is empty", () => {
    const { addStep, redo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    redo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("S1");
    expect(useStrategyStore.getState().redoStack).toHaveLength(0);
  });

  it("persists step data integrity across undo/redo cycles", () => {
    const { addStep, updateStep, undo, redo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    updateStep("s1", { displayName: "Second" });
    updateStep("s1", { displayName: "Third" });

    undo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("Second");
    undo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("S1");
    redo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("Second");
    redo();
    expect(useStrategyStore.getState().stepsById["s1"]?.displayName).toBe("Third");
  });
});
