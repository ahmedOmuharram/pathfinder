/**
 * Strategy list store for strategies and execution history
 */

import { create } from "zustand";
import type { StrategySummary } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/types/strategy";

interface StrategyListState {
  strategies: StrategySummary[];
  executedStrategies: StrategyWithMeta[];
  graphValidationStatus: Record<string, boolean>;

  setStrategies: (items: StrategySummary[]) => void;
  addStrategy: (item: StrategySummary) => void;
  removeStrategy: (id: string) => void;

  addExecutedStrategy: (strategy: StrategyWithMeta) => void;
  removeExecutedStrategy: (id: string) => void;
  setGraphValidationStatus: (id: string, hasErrors: boolean) => void;
}

function normalizeStrategyId(strategy: StrategyWithMeta): string {
  if (strategy.id) {
    return String(strategy.id);
  }
  return `executed-${Date.now()}`;
}

export const useStrategyListStore = create<StrategyListState>()((set, get) => ({
  strategies: [],
  executedStrategies: [],
  graphValidationStatus: {},

  setStrategies: (items) => set({ strategies: items }),

  addStrategy: (item) =>
    set((state) => {
      const existing = state.strategies.find((c) => c.id === item.id);
      if (existing) {
        return {
          strategies: state.strategies.map((c) =>
            c.id === item.id ? { ...c, ...item } : c
          ),
        };
      }
      return { strategies: [item, ...state.strategies] };
    }),

  removeStrategy: (id) =>
    set((state) => ({
      strategies: state.strategies.filter((c) => c.id !== id),
    })),

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

  removeExecutedStrategy: (id) =>
    set((state) => {
      const remaining = state.executedStrategies.filter((s) => s.id !== id);
      return { executedStrategies: remaining };
    }),
  setGraphValidationStatus: (id, hasErrors) =>
    set((state) => ({
      graphValidationStatus: {
        ...state.graphValidationStatus,
        [id]: hasErrors,
      },
    })),
}));
