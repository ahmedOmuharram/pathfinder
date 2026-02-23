import { describe, expect, test } from "vitest";
import type { StrategyStep } from "@/features/strategy/types";
import { computeNodeDeletionResult } from "@/features/strategy/graph/utils/nodeDeletionLogic";

function step(partial: Partial<StrategyStep> & { id: string }): StrategyStep {
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
  } as StrategyStep;
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
      { stepId: "transform", patch: { primaryInputStepId: undefined } },
      { stepId: "combine", patch: { secondaryInputStepId: undefined } },
    ]);
  });

  test("ignores deleted ids not present in steps", () => {
    const steps = [step({ id: "a" })];
    expect(computeNodeDeletionResult({ steps, deletedNodeIds: ["missing"] })).toEqual({
      removeIds: [],
      patches: [],
    });
  });
});
