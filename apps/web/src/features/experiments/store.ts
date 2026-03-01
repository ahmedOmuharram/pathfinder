import { create } from "zustand";
import type {
  Experiment,
  ExperimentSummary,
  ExperimentProgressData,
  ExperimentConfig,
  StepEvaluation,
  OperatorComparison,
  StepContribution,
  ParameterSensitivity,
} from "@pathfinder/shared";
import {
  listExperiments,
  getExperiment,
  deleteExperiment as deleteExperimentApi,
  createExperimentStream,
  createBatchExperimentStream,
  createBenchmarkStream,
} from "./api";
import type { BenchmarkControlSetInput } from "./api";

type ExperimentView =
  | "list"
  | "mode-select"
  | "setup"
  | "multi-step-setup"
  | "results"
  | "compare"
  | "overlap"
  | "enrichment-compare"
  | "benchmark-results";

export interface TrialHistoryEntry {
  trialNumber: number;
  score: number;
  bestScore: number;
}

export interface StepAnalysisLiveItems {
  evaluations: StepEvaluation[];
  operators: OperatorComparison[];
  contributions: StepContribution[];
  sensitivities: ParameterSensitivity[];
}

const EMPTY_LIVE_ITEMS: StepAnalysisLiveItems = {
  evaluations: [],
  operators: [],
  contributions: [],
  sensitivities: [],
};

interface ExperimentState {
  view: ExperimentView;
  experiments: ExperimentSummary[];
  currentExperiment: Experiment | null;
  compareExperiment: Experiment | null;
  benchmarkExperiments: Experiment[];
  progress: ExperimentProgressData | null;
  trialHistory: TrialHistoryEntry[];
  stepAnalysisItems: StepAnalysisLiveItems;
  isRunning: boolean;
  hasOptimization: boolean;
  error: string | null;
  abortController: AbortController | null;
  cloneConfig: ExperimentConfig | null;
  cloneWithOptimize: boolean;
  runningConfig: ExperimentConfig | null;

  setView: (view: ExperimentView) => void;
  fetchExperiments: (siteId: string) => Promise<void>;
  loadExperiment: (id: string) => Promise<void>;
  loadCompareExperiment: (id: string) => Promise<void>;
  clearCompare: () => void;
  deleteExperiment: (id: string) => Promise<void>;
  runExperiment: (config: ExperimentConfig) => void;
  runBatchExperiment: (
    config: ExperimentConfig,
    organismParamName: string,
    targets: {
      organism: string;
      positiveControls: string[];
      negativeControls: string[];
    }[],
  ) => void;
  runBenchmark: (
    config: ExperimentConfig,
    controlSets: BenchmarkControlSetInput[],
  ) => void;
  cancelExperiment: () => void;
  clearError: () => void;
  cloneExperiment: (id: string) => Promise<void>;
  setClone: (config: ExperimentConfig) => void;
  clearClone: () => void;
  optimizeFromEvaluation: (experimentId: string) => Promise<void>;
  reset: () => void;
}

