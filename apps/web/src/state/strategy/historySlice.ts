import { enablePatches, produceWithPatches, applyPatches } from "immer";
import type { Patch } from "immer";
import type { StateCreator } from "zustand";
import type { DevtoolsMutators } from "@/state/middleware";
import type { HistorySlice, HistorySnapshot, StrategyState } from "./types";

enablePatches();

const MAX_HISTORY = 50;

function trimStack(stack: Patch[][]): Patch[][] {
  while (stack.length > MAX_HISTORY) {
    stack.shift();
  }
  return stack;
}

/**
 * Compute the inverse patches that would restore `prev` from `next`. Returns
 * an empty array when nothing changed.
 */
function inversePatchesBetween(
  prev: HistorySnapshot,
  next: HistorySnapshot,
): Patch[] {
  const [, , inverse] = produceWithPatches(prev, (draft) => {
    draft.strategy = next.strategy;
  });
  return inverse;
}

export const createHistorySlice: StateCreator<
  StrategyState,
  DevtoolsMutators,
  [],
  HistorySlice
> = (set, get) => ({
  undoStack: [],
  redoStack: [],

  pushSnapshot: (prev) => {
    const current: HistorySnapshot = { strategy: get().strategy };
    if (prev.strategy === null) return;
    const inverse = inversePatchesBetween(prev, current);
    if (inverse.length === 0) return;
    set((state) => ({
      undoStack: trimStack([...state.undoStack, inverse]),
      redoStack: [],
    }));
  },

  undo: () => {
    const { undoStack, redoStack, strategy } = get();
    const lastInverse = undoStack[undoStack.length - 1];
    if (!lastInverse) return;

    const current: HistorySnapshot = { strategy };
    const [restored, , forward] = produceWithPatches(current, (draft) => {
      applyPatches(draft, lastInverse);
    });

    set({
      strategy: restored.strategy,
      undoStack: undoStack.slice(0, -1),
      redoStack: [...redoStack, forward],
    });
  },

  redo: () => {
    const { undoStack, redoStack, strategy } = get();
    const lastForward = redoStack[redoStack.length - 1];
    if (!lastForward) return;

    const current: HistorySnapshot = { strategy };
    const [restored, , inverse] = produceWithPatches(current, (draft) => {
      applyPatches(draft, lastForward);
    });

    set({
      strategy: restored.strategy,
      undoStack: [...undoStack, inverse],
      redoStack: redoStack.slice(0, -1),
    });
  },

  canUndo: () => get().undoStack.length > 0,
  canRedo: () => get().redoStack.length > 0,
});
