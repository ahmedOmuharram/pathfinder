/**
 * Shared types for the strategy store slices.
 */

import type {
  GraphSnapshot,
  StrategyMeta,
  StrategyPatch,
  StrategyPlan,
  Step,
  Strategy,
} from "@pathfinder/shared";

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

  /** Latest stream-derived snapshot from a `data-graph-snapshot` part. */
  latestGraphSnapshot: GraphSnapshot | null;
  /** Latest stream-derived strategy metadata from a `data-strategy-meta` part. */
  latestStrategyMeta: StrategyMeta | null;
  /** Latest stream-derived patch from a `data-strategy-patch` part. */
  lastStrategyPatch: StrategyPatch | null;

  setGraphValidationStatus: (id: string, hasErrors: boolean) => void;

  // Stream-derived setters (from data-* parts)
  applyGraphSnapshot: (snapshot: GraphSnapshot) => void;
  setLatestStrategyMeta: (meta: StrategyMeta) => void;
  applyPatch: (patch: StrategyPatch) => void;
}

// ---------------------------------------------------------------------------
// Combined store type
// ---------------------------------------------------------------------------

export type StrategyState = DraftSlice & HistorySlice & ListSlice & MetaSlice;
