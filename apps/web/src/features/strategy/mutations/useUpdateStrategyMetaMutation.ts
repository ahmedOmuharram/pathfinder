"use client";

import type { Strategy } from "@pathfinder/shared";
import { useStrategyCacheUtils } from "@/state/strategy/useStrategyQuery";
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

export function useUpdateStrategyMetaMutation(conversationId: string) {
  const push = usePushStrategyMutation();
  const cache = useStrategyCacheUtils();
  return {
    ...push,
    mutate: (vars: UpdateStrategyMetaVars) => {
      const current = cache.get(conversationId);
      if (!current) return;
      push.mutate({ optimistic: applyMeta(current, vars) });
    },
    mutateAsync: async (vars: UpdateStrategyMetaVars) => {
      const current = cache.get(conversationId);
      if (!current) {
        throw new Error("Cannot update strategy meta: no strategy loaded");
      }
      return push.mutateAsync({ optimistic: applyMeta(current, vars) });
    },
  };
}
