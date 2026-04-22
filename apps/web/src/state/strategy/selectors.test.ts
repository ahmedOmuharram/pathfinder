/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import type { Step } from "@pathfinder/shared";
import { useStrategyStore } from "./store";
import { useStepsById } from "./selectors";

function step(partial: Partial<Step> & { id: string; displayName: string }): Step {
  return { isBuilt: false, isFiltered: false, ...partial } as Step;
}

describe("state/strategy/selectors — useStepsById", () => {
  beforeEach(() => {
    useStrategyStore.getState().clear();
  });

  it("returns empty map when strategy is null", () => {
    const { result } = renderHook(() => useStepsById());
    expect(result.current).toEqual({});
  });

  it("returns step map keyed by step id", () => {
    const { addStep } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "Search 1", searchName: "geneById", recordType: "gene" }));
    addStep(step({ id: "s2", displayName: "Search 2", searchName: "geneById", recordType: "gene" }));

    const { result } = renderHook(() => useStepsById());
    expect(Object.keys(result.current).sort()).toEqual(["s1", "s2"]);
    expect(result.current["s1"]?.displayName).toBe("Search 1");
    expect(result.current["s2"]?.displayName).toBe("Search 2");
  });

  it("returns stable reference when strategy.steps array identity is unchanged", () => {
    const { addStep } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));

    const { result, rerender } = renderHook(() => useStepsById());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });

  it("returns updated map when steps change", () => {
    const { addStep, updateStep } = useStrategyStore.getState();
    addStep(step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }));

    const { result, rerender } = renderHook(() => useStepsById());
    const before = result.current;

    updateStep("s1", { displayName: "Renamed" });
    rerender();
    expect(result.current).not.toBe(before);
    expect(result.current["s1"]?.displayName).toBe("Renamed");
  });
});
