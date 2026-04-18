import { enablePatches, produceWithPatches, applyPatches } from "immer";
import type { Draft, Patch } from "immer";
import type { Step, Strategy } from "@pathfinder/shared";
import type { StateCreator } from "zustand";
import type { DevtoolsMutators } from "@/state/middleware";
import type { StrategyState, HistorySlice } from "./types";

enablePatches();

const MAX_HISTORY = 50;

export interface HistorySnapshot {
  strategy: Strategy | null;
  stepsById: Record<string, Step>;
}

export type HistoryRecipe = (draft: Draft<HistorySnapshot>) => void;

function trimStack(stack: Patch[][]): Patch[][] {
  while (stack.length > MAX_HISTORY) {
    stack.shift();
  }
  return stack;
}

/**
 * Apply a recipe that mutates the strategy/stepsById snapshot, and record an
 * undo-patch entry when the previous state had a non-null strategy.
 *
 * Returns the partial state update to merge into the Zustand store.
 */
export function pushHistory(
  state: HistorySnapshot & { undoStack: Patch[][]; redoStack: Patch[][] },
  recipe: HistoryRecipe,
): HistorySnapshot & { undoStack: Patch[][]; redoStack: Patch[][] } {
  const prev: HistorySnapshot = { strategy: state.strategy, stepsById: state.stepsById };
  const [next, , inverse] = produceWithPatches(prev, recipe);

  const hadPriorStrategy = state.strategy !== null;
  const nextUndoStack = hadPriorStrategy && inverse.length > 0
    ? trimStack([...state.undoStack, inverse])
    : state.undoStack;

  return {
    strategy: next.strategy,
    stepsById: next.stepsById,
    undoStack: nextUndoStack,
    redoStack: [],
  };
}

export const createHistorySlice: StateCreator<StrategyState, DevtoolsMutators, [], HistorySlice> = (
  set,
  get,
) => ({
  undoStack: [],
  redoStack: [],

  undo: () => {
    const { undoStack, redoStack, strategy, stepsById } = get();
    const lastInverse = undoStack[undoStack.length - 1];
    if (!lastInverse) return;

    const current: HistorySnapshot = { strategy, stepsById };
    const [restored, , forward] = produceWithPatches(current, (draft) => {
      applyPatches(draft, lastInverse);
    });

    set({
      strategy: restored.strategy,
      stepsById: restored.stepsById,
      undoStack: undoStack.slice(0, -1),
      redoStack: [...redoStack, forward],
    });
  },

  redo: () => {
    const { undoStack, redoStack, strategy, stepsById } = get();
    const lastForward = redoStack[redoStack.length - 1];
    if (!lastForward) return;

    const current: HistorySnapshot = { strategy, stepsById };
    const [restored, , inverse] = produceWithPatches(current, (draft) => {
      applyPatches(draft, lastForward);
    });

    set({
      strategy: restored.strategy,
      stepsById: restored.stepsById,
      undoStack: [...undoStack, inverse],
      redoStack: redoStack.slice(0, -1),
    });
  },

  canUndo: () => get().undoStack.length > 0,
  canRedo: () => get().redoStack.length > 0,
});
