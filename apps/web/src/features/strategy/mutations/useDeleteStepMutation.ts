"use client";

import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

export interface DeleteStepVars {
  stepId: string;
}

/** Compute the closure of step ids whose removal cascades from a single deletion. */
function computeCascade(steps: Step[], rootId: string): Set<string> {
  const removed = new Set<string>([rootId]);
  let added = true;
  while (added) {
    added = false;
    for (const s of steps) {
      if (removed.has(s.id)) continue;
      const primary = s.primaryInputStepId;
      const secondary = s.secondaryInputStepId;
      if (
        (primary != null && removed.has(primary)) ||
        (secondary != null && removed.has(secondary))
      ) {
        removed.add(s.id);
        added = true;
      }
    }
  }
  return removed;
}

function applyDelete(strategy: Strategy, stepId: string): Strategy {
  const removed = computeCascade(strategy.steps, stepId);
  return {
    ...strategy,
    steps: strategy.steps.filter((s) => !removed.has(s.id)),
  };
}

/**
 * Delete a step. Cascades to any step that depends on it (transitively) so
 * the resulting graph remains consistent.
 */
export function useDeleteStepMutation() {
  const push = usePushStrategyMutation();
  return {
    ...push,
    mutate: (vars: DeleteStepVars) => {
      const current = useStrategyStore.getState().strategy;
      if (!current) return;
      push.mutate({ optimistic: applyDelete(current, vars.stepId) });
    },
    mutateAsync: async (vars: DeleteStepVars) => {
      const current = useStrategyStore.getState().strategy;
      if (!current) {
        throw new Error("Cannot delete step: no strategy loaded");
      }
      return push.mutateAsync({
        optimistic: applyDelete(current, vars.stepId),
      });
    },
  };
}
