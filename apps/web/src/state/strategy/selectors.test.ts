/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import type { Step, Strategy } from "@pathfinder/shared";
import {
  useStrategyHistory,
  useStrategyListActions,
} from "@/state/useStrategySelectors";
import { useStepsById } from "./selectors";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children);
  }
  return Wrapper;
}

describe("state/useStrategySelectors", () => {
  it("useStrategyHistory returns undo/redo functions and pushSnapshot", () => {
    const { result } = renderHook(() => useStrategyHistory("strategy-1"), {
      wrapper: makeWrapper(),
    });
    expect(typeof result.current.undo).toBe("function");
    expect(typeof result.current.redo).toBe("function");
    expect(typeof result.current.canUndo).toBe("function");
    expect(typeof result.current.canRedo).toBe("function");
    expect(typeof result.current.pushSnapshot).toBe("function");
  });

  it("useStrategyListActions returns setGraphValidationStatus", () => {
    const { result } = renderHook(() => useStrategyListActions());
    expect(typeof result.current.setGraphValidationStatus).toBe("function");
  });
});

function makeStep(id: string): Step {
  return {
    id,
    displayName: `Step ${id}`,
    searchName: "GenesByTaxon",
    recordType: "gene",
    isFiltered: false,
  };
}

function makeStrategy(steps: Step[]): Strategy {
  return {
    id: "strategy-1",
    name: "Test",
    siteId: "plasmodb",
    recordType: "gene",
    steps,
    rootStepId: steps[steps.length - 1]?.id ?? null,
    isSaved: false,
    description: null,
    wdkStrategyId: null,
    wdkUrl: null,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  };
}

function stepsById(strategy: Strategy | null | undefined): Record<string, Step> {
  return renderHook(() => useStepsById(strategy)).result.current;
}

describe("state/strategy/selectors — useStepsById", () => {
  it("indexes every step under its own id", () => {
    const s1 = makeStep("s1");
    const s2 = makeStep("s2");
    const map = stepsById(makeStrategy([s1, s2]));
    expect(Object.keys(map).sort()).toEqual(["s1", "s2"]);
    expect(map["s1"]).toBe(s1);
    expect(map["s2"]).toBe(s2);
  });

  it("keeps the last step when two steps share an id", () => {
    const first = makeStep("dup");
    const second = { ...makeStep("dup"), displayName: "Later" };
    const map = stepsById(makeStrategy([first, second]));
    expect(Object.keys(map)).toEqual(["dup"]);
    expect(map["dup"]).toBe(second);
  });

  it("returns one shared empty map for null, undefined and step-less strategies", () => {
    const forNull = stepsById(null);
    expect(forNull).toEqual({});
    expect(stepsById(undefined)).toBe(forNull);
    expect(stepsById(makeStrategy([]))).toBe(forNull);
    expect(stepsById(makeStrategy([]))).toBe(forNull);
  });

  it("returns the identical map for repeated reads of the same steps array", () => {
    const strategy = makeStrategy([makeStep("s1")]);
    const first = stepsById(strategy);
    expect(stepsById(strategy)).toBe(first);
    expect(stepsById({ ...strategy, name: "Renamed" })).toBe(first);
  });

  it("returns a fresh map once the steps array itself is replaced", () => {
    const first = stepsById(makeStrategy([makeStep("s1")]));
    const second = stepsById(makeStrategy([makeStep("s1")]));
    expect(second).not.toBe(first);
    expect(second).toEqual(first);
  });
});
