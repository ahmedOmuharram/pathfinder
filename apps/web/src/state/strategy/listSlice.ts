/**
 * List slice — executed strategies tracking.
 *
 * The sidebar strategy list cache lives in TanStack Query and is managed
 * by `addStrategyToCache` in `lib/query/mutations/`. This slice only
 * tracks strategies that have been executed against WDK.
 */

import type { StateCreator } from "zustand";
import type { StrategyState, ListSlice } from "./types";
import { normalizeStrategyId } from "./helpers";

export const createListSlice: StateCreator<StrategyState, [], [], ListSlice> = (
  set,
) => ({
  executedStrategies: [],

  addExecutedStrategy: (strategy) =>
    set((state) => {
      const id = normalizeStrategyId(strategy);
      const existingIndex = state.executedStrategies.findIndex((s) => s.id === id);
      const nextStrategy = {
        ...strategy,
        id,
        updatedAt: new Date().toISOString(),
      };
      if (existingIndex >= 0) {
        const updated = [...state.executedStrategies];
        updated[existingIndex] = nextStrategy;
        return { executedStrategies: updated };
      }
      return {
        executedStrategies: [nextStrategy, ...state.executedStrategies],
      };
    }),
});
