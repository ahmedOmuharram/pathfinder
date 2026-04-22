import { beforeEach, describe, expect, it } from "vitest";
import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "./store";

function step(partial: Partial<Step> & { id: string; displayName: string }): Step {
  return { isBuilt: false, isFiltered: false, ...partial } as Step;
}

function findStep(id: string): Step | undefined {
  return useStrategyStore.getState().strategy?.steps.find((s) => s.id === id);
}

function snapshotState() {
  return { strategy: useStrategyStore.getState().strategy };
}

describe("state/strategy/historySlice (Immer patches via explicit pushSnapshot)", () => {
  beforeEach(() => {
    useStrategyStore.getState().clear();
  });

  it("does NOT auto-push history on raw addStep/updateStep", () => {
    const { addStep, updateStep } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "Search 1", searchName: "geneById", recordType: "gene" }));
    updateStep("s1", { displayName: "Renamed" });
    expect(useStrategyStore.getState().undoStack).toHaveLength(0);
  });

  it("pushSnapshot stores the inverse patches required to undo back to prev", () => {
    const { addStep, updateStep, pushSnapshot } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "Search 1", searchName: "geneById", recordType: "gene" }));
    const beforeUpdate = snapshotState();
    updateStep("s1", { displayName: "Renamed" });
    pushSnapshot(beforeUpdate);

    const { undoStack, redoStack } = useStrategyStore.getState();
    expect(undoStack).toHaveLength(1);
    expect(redoStack).toHaveLength(0);

    const patches = undoStack[0];
    if (!patches) throw new Error("expected patches");
    expect(Array.isArray(patches)).toBe(true);
    expect(patches.length).toBeGreaterThan(0);
  });

  it("pushSnapshot is a no-op when prev.strategy is null (initial state has nothing to undo to)", () => {
    const { addStep, pushSnapshot } = useStrategyStore.getState();
    const initialSnap = snapshotState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    pushSnapshot(initialSnap);
    expect(useStrategyStore.getState().undoStack).toHaveLength(0);
  });

  it("undo restores prior strategy and populates redoStack", () => {
    const { addStep, updateStep, pushSnapshot, undo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "Search 1", searchName: "geneById", recordType: "gene" }));
    const before = snapshotState();
    updateStep("s1", { displayName: "Renamed" });
    pushSnapshot(before);

    undo();
    expect(findStep("s1")?.displayName).toBe("Search 1");
    expect(useStrategyStore.getState().redoStack).toHaveLength(1);
    expect(useStrategyStore.getState().undoStack).toHaveLength(0);
  });

  it("redo restores forward patches after undo", () => {
    const { addStep, updateStep, pushSnapshot, undo, redo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "Search 1", searchName: "geneById", recordType: "gene" }));
    const before = snapshotState();
    updateStep("s1", { displayName: "Renamed" });
    pushSnapshot(before);
    undo();
    redo();
    expect(findStep("s1")?.displayName).toBe("Renamed");
    expect(useStrategyStore.getState().undoStack).toHaveLength(1);
    expect(useStrategyStore.getState().redoStack).toHaveLength(0);
  });

  it("new pushSnapshot after undo clears redoStack", () => {
    const { addStep, updateStep, pushSnapshot, undo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "Search 1", searchName: "geneById", recordType: "gene" }));
    const before1 = snapshotState();
    updateStep("s1", { displayName: "Renamed" });
    pushSnapshot(before1);
    undo();
    expect(useStrategyStore.getState().redoStack).toHaveLength(1);

    const before2 = snapshotState();
    updateStep("s1", { displayName: "Fresh" });
    pushSnapshot(before2);
    expect(useStrategyStore.getState().redoStack).toHaveLength(0);
    expect(useStrategyStore.getState().undoStack).toHaveLength(1);
    expect(findStep("s1")?.displayName).toBe("Fresh");
  });

  it("undo/redo restores step removal", () => {
    const { addStep, removeStep, pushSnapshot, undo, redo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    addStep(step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }));
    const before = snapshotState();
    removeStep("s1");
    pushSnapshot(before);

    expect(findStep("s1")).toBeUndefined();
    undo();
    expect(findStep("s1")?.displayName).toBe("S1");
    redo();
    expect(findStep("s1")).toBeUndefined();
  });

  it("caps undoStack at MAX_HISTORY (50)", () => {
    const { addStep, updateStep, pushSnapshot } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "init", searchName: "geneById", recordType: "gene" }));
    for (let i = 0; i < 60; i += 1) {
      const prev = snapshotState();
      updateStep("s1", { displayName: `name-${i}` });
      pushSnapshot(prev);
    }
    const { undoStack } = useStrategyStore.getState();
    expect(undoStack.length).toBe(50);
  });

  it("clear empties both stacks", () => {
    const { addStep, updateStep, pushSnapshot, clear } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    const prev = snapshotState();
    updateStep("s1", { displayName: "R" });
    pushSnapshot(prev);
    clear();
    const state = useStrategyStore.getState();
    expect(state.undoStack).toHaveLength(0);
    expect(state.redoStack).toHaveLength(0);
    expect(state.strategy).toBeNull();
  });

  it("undo is a no-op when undoStack is empty", () => {
    const { undo } = useStrategyStore.getState();
    undo();
    expect(useStrategyStore.getState().strategy).toBeNull();
    expect(useStrategyStore.getState().undoStack).toHaveLength(0);
  });

  it("redo is a no-op when redoStack is empty", () => {
    const { addStep, redo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    redo();
    expect(findStep("s1")?.displayName).toBe("S1");
    expect(useStrategyStore.getState().redoStack).toHaveLength(0);
  });

  it("persists step data integrity across multiple undo/redo cycles", () => {
    const { addStep, updateStep, pushSnapshot, undo, redo } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    const a = snapshotState();
    updateStep("s1", { displayName: "Second" });
    pushSnapshot(a);
    const b = snapshotState();
    updateStep("s1", { displayName: "Third" });
    pushSnapshot(b);

    undo();
    expect(findStep("s1")?.displayName).toBe("Second");
    undo();
    expect(findStep("s1")?.displayName).toBe("S1");
    redo();
    expect(findStep("s1")?.displayName).toBe("Second");
    redo();
    expect(findStep("s1")?.displayName).toBe("Third");
  });

  it("pushSnapshot is a no-op when nothing changed", () => {
    const { addStep, pushSnapshot } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));
    const same: { strategy: Strategy | null } = snapshotState();
    pushSnapshot(same);
    expect(useStrategyStore.getState().undoStack).toHaveLength(0);
  });
});
