import type { StateCreator } from "zustand";
import type { DevtoolsMutators } from "@/state/middleware";
import type { LifecycleSlice, StrategyState } from "./types";
import {
  initialStepSnapshot,
  transitionStep,
  type StepMachineEvent,
  type StepMachineSnapshot,
} from "./stepMachine";

function ensureSnapshot(
  map: Record<string, StepMachineSnapshot>,
  stepId: string,
): StepMachineSnapshot {
  const existing = map[stepId];
  if (existing) return existing;
  return initialStepSnapshot();
}

export const createLifecycleSlice: StateCreator<
  StrategyState,
  DevtoolsMutators,
  [],
  LifecycleSlice
> = (set, get) => ({
  stepLifecycleById: {},

  initStepLifecycle: (stepId, seed) => {
    set((state) => {
      if (state.stepLifecycleById[stepId]) return state;
      return {
        stepLifecycleById: {
          ...state.stepLifecycleById,
          [stepId]: initialStepSnapshot(seed),
        },
      };
    });
  },

  dispatchStepEvent: (stepId, event) => {
    set((state) => {
      const current = ensureSnapshot(state.stepLifecycleById, stepId);
      const next = transitionStep(current, event);
      if (next === current) return state;
      return {
        stepLifecycleById: { ...state.stepLifecycleById, [stepId]: next },
      };
    });
  },

  removeStepLifecycle: (stepId) => {
    set((state) => {
      if (!state.stepLifecycleById[stepId]) return state;
      const next = { ...state.stepLifecycleById };
      delete next[stepId];
      return { stepLifecycleById: next };
    });
  },

  getStepLifecycle: (stepId) => {
    return get().stepLifecycleById[stepId] ?? null;
  },

  applyStepValidationErrors: (errors) => {
    set((state) => {
      let changed = false;
      const next = { ...state.stepLifecycleById };
      for (const [stepId, message] of Object.entries(errors)) {
        const snapshot = next[stepId] ?? initialStepSnapshot();
        const event: StepMachineEvent =
          message != null
            ? {
                type: "VALIDATION_ERROR",
                errors: { general: [message], byKey: {} },
              }
            : { type: "VALIDATION_SUCCESS" };
        const validating = transitionStep(snapshot, { type: "VALIDATE" });
        const resolved = transitionStep(validating, event);
        if (resolved !== snapshot) {
          next[stepId] = resolved;
          changed = true;
        }
      }
      if (!changed) return state;
      return { stepLifecycleById: next };
    });
  },

  applyStepCounts: (counts) => {
    set((state) => {
      let changed = false;
      const next = { ...state.stepLifecycleById };
      for (const [stepId, count] of Object.entries(counts)) {
        const resolvedCount: number | null =
          typeof count === "number" ? count : null;
        const snapshot = next[stepId] ?? initialStepSnapshot({ state: "valid" });
        const running = transitionStep(snapshot, { type: "RUN_COUNTS" });
        const done = transitionStep(running, {
          type: "COUNTS_READY",
          count: resolvedCount,
        });
        if (done !== snapshot) {
          next[stepId] = done;
          changed = true;
        }
      }
      if (!changed) return state;
      return { stepLifecycleById: next };
    });
  },
});
