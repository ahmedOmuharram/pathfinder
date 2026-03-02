import { create } from "zustand";
import type { ExperimentConfig, ExperimentProgressData } from "@pathfinder/shared";
import {
  createExperimentStream,
  createBatchExperimentStream,
  createBenchmarkStream,
} from "../api";
import type { BenchmarkControlSetInput } from "../api";
import type { TrialHistoryEntry, StepAnalysisLiveItems } from "../types";
import { useExperimentViewStore } from "./useExperimentViewStore";
import { runExperimentStream, EMPTY_LIVE_ITEMS } from "../utils/experimentStreamRunner";

interface ExperimentRunState {
  isRunning: boolean;
  hasOptimization: boolean;
  progress: ExperimentProgressData | null;
  trialHistory: TrialHistoryEntry[];
  stepAnalysisItems: StepAnalysisLiveItems;
  error: string | null;
  abortController: AbortController | null;
  runningConfig: ExperimentConfig | null;

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
  reset: () => void;
}

export const useExperimentRunStore = create<ExperimentRunState>((set, get) => ({
  isRunning: false,
  hasOptimization: false,
  progress: null,
  trialHistory: [],
  stepAnalysisItems: EMPTY_LIVE_ITEMS,
  error: null,
  abortController: null,
  runningConfig: null,

  runExperiment: (config) => {
    runExperimentStream(
      { set, get },
      {
        config,
        hasOptimization:
          (config.optimizationSpecs?.length ?? 0) > 0 ||
          config.enableStepAnalysis === true,
        openStream: (callbacks, controller) => {
          createExperimentStream(
            config,
            {
              onProgress: callbacks.onProgress,
              onComplete: (experiment) => {
                useExperimentViewStore.setState({
                  currentExperiment: experiment,
                  view: "results",
                });
                useExperimentViewStore.getState().fetchExperiments(config.siteId);
                callbacks.onRunComplete();
              },
              onError: callbacks.onError,
            },
            controller,
          );
        },
      },
    );
  },

  runBatchExperiment: (config, organismParamName, targets) => {
    runExperimentStream(
      { set, get },
      {
        config,
        hasOptimization: false,
        openStream: (callbacks, controller) => {
          createBatchExperimentStream(
            config,
            organismParamName,
            targets,
            {
              onProgress: callbacks.onProgress,
              onComplete: (experiments) => {
                const first = experiments[0] ?? null;
                useExperimentViewStore.setState({
                  currentExperiment: first,
                  view: first ? "results" : "list",
                });
                useExperimentViewStore.getState().fetchExperiments(config.siteId);
                callbacks.onRunComplete();
              },
              onError: callbacks.onError,
            },
            controller,
          );
        },
      },
    );
  },

  runBenchmark: (config, controlSets) => {
    runExperimentStream(
      { set, get },
      {
        config,
        hasOptimization: false,
        openStream: (callbacks, controller) => {
          createBenchmarkStream(
            config,
            controlSets,
            {
              onProgress: callbacks.onProgress,
              onComplete: (experiments) => {
                const primary =
                  experiments.find((e) => e.isPrimaryBenchmark) ??
                  experiments[0] ??
                  null;
                useExperimentViewStore.setState({
                  currentExperiment: primary,
                  benchmarkExperiments: experiments,
                  view: "benchmark-results",
                });
                useExperimentViewStore.getState().fetchExperiments(config.siteId);
                callbacks.onRunComplete();
              },
              onError: callbacks.onError,
            },
            controller,
          );
        },
      },
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

  reset: () => {
    get().abortController?.abort();
    set({
      isRunning: false,
      hasOptimization: false,
      progress: null,
      trialHistory: [],
      stepAnalysisItems: EMPTY_LIVE_ITEMS,
      error: null,
      abortController: null,
      runningConfig: null,
    });
  },
}));
