"use client";

import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
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

/**
 * Patch a single step's fields. Optimistically updates the store and pushes
 * the resulting strategy to the server.
 */
export function useUpdateStepMutation() {
  const push = usePushStrategyMutation();
  return {
    ...push,
    mutate: (vars: UpdateStepVars) => {
      const current = useStrategyStore.getState().strategy;
      if (!current) return;
      push.mutate({ optimistic: applyPatch(current, vars.stepId, vars.patch) });
    },
    mutateAsync: async (vars: UpdateStepVars) => {
      const current = useStrategyStore.getState().strategy;
      if (!current) {
        throw new Error("Cannot update step: no strategy loaded");
      }
      return push.mutateAsync({
        optimistic: applyPatch(current, vars.stepId, vars.patch),
      });
    },
  };
}
