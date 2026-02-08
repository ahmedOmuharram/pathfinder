/**
 * Strategy state store - builds strategy from individual steps
 */

import { create } from "zustand";
import type { StrategyPlan } from "@pathfinder/shared";
import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import {
  getRootSteps,
  getRootStepId,
  serializeStrategyPlan,
} from "@/features/strategy/domain/graph";
import { inferStepKind } from "@/core/strategyGraph";

const isUrlLike = (value: string | null | undefined) =>
  typeof value === "string" &&
  (value.startsWith("http://") || value.startsWith("https://"));

const normalizeName = (value: string | null | undefined) =>
  typeof value === "string" ? value.trim().toLowerCase() : "";

const isFallbackDisplayName = (name: string | null | undefined, step: StrategyStep) => {
  if (!name) return true;
  if (isUrlLike(name)) return true;
  const normalized = normalizeName(name);
  const candidates = new Set<string>([
    normalizeName(step.searchName),
    normalizeName(inferStepKind(step)),
  ]);
  if (step.operator) {
    const op = normalizeName(step.operator);
    candidates.add(op);
    candidates.add(`${op} combine`);
  }
  return candidates.has(normalized);
};

const MAX_HISTORY = 50;

const pushHistory = (state: StrategyState, strategy: StrategyWithMeta | null) => {
  if (!strategy) {
    return { history: state.history, historyIndex: state.historyIndex };
  }
  const nextHistory = state.history.slice(0, state.historyIndex + 1);
  nextHistory.push(strategy);
  if (nextHistory.length > MAX_HISTORY) {
    nextHistory.shift();
  }
  return { history: nextHistory, historyIndex: nextHistory.length - 1 };
};

interface StrategyState {
  // Current strategy (for visualization)
  strategy: StrategyWithMeta | null;

  // Individual steps (keyed by stepId)
  stepsById: Record<string, StrategyStep>;

  // History for undo/redo
  history: StrategyWithMeta[];
  historyIndex: number;

  // Actions
  addStep: (step: StrategyStep) => void;
  updateStep: (stepId: string, updates: Partial<StrategyStep>) => void;
  removeStep: (stepId: string) => void;
  setStrategy: (strategy: StrategyWithMeta | null) => void;
  setWdkInfo: (
    wdkStrategyId: number,
    wdkUrl?: string | null,
    name?: string | null,
    description?: string | null,
  ) => void;
  setStrategyMeta: (updates: Partial<StrategyWithMeta>) => void;
  buildPlan: () => {
    plan: StrategyPlan;
    name: string;
    recordType: string | null;
  } | null;
  setStepValidationErrors: (errors: Record<string, string | undefined>) => void;
  setStepCounts: (counts: Record<string, number | null | undefined>) => void;
  clear: () => void;

  // Undo/redo
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
}

