"use client";

import { useStrategyStore } from "@/state/strategy/store";
import { useApplyOperation } from "./useApplyOperation";

/**
 * Returns a callback that re-fires the most recent failed graph operation,
 * if any. `lastFailedOperation` is set by `useApplyOperation.onError` and
 * cleared on success.
 */
export function useRetryLastPush(conversationId: string): () => void {
  const apply = useApplyOperation(conversationId);
  return () => {
    const failed = useStrategyStore.getState().lastFailedOperation;
    if (failed === null) return;
    apply.mutate({ op: failed.op });
  };
}
