"use client";

import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyCacheUtils } from "@/state/strategy/useStrategyQuery";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

export interface UpdateStepVars {
  stepId: string;
  patch: Partial<Step>;
}

function applyPatch(strategy: Strategy, stepId: string, patch: Partial<Step>): Strategy {
  return {
    ...strategy,
    steps: strategy.steps.map((s) => (s.id === stepId ? { ...s, ...patch } : s)),
  };
}

export function useUpdateStepMutation(conversationId: string) {
  const push = usePushStrategyMutation();
  const cache = useStrategyCacheUtils();
  return {
    ...push,
    mutate: (vars: UpdateStepVars) => {
      const current = cache.get(conversationId);
      if (!current) return;
      push.mutate({ optimistic: applyPatch(current, vars.stepId, vars.patch) });
    },
    mutateAsync: async (vars: UpdateStepVars) => {
      const current = cache.get(conversationId);
      if (!current) {
        throw new Error("Cannot update step: no strategy loaded");
      }
      return push.mutateAsync({
        optimistic: applyPatch(current, vars.stepId, vars.patch),
      });
    },
  };
}
