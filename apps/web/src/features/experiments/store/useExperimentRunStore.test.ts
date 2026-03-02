import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ExperimentConfig, ExperimentProgressData } from "@pathfinder/shared";
import type { StepAnalysisLiveItems, TrialHistoryEntry } from "../types";
import type { StreamRunnerCallbacks } from "../utils/experimentStreamRunner";

/* ── Mocks ─────────────────────────────────────────────────────────── */

// Capture the callbacks that runExperimentStream passes to the stream opener
// so we can simulate progress / complete / error events in tests.
let capturedCallbacks: StreamRunnerCallbacks | null = null;
let capturedController: AbortController | null = null;

vi.mock("../utils/experimentStreamRunner", async (importOriginal) => {
  const original =
    await importOriginal<typeof import("../utils/experimentStreamRunner")>();
  return {
    ...original,
    runExperimentStream: vi.fn(({ set, get }, opts) => {
      // Mirror the real runner's init logic so the store state updates
      get().abortController?.abort();
      const controller = new AbortController();
      set({
        isRunning: true,
        hasOptimization: opts.hasOptimization,
        progress: null,
        trialHistory: [],
        stepAnalysisItems: original.EMPTY_LIVE_ITEMS,
        error: null,
        runningConfig: opts.config,
        abortController: controller,
      });
      capturedController = controller;

      // Capture the callbacks by calling openStream the same way the real runner does
      const callbacks: StreamRunnerCallbacks = {
        onProgress: (data: ExperimentProgressData) => {
          set(
            (s: {
              trialHistory: TrialHistoryEntry[];
              stepAnalysisItems: StepAnalysisLiveItems;
            }) => ({
              progress: data,
              trialHistory: original.accumulateTrial(s.trialHistory, data),
              stepAnalysisItems: original.accumulateStepAnalysis(
                s.stepAnalysisItems,
                data,
              ),
            }),
          );
        },
        onRunComplete: () => {
          set({
            isRunning: false,
            abortController: null,
            runningConfig: null,
          });
        },
        onError: (error: string) => {
          set({
            error,
            isRunning: false,
            abortController: null,
            runningConfig: null,
          });
        },
      };
      capturedCallbacks = callbacks;
      opts.openStream(callbacks, controller);
    }),
  };
});

vi.mock("../api", () => ({
  createExperimentStream: vi.fn(),
  createBatchExperimentStream: vi.fn(),
  createBenchmarkStream: vi.fn(),
}));

vi.mock("./useExperimentViewStore", () => ({
  useExperimentViewStore: {
    setState: vi.fn(),
    getState: vi.fn(() => ({
      fetchExperiments: vi.fn(),
    })),
  },
}));

// Import store after mocks are set up
const { useExperimentRunStore } = await import("./useExperimentRunStore");
const { EMPTY_LIVE_ITEMS } = await import("../utils/experimentStreamRunner");

/* ── Factory ───────────────────────────────────────────────────────── */

function makeConfig(overrides: Partial<ExperimentConfig> = {}): ExperimentConfig {
  return {
    siteId: "plasmodb",
    recordType: "gene",
    searchName: "geneById",
    parameters: {},
    positiveControls: ["g1"],
    negativeControls: ["g2"],
    controlsSearchName: "geneById",
    controlsParamName: "gene_ids",
    enableCrossValidation: false,
    kFolds: 5,
    enrichmentTypes: [],
    name: "Test Experiment",
    ...overrides,
  };
}

function makeProgressData(
  overrides: Partial<ExperimentProgressData> = {},
): ExperimentProgressData {
  return {
    experimentId: "exp-1",
    phase: "running",
    message: "Processing...",
    ...overrides,
  } as ExperimentProgressData;
}

function makeStepEvaluation(overrides: Record<string, unknown> = {}) {
  return {
    stepId: "s1",
    searchName: "geneById",
    displayName: "Gene ID",
    resultCount: 100,
    positiveHits: 5,
    positiveTotal: 10,
    negativeHits: 1,
    negativeTotal: 10,
    recall: 0.5,
    falsePositiveRate: 0.1,
    capturedPositiveIds: [],
    capturedNegativeIds: [],
    tpMovement: 0,
    fpMovement: 0,
    fnMovement: 0,
    contribution: 0.5,
    score: 0.8,
    ...overrides,
  };
}

