import type { ExperimentConfig, ExperimentProgressData } from "@pathfinder/shared";
import type { StepAnalysisLiveItems, TrialHistoryEntry } from "../types";

/* ── Types ──────────────────────────────────────────────────────────── */

/** The subset of Zustand set/get we need from the run store. */
interface RunStoreAccessors {
  set: (
    partial:
      | Partial<RunStoreSlice>
      | ((state: RunStoreSlice) => Partial<RunStoreSlice>),
  ) => void;
  get: () => RunStoreSlice;
}

/** The slice of state the runner reads/writes. */
interface RunStoreSlice {
  isRunning: boolean;
  hasOptimization: boolean;
  progress: ExperimentProgressData | null;
  trialHistory: TrialHistoryEntry[];
  stepAnalysisItems: StepAnalysisLiveItems;
  error: string | null;
  abortController: AbortController | null;
  runningConfig: ExperimentConfig | null;
}

/**
 * Callbacks provided to the `openStream` function.
 *
 * - `onProgress` should be wired to the stream's progress handler.
 * - `onRunComplete` **resets the running state** and should be called
 *   *after* the caller has finished its view-store updates.
 * - `onError` handles errors uniformly.
 */
export interface StreamRunnerCallbacks {
  onProgress: (data: ExperimentProgressData) => void;
  onRunComplete: () => void;
  onError: (error: string) => void;
}

export interface StreamRunnerOpts {
  /** The experiment config being run (stored as `runningConfig`). */
  config: ExperimentConfig;
  /** Whether this run involves optimization / step-analysis progress. */
  hasOptimization: boolean;
  /**
   * Opens the SSE stream. The implementor wires the stream-creator's
   * typed `onComplete` to first perform any view-store updates, then
   * call `callbacks.onRunComplete()` to reset running state.
   */
  openStream: (callbacks: StreamRunnerCallbacks, controller: AbortController) => void;
}

/* ── Accumulator helpers ─────────────────────────────────────────────── */

export function accumulateTrial(
  existing: TrialHistoryEntry[],
  progressData: ExperimentProgressData,
): TrialHistoryEntry[] {
  const tp = progressData.trialProgress;
  if (!tp) return existing;

  if (tp.trial?.trialNumber != null) {
    const { trialNumber, score } = tp.trial;
    if (existing.some((e) => e.trialNumber === trialNumber)) return existing;
    return [
      ...existing,
      {
        trialNumber,
        score,
        bestScore: tp.bestTrial?.score ?? score,
      },
    ];
  }

  return existing;
}

export function accumulateStepAnalysis(
  existing: StepAnalysisLiveItems,
  data: ExperimentProgressData,
): StepAnalysisLiveItems {
  const sa = data.stepAnalysisProgress;
  if (!sa) return existing;

  if (sa.stepEvaluation) {
    const dup = existing.evaluations.some(
      (e) => e.stepId === sa.stepEvaluation!.stepId,
    );
    if (!dup) {
      return {
        ...existing,
        evaluations: [...existing.evaluations, sa.stepEvaluation],
      };
    }
  }
  if (sa.operatorComparison) {
    const dup = existing.operators.some(
      (o) => o.combineNodeId === sa.operatorComparison!.combineNodeId,
    );
    if (!dup) {
      return {
        ...existing,
        operators: [...existing.operators, sa.operatorComparison],
      };
    }
  }
  if (sa.stepContribution) {
    const dup = existing.contributions.some(
      (c) => c.stepId === sa.stepContribution!.stepId,
    );
    if (!dup) {
      return {
        ...existing,
        contributions: [...existing.contributions, sa.stepContribution],
      };
    }
  }
  if (sa.parameterSensitivity) {
    const key = `${sa.parameterSensitivity.stepId}:${sa.parameterSensitivity.paramName}`;
    const dup = existing.sensitivities.some(
      (s) => `${s.stepId}:${s.paramName}` === key,
    );
    if (!dup) {
      return {
        ...existing,
        sensitivities: [...existing.sensitivities, sa.parameterSensitivity],
      };
    }
  }

  return existing;
}

/* ── Empty-state constant ──────────────────────────────────────────── */

export const EMPTY_LIVE_ITEMS: StepAnalysisLiveItems = {
  evaluations: [],
  operators: [],
  contributions: [],
  sensitivities: [],
};

/* ── The runner ─────────────────────────────────────────────────────── */

/**
 * Shared streaming runner used by `runExperiment`, `runBatchExperiment`,
 * and `runBenchmark` inside the Zustand run store.
 *
 * Encapsulates the abort-previous / set-running / progress / complete / error
 * lifecycle so each store method only supplies the stream opener (which also
 * handles its own view-store update on completion).
 */
export function runExperimentStream(
  { set, get }: RunStoreAccessors,
  opts: StreamRunnerOpts,
): void {
  // 1. Abort any in-flight run
  get().abortController?.abort();

  // 2. Fresh controller + running state
  const controller = new AbortController();
  set({
    isRunning: true,
    hasOptimization: opts.hasOptimization,
    progress: null,
    trialHistory: [],
    stepAnalysisItems: EMPTY_LIVE_ITEMS,
    error: null,
    runningConfig: opts.config,
    abortController: controller,
  });

  // 3. Open the stream with shared callbacks
  opts.openStream(
    {
      onProgress: (data) => {
        set((s) => ({
          progress: data,
          trialHistory: accumulateTrial(s.trialHistory, data),
          stepAnalysisItems: accumulateStepAnalysis(s.stepAnalysisItems, data),
        }));
      },
      onRunComplete: () => {
        set({
          isRunning: false,
          abortController: null,
          runningConfig: null,
        });
      },
      onError: (error) => {
        set({
          error,
          isRunning: false,
          abortController: null,
          runningConfig: null,
        });
      },
    },
    controller,
  );
}
