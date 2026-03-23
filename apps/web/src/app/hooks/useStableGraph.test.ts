/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { useStableGraph } from "./useStableGraph";
import type { Strategy } from "@pathfinder/shared";

const makeStrategy = (steps: number): Strategy => ({
  id: "s1",
  name: "Test",
  siteId: "plasmodb",
  recordType: "gene",
  steps: Array.from({ length: steps }, (_, i) => ({
    id: `step-${i}`,
    kind: "search" as const,
    displayName: `Step ${i}`,
    searchName: "GeneByTextSearch",
    isBuilt: false as const,
    isFiltered: false as const,
  })),
  rootStepId: "step-0",
  isSaved: false,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
});

describe("useStableGraph", () => {
  it("returns strategy and hasGraph=true when strategy has steps", () => {
    const strategy = makeStrategy(2);
    const { result } = renderHook(() => useStableGraph(strategy));
    expect(result.current.hasGraph).toBe(true);
    expect(result.current.displayStrategy).toBe(strategy);
  });

  it("returns null when no strategy", () => {
    const { result } = renderHook(() => useStableGraph(null));
    expect(result.current.hasGraph).toBe(false);
    expect(result.current.displayStrategy).toBeNull();
  });

  it("returns null when strategy has empty steps", () => {
    const { result } = renderHook(() => useStableGraph(makeStrategy(0)));
    expect(result.current.hasGraph).toBe(false);
  });

  it("keeps cached strategy when strategy becomes null", () => {
    const strategy = makeStrategy(2);
    const { result, rerender } = renderHook(({ s }) => useStableGraph(s), {
      initialProps: { s: strategy as Strategy | null },
    });
    expect(result.current.hasGraph).toBe(true);

    rerender({ s: null });
    // Cache persists — graph stays visible
    expect(result.current.hasGraph).toBe(true);
    expect(result.current.displayStrategy).toBe(strategy);
  });

  it("keeps cached strategy when steps become empty", () => {
    const strategy = makeStrategy(3);
    const { result, rerender } = renderHook(({ s }) => useStableGraph(s), {
      initialProps: { s: strategy as Strategy | null },
    });

    rerender({ s: makeStrategy(0) });
    expect(result.current.hasGraph).toBe(true);
    expect(result.current.displayStrategy).toBe(strategy);
  });

  it("updates to new strategy when new one has steps", () => {
    const s1 = makeStrategy(2);
    const s2 = makeStrategy(4);
    const { result, rerender } = renderHook(({ s }) => useStableGraph(s), {
      initialProps: { s: s1 as Strategy | null },
    });

    rerender({ s: s2 });
    expect(result.current.displayStrategy).toBe(s2);
  });
});
