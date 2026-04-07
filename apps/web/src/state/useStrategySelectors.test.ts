/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { useStrategyStore } from "./strategy/store";
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
      isBuilt: false,
      isFiltered: false,
    });

    const { result } = renderHook(() => useCurrentStrategy());
    expect(result.current.strategy).not.toBeNull();
    expect(result.current.stepsById["s1"]).toBeDefined();
    expect(result.current.stepsById["s1"]?.displayName).toBe("Search 1");
  });

  it("useStrategyList returns executedStrategies and graphValidationStatus", () => {
    useStrategyStore.getState().setGraphValidationStatus("s1", true);

    const { result } = renderHook(() => useStrategyList());
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
    expect(typeof result.current.addExecutedStrategy).toBe("function");
    expect(typeof result.current.setGraphValidationStatus).toBe("function");
  });
});
