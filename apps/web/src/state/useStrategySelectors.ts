/**
 * Typed convenience selectors for the strategy store.
 *
 * These hooks provide focused slices of the strategy store so consumers
 * do not need to reach into the raw store shape.
 */

import { useStrategyStore } from "@/state/strategy/store";

// ---------------------------------------------------------------------------
// Read selectors
// ---------------------------------------------------------------------------

/** Returns the current strategy and its step map. */
export function useCurrentStrategy() {
  const strategy = useStrategyStore((s) => s.strategy);
  const stepsById = useStrategyStore((s) => s.stepsById);
  return { strategy, stepsById };
}

/** Returns the strategy list and executed strategies (sidebar data). */
export function useStrategyList() {
  const strategies = useStrategyStore((s) => s.strategies);
  const executedStrategies = useStrategyStore((s) => s.executedStrategies);
  const graphValidationStatus = useStrategyStore((s) => s.graphValidationStatus);
  return { strategies, executedStrategies, graphValidationStatus };
}

/** Returns undo/redo state. */
export function useStrategyHistory() {
  const undo = useStrategyStore((s) => s.undo);
  const redo = useStrategyStore((s) => s.redo);
  const canUndo = useStrategyStore((s) => s.canUndo);
  const canRedo = useStrategyStore((s) => s.canRedo);
  return { undo, redo, canUndo, canRedo };
}

// ---------------------------------------------------------------------------
// Action selectors
// ---------------------------------------------------------------------------

/** Returns mutation actions for the current strategy draft. */
export function useStrategyActions() {
  const addStep = useStrategyStore((s) => s.addStep);
  const updateStep = useStrategyStore((s) => s.updateStep);
  const removeStep = useStrategyStore((s) => s.removeStep);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const setWdkInfo = useStrategyStore((s) => s.setWdkInfo);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const buildPlan = useStrategyStore((s) => s.buildPlan);
  const setStepValidationErrors = useStrategyStore((s) => s.setStepValidationErrors);
  const setStepCounts = useStrategyStore((s) => s.setStepCounts);
  const clear = useStrategyStore((s) => s.clear);
  return {
    addStep,
    updateStep,
    removeStep,
    setStrategy,
    setWdkInfo,
    setStrategyMeta,
    buildPlan,
    setStepValidationErrors,
    setStepCounts,
    clear,
  };
}

/** Returns list mutation actions (add/remove strategies from sidebar). */
export function useStrategyListActions() {
  const setStrategies = useStrategyStore((s) => s.setStrategies);
  const addStrategyToList = useStrategyStore((s) => s.addStrategyToList);
  const removeStrategyFromList = useStrategyStore((s) => s.removeStrategyFromList);
  const addExecutedStrategy = useStrategyStore((s) => s.addExecutedStrategy);
  const setGraphValidationStatus = useStrategyStore((s) => s.setGraphValidationStatus);
  return {
    setStrategies,
    addStrategyToList,
    removeStrategyFromList,
    addExecutedStrategy,
    setGraphValidationStatus,
  };
}