// Build a Strategy object from individual steps
function buildStrategy(
  stepsById: Record<string, StrategyStep>,
  existing: StrategyWithMeta | null,
): StrategyWithMeta | null {
  const steps = Object.values(stepsById);
  if (steps.length === 0) return null;

  // Find the root step (the step that isn't an input to any other step).
  // IMPORTANT: We keep the strategy visible even when the graph is invalid (multi-root),
  // but we represent invalidity by setting rootStepId=null.
  const roots = getRootSteps(steps);
  const rootStepId = roots.length === 1 ? getRootStepId(steps) : null;

  return {
    id: existing?.id || "draft",
    name: existing?.name || "Draft Strategy",
    siteId: existing?.siteId || "plasmodb",
    recordType: existing?.recordType || steps[0]?.recordType || "gene",
    steps,
    rootStepId,
    wdkStrategyId: existing?.wdkStrategyId,
    wdkUrl: existing?.wdkUrl,
    description: existing?.description,
    createdAt: existing?.createdAt || new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

export const useStrategyStore = create<StrategyState>((set, get) => ({
  strategy: null,
  stepsById: {},
  history: [],
  historyIndex: -1,

  addStep: (step) => {
    set((state) => {
      const existing = state.stepsById[step.id];
      // AI-driven updates often send partial step payloads.
      // Treat this as an upsert+patch: only overwrite fields that are present
      // (not `undefined`), otherwise keep the existing values.
      const updates = Object.fromEntries(
        Object.entries(step).filter(([, value]) => value !== undefined),
      ) as Partial<StrategyStep>;
      const nextStepRecord: StrategyStep = {
        ...(existing ?? step),
        ...updates,
      };

      // Preserve recordType if incoming omits it.
      if (existing?.recordType && !nextStepRecord.recordType) {
        nextStepRecord.recordType = existing.recordType;
      }

      // Preserve user-edited (non-fallback) displayName.
      if (existing?.displayName) {
        const existingName = existing.displayName;
        const incomingName = step.displayName;
        const keepExisting =
          !incomingName ||
          !isFallbackDisplayName(existingName, existing) ||
          isFallbackDisplayName(incomingName, step as StrategyStep);
        if (keepExisting) {
          nextStepRecord.displayName = existingName;
        }
      }
      if (!nextStepRecord.id) {
        nextStepRecord.id = step.id;
      }
      if (!nextStepRecord.displayName) {
        nextStepRecord.displayName =
          step.displayName ||
          existing?.displayName ||
          step.searchName ||
          "Untitled step";
      }
      const nextStep = nextStepRecord as StrategyStep;
      const newStepsById = { ...state.stepsById, [step.id]: nextStep };
      const strategy = buildStrategy(newStepsById, state.strategy);

      const historyState = pushHistory(state, strategy);
      return {
        stepsById: newStepsById,
        strategy,
        ...historyState,
      };
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
      const historyState = pushHistory(state, strategy);
      return {
        stepsById: newStepsById,
        strategy,
        ...historyState,
      };
    });
  },

  removeStep: (stepId) => {
    set((state) => {
      const rest = { ...state.stepsById };
      delete rest[stepId];
      const strategy = buildStrategy(rest, state.strategy);
      const historyState = pushHistory(state, strategy);
      return {
        stepsById: rest,
        strategy,
        ...historyState,
      };
    });
  },

  setStrategy: (strategy) => {
    if (!strategy) {
      set({ strategy: null, stepsById: {} });
      return;
    }
    const existingSteps = get().stepsById;
    const stepsById: Record<string, StrategyStep> = {};
    const incomingSteps = strategy.steps ?? [];
    const mergedSteps = incomingSteps.map((step) => {
      let nextStep = step;
      const existing = existingSteps[step.id];
      if (!existing) {
        return step;
      }
      const existingName = existing.displayName;
      const incomingName = step.displayName;
      if (!nextStep.recordType && existing.recordType) {
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
      return {
        strategy: {
          ...state.strategy,
          name: name ?? state.strategy.name,
          description: description ?? state.strategy.description,
          wdkStrategyId,
          wdkUrl: wdkUrl ?? state.strategy.wdkUrl,
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
      let changed = false;
      const nextStepsById = { ...state.stepsById };
      for (const [stepId, message] of Object.entries(errors)) {
        const step = nextStepsById[stepId];
        if (!step) continue;
        const nextMessage = message || undefined;
        if (step.validationError !== nextMessage) {
          nextStepsById[stepId] = { ...step, validationError: nextMessage };
          changed = true;
        }
      }
      if (!changed) return state;
      return {
        stepsById: nextStepsById,
        strategy: buildStrategy(nextStepsById, state.strategy),
      };
    });
  },
  setStepCounts: (counts) => {
    set((state) => {
      if (!state.strategy) return state;
      let changed = false;
      const nextStepsById = { ...state.stepsById };
      for (const [stepId, count] of Object.entries(counts)) {
        const step = nextStepsById[stepId];
        if (!step) continue;
        const nextCount =
          typeof count === "number" || count === null ? count : undefined;
        if (step.resultCount !== nextCount) {
          nextStepsById[stepId] = { ...step, resultCount: nextCount };
          changed = true;
        }
      }
      if (!changed) return state;
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

  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      const strategy = history[newIndex];
      const stepsById: Record<string, StrategyStep> = {};
      for (const step of strategy.steps) {
        stepsById[step.id] = step;
      }
      set({
        strategy,
        stepsById,
        historyIndex: newIndex,
      });
    }
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      const strategy = history[newIndex];
      const stepsById: Record<string, StrategyStep> = {};
      for (const step of strategy.steps) {
        stepsById[step.id] = step;
      }
      set({
        strategy,
        stepsById,
        historyIndex: newIndex,
      });
    }
  },

  canUndo: () => get().historyIndex > 0,
  canRedo: () => get().historyIndex < get().history.length - 1,
}));