function _accumulateTrial(
  existing: TrialHistoryEntry[],
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  progressData: any,
): TrialHistoryEntry[] {
  const tp = progressData?.trialProgress;
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

function _accumulateStepAnalysis(
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

export const useExperimentStore = create<ExperimentState>((set, get) => ({
  view: "list",
  experiments: [],
  currentExperiment: null,
  compareExperiment: null,
  benchmarkExperiments: [],
  progress: null,
  trialHistory: [],
  stepAnalysisItems: EMPTY_LIVE_ITEMS,
  isRunning: false,
  hasOptimization: false,
  error: null,
  abortController: null,
  cloneConfig: null,
  cloneWithOptimize: false,
  runningConfig: null,

  setView: (view) => set({ view }),

  fetchExperiments: async (siteId) => {
    try {
      const experiments = await listExperiments(siteId);
      set({ experiments });
    } catch (err) {
      set({ error: String(err) });
    }
  },

  loadExperiment: async (id) => {
    try {
      const experiment = await getExperiment(id);
      set({ currentExperiment: experiment, view: "results" });
    } catch (err) {
      set({ error: String(err) });
    }
  },

  loadCompareExperiment: async (id) => {
    try {
      const experiment = await getExperiment(id);
      set({ compareExperiment: experiment, view: "compare" });
    } catch (err) {
      set({ error: String(err) });
    }
  },

  clearCompare: () => set({ compareExperiment: null, view: "results" }),

  deleteExperiment: async (id) => {
    try {
      await deleteExperimentApi(id);
      set((s) => ({
        experiments: s.experiments.filter((e) => e.id !== id),
        currentExperiment: s.currentExperiment?.id === id ? null : s.currentExperiment,
        view: s.currentExperiment?.id === id ? "list" : s.view,
      }));
    } catch (err) {
      set({ error: String(err) });
    }
  },

  runExperiment: (config) => {
    const prev = get().abortController;
    prev?.abort();

    const controller = new AbortController();
    const hasOpt =
      (config.optimizationSpecs?.length ?? 0) > 0 || config.enableStepAnalysis === true;
    set({
      isRunning: true,
      hasOptimization: hasOpt,
      progress: null,
      trialHistory: [],
      stepAnalysisItems: EMPTY_LIVE_ITEMS,
      error: null,
      runningConfig: config,
      abortController: controller,
    });

    createExperimentStream(
      config,
      {
        onProgress: (data) => {
          set((s) => ({
            progress: data,
            trialHistory: _accumulateTrial(s.trialHistory, data),
            stepAnalysisItems: _accumulateStepAnalysis(s.stepAnalysisItems, data),
          }));
        },
        onComplete: (experiment) => {
          set({
            currentExperiment: experiment,
            isRunning: false,
            view: "results",
            abortController: null,
            runningConfig: null,
          });
          get().fetchExperiments(config.siteId);
        },
        onError: (error) => {
          set({ error, isRunning: false, abortController: null, runningConfig: null });
        },
      },
      controller,
    );
  },

  runBatchExperiment: (config, organismParamName, targets) => {
    const prev = get().abortController;
    prev?.abort();

    const controller = new AbortController();
    set({
      isRunning: true,
      hasOptimization: false,
      progress: null,
      trialHistory: [],
      stepAnalysisItems: EMPTY_LIVE_ITEMS,
      error: null,
      runningConfig: config,
      abortController: controller,
    });

    createBatchExperimentStream(
      config,
      organismParamName,
      targets,
      {
        onProgress: (data) => {
          set((s) => ({
            progress: data,
            trialHistory: _accumulateTrial(s.trialHistory, data),
            stepAnalysisItems: _accumulateStepAnalysis(s.stepAnalysisItems, data),
          }));
        },
        onComplete: (experiments, _batchId) => {
          const first = experiments[0] ?? null;
          set({
            currentExperiment: first,
            isRunning: false,
            view: first ? "results" : "list",
            abortController: null,
            runningConfig: null,
          });
          get().fetchExperiments(config.siteId);
        },
        onError: (error) => {
          set({ error, isRunning: false, abortController: null, runningConfig: null });
        },
      },
      controller,
    );
  },

  runBenchmark: (config, controlSets) => {
    const prev = get().abortController;
    prev?.abort();

    const controller = new AbortController();
    set({
      isRunning: true,
      hasOptimization: false,
      progress: null,
      trialHistory: [],
      stepAnalysisItems: EMPTY_LIVE_ITEMS,
      error: null,
      benchmarkExperiments: [],
      runningConfig: config,
      abortController: controller,
    });

    createBenchmarkStream(
      config,
      controlSets,
      {
        onProgress: (data) => {
          set((s) => ({
            progress: data,
            trialHistory: _accumulateTrial(s.trialHistory, data),
            stepAnalysisItems: _accumulateStepAnalysis(s.stepAnalysisItems, data),
          }));
        },
        onComplete: (experiments, _benchmarkId) => {
          const primary =
            experiments.find((e) => e.isPrimaryBenchmark) ?? experiments[0] ?? null;
          set({
            currentExperiment: primary,
            benchmarkExperiments: experiments,
            isRunning: false,
            view: "benchmark-results",
            abortController: null,
            runningConfig: null,
          });
          get().fetchExperiments(config.siteId);
        },
        onError: (error) => {
          set({ error, isRunning: false, abortController: null, runningConfig: null });
        },
      },
      controller,
    );
  },

  cancelExperiment: () => {
    const controller = get().abortController;
    controller?.abort();
    set({
      isRunning: false,
      hasOptimization: false,
      abortController: null,
      runningConfig: null,
    });
  },

  clearError: () => set({ error: null }),

  cloneExperiment: async (id) => {
    try {
      const experiment = await getExperiment(id);
      set({ cloneConfig: experiment.config, view: "setup" });
    } catch (err) {
      set({ error: String(err) });
    }
  },

  setClone: (config) => set({ cloneConfig: config, view: "setup" }),
  clearClone: () => set({ cloneConfig: null, cloneWithOptimize: false }),

  optimizeFromEvaluation: async (experimentId) => {
    try {
      const experiment = await getExperiment(experimentId);
      const config = { ...experiment.config, parentExperimentId: experimentId };
      const isMultiStep = config.mode === "multi-step" || config.mode === "import";

      if (isMultiStep) {
        config.enableStepAnalysis = true;
        set({
          cloneConfig: config,
          cloneWithOptimize: true,
          view: "multi-step-setup",
        });
      } else {
        set({
          cloneConfig: config,
          cloneWithOptimize: true,
          view: "setup",
        });
      }
    } catch (err) {
      set({ error: String(err) });
    }
  },

  reset: () => {
    get().abortController?.abort();
    set({
      view: "list",
      currentExperiment: null,
      compareExperiment: null,
      benchmarkExperiments: [],
      progress: null,
      trialHistory: [],
      stepAnalysisItems: EMPTY_LIVE_ITEMS,
      isRunning: false,
      hasOptimization: false,
      error: null,
      abortController: null,
      cloneConfig: null,
      cloneWithOptimize: false,
      runningConfig: null,
    });
  },
}));
