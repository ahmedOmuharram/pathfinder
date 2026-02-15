import { describe, expect, it } from "vitest";
import { buildSpineLayout } from "./compactLayout";
import type { Step } from "@pathfinder/shared";

function makeStep(
  overrides: Partial<Step> & { id: string; displayName: string },
): Step {
  return { resultCount: null, ...overrides } as Step;
}

describe("buildSpineLayout", () => {
  it("returns empty array for no steps", () => {
    expect(buildSpineLayout([], null)).toEqual([]);
    expect(buildSpineLayout([], "abc")).toEqual([]);
  });

  it("handles a single search step", () => {
    const steps = [makeStep({ id: "s1", displayName: "Search 1" })];
    const result = buildSpineLayout(steps, "s1");
    expect(result).toHaveLength(1);
    expect(result[0].step.displayName).toBe("Search 1");
    expect(result[0].step.kind).toBe("search");
    expect(result[0].step.stepNumber).toBe(1);
    expect(result[0].secondaryInput).toBeUndefined();
  });

  it("handles a linear chain: search -> transform", () => {
    const steps = [
      makeStep({ id: "s1", displayName: "Search 1" }),
      makeStep({
        id: "t1",
        displayName: "Transform 1",
        primaryInputStepId: "s1",
      }),
    ];
    const result = buildSpineLayout(steps, "t1");
    expect(result).toHaveLength(2);
    expect(result[0].step.displayName).toBe("Search 1");
    expect(result[0].step.stepNumber).toBe(1);
    expect(result[1].step.displayName).toBe("Transform 1");
    expect(result[1].step.stepNumber).toBe(2);
    expect(result[0].secondaryInput).toBeUndefined();
    expect(result[1].secondaryInput).toBeUndefined();
  });

  it("handles a combine: two searches -> combine", () => {
    const steps = [
      makeStep({ id: "s1", displayName: "Search A" }),
      makeStep({ id: "s2", displayName: "Search B" }),
      makeStep({
        id: "c1",
        displayName: "Combined",
        primaryInputStepId: "s1",
        secondaryInputStepId: "s2",
        operator: "INTERSECT",
      }),
    ];
    const result = buildSpineLayout(steps, "c1");
    // Spine: s1 -> c1 (with s2 as secondary)
    expect(result).toHaveLength(2);
    expect(result[0].step.displayName).toBe("Search A");
    expect(result[0].secondaryInput).toBeUndefined();
    expect(result[1].step.displayName).toBe("Combined");
    expect(result[1].step.operator).toBe("INTERSECT");
    expect(result[1].secondaryInput?.displayName).toBe("Search B");
  });

  it("handles combine followed by transform", () => {
    const steps = [
      makeStep({ id: "s1", displayName: "A" }),
      makeStep({ id: "s2", displayName: "B" }),
      makeStep({
        id: "c1",
        displayName: "C",
        primaryInputStepId: "s1",
        secondaryInputStepId: "s2",
        operator: "UNION",
      }),
      makeStep({
        id: "t1",
        displayName: "Transform",
        primaryInputStepId: "c1",
      }),
    ];
    const result = buildSpineLayout(steps, "t1");
    // Spine: s1 -> c1 (sec: s2) -> t1
    expect(result).toHaveLength(3);
    expect(result[0].step.displayName).toBe("A");
    expect(result[1].step.displayName).toBe("C");
    expect(result[1].secondaryInput?.displayName).toBe("B");
    expect(result[2].step.displayName).toBe("Transform");
  });

  it("assigns step numbers in execution (topological) order", () => {
    const steps = [
      makeStep({ id: "s1", displayName: "First" }),
      makeStep({ id: "s2", displayName: "Second" }),
      makeStep({
        id: "c1",
        displayName: "Combine",
        primaryInputStepId: "s1",
        secondaryInputStepId: "s2",
        operator: "INTERSECT",
      }),
      makeStep({
        id: "t1",
        displayName: "Last",
        primaryInputStepId: "c1",
      }),
    ];
    const result = buildSpineLayout(steps, "t1");
    // topo order: s1=1, s2=2, c1=3, t1=4
    expect(result[0].step.stepNumber).toBe(1); // s1
    expect(result[1].step.stepNumber).toBe(3); // c1
    expect(result[1].secondaryInput?.stepNumber).toBe(2); // s2
    expect(result[2].step.stepNumber).toBe(4); // t1
  });

  it("handles chained combines (VEuPathDB-style pipeline)", () => {
    // s1 + s2 -> c3, c3 + s4 -> c5, c5 -> t6
    const steps = [
      makeStep({ id: "s1", displayName: "Step 1" }),
      makeStep({ id: "s2", displayName: "Step 2" }),
      makeStep({
        id: "c3",
        displayName: "Step 3",
        primaryInputStepId: "s1",
        secondaryInputStepId: "s2",
        operator: "INTERSECT",
      }),
      makeStep({ id: "s4", displayName: "Step 4" }),
      makeStep({
        id: "c5",
        displayName: "Step 5",
        primaryInputStepId: "c3",
        secondaryInputStepId: "s4",
        operator: "UNION",
      }),
      makeStep({
        id: "t6",
        displayName: "Step 6",
        primaryInputStepId: "c5",
      }),
    ];
    const result = buildSpineLayout(steps, "t6");
    // Spine: s1 -> c3 (sec: s2) -> c5 (sec: s4) -> t6
    expect(result).toHaveLength(4);
    expect(result.map((s) => s.step.displayName)).toEqual([
      "Step 1",
      "Step 3",
      "Step 5",
      "Step 6",
    ]);
    expect(result[1].secondaryInput?.displayName).toBe("Step 2");
    expect(result[2].secondaryInput?.displayName).toBe("Step 4");
    expect(result[0].secondaryInput).toBeUndefined();
    expect(result[3].secondaryInput).toBeUndefined();
  });
});
