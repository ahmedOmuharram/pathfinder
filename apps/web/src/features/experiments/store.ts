import { create } from "zustand";
import type {
  Experiment,
  ExperimentSummary,
  ExperimentProgressData,
  ExperimentConfig,
} from "@pathfinder/shared";
import {
  listExperiments,
  getExperiment,
  deleteExperiment as deleteExperimentApi,
  createExperimentStream,
  createBatchExperimentStream,
} from "./api";

type ExperimentView =
  | "list"
  | "mode-select"
  | "setup"
  | "multi-step-setup"
  | "results"
  | "compare"
  | "overlap"
  | "enrichment-compare";

export interface TrialMutation {
  nodeId: string;
  param?: string;
  value?: unknown;
  operator?: string;
}

export interface TrialHistoryEntry {
  trialNumber: number;
  score: number;
  bestScore: number;
  isNewBest?: boolean;
  paramMutations?: TrialMutation[];
  operatorMutations?: TrialMutation[];
  structuralVariant?: string | null;
}

interface ExperimentState {
  view: ExperimentView;
  experiments: ExperimentSummary[];
  currentExperiment: Experiment | null;
  compareExperiment: Experiment | null;
  progress: ExperimentProgressData | null;
  trialHistory: TrialHistoryEntry[];
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

  // Tree optimization trial_result (check FIRST -- also has trial.trialNumber)
  if (tp.phase === "trial_result" && tp.trial) {
    const {
      trialNumber,
      score,
      isNewBest,
      paramMutations,
      operatorMutations,
      structuralVariant,
    } = tp.trial;
    if (existing.some((e) => e.trialNumber === trialNumber)) return existing;
    return [
      ...existing,
      {
        trialNumber,
        score,
        bestScore: tp.bestScore ?? score,
        isNewBest,
        paramMutations: paramMutations ?? [],
        operatorMutations: operatorMutations ?? [],
        structuralVariant: structuralVariant ?? null,
      },
    ];
  }

  // Single-step optimization
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

export const useExperimentStore = create<ExperimentState>((set, get) => ({
  view: "list",
  experiments: [],
  currentExperiment: null,
  compareExperiment: null,
  progress: null,
  trialHistory: [],
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

    const hasOpt =
      (config.optimizationSpecs?.length ?? 0) > 0 ||
      config.enableTreeOptimization === true;
    set({
      isRunning: true,
      hasOptimization: hasOpt,
      progress: null,
      trialHistory: [],
      error: null,
      runningConfig: config,
    });

    const controller = createExperimentStream(config, {
      onProgress: (data) => {
        set({
          progress: data,
          trialHistory: _accumulateTrial(get().trialHistory, data),
        });
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
    });

    set({ abortController: controller });
  },

  runBatchExperiment: (config, organismParamName, targets) => {
    const prev = get().abortController;
    prev?.abort();

    set({
      isRunning: true,
      progress: null,
      trialHistory: [],
      error: null,
      runningConfig: config,
    });

    const controller = createBatchExperimentStream(config, organismParamName, targets, {
      onProgress: (data) => {
        set({
          progress: data,
          trialHistory: _accumulateTrial(get().trialHistory, data),
        });
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
    });

    set({ abortController: controller });
  },

  cancelExperiment: () => {
    const controller = get().abortController;
    controller?.abort();
    set({ isRunning: false, abortController: null, runningConfig: null });
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
        config.enableTreeOptimization = true;
        config.treeOptimizationBudget = config.treeOptimizationBudget ?? 20;
        config.optimizeOperators = config.optimizeOperators ?? true;
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

  reset: () =>
    set({
      view: "list",
      currentExperiment: null,
      compareExperiment: null,
      progress: null,
      trialHistory: [],
      isRunning: false,
      hasOptimization: false,
      error: null,
      abortController: null,
      cloneConfig: null,
      cloneWithOptimize: false,
      runningConfig: null,
    }),
}));
