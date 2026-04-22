"use client";

import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

export interface AddStepVars {
  step: Step;
}

function applyAdd(strategy: Strategy, step: Step): Strategy {
  return { ...strategy, steps: [...strategy.steps, step] };
}

/**
 * Append a new step to the strategy. The caller supplies a fully-formed step
 * (client-generated id; combine inputs already wired). The server-canonical
 * response (with `wdkStepId` populated) replaces the optimistic copy on
 * success.
 */
export function useAddStepMutation() {
  const push = usePushStrategyMutation();
  return {
    ...push,
    mutate: (vars: AddStepVars) => {
      const current = useStrategyStore.getState().strategy;
      if (!current) return;
      push.mutate({ optimistic: applyAdd(current, vars.step) });
    },
    mutateAsync: async (vars: AddStepVars) => {
      const current = useStrategyStore.getState().strategy;
      if (!current) {
        throw new Error("Cannot add step: no strategy loaded");
      }
      return push.mutateAsync({ optimistic: applyAdd(current, vars.step) });
    },
  };
}
