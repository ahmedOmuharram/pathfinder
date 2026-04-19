/**
 * Draft slice — current strategy, step map, step CRUD, display name preservation.
 */

import type { Step } from "@pathfinder/shared";
import type { StateCreator } from "zustand";
import { serializeStrategyAst, isFallbackDisplayName } from "@/lib/strategyGraph";
import type { DevtoolsMutators } from "@/state/middleware";
import type { StrategyState, DraftSlice } from "./types";
import { buildStrategy } from "./helpers";
import { pushHistory } from "./historySlice";
import { initialStepSnapshot, type StepMachineSnapshot } from "./stepMachine";

function seedSnapshotForStep(step: Step): StepMachineSnapshot {
  const wireErrors = step.validation?.errors;
  const wireValid = step.validation?.isValid;
  const estimate: number | null =
    typeof step.estimatedSize === "number" ? step.estimatedSize : null;
  if (wireValid === false && wireErrors) {
    return initialStepSnapshot({
      state: "invalid",
      context: {
        validationErrors: {
          general: wireErrors.general ?? [],
          byKey: wireErrors.byKey ?? {},
        },
        estimatedSize: estimate,
      },
    });
  }
  if (estimate !== null) {
    return initialStepSnapshot({
      state: "complete",
      context: { estimatedSize: estimate },
    });
  }
  return initialStepSnapshot();
}

function syncLifecycleForSteps(
  current: Record<string, StepMachineSnapshot>,
  stepsById: Record<string, Step>,
): Record<string, StepMachineSnapshot> {
  const next: Record<string, StepMachineSnapshot> = {};
  for (const [id, step] of Object.entries(stepsById)) {
    next[id] = current[id] ?? seedSnapshotForStep(step);
  }
  return next;
}

// ---------------------------------------------------------------------------
// Display-name preservation
// ---------------------------------------------------------------------------

/**
 * Decide whether to keep an existing step's displayName when an incoming
 * update arrives (e.g. from the AI).  Rules:
 *  - If the existing name is user-edited (not a fallback), keep it unless
 *    the incoming name is also non-fallback.
 *  - If the incoming name is a generic fallback, keep the existing name.
 */
function preserveDisplayName(existing: Step, incoming: Step, merged: Step): Step {
  const existingName = existing.displayName;
  if (existingName == null || existingName === "") return merged;

  const incomingName = incoming.displayName;
  const keepExisting =
    incomingName == null || incomingName === "" ||
    !isFallbackDisplayName(existingName, existing) ||
    isFallbackDisplayName(incomingName, incoming);

  if (keepExisting) {
    return { ...merged, displayName: existingName };
  }
  return merged;
}

/** Ensure a step always has a displayName. */
function ensureDisplayName(step: Step, existing: Step | undefined): Step {
  if (step.displayName != null && step.displayName !== "") return step;
  const existingName = existing?.displayName;
  const fallbackName = existingName != null && existingName !== ""
    ? existingName
    : step.searchName != null && step.searchName !== ""
      ? step.searchName
      : "Untitled step";
  return { ...step, displayName: fallbackName };
}

// ---------------------------------------------------------------------------
// Slice
// ---------------------------------------------------------------------------

