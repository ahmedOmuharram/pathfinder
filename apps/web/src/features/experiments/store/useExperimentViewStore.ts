import { create } from "zustand";
import type {
  Experiment,
  ExperimentSummary,
  ExperimentConfig,
} from "@pathfinder/shared";
import {
  listExperiments,
  getExperiment,
  deleteExperiment as deleteExperimentApi,
} from "../api";

export type ExperimentView =
  | "list"
  | "mode-select"
  | "setup"
  | "multi-step-setup"
  | "results"
  | "compare"
  | "overlap"
  | "enrichment-compare"
  | "benchmark-results";

interface ExperimentViewState {
  view: ExperimentView;
  experiments: ExperimentSummary[];
  currentExperiment: Experiment | null;
  compareExperiment: Experiment | null;
  benchmarkExperiments: Experiment[];
  cloneConfig: ExperimentConfig | null;
  cloneWithOptimize: boolean;
  error: string | null;

  setView: (view: ExperimentView) => void;
  fetchExperiments: (siteId: string) => Promise<void>;
  loadExperiment: (id: string) => Promise<void>;
  loadCompareExperiment: (id: string) => Promise<void>;
  clearCompare: () => void;
  deleteExperiment: (id: string) => Promise<void>;
  cloneExperiment: (id: string) => Promise<void>;
  setClone: (config: ExperimentConfig) => void;
  clearClone: () => void;
  optimizeFromEvaluation: (experimentId: string) => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

export const useExperimentViewStore = create<ExperimentViewState>((set) => ({
  view: "list",
  experiments: [],
  currentExperiment: null,
  compareExperiment: null,
  benchmarkExperiments: [],
  cloneConfig: null,
  cloneWithOptimize: false,
  error: null,

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

  clearError: () => set({ error: null }),

  reset: () =>
    set({
      view: "list",
      currentExperiment: null,
      compareExperiment: null,
      benchmarkExperiments: [],
      cloneConfig: null,
      cloneWithOptimize: false,
      error: null,
    }),
}));
