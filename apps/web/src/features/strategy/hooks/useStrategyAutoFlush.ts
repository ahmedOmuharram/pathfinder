"use client";

import { useIsMutating, useQueryClient } from "@tanstack/react-query";
import { APPLY_OPERATION_MUTATION_KEY } from "@/features/strategy/mutations/useApplyOperation";

interface AutoFlushState {
  /** True when at least one push mutation is currently in flight. */
  pending: boolean;
  /**
   * Resolves when all in-flight push mutations have settled. Consumers should
   * `await` this before allowing navigation away from the strategy surface.
   */
  awaitFlush: () => Promise<void>;
}

/**
 * Tracks pending strategy push mutations and exposes an awaiter so the
 * conversation router can flush in-flight saves before navigating.
 *
 * Wire `awaitFlush` into navigation handlers (back, sidebar conversation
 * switch, etc.) to prevent dropped optimistic edits.
 */
export function useStrategyAutoFlush(): AutoFlushState {
  const queryClient = useQueryClient();
  const inFlight = useIsMutating({ mutationKey: APPLY_OPERATION_MUTATION_KEY });

  const awaitFlush = async () => {
    const cache = queryClient.getMutationCache();
    const pushKeyJson = JSON.stringify(APPLY_OPERATION_MUTATION_KEY);
    const pendingFor = () =>
      cache
        .getAll()
        .filter(
          (m) =>
            m.state.status === "pending" &&
            JSON.stringify(m.options.mutationKey ?? []) === pushKeyJson,
        );
    let pending = pendingFor();
    while (pending.length > 0) {
      await Promise.all(
        pending.map(
          (m) =>
            new Promise<void>((resolve) => {
              const unsubscribe = cache.subscribe((event) => {
                if (event.mutation === m && m.state.status !== "pending") {
                  unsubscribe();
                  resolve();
                }
              });
            }),
        ),
      );
      pending = pendingFor();
    }
  };

  return { pending: inFlight > 0, awaitFlush };
}
