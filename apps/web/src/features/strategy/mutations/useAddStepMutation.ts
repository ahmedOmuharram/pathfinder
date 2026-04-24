"use client";

import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyCacheUtils } from "@/state/strategy/useStrategyQuery";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

export interface AddStepVars {
  step: Step;
}

function applyAdd(strategy: Strategy, step: Step): Strategy {
  return { ...strategy, steps: [...strategy.steps, step] };
}

export function useAddStepMutation(conversationId: string) {
  const push = usePushStrategyMutation();
  const cache = useStrategyCacheUtils();
  return {
    ...push,
    mutate: (vars: AddStepVars) => {
      const current = cache.get(conversationId);
      if (!current) return;
      push.mutate({ optimistic: applyAdd(current, vars.step) });
    },
    mutateAsync: async (vars: AddStepVars) => {
      const current = cache.get(conversationId);
      if (!current) {
        throw new Error("Cannot add step: no strategy loaded");
      }
      return push.mutateAsync({ optimistic: applyAdd(current, vars.step) });
    },
  };
}
