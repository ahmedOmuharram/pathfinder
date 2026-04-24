"use client";

import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyCacheUtils } from "@/state/strategy/useStrategyQuery";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

export interface DeleteStepVars {
  stepId: string;
}

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

export function useDeleteStepMutation(conversationId: string) {
  const push = usePushStrategyMutation();
  const cache = useStrategyCacheUtils();
  return {
    ...push,
    mutate: (vars: DeleteStepVars) => {
      const current = cache.get(conversationId);
      if (!current) return;
      push.mutate({ optimistic: applyDelete(current, vars.stepId) });
    },
    mutateAsync: async (vars: DeleteStepVars) => {
      const current = cache.get(conversationId);
      if (!current) {
        throw new Error("Cannot delete step: no strategy loaded");
      }
      return push.mutateAsync({
        optimistic: applyDelete(current, vars.stepId),
      });
    },
  };
}
