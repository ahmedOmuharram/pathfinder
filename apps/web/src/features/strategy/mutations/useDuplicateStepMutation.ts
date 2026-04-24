"use client";

import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyCacheUtils } from "@/state/strategy/useStrategyQuery";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

export interface DuplicateStepVars {
  stepId: string;
}

const generateStepId = () => `step_${Math.random().toString(16).slice(2, 10)}`;

/**
 * Build the optimistic next-strategy after duplicating step `sourceId`.
 *
 * Insertion choice (single-rooted invariant must hold):
 *   1. Shallow-clone the source step with a fresh client id (parameters,
 *      searchName, recordType, kind preserved).
 *   2. Auto-wire the duplicate via a new combine step (operator INTERSECT) so
 *      the graph stays single-rooted. The combine takes the source as primary
 *      input and the duplicate as secondary input.
 *   3. If the source has a parent step (P references source as primary or
 *      secondary), rewire P's input slot to point at the new combine instead
 *      of the source. The combine slots into the topology where the source
 *      previously was.
 *   4. If the source is a root (no parent), the new combine becomes the new
 *      root.
 *
 * Returns null when the step id is unknown (caller should bail).
 */
export function applyDuplicate(
  strategy: Strategy,
  sourceId: string,
): Strategy | null {
  const source = strategy.steps.find((s) => s.id === sourceId);
  if (!source) return null;

  const duplicateId = generateStepId();
  const combineId = generateStepId();

  const duplicate: Step = {
    ...source,
    id: duplicateId,
    wdkStepId: null,
    estimatedSize: null,
    isBuilt: false,
    validation: null,
  };

  const combine: Step = {
    id: combineId,
    kind: "combine",
    displayName: "INTERSECT combine",
    operator: "INTERSECT",
    recordType: source.recordType ?? null,
    primaryInputStepId: sourceId,
    secondaryInputStepId: duplicateId,
    isBuilt: false,
    isFiltered: false,
  };

  const parentStep = strategy.steps.find(
    (s) =>
      s.primaryInputStepId === sourceId || s.secondaryInputStepId === sourceId,
  );

  const nextSteps: Step[] = strategy.steps.map((s) => {
    if (s.id === parentStep?.id) {
      const patched: Step = { ...s };
      if (patched.primaryInputStepId === sourceId) {
        patched.primaryInputStepId = combineId;
      }
      if (patched.secondaryInputStepId === sourceId) {
        patched.secondaryInputStepId = combineId;
      }
      return patched;
    }
    return s;
  });
  nextSteps.push(duplicate);
  nextSteps.push(combine);

  return { ...strategy, steps: nextSteps };
}

/**
 * Duplicate a step. The duplicate inherits all parameters and is wired into
 * the graph via a new INTERSECT combine alongside the source so the graph
 * stays single-rooted. The user can change the operator afterwards.
 */
export function useDuplicateStepMutation(conversationId: string) {
  const push = usePushStrategyMutation();
  const cache = useStrategyCacheUtils();
  return {
    ...push,
    mutate: (vars: DuplicateStepVars) => {
      const current = cache.get(conversationId);
      if (!current) return;
      const next = applyDuplicate(current, vars.stepId);
      if (!next) return;
      push.mutate({ optimistic: next });
    },
    mutateAsync: async (vars: DuplicateStepVars) => {
      const current = cache.get(conversationId);
      if (!current) {
        throw new Error("Cannot duplicate step: no strategy loaded");
      }
      const next = applyDuplicate(current, vars.stepId);
      if (!next) {
        throw new Error(`Cannot duplicate step: unknown step id ${vars.stepId}`);
      }
      return push.mutateAsync({ optimistic: next });
    },
  };
}