export const createDraftSlice: StateCreator<StrategyState, DevtoolsMutators, [], DraftSlice> = (
  set,
  get,
) => ({
  strategy: null,
  stepsById: {},

  addStep: (step) => {
    set((state) => {
      const existing = state.stepsById[step.id];

      const updates = Object.fromEntries(Object.entries(step)) as Partial<Step>;
      let nextStep: Step = {
        ...(existing ?? step),
        ...updates,
      };

      if (
        existing?.recordType !== null &&
        existing?.recordType !== undefined &&
        (nextStep.recordType === null || nextStep.recordType === undefined)
      ) {
        nextStep = { ...nextStep, recordType: existing.recordType };
      }

      if (existing) {
        nextStep = preserveDisplayName(existing, step, nextStep);
      }

      if (!nextStep.id) {
        nextStep = { ...nextStep, id: step.id };
      }

      nextStep = ensureDisplayName(nextStep, existing);

      const historyState = pushHistory(state, (draft) => {
        draft.stepsById[step.id] = nextStep;
        draft.strategy = buildStrategy(draft.stepsById, draft.strategy);
      });
      const lifecycleNext = state.stepLifecycleById[step.id]
        ? state.stepLifecycleById
        : {
            ...state.stepLifecycleById,
            [step.id]: seedSnapshotForStep(nextStep),
          };
      return { ...historyState, stepLifecycleById: lifecycleNext };
    });
  },

  updateStep: (stepId, updates) => {
    set((state) => {
      const existingStep = state.stepsById[stepId];
      if (!existingStep) return state;

      const nextStep: Step = { ...existingStep, ...updates };

      return pushHistory(state, (draft) => {
        draft.stepsById[stepId] = nextStep;
        draft.strategy = buildStrategy(draft.stepsById, draft.strategy);
      });
    });
  },

  removeStep: (stepId) => {
    set((state) => {
      if (!state.stepsById[stepId]) return state;
      const historyState = pushHistory(state, (draft) => {
        delete draft.stepsById[stepId];
        draft.strategy = buildStrategy(draft.stepsById, draft.strategy);
      });
      const lifecycleNext = { ...state.stepLifecycleById };
      delete lifecycleNext[stepId];
      return { ...historyState, stepLifecycleById: lifecycleNext };
    });
  },

  setStrategy: (strategy) => {
    if (!strategy) {
      set({
        strategy: null,
        stepsById: {},
        stepLifecycleById: {},
        undoStack: [],
        redoStack: [],
      });
      return;
    }
    set((state) => {
      const existingSteps = state.stepsById;
      const incomingSteps = strategy.steps;
      const mergedSteps = incomingSteps.map((step) => {
        const existing = existingSteps[step.id];
        if (!existing) return step;

        let nextStep = step;
        const existingName = existing.displayName;
        const incomingName = step.displayName;
        const hasExisting = existingName != null && existingName !== "";
        const hasIncoming = incomingName != null && incomingName !== "";

        if (
          (nextStep.recordType === null || nextStep.recordType === undefined) &&
          existing.recordType !== null &&
          existing.recordType !== undefined
        ) {
          nextStep = { ...nextStep, recordType: existing.recordType };
        }
        if (!hasIncoming && hasExisting) {
          return { ...nextStep, displayName: existingName };
        }
        if (hasExisting && !isFallbackDisplayName(existingName, existing)) {
          return { ...nextStep, displayName: existingName };
        }
        if (
          hasIncoming
          && isFallbackDisplayName(incomingName, step)
          && hasExisting
        ) {
          return { ...nextStep, displayName: existingName };
        }
        return nextStep;
      });

      const nextStepsById: Record<string, Step> = {};
      for (const step of mergedSteps) {
        nextStepsById[step.id] = step;
      }
      const mergedStrategy = { ...strategy, steps: mergedSteps };

      const historyState = pushHistory(state, (draft) => {
        draft.stepsById = nextStepsById;
        draft.strategy = mergedStrategy;
      });
      const lifecycleNext = syncLifecycleForSteps(
        state.stepLifecycleById,
        nextStepsById,
      );
      return { ...historyState, stepLifecycleById: lifecycleNext };
    });
  },

  setWdkInfo: (wdkStrategyId, wdkUrl, name, description) => {
    set((state) => {
      if (!state.strategy) return state;
      const resolvedDescription =
        description !== undefined ? description : state.strategy.description;
      const resolvedWdkUrl = wdkUrl !== undefined ? wdkUrl : state.strategy.wdkUrl;
      return {
        strategy: {
          ...state.strategy,
          name: name ?? state.strategy.name,
          description: resolvedDescription ?? null,
          wdkStrategyId,
          wdkUrl: resolvedWdkUrl ?? null,
          updatedAt: new Date().toISOString(),
        },
      };
    });
  },

  setStrategyMeta: (updates) => {
    set((state) => {
      if (!state.strategy) return state;
      return {
        strategy: {
          ...state.strategy,
          ...updates,
          updatedAt: new Date().toISOString(),
        },
      };
    });
  },

  buildPlan: () => {
    const state = get();
    return serializeStrategyAst(state.stepsById, state.strategy);
  },

  clear: () => {
    set({
      strategy: null,
      stepsById: {},
      stepLifecycleById: {},
      undoStack: [],
      redoStack: [],
    });
  },
});
