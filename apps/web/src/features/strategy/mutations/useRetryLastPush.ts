"use client";

import { useStrategyStore } from "@/state/strategy/store";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

/**
 * Returns a callback that re-fires the most recent failed push, if any.
 * `lastFailedPush` is set in the store by `usePushStrategyMutation.onError`
 * and cleared by its `onSuccess`. The retry uses the same optimistic strategy
 * payload that originally failed.
 */
export function useRetryLastPush(): () => void {
  const push = usePushStrategyMutation();
  return () => {
    const failed = useStrategyStore.getState().lastFailedPush;
    if (failed === null) return;
    push.mutate({ optimistic: failed.optimistic });
  };
}
