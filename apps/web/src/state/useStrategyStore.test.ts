import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Step } from "@pathfinder/shared";
import { useStrategyStore } from "./strategy/store";

/** Minimal Step with required boolean fields defaulted. */
function step(partial: Partial<Step> & { id: string; displayName: string }): Step {
  return { isBuilt: false, isFiltered: false, ...partial } as Step;
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

    // Incoming AI update tries to overwrite the name with a generic fallback.
    addStep(
      step({
        id: "s1",
        displayName: "search",
        searchName: "geneById",
        recordType: "gene",
      }),
    );

    const s = useStrategyStore.getState().stepsById["s1"];
    if (s === undefined) throw new Error("step s1 not found");
    expect(s.displayName).toBe("My Custom Name");
  });

  it("supports undo/redo over history", () => {
    const { addStep, updateStep, undo, redo, canUndo, canRedo } =
      useStrategyStore.getState();

    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
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
    expect(state.stepsById["s1"]).toBeUndefined();
    expect(state.stepsById["s2"]).toBeDefined();
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
    expect(Object.keys(state.stepsById)).toHaveLength(0);
  });

  it("setStrategy merges with existing steps preserving user edits", () => {
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
          displayName: "search",
          searchName: "geneById",
          recordType: "gene",
        }),
      ],
      rootStepId: "s1",
      isSaved: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.displayName).toBe("My Custom Name");
  });

  it("setStrategyMeta updates strategy metadata", () => {
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

  it("setStepValidationErrors updates validation errors", () => {
    const { addStep, setStepValidationErrors } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    setStepValidationErrors({ s1: "Error message" });
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.validation?.errors?.general?.[0]).toBe(
      "Error message",
    );
  });

  it("setStepCounts updates step counts", () => {
    const { addStep, setStepCounts } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    setStepCounts({ s1: 42 });
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.estimatedSize).toBe(42);
  });

  it("buildPlan returns null for empty strategy", () => {
    const { buildPlan } = useStrategyStore.getState();
    expect(buildPlan()).toBeNull();
  });

  it("buildPlan returns plan for valid strategy", () => {
    const { addStep, buildPlan } = useStrategyStore.getState();
    addStep(
      step({
        id: "s1",
        displayName: "Search 1",
        searchName: "geneById",
        recordType: "gene",
      }),
    );
    const plan = buildPlan();
    expect(plan).not.toBeNull();
    expect(plan?.plan.root.id).toBe("s1");
    expect(plan?.plan.root.searchName).toBe("geneById");
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
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.recordType).toBe("gene");
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
    const state = useStrategyStore.getState();
    expect(state.stepsById["s1"]?.displayName).toBe("geneById");
  });
});

describe("state/useStrategyStore (list management)", () => {
  beforeEach(() => {
    useStrategyStore.setState({
      strategies: [],
      executedStrategies: [],
      graphValidationStatus: {},
    });
  });

  it("adds and updates strategies by id", () => {
    const { addStrategyToList } = useStrategyStore.getState();
    addStrategyToList({
      id: "s1",
      name: "A",
      title: "A",
      siteId: "plasmodb",
      recordType: "gene",
      stepCount: 0,
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "t1",
      updatedAt: "t1",
    });
    addStrategyToList({
      id: "s1",
      name: "A2",
      title: "A2",
      siteId: "plasmodb",
      recordType: "gene",
      stepCount: 1,
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "t1",
      updatedAt: "t2",
    });

    const { strategies } = useStrategyStore.getState();
    expect(strategies).toHaveLength(1);
    expect(strategies[0]).toMatchObject({ id: "s1", name: "A2", stepCount: 1 });
  });

  it("normalizes executed strategy id when missing", () => {
    const nowSpy = vi.spyOn(Date, "now").mockReturnValue(1234);
    const { addExecutedStrategy } = useStrategyStore.getState();
    addExecutedStrategy({
      id: "",
      name: "Exec",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "t1",
      updatedAt: "t1",
    });

    const { executedStrategies } = useStrategyStore.getState();
    expect(executedStrategies).toHaveLength(1);
    expect(executedStrategies[0]?.id).toBe("executed-1234");
    nowSpy.mockRestore();
  });

  it("tracks graph validation status per id", () => {
    const { setGraphValidationStatus } = useStrategyStore.getState();
    setGraphValidationStatus("s1", true);
    expect(useStrategyStore.getState().graphValidationStatus).toEqual({
      s1: true,
    });
  });

  it("removes strategy by id", () => {
    const { addStrategyToList, removeStrategyFromList } = useStrategyStore.getState();
    addStrategyToList({
      id: "s1",
      name: "A",
      title: "A",
      siteId: "plasmodb",
      recordType: "gene",
      stepCount: 0,
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "t1",
      updatedAt: "t1",
    });
    addStrategyToList({
      id: "s2",
      name: "B",
      title: "B",
      siteId: "plasmodb",
      recordType: "gene",
      stepCount: 0,
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "t1",
      updatedAt: "t1",
    });
    removeStrategyFromList("s1");
    const { strategies } = useStrategyStore.getState();
    expect(strategies).toHaveLength(1);
    expect(strategies[0]?.id).toBe("s2");
  });

  it("updates existing executed strategy when id matches", () => {
    const { addExecutedStrategy } = useStrategyStore.getState();
    const strategy1 = {
      id: "exec1",
      name: "Exec 1",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "t1",
      updatedAt: "t1",
    };
    addExecutedStrategy(strategy1);
    const strategy2 = {
      ...strategy1,
      name: "Exec 1 Updated",
    };
    addExecutedStrategy(strategy2);
    const { executedStrategies } = useStrategyStore.getState();
    expect(executedStrategies).toHaveLength(1);
    expect(executedStrategies[0]?.name).toBe("Exec 1 Updated");
  });
});
