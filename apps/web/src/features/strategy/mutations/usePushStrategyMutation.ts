"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { Strategy } from "@pathfinder/shared";
import { conversationDetailKey, pushConversation } from "@/lib/api/conversations";
import { toUserMessage } from "@/lib/api/errors";
import { serializeStrategyAst } from "@/lib/strategyGraph/serialize";
import { useStrategyStore } from "@/state/strategy/store";

export interface PushStrategyVars {
  optimistic: Strategy;
}

interface PushContext {
  snapshot: Strategy | null;
  key: ReturnType<typeof conversationDetailKey>;
}

class SyncPausedError extends Error {
  constructor() {
    super("Sync paused — record-type mismatch");
    this.name = "SyncPausedError";
  }
}

export const PUSH_STRATEGY_MUTATION_KEY = ["strategy", "push"] as const;
export const PUSH_STRATEGY_SCOPE_ID = "strategy-push";

export function usePushStrategyMutation() {
  const queryClient = useQueryClient();

  return useMutation<Strategy, Error, PushStrategyVars, PushContext>({
    mutationKey: PUSH_STRATEGY_MUTATION_KEY,
    scope: { id: PUSH_STRATEGY_SCOPE_ID },
    onMutate: ({ optimistic }) => {
      const validationPaused =
        useStrategyStore.getState().graphValidationStatus[optimistic.id] === true;
      if (validationPaused) {
        toast.warning("Sync paused — record-type mismatch");
        throw new SyncPausedError();
      }
      const key = conversationDetailKey(optimistic.id);
      const snapshot = queryClient.getQueryData<Strategy>(key) ?? null;
      queryClient.setQueryData<Strategy>(key, optimistic);
      return { snapshot, key };
    },
    mutationFn: async ({ optimistic }) => {
      const planResult = serializeStrategyAst(
        Object.fromEntries(optimistic.steps.map((s) => [s.id, s])),
        optimistic,
      );
      if (!planResult) {
        throw new Error(
          "Cannot push strategy: graph has multiple roots or invalid combine.",
        );
      }
      return pushConversation(optimistic.id, {
        name: planResult.name,
        siteId: optimistic.siteId,
        strategyAst: planResult.plan,
        description: optimistic.description ?? null,
      });
    },
    onSuccess: (serverResponse, _vars, context) => {
      queryClient.setQueryData<Strategy>(context.key, serverResponse);
      useStrategyStore.getState().setLastFailedPush(null);
    },
    onError: (err, vars, context) => {
      if (context !== undefined) {
        queryClient.setQueryData<Strategy | null>(context.key, context.snapshot);
      }
      if (err instanceof SyncPausedError) {
        return;
      }
      useStrategyStore.getState().setLastFailedPush({ optimistic: vars.optimistic });
      toast.error(toUserMessage(err, "Sync failed"));
    },
  });
}
