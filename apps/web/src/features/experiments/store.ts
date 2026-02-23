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
} from "./api";

type ExperimentView =
  | "list"
  | "setup"
  | "results"
  | "compare"
  | "overlap"
  | "enrichment-compare";

interface ExperimentState {
  view: ExperimentView;
  experiments: ExperimentSummary[];
  currentExperiment: Experiment | null;
  compareExperiment: Experiment | null;
  progress: ExperimentProgressData | null;
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

export const useExperimentStore = create<ExperimentState>((set, get) => ({
  view: "list",
  experiments: [],
  currentExperiment: null,
  compareExperiment: null,
  progress: null,
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

    set({ isRunning: true, progress: null, error: null });

    const controller = createExperimentStream(config, {
      onProgress: (data) => {
        set({ progress: data });
      },
      onComplete: (experiment) => {
        set({
          currentExperiment: experiment,
          isRunning: false,
          view: "results",
          abortController: null,
        });
        const siteId = config.siteId;
        get().fetchExperiments(siteId);
      },
      onError: (error) => {
        set({ error, isRunning: false, abortController: null });
      },
    });

    set({ abortController: controller });
  },

  runBatchExperiment: (_config, _organismParamName, _targets) => {
    // Batch experiment support - to be implemented
    set({ error: "Batch experiments not yet implemented in this build" });
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
      isRunning: false,
      error: null,
      abortController: null,
      cloneConfig: null,
    }),
}));
