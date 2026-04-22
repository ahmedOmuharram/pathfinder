/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { useStrategyStore } from "./strategy/store";
import {
  useCurrentStrategy,
  useStrategyHistory,
  useStrategyActions,
  useStrategyListActions,
} from "./useStrategySelectors";

describe("state/useStrategySelectors", () => {
  beforeEach(() => {
    useStrategyStore.getState().clear();
    useStrategyStore.setState({ graphValidationStatus: {} });
  });

  it("useCurrentStrategy returns the current strategy", () => {
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
    expect(result.current).not.toBeNull();
    expect(result.current?.steps[0]?.displayName).toBe("Search 1");
  });

  it("useStrategyHistory returns undo/redo functions and pushSnapshot", () => {
    const { result } = renderHook(() => useStrategyHistory());
    expect(typeof result.current.undo).toBe("function");
    expect(typeof result.current.redo).toBe("function");
    expect(typeof result.current.canUndo).toBe("function");
    expect(typeof result.current.canRedo).toBe("function");
    expect(typeof result.current.pushSnapshot).toBe("function");
  });

  it("useStrategyActions returns mutation actions (no buildPlan)", () => {
    const { result } = renderHook(() => useStrategyActions());
    expect(typeof result.current.addStep).toBe("function");
    expect(typeof result.current.updateStep).toBe("function");
    expect(typeof result.current.removeStep).toBe("function");
    expect(typeof result.current.setStrategy).toBe("function");
    expect(typeof result.current.setStrategyMeta).toBe("function");
    expect(typeof result.current.clear).toBe("function");
  });

  it("useStrategyListActions returns list mutation actions", () => {
    const { result } = renderHook(() => useStrategyListActions());
    expect(typeof result.current.setGraphValidationStatus).toBe("function");
  });
});
