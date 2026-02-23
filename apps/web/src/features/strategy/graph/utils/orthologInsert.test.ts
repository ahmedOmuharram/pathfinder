import { describe, expect, it } from "vitest";
import type { StrategyStep } from "@/features/strategy/types";
import { computeOrthologInsert } from "@/features/strategy/graph/utils/orthologInsert";

function step(partial: Partial<StrategyStep> & { id: string }): StrategyStep {
  return {
    id: partial.id,
    kind: partial.kind ?? "search",
    displayName: partial.displayName ?? partial.id,
    searchName: partial.searchName,
    recordType: partial.recordType,
    parameters: partial.parameters,
    primaryInputStepId: partial.primaryInputStepId,
    secondaryInputStepId: partial.secondaryInputStepId,
    operator: partial.operator,
  } as StrategyStep;
}

describe("computeOrthologInsert", () => {
  it("creates a transform step from selected id and patches downstream primary when insertBetween", () => {
    const steps = [
      step({ id: "a", recordType: "gene" }),
      step({ id: "b", kind: "transform", primaryInputStepId: "a" }),
    ];
    const result = computeOrthologInsert({
      selectedId: "a",
      steps,
      strategyRecordType: null,
      search: { name: "ortholog_search", displayName: "Find orthologs" } as any,
      options: { insertBetween: true },
      generateId: () => "new1",
    });

    expect(result.newStep).toMatchObject({
      id: "new1",
      kind: "transform",
      primaryInputStepId: "a",
      searchName: "ortholog_search",
      recordType: "gene",
    });
    expect(result.downstreamPatch).toEqual({
      stepId: "b",
      patch: { primaryInputStepId: "new1" },
    });
  });

  it("patches downstream secondary when downstream uses selected as secondary input", () => {
    const steps = [
      step({ id: "a", recordType: "gene" }),
      step({
        id: "c",
        kind: "combine",
        primaryInputStepId: "x",
        secondaryInputStepId: "a",
      }),
    ];
    const result = computeOrthologInsert({
      selectedId: "a",
      steps,
      strategyRecordType: null,
      search: { name: "ortholog_search", displayName: "Ortholog tool" } as any,
      options: { insertBetween: true },
      generateId: () => "new2",
    });
    expect(result.downstreamPatch).toEqual({
      stepId: "c",
      patch: { secondaryInputStepId: "new2" },
    });
  });

  it("does not patch downstream when insertBetween is false", () => {
    const steps = [
      step({ id: "a", recordType: "gene" }),
      step({ id: "b", kind: "transform", primaryInputStepId: "a" }),
    ];
    const result = computeOrthologInsert({
      selectedId: "a",
      steps,
      strategyRecordType: null,
      search: { name: "ortholog_search", displayName: null } as any,
      options: { insertBetween: false },
      generateId: () => "new3",
    });
    expect(result.downstreamPatch).toBeUndefined();
  });
});
