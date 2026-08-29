import { describe, expect, it } from "vitest";
import type { Step, Strategy } from "@pathfinder/shared";
import { useStepsById } from "./selectors";

/**
 * `useStepsById` is named like a hook but calls none: it is a pure function
 * over a strategy. Exercising it through `renderHook` in jsdom is what left it
 * at a 0% mutation score - every mutant errored in that environment instead of
 * being killed, so nothing here was actually verified.
 *
 * The WeakMap cache is the part worth pinning: it keys on the steps ARRAY
 * identity, so a re-render with the same array must not rebuild the map (that
 * is what stops downstream memoized consumers re-rendering forever).
 */

function step(id: string): Step {
  return { id, searchName: "GenesByTaxon", isFiltered: false };
}

function strategy(steps: Step[]): Strategy {
  return {
    id: "s",
    name: "T",
    siteId: "plasmodb",
    isSaved: false,
    recordType: "gene",
    steps,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  };
}

describe("useStepsById", () => {
  it("indexes steps by id", () => {
    const result = useStepsById(strategy([step("a"), step("b")]));

    expect(Object.keys(result).sort()).toEqual(["a", "b"]);
    expect(result["a"]?.id).toBe("a");
  });

  it("returns the same object for the same steps array", () => {
    const s = strategy([step("a")]);

    expect(useStepsById(s)).toBe(useStepsById(s));
  });

  it("rebuilds when the steps array identity changes", () => {
    const first = useStepsById(strategy([step("a")]));
    const second = useStepsById(strategy([step("a")]));

    expect(second).not.toBe(first);
    expect(second).toEqual(first);
  });

  it("returns the shared empty map for a strategy with no steps", () => {
    expect(useStepsById(strategy([]))).toBe(useStepsById(strategy([])));
    expect(useStepsById(strategy([]))).toEqual({});
  });

  it("returns the shared empty map for null and undefined", () => {
    expect(useStepsById(null)).toEqual({});
    expect(useStepsById(undefined)).toEqual({});
    expect(useStepsById(null)).toBe(useStepsById(undefined));
  });

  it("the empty map is frozen so a caller cannot poison the shared value", () => {
    const empty = useStepsById(null);

    expect(Object.isFrozen(empty)).toBe(true);
  });

  it("a later step with a duplicate id wins", () => {
    const first = step("a");
    const second = { ...step("a"), searchName: "GenesByText" };

    const result = useStepsById(strategy([first, second]));

    expect(result["a"]?.searchName).toBe("GenesByText");
  });

  it("keeps every step when ids are distinct", () => {
    const result = useStepsById(strategy([step("a"), step("b"), step("c")]));

    expect(Object.keys(result)).toHaveLength(3);
  });
});
