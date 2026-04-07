/**
 * Shared types for the strategy store slices.
 */

import type { StrategyPlan, Step, Strategy } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Per-slice state + action interfaces
// ---------------------------------------------------------------------------

export interface DraftSlice {
  strategy: Strategy | null;
  stepsById: Record<string, Step>;

  addStep: (step: Step) => void;
  updateStep: (stepId: string, updates: Partial<Step>) => void;
  removeStep: (stepId: string) => void;
  setStrategy: (strategy: Strategy | null) => void;
  setWdkInfo: (
    wdkStrategyId: number,
    wdkUrl?: string | null,
    name?: string | null,
    description?: string | null,
  ) => void;
  setStrategyMeta: (updates: Partial<Strategy>) => void;
  buildPlan: () => {
    plan: StrategyPlan;
    name: string;
    recordType: string | null;
  } | null;
  setStepValidationErrors: (errors: Record<string, string | undefined>) => void;
  setStepCounts: (counts: Record<string, number | null | undefined>) => void;
  clear: () => void;
}

export interface HistorySlice {
  history: Strategy[];
  historyIndex: number;

  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
}

export interface ListSlice {
  executedStrategies: Strategy[];

  addExecutedStrategy: (strategy: Strategy) => void;
}

export interface MetaSlice {
  graphValidationStatus: Record<string, boolean>;

  setGraphValidationStatus: (id: string, hasErrors: boolean) => void;
}

// ---------------------------------------------------------------------------
// Combined store type
// ---------------------------------------------------------------------------

export type StrategyState = DraftSlice & HistorySlice & ListSlice & MetaSlice;
