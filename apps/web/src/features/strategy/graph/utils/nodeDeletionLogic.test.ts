import { describe, expect, test } from "vitest";
import type { Step } from "@pathfinder/shared";
import { computeNodeDeletionResult } from "@/features/strategy/graph/utils/nodeDeletionLogic";

function step(partial: Partial<Step> & { id: string }): Step {
  return {
    id: partial.id,
    kind: partial.kind ?? "search",
    displayName: partial.displayName ?? partial.id,
    operator: partial.operator,
    recordType: partial.recordType,
    parameters: partial.parameters,
    searchName: partial.searchName,
    primaryInputStepId: partial.primaryInputStepId,
    secondaryInputStepId: partial.secondaryInputStepId,
  } as Step;
}

describe("computeNodeDeletionResult", () => {
  test("no-ops with empty inputs", () => {
    expect(computeNodeDeletionResult({ steps: [], deletedNodeIds: ["a"] })).toEqual({
      removeIds: [],
      patches: [],
    });
    expect(
      computeNodeDeletionResult({ steps: [step({ id: "a" })], deletedNodeIds: [] }),
    ).toEqual({ removeIds: [], patches: [] });
  });

  test("removes only explicitly deleted steps, detaching downstream inputs", () => {
    const steps = [
      step({ id: "search" }),
      step({ id: "transform", primaryInputStepId: "search" }),
      step({
        id: "combine",
        kind: "combine",
        primaryInputStepId: "transform",
        secondaryInputStepId: "search",
      }),
    ];
    const result = computeNodeDeletionResult({ steps, deletedNodeIds: ["search"] });
    expect(result.removeIds).toEqual(["search"]);
    expect(result.patches).toEqual([
      { stepId: "transform", patch: { primaryInputStepId: null } },
      { stepId: "combine", patch: { secondaryInputStepId: null } },
    ]);
  });

  test("ignores deleted ids not present in steps", () => {
    const steps = [step({ id: "a" })];
    expect(computeNodeDeletionResult({ steps, deletedNodeIds: ["missing"] })).toEqual({
      removeIds: [],
      patches: [],
    });
  });

  test("clears operator and colocationParams when input to a combine step is deleted", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "b" }),
      step({
        id: "combine",
        kind: "combine",
        operator: "INTERSECT",
        primaryInputStepId: "a",
        secondaryInputStepId: "b",
        colocationParams: { upstream: 1000, downstream: 1000, strand: "both" },
      }),
    ];
    const result = computeNodeDeletionResult({ steps, deletedNodeIds: ["b"] });
    expect(result.removeIds).toEqual(["b"]);
    const combinePatch = result.patches.find((p) => p.stepId === "combine");
    expect(combinePatch).toBeDefined();
    expect(combinePatch!.patch.secondaryInputStepId).toBeNull();
    expect(combinePatch!.patch.operator).toBeNull();
    expect(combinePatch!.patch.colocationParams).toBeNull();
  });

  test("clears operator when primary input to a combine step is deleted", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "b" }),
      step({
        id: "combine",
        kind: "combine",
        operator: "UNION",
        primaryInputStepId: "a",
        secondaryInputStepId: "b",
      }),
    ];
    const result = computeNodeDeletionResult({ steps, deletedNodeIds: ["a"] });
    const combinePatch = result.patches.find((p) => p.stepId === "combine");
    expect(combinePatch).toBeDefined();
    expect(combinePatch!.patch.primaryInputStepId).toBeNull();
    expect(combinePatch!.patch.operator).toBeNull();
  });

  test("does not clear operator for steps without one", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "t", kind: "transform", primaryInputStepId: "a" }),
    ];
    const result = computeNodeDeletionResult({ steps, deletedNodeIds: ["a"] });
    const tPatch = result.patches.find((p) => p.stepId === "t");
    expect(tPatch).toBeDefined();
    expect(tPatch!.patch.primaryInputStepId).toBeNull();
    expect(tPatch!.patch).not.toHaveProperty("operator");
  });

  test("deleting multiple nodes at once produces patches for all affected steps", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "b" }),
      step({ id: "c", primaryInputStepId: "a" }),
      step({ id: "d", primaryInputStepId: "b" }),
    ];
    const result = computeNodeDeletionResult({
      steps,
      deletedNodeIds: ["a", "b"],
    });
    expect(result.removeIds.sort()).toEqual(["a", "b"]);
    expect(result.patches).toHaveLength(2);
    expect(result.patches.map((p) => p.stepId).sort()).toEqual(["c", "d"]);
  });

  test("deleting both inputs of a combine clears both input fields and operator", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "b" }),
      step({
        id: "combine",
        kind: "combine",
        operator: "INTERSECT",
        primaryInputStepId: "a",
        secondaryInputStepId: "b",
      }),
    ];
    const result = computeNodeDeletionResult({
      steps,
      deletedNodeIds: ["a", "b"],
    });
    expect(result.removeIds.sort()).toEqual(["a", "b"]);
    const combinePatch = result.patches.find((p) => p.stepId === "combine");
    expect(combinePatch).toBeDefined();
    expect(combinePatch!.patch.primaryInputStepId).toBeNull();
    expect(combinePatch!.patch.secondaryInputStepId).toBeNull();
    expect(combinePatch!.patch.operator).toBeNull();
    expect(combinePatch!.patch.colocationParams).toBeNull();
  });

  test("no patches when deleted step is not referenced by anyone", () => {
    const steps = [step({ id: "a" }), step({ id: "b" })];
    const result = computeNodeDeletionResult({ steps, deletedNodeIds: ["a"] });
    expect(result.removeIds).toEqual(["a"]);
    expect(result.patches).toEqual([]);
  });

  test("deleting an intermediate transform detaches downstream but does not cascade", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "b", kind: "transform", primaryInputStepId: "a" }),
      step({ id: "c", kind: "transform", primaryInputStepId: "b" }),
    ];
    const result = computeNodeDeletionResult({ steps, deletedNodeIds: ["b"] });
    expect(result.removeIds).toEqual(["b"]);
    expect(result.patches).toEqual([
      { stepId: "c", patch: { primaryInputStepId: null } },
    ]);
    // a is unaffected
    expect(result.patches.find((p) => p.stepId === "a")).toBeUndefined();
  });
});
