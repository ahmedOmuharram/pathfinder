/**
 * Typed convenience selectors for the strategy store.
 *
 * Each hook uses useShallow to create a single subscription that only
 * re-renders when the selected fields actually change.
 */

import { useShallow } from "zustand/react/shallow";
import { useStrategyStore } from "@/state/strategy/store";

/** Returns the current strategy. */
export function useCurrentStrategy() {
  return useStrategyStore((s) => s.strategy);
}

/** Returns undo/redo state. */
export function useStrategyHistory() {
  return useStrategyStore(
    useShallow((s) => ({
      undo: s.undo,
      redo: s.redo,
      canUndo: s.canUndo,
      canRedo: s.canRedo,
      pushSnapshot: s.pushSnapshot,
    })),
  );
}

/** Returns mutation actions for the current strategy draft. */
export function useStrategyActions() {
  return useStrategyStore(
    useShallow((s) => ({
      addStep: s.addStep,
      updateStep: s.updateStep,
      removeStep: s.removeStep,
      setStrategy: s.setStrategy,
      setWdkInfo: s.setWdkInfo,
      setStrategyMeta: s.setStrategyMeta,
      applyStepValidationErrors: s.applyStepValidationErrors,
      applyStepCounts: s.applyStepCounts,
      clear: s.clear,
    })),
  );
}

/** Returns list mutation actions (graph validation). */
export function useStrategyListActions() {
  return useStrategyStore(
    useShallow((s) => ({
      setGraphValidationStatus: s.setGraphValidationStatus,
    })),
  );
}
