import { describe, it, expect } from "vitest";
import type { PlanStepNode } from "@pathfinder/shared";
import { flattenPlanStepNode } from "./multiStepUtils";

describe("flattenPlanStepNode", () => {
  it("flattens a single leaf node into one step", () => {
    const node: PlanStepNode = {
      id: "s1",
      searchName: "GenesByTaxon",
      displayName: "Genes by Taxon",
      parameters: { organism: "pf3d7" },
    };

    const steps = flattenPlanStepNode(node, "gene");

    expect(steps).toHaveLength(1);
    expect(steps[0]).toEqual({
      id: "s1",
      displayName: "Genes by Taxon",
      searchName: "GenesByTaxon",
      recordType: "gene",
      parameters: { organism: "pf3d7" },
      operator: null,
      primaryInputStepId: null,
      secondaryInputStepId: null,
    });
  });

  it("generates an ID when node.id is undefined", () => {
    const node: PlanStepNode = {
      searchName: "GenesByTaxon",
    };

    const steps = flattenPlanStepNode(node, "gene");

    expect(steps).toHaveLength(1);
    expect(steps[0]!.id).toMatch(/^step_[0-9a-f]+$/);
  });

  it("uses searchName as displayName fallback when displayName is undefined", () => {
    const node: PlanStepNode = {
      id: "s1",
      searchName: "GenesByTaxon",
    };

    const steps = flattenPlanStepNode(node, "gene");

    expect(steps[0]!.displayName).toBe("GenesByTaxon");
  });

  it("flattens a node with primaryInput (transform/unary)", () => {
    const node: PlanStepNode = {
      id: "transform1",
      searchName: "TransformByOrthologs",
      displayName: "Orthologs",
      primaryInput: {
        id: "search1",
        searchName: "GenesByTaxon",
        displayName: "By Taxon",
        parameters: { organism: "pf3d7" },
      },
    };

    const steps = flattenPlanStepNode(node, "gene");

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
    const node: PlanStepNode = {
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

    const steps = flattenPlanStepNode(node, "gene");

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
    const node: PlanStepNode = {
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

    const steps = flattenPlanStepNode(node, "transcript");

    expect(steps).toHaveLength(5);
    // Order: leaf1, leaf2, mid, leaf3, root (DFS, primary then secondary, parent last)
    expect(steps.map((s) => s.id)).toEqual(["leaf1", "leaf2", "mid", "leaf3", "root"]);
    expect(steps[2]!.primaryInputStepId).toBe("leaf1");
    expect(steps[2]!.secondaryInputStepId).toBe("leaf2");
    expect(steps[4]!.primaryInputStepId).toBe("mid");
    expect(steps[4]!.secondaryInputStepId).toBe("leaf3");
  });

  it("converts parameter values to strings", () => {
    const node: PlanStepNode = {
      id: "s1",
      searchName: "GenesByFoldChange",
      parameters: {
        fold_change: 2.5,
        direction: "up",
        p_value: null,
        count: 42,
      },
    };

    const steps = flattenPlanStepNode(node, "gene");

    expect(steps[0]!.parameters).toEqual({
      fold_change: "2.5",
      direction: "up",
      p_value: "",
      count: "42",
    });
  });

  it("handles node with empty parameters", () => {
    const node: PlanStepNode = {
      id: "s1",
      searchName: "AllGenes",
      parameters: {},
    };

    const steps = flattenPlanStepNode(node, "gene");

    expect(steps[0]!.parameters).toEqual({});
  });

  it("handles node with undefined parameters", () => {
    const node: PlanStepNode = {
      id: "s1",
      searchName: "AllGenes",
    };

    const steps = flattenPlanStepNode(node, "gene");

    expect(steps[0]!.parameters).toEqual({});
  });

  it("sets recordType on all steps from the argument", () => {
    const node: PlanStepNode = {
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

    const steps = flattenPlanStepNode(node, "transcript");

    for (const step of steps) {
      expect(step.recordType).toBe("transcript");
    }
  });
});
