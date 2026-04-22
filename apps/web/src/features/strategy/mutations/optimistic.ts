import type { Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";

export interface StrategySnapshot {
  strategy: Strategy | null;
}

/** Snapshot the current store strategy for later rollback. */
export function snapshotStrategy(): StrategySnapshot {
  return { strategy: useStrategyStore.getState().strategy };
}

/** Replace the store's strategy with a new value (synchronous optimistic write). */
export function applyOptimisticStrategy(next: Strategy): void {
  useStrategyStore.getState().setStrategy(next);
}

/** Restore a previously snapshotted strategy (rollback). */
export function rollbackStrategy(snapshot: StrategySnapshot): void {
  useStrategyStore.getState().setStrategy(snapshot.strategy);
}
