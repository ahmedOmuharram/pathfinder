/**
 * Draft slice — current strategy, step map, step CRUD, display name preservation.
 */

import type { Step } from "@pathfinder/shared";
import type { StateCreator } from "zustand";
import { serializeStrategyPlan, isFallbackDisplayName } from "@/lib/strategyGraph";
import type { StrategyState, DraftSlice } from "./types";
import { buildStrategy } from "./helpers";
import { pushHistory } from "./historySlice";
import { applyStepValidationErrors, applyStepCounts } from "./stepAnnotations";

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
  if (!existingName) return merged;

  const incomingName = incoming.displayName;
  const keepExisting =
    !incomingName ||
    !isFallbackDisplayName(existingName, existing) ||
    isFallbackDisplayName(incomingName, incoming);

  if (keepExisting) {
    return { ...merged, displayName: existingName };
  }
  return merged;
}

/** Ensure a step always has a displayName. */
function ensureDisplayName(step: Step, existing: Step | undefined): Step {
  if (step.displayName) return step;
  return {
    ...step,
    displayName: existing?.displayName ?? step.searchName ?? "Untitled step",
  };
}

// ---------------------------------------------------------------------------
// Slice
// ---------------------------------------------------------------------------

export const createDraftSlice: StateCreator<StrategyState, [], [], DraftSlice> = (
  set,
  get,
) => ({
  strategy: null,
  stepsById: {},

  addStep: (step) => {
    set((state) => {
      const existing = state.stepsById[step.id];

      // AI-driven updates often send partial step payloads.
      // Treat as upsert+patch: only overwrite defined fields.
      // Object.entries omits absent properties, so the spread below
      // naturally acts as a patch — only present keys overwrite.
      const updates = Object.fromEntries(Object.entries(step)) as Partial<Step>;
      let nextStep: Step = {
        ...(existing ?? step),
        ...updates,
      };

      // Preserve recordType if incoming omits it.
      if (
        existing?.recordType !== null &&
        existing?.recordType !== undefined &&
        (nextStep.recordType === null || nextStep.recordType === undefined)
      ) {
        nextStep = { ...nextStep, recordType: existing.recordType };
      }

      // Preserve user-edited displayName.
      if (existing) {
        nextStep = preserveDisplayName(existing, step, nextStep);
      }

      if (!nextStep.id) {
        nextStep = { ...nextStep, id: step.id };
      }

      nextStep = ensureDisplayName(nextStep, existing);

      const newStepsById = { ...state.stepsById, [step.id]: nextStep };
      const strategy = buildStrategy(newStepsById, state.strategy);
      const historyState = pushHistory(state.history, state.historyIndex, strategy);
      return { stepsById: newStepsById, strategy, ...historyState };
    });
  },

  updateStep: (stepId, updates) => {
    set((state) => {
      const existingStep = state.stepsById[stepId];
      if (!existingStep) return state;

      const newStepsById = {
        ...state.stepsById,
        [stepId]: { ...existingStep, ...updates },
      };
      const strategy = buildStrategy(newStepsById, state.strategy);
      const historyState = pushHistory(state.history, state.historyIndex, strategy);
      return { stepsById: newStepsById, strategy, ...historyState };
    });
  },

  removeStep: (stepId) => {
    set((state) => {
      const rest = { ...state.stepsById };
      delete rest[stepId];
      const strategy = buildStrategy(rest, state.strategy);
      const historyState = pushHistory(state.history, state.historyIndex, strategy);
      return { stepsById: rest, strategy, ...historyState };
    });
  },

  setStrategy: (strategy) => {
    if (!strategy) {
      set({ strategy: null, stepsById: {}, history: [], historyIndex: -1 });
      return;
    }
    const existingSteps = get().stepsById;
    const incomingSteps = strategy.steps;
    const mergedSteps = incomingSteps.map((step) => {
      const existing = existingSteps[step.id];
      if (!existing) return step;

      let nextStep = step;
      const existingName = existing.displayName;
      const incomingName = step.displayName;

      if (
        (nextStep.recordType === null || nextStep.recordType === undefined) &&
        existing.recordType !== null &&
        existing.recordType !== undefined
      ) {
        nextStep = { ...nextStep, recordType: existing.recordType };
      }
      if (!incomingName && existingName) {
        return { ...nextStep, displayName: existingName };
      }
      if (existingName && !isFallbackDisplayName(existingName, existing)) {
        return { ...nextStep, displayName: existingName };
      }
      if (incomingName && isFallbackDisplayName(incomingName, step) && existingName) {
        return { ...nextStep, displayName: existingName };
      }
      return nextStep;
    });

    const stepsById: Record<string, Step> = {};
    for (const step of mergedSteps) {
      stepsById[step.id] = step;
    }

    const { history, historyIndex } = get();
    const newHistory = history.slice(0, historyIndex + 1);
    const mergedStrategy = { ...strategy, steps: mergedSteps };
    newHistory.push(mergedStrategy);

    set({
      strategy: mergedStrategy,
      stepsById,
      history: newHistory,
      historyIndex: newHistory.length - 1,
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
    return serializeStrategyPlan(state.stepsById, state.strategy);
  },

  setStepValidationErrors: (errors) => {
    set((state) => {
      if (!state.strategy) return state;
      const nextStepsById = applyStepValidationErrors(state.stepsById, errors);
      if (!nextStepsById) return state;
      return {
        stepsById: nextStepsById,
        strategy: buildStrategy(nextStepsById, state.strategy),
      };
    });
  },

  setStepCounts: (counts) => {
    set((state) => {
      if (!state.strategy) return state;
      const nextStepsById = applyStepCounts(state.stepsById, counts);
      if (!nextStepsById) return state;
      return {
        stepsById: nextStepsById,
        strategy: buildStrategy(nextStepsById, state.strategy),
      };
    });
  },

  clear: () => {
    set({
      strategy: null,
      stepsById: {},
      history: [],
      historyIndex: -1,
    });
  },
});
