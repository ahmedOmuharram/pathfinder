"use client";

import { useQueryClient, useIsMutating } from "@tanstack/react-query";
import type { Step, Strategy } from "@pathfinder/shared";
import { conversationDetailKey } from "@/lib/api/conversations";
import {
  PUSH_STRATEGY_MUTATION_KEY,
  usePushStrategyMutation,
} from "@/features/strategy/mutations/usePushStrategyMutation";

function applyPatch(strategy: Strategy, stepId: string, patch: Partial<Step>): Strategy {
  return {
    ...strategy,
    steps: strategy.steps.map((s) => (s.id === stepId ? { ...s, ...patch } : s)),
  };
}

export interface StrategyDraft {
  applyStepPatch: (stepId: string, patch: Partial<Step>) => void;
  flush: () => void;
  isFlushing: boolean;
}

export function useStrategyDraft(conversationId: string): StrategyDraft {
  const queryClient = useQueryClient();
  const push = usePushStrategyMutation();
  const inFlight = useIsMutating({ mutationKey: PUSH_STRATEGY_MUTATION_KEY });
  const key = conversationDetailKey(conversationId);

  return {
    applyStepPatch: (stepId, patch) => {
      const current = queryClient.getQueryData<Strategy>(key) ?? null;
      if (current === null) return;
      queryClient.setQueryData<Strategy>(key, applyPatch(current, stepId, patch));
    },
    flush: () => {
      const current = queryClient.getQueryData<Strategy>(key) ?? null;
      if (current === null) return;
      push.mutate({ optimistic: current });
    },
    isFlushing: inFlight > 0,
  };
}
