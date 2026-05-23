import { describe, it, expect } from "vitest";
import type { StrategyStepNode } from "@pathfinder/shared";
import { flattenStrategyStepNode } from "./multiStepUtils";

describe("flattenStrategyStepNode", () => {
  it("flattens a single leaf node into one step", () => {
    const node: StrategyStepNode = {
      id: "s1",
      searchName: "GenesByTaxon",
      displayName: "Genes by Taxon",
      parameters: { organism: { type: "single-pick-vocabulary", value: "pf3d7" } },
    };

    const steps = flattenStrategyStepNode(node, "gene");

    expect(steps).toHaveLength(1);
    expect(steps[0]).toEqual({
      id: "s1",
      displayName: "Genes by Taxon",
      searchName: "GenesByTaxon",
      recordType: "gene",
      parameters: { organism: { type: "single-pick-vocabulary", value: "pf3d7" } },
      operator: null,
      primaryInputStepId: null,
      secondaryInputStepId: null,
      isBuilt: false,
      isFiltered: false,
    });
  });

  it("generates an ID when node.id is undefined", () => {
    const node: StrategyStepNode = {
      searchName: "GenesByTaxon",
    };

    const steps = flattenStrategyStepNode(node, "gene");

    expect(steps).toHaveLength(1);
    expect(steps[0]!.id).toMatch(/^step_[0-9a-f]+$/);
  });

  it("uses searchName as displayName fallback when displayName is undefined", () => {
    const node: StrategyStepNode = {
      id: "s1",
      searchName: "GenesByTaxon",
    };

    const steps = flattenStrategyStepNode(node, "gene");

    expect(steps[0]!.displayName).toBe("GenesByTaxon");
  });

  it("flattens a node with primaryInput (transform/unary)", () => {
    const node: StrategyStepNode = {
      id: "transform1",
      searchName: "TransformByOrthologs",
      displayName: "Orthologs",
      primaryInput: {
        id: "search1",
        searchName: "GenesByTaxon",
        displayName: "By Taxon",
        parameters: { organism: { type: "single-pick-vocabulary", value: "pf3d7" } },
      },
    };

    const steps = flattenStrategyStepNode(node, "gene");

    expect(steps).toHaveLength(2);
    // First step is the child (primary input)
    expect(steps[0]!.id).toBe("search1");
    expect(steps[0]!.searchName).toBe("GenesByTaxon");
    // Second step is the parent
    expect(steps[1]!.id).toBe("transform1");
    expect(steps[1]!.primaryInputStepId).toBe("search1");
    expect(steps[1]!.secondaryInputStepId).toBeNull();
  });

  it("flattens a node with primaryInput and secondaryInput (combine/binary)", () => {
    const node: StrategyStepNode = {
      id: "combine1",
      searchName: "BooleanQuestion",
      displayName: "Intersect",
      operator: "INTERSECT",
      primaryInput: {
        id: "left",
        searchName: "GenesByTaxon",
        displayName: "Left",
      },
      secondaryInput: {
        id: "right",
        searchName: "GenesByProduct",
        displayName: "Right",
      },
    };

    const steps = flattenStrategyStepNode(node, "gene");

    expect(steps).toHaveLength(3);
    // Children first, in order
    expect(steps[0]!.id).toBe("left");
    expect(steps[1]!.id).toBe("right");
    // Parent last
    expect(steps[2]!.id).toBe("combine1");
    expect(steps[2]!.primaryInputStepId).toBe("left");
    expect(steps[2]!.secondaryInputStepId).toBe("right");
    expect(steps[2]!.operator).toBe("INTERSECT");
  });

  it("handles deeply nested tree (3 levels)", () => {
    const node: StrategyStepNode = {
      id: "root",
      searchName: "BooleanQuestion",
      displayName: "Root Combine",
      operator: "UNION",
      primaryInput: {
        id: "mid",
        searchName: "BooleanQuestion",
        displayName: "Mid Combine",
        operator: "INTERSECT",
        primaryInput: {
          id: "leaf1",
          searchName: "GenesByTaxon",
          displayName: "Leaf 1",
        },
        secondaryInput: {
          id: "leaf2",
          searchName: "GenesByProduct",
          displayName: "Leaf 2",
        },
      },
      secondaryInput: {
        id: "leaf3",
        searchName: "GenesByLocation",
        displayName: "Leaf 3",
      },
    };

    const steps = flattenStrategyStepNode(node, "transcript");

    expect(steps).toHaveLength(5);
    // Order: leaf1, leaf2, mid, leaf3, root (DFS, primary then secondary, parent last)
    expect(steps.map((s) => s.id)).toEqual(["leaf1", "leaf2", "mid", "leaf3", "root"]);
    expect(steps[2]!.primaryInputStepId).toBe("leaf1");
    expect(steps[2]!.secondaryInputStepId).toBe("leaf2");
    expect(steps[4]!.primaryInputStepId).toBe("mid");
    expect(steps[4]!.secondaryInputStepId).toBe("leaf3");
  });

  it("passes typed parameter values through unchanged", () => {
    const node: StrategyStepNode = {
      id: "s1",
      searchName: "GenesByFoldChange",
      parameters: {
        fold_change: { type: "number", value: 2.5 },
        direction: { type: "single-pick-vocabulary", value: "up" },
        count: { type: "number", value: 42 },
      },
    };

    const steps = flattenStrategyStepNode(node, "gene");

    expect(steps[0]!.parameters).toEqual({
      fold_change: { type: "number", value: 2.5 },
      direction: { type: "single-pick-vocabulary", value: "up" },
      count: { type: "number", value: 42 },
    });
  });

  it("handles node with empty parameters", () => {
    const node: StrategyStepNode = {
      id: "s1",
      searchName: "AllGenes",
      parameters: {},
    };

    const steps = flattenStrategyStepNode(node, "gene");

    expect(steps[0]!.parameters).toEqual({});
  });

  it("handles node with undefined parameters", () => {
    const node: StrategyStepNode = {
      id: "s1",
      searchName: "AllGenes",
    };

    const steps = flattenStrategyStepNode(node, "gene");

    expect(steps[0]!.parameters).toEqual({});
  });

  it("sets recordType on all steps from the argument", () => {
    const node: StrategyStepNode = {
      id: "combine1",
      searchName: "BooleanQuestion",
      primaryInput: {
        id: "s1",
        searchName: "GenesByTaxon",
      },
      secondaryInput: {
        id: "s2",
        searchName: "GenesByProduct",
      },
    };

    const steps = flattenStrategyStepNode(node, "transcript");

    for (const step of steps) {
      expect(step.recordType).toBe("transcript");
    }
  });
});
