import { describe, expect, it } from "vitest";
import { buildStrategyFromGraphSnapshot } from "./graphSnapshot";

describe("features/chat/utils/graphSnapshot", () => {
  it("treats missing steps field as metadata-only update (keeps existing steps)", () => {
    const strategy = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: { name: "New" }, // no steps field
      stepsById: {
        a: { id: "a", displayName: "A", kind: "search" as any },
      },
      existingStrategy: {
        id: "old",
        name: "Old",
        siteId: "plasmodb",
        recordType: "gene",
        steps: [{ id: "a", displayName: "A" } as any],
        rootStepId: "a",
        createdAt: "t",
        updatedAt: "t",
      } as any,
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
      graphSnapshot: { steps: null as any },
      stepsById: { a: { id: "a", displayName: "A", kind: "search" as any } },
      existingStrategy: null,
    });
    expect(strategy.steps).toEqual([]);
  });

  it("treats explicit steps:undefined as a wipe (steps become empty) because steps field is present", () => {
    const strategy = buildStrategyFromGraphSnapshot({
      snapshotId: "s1",
      siteId: "plasmodb",
      graphSnapshot: { steps: undefined as any },
      stepsById: { a: { id: "a", displayName: "A", kind: "search" as any } },
      existingStrategy: {
        id: "s1",
        name: "Old",
        siteId: "plasmodb",
        recordType: "gene",
        steps: [{ id: "a", displayName: "A" } as any],
        rootStepId: "a",
        createdAt: "t",
        updatedAt: "t",
      } as any,
    });
    expect(strategy.steps).toEqual([]);
  });

  it("uses existing recordType when snapshot recordType is undefined, and can explicitly null it", () => {
    const existing = {
      id: "s1",
      name: "Old",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      createdAt: "t",
      updatedAt: "t",
    } as any;

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
        a: {
          id: "a",
          displayName: "Curated Name",
          kind: "search" as any,
          searchName: "q",
        },
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
        a: {
          id: "a",
          displayName: "My Custom Name",
          kind: "search" as any,
          searchName: "q",
        },
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
            inputStepIds: ["a", "b", 123] as any,
          },
        ],
      },
      stepsById: {},
      existingStrategy: null,
    });
    const c = strategy.steps.find((s) => s.id === "c");
    expect(c?.primaryInputStepId).toBe("a");
    expect(c?.secondaryInputStepId).toBe("b");
  });
});
