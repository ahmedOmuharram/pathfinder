import { describe, expect, test } from "vitest";
import { layoutStrategyGraph } from "@/lib/strategyGraph/layout";
import type { Strategy } from "@pathfinder/shared";

describe("layoutStrategyGraph", () => {
  test("returns an empty map for null/empty strategy", async () => {
    expect((await layoutStrategyGraph(null)).size).toBe(0);
    expect((await layoutStrategyGraph({ steps: [] } as unknown as Strategy)).size).toBe(
      0,
    );
  });

  test("lays out a single leaf step with a numeric position", async () => {
    const strategy = {
      id: "s1",
      steps: [{ id: "a", displayName: "A" }],
    } as unknown as Strategy;

    const positions = await layoutStrategyGraph(strategy);
    const pos = positions.get("a");
    expect(pos).toBeDefined();
    expect(Number.isFinite(pos!.x)).toBe(true);
    expect(Number.isFinite(pos!.y)).toBe(true);
  });

  test("lays out a linear chain with source ranked left of target", async () => {
    const strategy = {
      id: "s2",
      steps: [
        { id: "a", displayName: "A" },
        { id: "b", displayName: "B", primaryInputStepId: "a" },
      ],
    } as unknown as Strategy;

    const positions = await layoutStrategyGraph(strategy);
    const a = positions.get("a")!;
    const b = positions.get("b")!;
    expect(a.x).toBeLessThan(b.x);
  });

  test("primary input source is vertically above secondary input source on a combine", async () => {
    const strategy = {
      id: "s-order",
      steps: [
        { id: "secondary", displayName: "Secondary" },
        { id: "primary", displayName: "Primary" },
        {
          id: "comb",
          displayName: "Combine",
          primaryInputStepId: "primary",
          secondaryInputStepId: "secondary",
          operator: "UNION",
        },
      ],
    } as unknown as Strategy;

    const positions = await layoutStrategyGraph(strategy);
    const primary = positions.get("primary")!;
    const secondary = positions.get("secondary")!;
    // FIXED_ORDER with primary-in port index 0 (top of WEST side) and
    // secondary-in index 1 (below) pins the primary source above.
    expect(primary.y).toBeLessThanOrEqual(secondary.y);
  });

  test("nested combines keep primary above secondary at every level", async () => {
    const strategy = {
      id: "nested",
      steps: [
        { id: "a", displayName: "A" },
        { id: "b", displayName: "B" },
        {
          id: "c1",
          displayName: "Combine 1",
          primaryInputStepId: "a",
          secondaryInputStepId: "b",
          operator: "UNION",
        },
        { id: "d", displayName: "D" },
        {
          id: "c2",
          displayName: "Combine 2",
          primaryInputStepId: "c1",
          secondaryInputStepId: "d",
          operator: "INTERSECT",
        },
      ],
    } as unknown as Strategy;

    const positions = await layoutStrategyGraph(strategy);
    expect(positions.get("a")!.y).toBeLessThanOrEqual(positions.get("b")!.y);
    expect(positions.get("c1")!.y).toBeLessThanOrEqual(positions.get("d")!.y);
    // The combine itself sits to the right of its inputs.
    expect(positions.get("c1")!.x).toBeGreaterThan(positions.get("a")!.x);
    expect(positions.get("c2")!.x).toBeGreaterThan(positions.get("c1")!.x);
  });

  test("skips edges whose endpoints reference missing steps", async () => {
    const strategy = {
      id: "missing",
      steps: [{ id: "a", displayName: "A", primaryInputStepId: "ghost" }],
    } as unknown as Strategy;

    // Should not throw even though "ghost" is not a step.
    const positions = await layoutStrategyGraph(strategy);
    expect(positions.get("a")).toBeDefined();
  });
});
