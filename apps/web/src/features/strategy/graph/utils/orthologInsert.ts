import type { Search } from "@pathfinder/shared";
import type { StrategyStep } from "@/features/strategy/types";
import { resolveRecordType } from "@/lib/strategyGraph";

export type OrthologInsertResult = {
  newStep: StrategyStep;
  downstreamPatch?: { stepId: string; patch: Partial<StrategyStep> };
};

function findFirstDownstream(
  steps: StrategyStep[],
  selectedId: string,
): { step: StrategyStep; uses: "primary" | "secondary" } | null {
  for (const s of steps) {
    if (s.primaryInputStepId === selectedId) return { step: s, uses: "primary" };
    if (s.secondaryInputStepId === selectedId) return { step: s, uses: "secondary" };
  }
  return null;
}

export function computeOrthologInsert(args: {
  selectedId: string;
  steps: StrategyStep[];
  strategyRecordType?: string | null;
  search: Search;
  options: { insertBetween: boolean };
  generateId: () => string;
}): OrthologInsertResult {
  const { selectedId, steps, strategyRecordType, search, options, generateId } = args;
  const stepsById = new Map(steps.map((s) => [s.id, s]));

  const inferredRecordType =
    resolveRecordType(selectedId, stepsById) ||
    strategyRecordType ||
    stepsById.get(selectedId)?.recordType ||
    null;

  const newId = generateId();
  const newStep: StrategyStep = {
    id: newId,
    kind: "transform",
    displayName: search.displayName || "Find orthologs",
    searchName: search.name,
    recordType: inferredRecordType ?? undefined,
    parameters: {},
    primaryInputStepId: selectedId,
  };

  const downstream = findFirstDownstream(steps, selectedId);
  if (!options.insertBetween || !downstream) {
    return { newStep };
  }

  if (downstream.uses === "primary") {
    return {
      newStep,
      downstreamPatch: {
        stepId: downstream.step.id,
        patch: { primaryInputStepId: newId },
      },
    };
  }
  return {
    newStep,
    downstreamPatch: {
      stepId: downstream.step.id,
      patch: { secondaryInputStepId: newId },
    },
  };
}
