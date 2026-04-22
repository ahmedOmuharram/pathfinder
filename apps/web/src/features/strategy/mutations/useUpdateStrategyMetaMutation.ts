"use client";

import type { Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

export interface UpdateStrategyMetaVars {
  name?: string;
  description?: string | null;
}

function applyMeta(
  strategy: Strategy,
  vars: UpdateStrategyMetaVars,
): Strategy {
  const next: Strategy = { ...strategy };
  if (vars.name !== undefined) next.name = vars.name;
  if (vars.description !== undefined) next.description = vars.description;
  return next;
}

/**
 * Patch the strategy's display metadata (name / description). The same push
 * primitive carries the changes to the server.
 */
export function useUpdateStrategyMetaMutation() {
  const push = usePushStrategyMutation();
  return {
    ...push,
    mutate: (vars: UpdateStrategyMetaVars) => {
      const current = useStrategyStore.getState().strategy;
      if (!current) return;
      push.mutate({ optimistic: applyMeta(current, vars) });
    },
    mutateAsync: async (vars: UpdateStrategyMetaVars) => {
      const current = useStrategyStore.getState().strategy;
      if (!current) {
        throw new Error("Cannot update strategy meta: no strategy loaded");
      }
      return push.mutateAsync({ optimistic: applyMeta(current, vars) });
    },
  };
}
