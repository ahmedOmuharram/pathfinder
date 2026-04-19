/**
 * Shared types for the strategy store slices.
 */

import type { Patch } from "immer";
import type {
  GraphSnapshot,
  StrategyMeta,
  StrategyPatch,
  StrategyAst,
  Step,
  Strategy,
} from "@pathfinder/shared";
import type {
  StepLifecycleSeed,
  StepMachineEvent,
  StepMachineSnapshot,
} from "./stepMachine";

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
    plan: StrategyAst;
    name: string;
    recordType: string | null;
  } | null;
  clear: () => void;
}

export interface LifecycleSlice {
  /** Per-step XState v5 machine snapshot. Pure reducer, no running actors. */
  stepLifecycleById: Record<string, StepMachineSnapshot>;

  /** Ensure a lifecycle entry exists for the given step id. No-op if already present. */
  initStepLifecycle: (stepId: string, seed?: StepLifecycleSeed) => void;
  /** Dispatch an event to the step's machine. Auto-initializes if missing. */
  dispatchStepEvent: (stepId: string, event: StepMachineEvent) => void;
  /** Remove the lifecycle entry for a step id. */
  removeStepLifecycle: (stepId: string) => void;
  /** Read-only snapshot accessor. Returns null if no entry exists. */
  getStepLifecycle: (stepId: string) => StepMachineSnapshot | null;

  /** Apply validation results for a batch of steps (error message or cleared). */
  applyStepValidationErrors: (errors: Record<string, string | undefined>) => void;
  /** Apply count results for a batch of steps (number, null, or undefined). */
  applyStepCounts: (counts: Record<string, number | null | undefined>) => void;
}

export interface HistorySlice {
  undoStack: Patch[][];
  redoStack: Patch[][];

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

export type StrategyState = DraftSlice &
  HistorySlice &
  ListSlice &
  MetaSlice &
  LifecycleSlice;
