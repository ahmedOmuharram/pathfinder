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
  | "setup"
  | "results"
  | "compare"
  | "overlap"
  | "enrichment-compare";

export interface TrialHistoryEntry {
  trialNumber: number;
  score: number;
  bestScore: number;
}

interface ExperimentState {
  view: ExperimentView;
  experiments: ExperimentSummary[];
  currentExperiment: Experiment | null;
  compareExperiment: Experiment | null;
  progress: ExperimentProgressData | null;
  trialHistory: TrialHistoryEntry[];
  isRunning: boolean;
  error: string | null;
  abortController: AbortController | null;
  cloneConfig: ExperimentConfig | null;

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
  reset: () => void;
}

function _accumulateTrial(
  existing: TrialHistoryEntry[],
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  progressData: any,
): TrialHistoryEntry[] {
  const tp = progressData?.trialProgress;
  if (!tp?.trial) return existing;
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

export const useExperimentStore = create<ExperimentState>((set, get) => ({
  view: "list",
  experiments: [],
  currentExperiment: null,
  compareExperiment: null,
  progress: null,
  trialHistory: [],
  isRunning: false,
  error: null,
  abortController: null,
  cloneConfig: null,

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

    set({ isRunning: true, progress: null, trialHistory: [], error: null });

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
        });
        get().fetchExperiments(config.siteId);
      },
      onError: (error) => {
        set({ error, isRunning: false, abortController: null });
      },
    });

    set({ abortController: controller });
  },

  runBatchExperiment: (config, organismParamName, targets) => {
    const prev = get().abortController;
    prev?.abort();

    set({ isRunning: true, progress: null, trialHistory: [], error: null });

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
        });
        get().fetchExperiments(config.siteId);
      },
      onError: (error) => {
        set({ error, isRunning: false, abortController: null });
      },
    });

    set({ abortController: controller });
  },

  cancelExperiment: () => {
    const controller = get().abortController;
    controller?.abort();
    set({ isRunning: false, abortController: null });
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
  clearClone: () => set({ cloneConfig: null }),

  reset: () =>
    set({
      view: "list",
      currentExperiment: null,
      compareExperiment: null,
      progress: null,
      trialHistory: [],
      isRunning: false,
      error: null,
      abortController: null,
      cloneConfig: null,
    }),
}));
