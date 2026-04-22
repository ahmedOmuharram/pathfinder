"use client";

import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import type { Strategy } from "@pathfinder/shared";
import { pushConversation } from "@/lib/api/conversations";
import { toUserMessage } from "@/lib/api/errors";
import { serializeStrategyAst } from "@/lib/strategyGraph/serialize";
import { useStrategyStore } from "@/state/strategy/store";
import {
  applyOptimisticStrategy,
  rollbackStrategy,
  snapshotStrategy,
  type StrategySnapshot,
} from "./optimistic";

export interface PushStrategyVars {
  /** The fully optimistic strategy to apply locally and serialize to the wire. */
  optimistic: Strategy;
}

class SyncPausedError extends Error {
  constructor() {
    super("Sync paused — record-type mismatch");
    this.name = "SyncPausedError";
  }
}

/** Mutation-key prefix used by `useStrategyAutoFlush` to detect in-flight pushes. */
export const PUSH_STRATEGY_MUTATION_KEY = ["strategy", "push"] as const;

/**
 * The single primitive that pushes the current strategy to the server.
 *
 * - `onMutate` snapshots and applies the optimistic strategy to the store.
 *   Throws if the validation gate (`graphValidationStatus[id]`) is set.
 * - `mutationFn` serializes the AST and calls `pushConversation`.
 * - `onSuccess` replaces the store with the server-canonical response.
 * - `onError` rolls back to the snapshot and surfaces a toast.
 */
export function usePushStrategyMutation() {
  return useMutation<Strategy, Error, PushStrategyVars, StrategySnapshot>({
    mutationKey: PUSH_STRATEGY_MUTATION_KEY,
    onMutate: ({ optimistic }) => {
      const validationPaused =
        useStrategyStore.getState().graphValidationStatus[optimistic.id] === true;
      if (validationPaused) {
        toast.warning("Sync paused — record-type mismatch");
        throw new SyncPausedError();
      }
      const snapshot = snapshotStrategy();
      applyOptimisticStrategy(optimistic);
      return snapshot;
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
    onSuccess: (serverResponse) => {
      useStrategyStore.getState().setStrategy(serverResponse);
      useStrategyStore.getState().setLastFailedPush(null);
    },
    onError: (err, vars, snapshot) => {
      if (snapshot) {
        rollbackStrategy(snapshot);
      }
      if (err instanceof SyncPausedError) {
        return;
      }
      useStrategyStore.getState().setLastFailedPush({ optimistic: vars.optimistic });
      toast.error(toUserMessage(err, "Sync failed"));
    },
  });
}
