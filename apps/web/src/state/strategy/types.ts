/**
 * Shared types for the strategy store slices.
 */

import type { Patch } from "immer";
import type { Step, Strategy } from "@pathfinder/shared";
import type {
  StepLifecycleSeed,
  StepMachineEvent,
  StepMachineSnapshot,
} from "./stepMachine";

// ---------------------------------------------------------------------------
// Per-slice state + action interfaces
// ---------------------------------------------------------------------------

export interface StrategyMetaUpdate {
  name?: string;
  description?: string | null;
  wdkStrategyId?: number | null;
  wdkUrl?: string | null;
}

/**
 * The most recent failed push payload, kept in the store so a retry button
 * can re-fire it without recomputing the optimistic strategy.
 */
export interface FailedPushPayload {
  optimistic: Strategy;
}

export interface DraftSlice {
  strategy: Strategy | null;
  lastFailedPush: FailedPushPayload | null;

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
  setStrategyMeta: (updates: StrategyMetaUpdate) => void;
  setLastFailedPush: (payload: FailedPushPayload | null) => void;
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

export interface HistorySnapshot {
  strategy: Strategy | null;
}

export interface HistorySlice {
  undoStack: Patch[][];
  redoStack: Patch[][];

  /**
   * Record a forward step from the given previous snapshot to the current
   * store state. Mutations call this in `onSuccess` after the server-canonical
   * strategy has replaced the optimistic copy.
   */
  pushSnapshot: (prev: HistorySnapshot) => void;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
}

export interface MetaSlice {
  graphValidationStatus: Record<string, boolean>;

  setGraphValidationStatus: (id: string, hasErrors: boolean) => void;
}

// ---------------------------------------------------------------------------
// Combined store type
// ---------------------------------------------------------------------------

export type StrategyState = DraftSlice &
  HistorySlice &
  MetaSlice &
  LifecycleSlice;
