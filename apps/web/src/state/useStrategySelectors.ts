/**
 * Typed convenience selectors for the strategy store.
 *
 * Each hook uses useShallow to create a single subscription that only
 * re-renders when the selected fields actually change.
 */

import { useShallow } from "zustand/react/shallow";
import { useStrategyStore } from "@/state/strategy/store";

/** Returns the current strategy and its step map. */
export function useCurrentStrategy() {
  return useStrategyStore(
    useShallow((s) => ({
      strategy: s.strategy,
      stepsById: s.stepsById,
    })),
  );
}

/** Returns the executed strategies and graph validation status. */
export function useStrategyList() {
  return useStrategyStore(
    useShallow((s) => ({
      executedStrategies: s.executedStrategies,
      graphValidationStatus: s.graphValidationStatus,
    })),
  );
}

/** Returns undo/redo state. */
export function useStrategyHistory() {
  return useStrategyStore(
    useShallow((s) => ({
      undo: s.undo,
      redo: s.redo,
      canUndo: s.canUndo,
      canRedo: s.canRedo,
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
      buildPlan: s.buildPlan,
      setStepValidationErrors: s.setStepValidationErrors,
      setStepCounts: s.setStepCounts,
      clear: s.clear,
    })),
  );
}

/** Returns list mutation actions (track executed, graph validation). */
export function useStrategyListActions() {
  return useStrategyStore(
    useShallow((s) => ({
      addExecutedStrategy: s.addExecutedStrategy,
      setGraphValidationStatus: s.setGraphValidationStatus,
    })),
  );
}
