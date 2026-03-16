/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { useStrategyStore } from "./useStrategyStore";
import {
  useCurrentStrategy,
  useStrategyList,
  useStrategyHistory,
  useStrategyActions,
  useStrategyListActions,
} from "./useStrategySelectors";

describe("state/useStrategySelectors", () => {
  beforeEach(() => {
    useStrategyStore.getState().clear();
    useStrategyStore.setState({
      strategies: [],
      executedStrategies: [],
      graphValidationStatus: {},
    });
  });

  it("useCurrentStrategy returns strategy and stepsById", () => {
    const { addStep } = useStrategyStore.getState();
    addStep({
      id: "s1",
      displayName: "Search 1",
      searchName: "geneById",
      recordType: "gene",
    });

    const { result } = renderHook(() => useCurrentStrategy());
    expect(result.current.strategy).not.toBeNull();
    expect(result.current.stepsById["s1"]).toBeDefined();
    expect(result.current.stepsById["s1"]?.displayName).toBe("Search 1");
  });

  it("useStrategyList returns strategies, executedStrategies, graphValidationStatus", () => {
    useStrategyStore.getState().addStrategyToList({
      id: "s1",
      name: "A",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "t1",
      updatedAt: "t1",
    });
    useStrategyStore.getState().setGraphValidationStatus("s1", true);

    const { result } = renderHook(() => useStrategyList());
    expect(result.current.strategies).toHaveLength(1);
    expect(result.current.graphValidationStatus["s1"]).toBe(true);
  });

  it("useStrategyHistory returns undo/redo functions", () => {
    const { result } = renderHook(() => useStrategyHistory());
    expect(typeof result.current.undo).toBe("function");
    expect(typeof result.current.redo).toBe("function");
    expect(typeof result.current.canUndo).toBe("function");
    expect(typeof result.current.canRedo).toBe("function");
  });

  it("useStrategyActions returns all mutation actions", () => {
    const { result } = renderHook(() => useStrategyActions());
    expect(typeof result.current.addStep).toBe("function");
    expect(typeof result.current.updateStep).toBe("function");
    expect(typeof result.current.removeStep).toBe("function");
    expect(typeof result.current.setStrategy).toBe("function");
    expect(typeof result.current.buildPlan).toBe("function");
    expect(typeof result.current.clear).toBe("function");
  });

  it("useStrategyListActions returns list mutation actions", () => {
    const { result } = renderHook(() => useStrategyListActions());
    expect(typeof result.current.setStrategies).toBe("function");
    expect(typeof result.current.addStrategyToList).toBe("function");
    expect(typeof result.current.removeStrategyFromList).toBe("function");
    expect(typeof result.current.addExecutedStrategy).toBe("function");
    expect(typeof result.current.setGraphValidationStatus).toBe("function");
  });
});