/* ── Tests ──────────────────────────────────────────────────────────── */

describe("features/experiments/store/useExperimentRunStore", () => {
  beforeEach(() => {
    useExperimentRunStore.getState().reset();
    capturedCallbacks = null;
    capturedController = null;
    vi.clearAllMocks();
  });

  /* ── Initial state ─────────────────────────────────────────────── */

  it("has correct initial state", () => {
    const state = useExperimentRunStore.getState();
    expect(state.isRunning).toBe(false);
    expect(state.hasOptimization).toBe(false);
    expect(state.progress).toBeNull();
    expect(state.trialHistory).toEqual([]);
    expect(state.stepAnalysisItems).toEqual(EMPTY_LIVE_ITEMS);
    expect(state.error).toBeNull();
    expect(state.abortController).toBeNull();
    expect(state.runningConfig).toBeNull();
  });

  /* ── clearError ────────────────────────────────────────────────── */

  it("clearError sets error to null", () => {
    useExperimentRunStore.setState({ error: "something broke" });
    expect(useExperimentRunStore.getState().error).toBe("something broke");

    useExperimentRunStore.getState().clearError();
    expect(useExperimentRunStore.getState().error).toBeNull();
  });

  it("clearError is a no-op when error is already null", () => {
    useExperimentRunStore.getState().clearError();
    expect(useExperimentRunStore.getState().error).toBeNull();
  });

  /* ── setError via setState ─────────────────────────────────────── */

  it("setting error directly updates state", () => {
    useExperimentRunStore.setState({ error: "Direct error" });
    expect(useExperimentRunStore.getState().error).toBe("Direct error");
  });

  /* ── runExperiment ─────────────────────────────────────────────── */

  it("runExperiment transitions to running state", () => {
    const config = makeConfig();
    useExperimentRunStore.getState().runExperiment(config);

    const state = useExperimentRunStore.getState();
    expect(state.isRunning).toBe(true);
    expect(state.runningConfig).toEqual(config);
    expect(state.progress).toBeNull();
    expect(state.error).toBeNull();
    expect(state.abortController).not.toBeNull();
  });

  it("runExperiment sets hasOptimization when optimizationSpecs exist", () => {
    const config = makeConfig({
      optimizationSpecs: [{ name: "p", type: "numeric" as const, min: 0, max: 1 }],
    } as Partial<ExperimentConfig>);

    useExperimentRunStore.getState().runExperiment(config);

    expect(useExperimentRunStore.getState().hasOptimization).toBe(true);
  });

  it("runExperiment sets hasOptimization when enableStepAnalysis is true", () => {
    const config = makeConfig({ enableStepAnalysis: true });

    useExperimentRunStore.getState().runExperiment(config);

    expect(useExperimentRunStore.getState().hasOptimization).toBe(true);
  });

  it("runExperiment resets previous state (progress, trials, errors)", () => {
    useExperimentRunStore.setState({
      progress: makeProgressData(),
      trialHistory: [{ trialNumber: 1, score: 0.5, bestScore: 0.5 }],
      error: "old error",
    });

    useExperimentRunStore.getState().runExperiment(makeConfig());

    const state = useExperimentRunStore.getState();
    expect(state.progress).toBeNull();
    expect(state.trialHistory).toEqual([]);
    expect(state.error).toBeNull();
  });

  /* ── Progress updates via callbacks ────────────────────────────── */

  it("onProgress updates progress state", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());
    expect(capturedCallbacks).not.toBeNull();

    const progressData = makeProgressData({ message: "Almost done" });
    capturedCallbacks!.onProgress(progressData);

    expect(useExperimentRunStore.getState().progress).toEqual(progressData);
  });

  /* ── Trial history accumulation ────────────────────────────────── */

  it("onProgress accumulates trial history entries", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());

    const progress1 = makeProgressData({
      trialProgress: {
        currentTrial: 1,
        totalTrials: 3,
        trial: {
          trialNumber: 1,
          score: 0.6,
          recall: null,
          falsePositiveRate: null,
          resultCount: null,
          parameters: {},
        },
        bestTrial: { trialNumber: 1, score: 0.6, parameters: {} },
        recentTrials: [],
      },
    } as Partial<ExperimentProgressData>);
    capturedCallbacks!.onProgress(progress1);

    expect(useExperimentRunStore.getState().trialHistory).toHaveLength(1);
    expect(useExperimentRunStore.getState().trialHistory[0]).toEqual({
      trialNumber: 1,
      score: 0.6,
      bestScore: 0.6,
    });

    const progress2 = makeProgressData({
      trialProgress: {
        currentTrial: 2,
        totalTrials: 3,
        trial: {
          trialNumber: 2,
          score: 0.8,
          recall: null,
          falsePositiveRate: null,
          resultCount: null,
          parameters: {},
        },
        bestTrial: { trialNumber: 2, score: 0.8, parameters: {} },
        recentTrials: [],
      },
    } as Partial<ExperimentProgressData>);
    capturedCallbacks!.onProgress(progress2);

    expect(useExperimentRunStore.getState().trialHistory).toHaveLength(2);
    expect(useExperimentRunStore.getState().trialHistory[1].trialNumber).toBe(2);
  });

  it("onProgress does not duplicate trial entries with the same trialNumber", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());

    const progress = makeProgressData({
      trialProgress: {
        currentTrial: 1,
        totalTrials: 3,
        trial: {
          trialNumber: 1,
          score: 0.6,
          recall: null,
          falsePositiveRate: null,
          resultCount: null,
          parameters: {},
        },
        bestTrial: { trialNumber: 1, score: 0.6, parameters: {} },
        recentTrials: [],
      },
    } as Partial<ExperimentProgressData>);

    capturedCallbacks!.onProgress(progress);
    capturedCallbacks!.onProgress(progress);

    expect(useExperimentRunStore.getState().trialHistory).toHaveLength(1);
  });

  /* ── Step analysis live items ──────────────────────────────────── */

  it("onProgress accumulates step analysis evaluations", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());

    const progress = makeProgressData({
      stepAnalysisProgress: {
        phase: "step_evaluation" as const,
        message: "Evaluating step",
        stepEvaluation: makeStepEvaluation(),
      },
    } as Partial<ExperimentProgressData>);
    capturedCallbacks!.onProgress(progress);

    const items = useExperimentRunStore.getState().stepAnalysisItems;
    expect(items.evaluations).toHaveLength(1);
    expect(items.evaluations[0].stepId).toBe("s1");
  });

  it("onProgress does not duplicate step analysis evaluations", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());

    const progress = makeProgressData({
      stepAnalysisProgress: {
        phase: "step_evaluation" as const,
        message: "Evaluating step",
        stepEvaluation: makeStepEvaluation(),
      },
    } as Partial<ExperimentProgressData>);

    capturedCallbacks!.onProgress(progress);
    capturedCallbacks!.onProgress(progress);

    expect(useExperimentRunStore.getState().stepAnalysisItems.evaluations).toHaveLength(
      1,
    );
  });

  /* ── onRunComplete ─────────────────────────────────────────────── */

  it("onRunComplete transitions out of running state", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());
    expect(useExperimentRunStore.getState().isRunning).toBe(true);

    capturedCallbacks!.onRunComplete();

    const state = useExperimentRunStore.getState();
    expect(state.isRunning).toBe(false);
    expect(state.abortController).toBeNull();
    expect(state.runningConfig).toBeNull();
  });

  /* ── onError ───────────────────────────────────────────────────── */

  it("onError sets error and stops running", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());

    capturedCallbacks!.onError("Stream failed");

    const state = useExperimentRunStore.getState();
    expect(state.error).toBe("Stream failed");
    expect(state.isRunning).toBe(false);
    expect(state.abortController).toBeNull();
    expect(state.runningConfig).toBeNull();
  });

  /* ── cancelExperiment ──────────────────────────────────────────── */

  it("cancelExperiment aborts the controller and stops running", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());
    const controller = useExperimentRunStore.getState().abortController;
    expect(controller).not.toBeNull();

    useExperimentRunStore.getState().cancelExperiment();

    expect(controller!.signal.aborted).toBe(true);
    const state = useExperimentRunStore.getState();
    expect(state.isRunning).toBe(false);
    expect(state.hasOptimization).toBe(false);
    expect(state.abortController).toBeNull();
    expect(state.runningConfig).toBeNull();
  });

  it("cancelExperiment is safe when nothing is running", () => {
    expect(() => {
      useExperimentRunStore.getState().cancelExperiment();
    }).not.toThrow();

    expect(useExperimentRunStore.getState().isRunning).toBe(false);
  });

  /* ── reset ─────────────────────────────────────────────────────── */

  it("reset aborts controller and restores all state to defaults", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());
    const controller = useExperimentRunStore.getState().abortController;

    useExperimentRunStore.getState().reset();

    expect(controller!.signal.aborted).toBe(true);
    const state = useExperimentRunStore.getState();
    expect(state.isRunning).toBe(false);
    expect(state.hasOptimization).toBe(false);
    expect(state.progress).toBeNull();
    expect(state.trialHistory).toEqual([]);
    expect(state.stepAnalysisItems).toEqual(EMPTY_LIVE_ITEMS);
    expect(state.error).toBeNull();
    expect(state.abortController).toBeNull();
    expect(state.runningConfig).toBeNull();
  });

  it("reset is safe when no controller exists", () => {
    expect(() => {
      useExperimentRunStore.getState().reset();
    }).not.toThrow();
  });

  /* ── Running state transitions ─────────────────────────────────── */

  it("full lifecycle: idle -> running -> progress -> complete -> idle", () => {
    // Idle
    expect(useExperimentRunStore.getState().isRunning).toBe(false);

    // Start run
    useExperimentRunStore.getState().runExperiment(makeConfig());
    expect(useExperimentRunStore.getState().isRunning).toBe(true);

    // Progress update
    capturedCallbacks!.onProgress(makeProgressData({ message: "50% done" }));
    expect(useExperimentRunStore.getState().progress?.message).toBe("50% done");
    expect(useExperimentRunStore.getState().isRunning).toBe(true);

    // Complete
    capturedCallbacks!.onRunComplete();
    expect(useExperimentRunStore.getState().isRunning).toBe(false);
    // Progress is preserved after completion (not cleared)
    expect(useExperimentRunStore.getState().progress).not.toBeNull();
  });

  it("full lifecycle: idle -> running -> error -> idle", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());
    expect(useExperimentRunStore.getState().isRunning).toBe(true);

    capturedCallbacks!.onError("Something went wrong");

    const state = useExperimentRunStore.getState();
    expect(state.isRunning).toBe(false);
    expect(state.error).toBe("Something went wrong");
  });

  it("full lifecycle: idle -> running -> cancel -> idle", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig());
    expect(useExperimentRunStore.getState().isRunning).toBe(true);

    useExperimentRunStore.getState().cancelExperiment();

    expect(useExperimentRunStore.getState().isRunning).toBe(false);
    expect(useExperimentRunStore.getState().abortController).toBeNull();
  });

  /* ── runBatchExperiment ────────────────────────────────────────── */

  it("runBatchExperiment transitions to running state with hasOptimization false", () => {
    const config = makeConfig();
    useExperimentRunStore.getState().runBatchExperiment(config, "organism", [
      {
        organism: "Plasmodium falciparum",
        positiveControls: ["g1"],
        negativeControls: ["g2"],
      },
    ]);

    const state = useExperimentRunStore.getState();
    expect(state.isRunning).toBe(true);
    expect(state.hasOptimization).toBe(false);
    expect(state.runningConfig).toEqual(config);
  });

  /* ── runBenchmark ──────────────────────────────────────────────── */

  it("runBenchmark transitions to running state", () => {
    const config = makeConfig();
    useExperimentRunStore.getState().runBenchmark(config, [
      {
        label: "Set A",
        positiveControls: ["g1"],
        negativeControls: ["g2"],
        isPrimary: true,
      },
    ]);

    const state = useExperimentRunStore.getState();
    expect(state.isRunning).toBe(true);
    expect(state.hasOptimization).toBe(false);
    expect(state.runningConfig).toEqual(config);
  });

  /* ── Re-running aborts previous ────────────────────────────────── */

  it("starting a new run aborts the previous one", () => {
    useExperimentRunStore.getState().runExperiment(makeConfig({ name: "Run 1" }));
    const firstController = useExperimentRunStore.getState().abortController;
    expect(firstController).not.toBeNull();

    useExperimentRunStore.getState().runExperiment(makeConfig({ name: "Run 2" }));

    expect(firstController!.signal.aborted).toBe(true);
    const state = useExperimentRunStore.getState();
    expect(state.isRunning).toBe(true);
    expect(state.runningConfig?.name).toBe("Run 2");
  });
});
