/**
 * Draft slice — current strategy and step CRUD primitives.
 *
 * Steps live exclusively in `strategy.steps`; consumers derive a `stepsById`
 * map via `useStepsById()` (selectors.ts). Each action mutates the store
 * synchronously without recording history — mutations explicitly call
 * `pushSnapshot` from historySlice on success.
 */

import type { Step, Strategy } from "@pathfinder/shared";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import type { StateCreator } from "zustand";
import { isFallbackDisplayName } from "@/lib/strategyGraph";
import { getRootSteps, getRootStepId } from "@/lib/strategyGraph/validate";
import type { DevtoolsMutators } from "@/state/middleware";
import { initialStepSnapshot, type StepMachineSnapshot } from "./stepMachine";
import type { DraftSlice, StrategyState } from "./types";

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
  steps: Step[],
): Record<string, StepMachineSnapshot> {
  const next: Record<string, StepMachineSnapshot> = {};
  for (const step of steps) {
    next[step.id] = current[step.id] ?? seedSnapshotForStep(step);
  }
  return next;
}

function ensureDisplayName(step: Step, existing: Step | undefined): Step {
  if (step.displayName != null && step.displayName !== "") return step;
  const existingName = existing?.displayName;
  const fallbackName =
    existingName != null && existingName !== ""
      ? existingName
      : step.searchName != null && step.searchName !== ""
        ? step.searchName
        : "Untitled step";
  return { ...step, displayName: fallbackName };
}

function preserveDisplayName(existing: Step, incoming: Step, merged: Step): Step {
  const existingName = existing.displayName;
  if (existingName == null || existingName === "") return merged;

  const incomingName = incoming.displayName;
  const keepExisting =
    incomingName == null ||
    incomingName === "" ||
    !isFallbackDisplayName(existingName, existing) ||
    isFallbackDisplayName(incomingName, incoming);

  if (keepExisting) {
    return { ...merged, displayName: existingName };
  }
  return merged;
}

function buildStrategyFromSteps(
  steps: Step[],
  existing: Strategy | null,
): Strategy | null {
  if (steps.length === 0) return null;
  const roots = getRootSteps(steps);
  const rootStepId = roots.length === 1 ? getRootStepId(steps) : null;
  return {
    id: existing?.id ?? "draft",
    name: existing?.name ?? DEFAULT_STREAM_NAME,
    siteId: existing?.siteId ?? "veupathdb",
    recordType: existing?.recordType ?? steps[0]?.recordType ?? "gene",
    steps,
    rootStepId,
    wdkStrategyId: existing?.wdkStrategyId ?? null,
    wdkUrl: existing?.wdkUrl ?? null,
    isSaved: existing?.isSaved ?? false,
    description: existing?.description ?? null,
    createdAt: existing?.createdAt ?? new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

export const createDraftSlice: StateCreator<
  StrategyState,
  DevtoolsMutators,
  [],
  DraftSlice
> = (set) => ({
  strategy: null,
  lastFailedPush: null,

  addStep: (step) => {
    set((state) => {
      const currentSteps = state.strategy?.steps ?? [];
      const existing = currentSteps.find((s) => s.id === step.id);

      let nextStep: Step = existing ? { ...existing, ...step } : { ...step };

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

      const nextSteps = existing
        ? currentSteps.map((s) => (s.id === step.id ? nextStep : s))
        : [...currentSteps, nextStep];

      const nextStrategy = buildStrategyFromSteps(nextSteps, state.strategy);
      const lifecycleNext = state.stepLifecycleById[step.id]
        ? state.stepLifecycleById
        : {
            ...state.stepLifecycleById,
            [step.id]: seedSnapshotForStep(nextStep),
          };
      return { strategy: nextStrategy, stepLifecycleById: lifecycleNext };
    });
  },

  updateStep: (stepId, updates) => {
    set((state) => {
      const currentSteps = state.strategy?.steps ?? [];
      const existing = currentSteps.find((s) => s.id === stepId);
      if (!existing) return state;
      const nextStep: Step = { ...existing, ...updates };
      const nextSteps = currentSteps.map((s) =>
        s.id === stepId ? nextStep : s,
      );
      return { strategy: buildStrategyFromSteps(nextSteps, state.strategy) };
    });
  },

  removeStep: (stepId) => {
    set((state) => {
      const currentSteps = state.strategy?.steps ?? [];
      if (!currentSteps.some((s) => s.id === stepId)) return state;
      const nextSteps = currentSteps.filter((s) => s.id !== stepId);
      const lifecycleNext = { ...state.stepLifecycleById };
      delete lifecycleNext[stepId];
      return {
        strategy: buildStrategyFromSteps(nextSteps, state.strategy),
        stepLifecycleById: lifecycleNext,
      };
    });
  },

  setStrategy: (strategy) => {
    if (!strategy) {
      set({
        strategy: null,
        stepLifecycleById: {},
        undoStack: [],
        redoStack: [],
      });
      return;
    }
    set((state) => ({
      strategy,
      stepLifecycleById: syncLifecycleForSteps(
        state.stepLifecycleById,
        strategy.steps,
      ),
    }));
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
      const nextStrategy: Strategy = {
        ...state.strategy,
        updatedAt: new Date().toISOString(),
      };
      if (updates.name !== undefined) nextStrategy.name = updates.name;
      if (updates.description !== undefined)
        nextStrategy.description = updates.description;
      if (updates.wdkStrategyId !== undefined)
        nextStrategy.wdkStrategyId = updates.wdkStrategyId;
      if (updates.wdkUrl !== undefined) nextStrategy.wdkUrl = updates.wdkUrl;
      return { strategy: nextStrategy };
    });
  },

  setLastFailedPush: (payload) => {
    set({ lastFailedPush: payload });
  },

  clear: () => {
    set({
      strategy: null,
      lastFailedPush: null,
      stepLifecycleById: {},
      undoStack: [],
      redoStack: [],
    });
  },
});
