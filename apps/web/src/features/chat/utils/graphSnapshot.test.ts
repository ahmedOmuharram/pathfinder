import { describe, expect, it } from "vitest";
import type { Step, Strategy } from "@pathfinder/shared";
import { buildStrategyFromGraphSnapshot } from "./graphSnapshot";
import type { GraphSnapshotInput } from "./graphSnapshot";

/** Minimal Step with required boolean fields defaulted. */
function s(partial: Partial<Step> & { id: string; displayName: string }): Step {
  return { isBuilt: false, isFiltered: false, ...partial } as Step;
}

describe("features/chat/utils/graphSnapshot", () => {
  it("treats missing steps field as metadata-only update (keeps existing steps)", () => {
    const strategy = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: { name: "New" }, // no steps field
      stepsById: {
        a: s({ id: "a", displayName: "A", kind: "search" }),
      },
      existingStrategy: {
        id: "old",
        name: "Old",
        siteId: "plasmodb",
        recordType: "gene",
        steps: [s({ id: "a", displayName: "A" })],
        rootStepId: "a",
        isSaved: false,
        createdAt: "t",
        updatedAt: "t",
      } satisfies Strategy,
    });

    expect(strategy.id).toBe("s1");
    expect(strategy.name).toBe("New");
    expect(strategy.steps).toHaveLength(1);
    expect(strategy.steps[0]?.id).toBe("a");
  });

  it("treats explicit steps:null as a wipe (steps become empty)", () => {
    const strategy = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: { steps: null } as unknown as GraphSnapshotInput,
      stepsById: { a: s({ id: "a", displayName: "A", kind: "search" }) },
      existingStrategy: null,
    });
    expect(strategy.steps).toEqual([]);
  });

  it("treats explicit steps:undefined as a wipe (steps become empty) because steps field is present", () => {
    const strategy = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: { steps: undefined } as unknown as GraphSnapshotInput,
      stepsById: { a: s({ id: "a", displayName: "A", kind: "search" }) },
      existingStrategy: {
        id: "s1",
        name: "Old",
        siteId: "plasmodb",
        recordType: "gene",
        steps: [s({ id: "a", displayName: "A" })],
        rootStepId: "a",
        isSaved: false,
        createdAt: "t",
        updatedAt: "t",
      } satisfies Strategy,
    });
    expect(strategy.steps).toEqual([]);
  });

  it("uses existing recordType when snapshot recordType is undefined, and can explicitly null it", () => {
    const existing: Strategy = {
      id: "s1",
      name: "Old",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "t",
      updatedAt: "t",
    };

    const keep = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: { name: "X" }, // recordType omitted
      stepsById: {},
      existingStrategy: existing,
    });
    expect(keep.recordType).toBe("gene");

    const nulled = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: { recordType: null },
      stepsById: {},
      existingStrategy: existing,
    });
    expect(nulled.recordType).toBeNull();
  });

  it("treats URL-like incoming displayName as fallback and preserves custom existing names", () => {
    const strategy = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: {
        steps: [
          {
            id: "a",
            displayName: "https://example.com/q",
            kind: "search",
            searchName: "q",
          },
        ],
      },
      stepsById: {
        a: s({
          id: "a",
          displayName: "Curated Name",
          kind: "search",
          searchName: "q",
        }),
      },
      existingStrategy: null,
    });
    expect(strategy.steps[0]?.displayName).toBe("Curated Name");
  });

  it("preserves existing non-fallback displayName when incoming is fallback-like", () => {
    const strategy = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: {
        steps: [{ id: "a", displayName: "search", kind: "search", searchName: "q" }],
      },
      stepsById: {
        a: s({
          id: "a",
          displayName: "My Custom Name",
          kind: "search",
          searchName: "q",
        }),
      },
      existingStrategy: null,
    });
    expect(strategy.steps[0]?.displayName).toBe("My Custom Name");
  });

  it("maps inputStepIds into primary/secondary inputs", () => {
    const strategy = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: {
        steps: [
          { id: "a", displayName: "A", kind: "search" },
          {
            id: "c",
            displayName: "C",
            kind: "combine",
            inputStepIds: ["a", "b", 123] as unknown as string[],
          },
        ],
      },
      stepsById: {},
      existingStrategy: null,
    });
    const c = strategy.steps.find((st) => st.id === "c");
    expect(c?.primaryInputStepId).toBe("a");
    expect(c?.secondaryInputStepId).toBe("b");
  });
});
