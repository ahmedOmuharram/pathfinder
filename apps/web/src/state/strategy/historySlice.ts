/**
 * History slice — undo/redo with bounded history buffer.
 */

import type { Strategy } from "@pathfinder/shared";
import type { StateCreator } from "zustand";
import type { StrategyState, HistorySlice } from "./types";
import { buildStepsById } from "./helpers";

const MAX_HISTORY = 50;

/**
 * Push a strategy snapshot onto the history stack, truncating future entries
 * and capping at MAX_HISTORY.
 */
export function pushHistory(
  history: Strategy[],
  historyIndex: number,
  strategy: Strategy | null,
): { history: Strategy[]; historyIndex: number } {
  if (!strategy) {
    return { history, historyIndex };
  }
  const nextHistory = history.slice(0, historyIndex + 1);
  nextHistory.push(strategy);
  if (nextHistory.length > MAX_HISTORY) {
    nextHistory.shift();
  }
  return { history: nextHistory, historyIndex: nextHistory.length - 1 };
}

export const createHistorySlice: StateCreator<StrategyState, [], [], HistorySlice> = (
  set,
  get,
) => ({
  history: [],
  historyIndex: -1,

  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      const strategy = history[newIndex];
      if (strategy === undefined) return;
      set({
        strategy,
        stepsById: buildStepsById(strategy.steps),
        historyIndex: newIndex,
      });
    }
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      const strategy = history[newIndex];
      if (strategy === undefined) return;
      set({
        strategy,
        stepsById: buildStepsById(strategy.steps),
        historyIndex: newIndex,
      });
    }
  },

  canUndo: () => get().historyIndex > 0,
  canRedo: () => get().historyIndex < get().history.length - 1,
});
