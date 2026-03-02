import { beforeEach, describe, expect, it, vi } from "vitest";
import { useExperimentViewStore } from "./useExperimentViewStore";
import type {
  Experiment,
  ExperimentSummary,
  ExperimentConfig,
} from "@pathfinder/shared";

/* ── Mocks ─────────────────────────────────────────────────────────── */

vi.mock("../api", () => ({
  listExperiments: vi.fn(),
  getExperiment: vi.fn(),
  deleteExperiment: vi.fn(),
}));

// Lazy import so the mock is in place before we grab references
const api = await import("../api");
const listExperimentsMock = vi.mocked(api.listExperiments);
const getExperimentMock = vi.mocked(api.getExperiment);
const deleteExperimentMock = vi.mocked(api.deleteExperiment);

/* ── Factories ─────────────────────────────────────────────────────── */

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

function makeExperiment(overrides: Partial<Experiment> = {}): Experiment {
  return {
    id: "exp-1",
    config: makeConfig(),
    status: "completed",
    metrics: null,
    crossValidation: null,
    enrichmentResults: [],
    truePositiveGenes: [],
    falseNegativeGenes: [],
    falsePositiveGenes: [],
    trueNegativeGenes: [],
    optimizationResult: null,
    notes: null,
    batchId: null,
    benchmarkId: null,
    controlSetLabel: null,
    isPrimaryBenchmark: false,
    error: null,
    totalTimeSeconds: null,
    createdAt: "2026-01-01T00:00:00Z",
    completedAt: null,
    wdkStrategyId: null,
    wdkStepId: null,
    stepAnalysis: null,
    rankMetrics: null,
    robustness: null,
    treeOptimization: null,
    ...overrides,
  };
}

function makeSummary(overrides: Partial<ExperimentSummary> = {}): ExperimentSummary {
  return {
    id: "exp-1",
    name: "Test Experiment",
    siteId: "plasmodb",
    searchName: "geneById",
    recordType: "gene",
    status: "completed",
    f1Score: 0.85,
    sensitivity: 0.9,
    specificity: 0.8,
    totalPositives: 10,
    totalNegatives: 5,
    createdAt: "2026-01-01T00:00:00Z",
    batchId: null,
    benchmarkId: null,
    controlSetLabel: null,
    isPrimaryBenchmark: false,
    ...overrides,
  };
}

/* ── Tests ──────────────────────────────────────────────────────────── */

describe("features/experiments/store/useExperimentViewStore", () => {
  beforeEach(() => {
    useExperimentViewStore.getState().reset();
    vi.clearAllMocks();
  });

  /* ── Initial state ─────────────────────────────────────────────── */

  it("has correct initial state", () => {
    const state = useExperimentViewStore.getState();
    expect(state.view).toBe("list");
    expect(state.experiments).toEqual([]);
    expect(state.currentExperiment).toBeNull();
    expect(state.compareExperiment).toBeNull();
    expect(state.benchmarkExperiments).toEqual([]);
    expect(state.cloneConfig).toBeNull();
    expect(state.cloneWithOptimize).toBe(false);
    expect(state.error).toBeNull();
  });

  /* ── setView ───────────────────────────────────────────────────── */

  it("setView changes the current view", () => {
    useExperimentViewStore.getState().setView("setup");
    expect(useExperimentViewStore.getState().view).toBe("setup");
  });

  it("setView supports all view values", () => {
    const views = [
      "list",
      "mode-select",
      "setup",
      "multi-step-setup",
      "results",
      "compare",
      "overlap",
      "enrichment-compare",
      "benchmark-results",
    ] as const;

    for (const view of views) {
      useExperimentViewStore.getState().setView(view);
      expect(useExperimentViewStore.getState().view).toBe(view);
    }
  });

  /* ── fetchExperiments ──────────────────────────────────────────── */

  it("fetchExperiments populates the experiments list", async () => {
    const summaries = [makeSummary({ id: "a" }), makeSummary({ id: "b" })];
    listExperimentsMock.mockResolvedValueOnce(summaries);

    await useExperimentViewStore.getState().fetchExperiments("plasmodb");

    expect(listExperimentsMock).toHaveBeenCalledWith("plasmodb");
    expect(useExperimentViewStore.getState().experiments).toEqual(summaries);
  });

  it("fetchExperiments sets error on failure", async () => {
    listExperimentsMock.mockRejectedValueOnce(new Error("Network error"));

    await useExperimentViewStore.getState().fetchExperiments("plasmodb");

    expect(useExperimentViewStore.getState().error).toBe("Error: Network error");
  });

  /* ── loadExperiment ────────────────────────────────────────────── */

  it("loadExperiment sets currentExperiment and switches to results view", async () => {
    const experiment = makeExperiment({ id: "exp-42" });
    getExperimentMock.mockResolvedValueOnce(experiment);

    await useExperimentViewStore.getState().loadExperiment("exp-42");

    const state = useExperimentViewStore.getState();
    expect(state.currentExperiment).toEqual(experiment);
    expect(state.view).toBe("results");
    expect(getExperimentMock).toHaveBeenCalledWith("exp-42");
  });

  it("loadExperiment sets error on failure", async () => {
    getExperimentMock.mockRejectedValueOnce(new Error("Not found"));

    await useExperimentViewStore.getState().loadExperiment("bad-id");

    expect(useExperimentViewStore.getState().error).toBe("Error: Not found");
    expect(useExperimentViewStore.getState().currentExperiment).toBeNull();
  });

  /* ── loadCompareExperiment ─────────────────────────────────────── */

  it("loadCompareExperiment sets compareExperiment and switches to compare view", async () => {
    const experiment = makeExperiment({ id: "exp-compare" });
    getExperimentMock.mockResolvedValueOnce(experiment);

    await useExperimentViewStore.getState().loadCompareExperiment("exp-compare");

    const state = useExperimentViewStore.getState();
    expect(state.compareExperiment).toEqual(experiment);
    expect(state.view).toBe("compare");
  });

  it("loadCompareExperiment sets error on failure", async () => {
    getExperimentMock.mockRejectedValueOnce(new Error("Failed"));

    await useExperimentViewStore.getState().loadCompareExperiment("bad-id");

    expect(useExperimentViewStore.getState().error).toBe("Error: Failed");
    expect(useExperimentViewStore.getState().compareExperiment).toBeNull();
  });

  /* ── clearCompare ──────────────────────────────────────────────── */

  it("clearCompare nulls compareExperiment and returns to results view", async () => {
    const experiment = makeExperiment({ id: "exp-compare" });
    getExperimentMock.mockResolvedValueOnce(experiment);
    await useExperimentViewStore.getState().loadCompareExperiment("exp-compare");

    useExperimentViewStore.getState().clearCompare();

    const state = useExperimentViewStore.getState();
    expect(state.compareExperiment).toBeNull();
    expect(state.view).toBe("results");
  });

  /* ── deleteExperiment ──────────────────────────────────────────── */

  it("deleteExperiment removes from list", async () => {
    const summaries = [makeSummary({ id: "a" }), makeSummary({ id: "b" })];
    listExperimentsMock.mockResolvedValueOnce(summaries);
    await useExperimentViewStore.getState().fetchExperiments("plasmodb");

    deleteExperimentMock.mockResolvedValueOnce(undefined);
    await useExperimentViewStore.getState().deleteExperiment("a");

    const remaining = useExperimentViewStore.getState().experiments;
    expect(remaining).toHaveLength(1);
    expect(remaining[0].id).toBe("b");
  });

  it("deleteExperiment clears currentExperiment and returns to list if it was the active one", async () => {
    const experiment = makeExperiment({ id: "exp-1" });
    getExperimentMock.mockResolvedValueOnce(experiment);
    await useExperimentViewStore.getState().loadExperiment("exp-1");
    expect(useExperimentViewStore.getState().view).toBe("results");

    deleteExperimentMock.mockResolvedValueOnce(undefined);
    await useExperimentViewStore.getState().deleteExperiment("exp-1");

    const state = useExperimentViewStore.getState();
    expect(state.currentExperiment).toBeNull();
    expect(state.view).toBe("list");
  });

  it("deleteExperiment keeps currentExperiment if a different one is deleted", async () => {
    const experiment = makeExperiment({ id: "exp-1" });
    getExperimentMock.mockResolvedValueOnce(experiment);
    await useExperimentViewStore.getState().loadExperiment("exp-1");

    deleteExperimentMock.mockResolvedValueOnce(undefined);
    await useExperimentViewStore.getState().deleteExperiment("other-id");

    const state = useExperimentViewStore.getState();
    expect(state.currentExperiment).toEqual(experiment);
    expect(state.view).toBe("results");
  });

  it("deleteExperiment sets error on failure", async () => {
    deleteExperimentMock.mockRejectedValueOnce(new Error("Delete failed"));

    await useExperimentViewStore.getState().deleteExperiment("exp-1");

    expect(useExperimentViewStore.getState().error).toBe("Error: Delete failed");
  });

  /* ── cloneExperiment ───────────────────────────────────────────── */

  it("cloneExperiment loads config and switches to setup view", async () => {
    const config = makeConfig({ name: "Clone Me" });
    const experiment = makeExperiment({ id: "exp-clone", config });
    getExperimentMock.mockResolvedValueOnce(experiment);

    await useExperimentViewStore.getState().cloneExperiment("exp-clone");

    const state = useExperimentViewStore.getState();
    expect(state.cloneConfig).toEqual(config);
    expect(state.view).toBe("setup");
  });

  it("cloneExperiment sets error on failure", async () => {
    getExperimentMock.mockRejectedValueOnce(new Error("Clone failed"));

    await useExperimentViewStore.getState().cloneExperiment("bad-id");

    expect(useExperimentViewStore.getState().error).toBe("Error: Clone failed");
  });

  /* ── setClone / clearClone ─────────────────────────────────────── */

  it("setClone sets cloneConfig and switches to setup view", () => {
    const config = makeConfig({ name: "Manual Clone" });

    useExperimentViewStore.getState().setClone(config);

    const state = useExperimentViewStore.getState();
    expect(state.cloneConfig).toEqual(config);
    expect(state.view).toBe("setup");
  });

  it("clearClone nulls cloneConfig and resets cloneWithOptimize", () => {
    const config = makeConfig();
    useExperimentViewStore.getState().setClone(config);
    useExperimentViewStore.setState({ cloneWithOptimize: true });

    useExperimentViewStore.getState().clearClone();

    const state = useExperimentViewStore.getState();
    expect(state.cloneConfig).toBeNull();
    expect(state.cloneWithOptimize).toBe(false);
  });

  /* ── optimizeFromEvaluation ────────────────────────────────────── */

  it("optimizeFromEvaluation sets clone config with parentExperimentId for single-step mode", async () => {
    const config = makeConfig({ mode: undefined });
    const experiment = makeExperiment({ id: "exp-opt", config });
    getExperimentMock.mockResolvedValueOnce(experiment);

    await useExperimentViewStore.getState().optimizeFromEvaluation("exp-opt");

    const state = useExperimentViewStore.getState();
    expect(state.cloneConfig).not.toBeNull();
    expect(
      (state.cloneConfig as ExperimentConfig & { parentExperimentId: string })
        .parentExperimentId,
    ).toBe("exp-opt");
    expect(state.cloneWithOptimize).toBe(true);
    expect(state.view).toBe("setup");
  });

  it("optimizeFromEvaluation navigates to multi-step-setup for multi-step mode", async () => {
    const config = makeConfig({ mode: "multi-step" });
    const experiment = makeExperiment({ id: "exp-ms", config });
    getExperimentMock.mockResolvedValueOnce(experiment);

    await useExperimentViewStore.getState().optimizeFromEvaluation("exp-ms");

    const state = useExperimentViewStore.getState();
    expect(state.cloneConfig?.enableStepAnalysis).toBe(true);
    expect(state.cloneWithOptimize).toBe(true);
    expect(state.view).toBe("multi-step-setup");
  });

  it("optimizeFromEvaluation navigates to multi-step-setup for import mode", async () => {
    const config = makeConfig({ mode: "import" });
    const experiment = makeExperiment({ id: "exp-imp", config });
    getExperimentMock.mockResolvedValueOnce(experiment);

    await useExperimentViewStore.getState().optimizeFromEvaluation("exp-imp");

    const state = useExperimentViewStore.getState();
    expect(state.view).toBe("multi-step-setup");
    expect(state.cloneConfig?.enableStepAnalysis).toBe(true);
  });

  it("optimizeFromEvaluation sets error on failure", async () => {
    getExperimentMock.mockRejectedValueOnce(new Error("Optimize failed"));

    await useExperimentViewStore.getState().optimizeFromEvaluation("bad-id");

    expect(useExperimentViewStore.getState().error).toBe("Error: Optimize failed");
  });

  /* ── clearError ────────────────────────────────────────────────── */

  it("clearError sets error to null", () => {
    useExperimentViewStore.setState({ error: "something broke" });

    useExperimentViewStore.getState().clearError();

    expect(useExperimentViewStore.getState().error).toBeNull();
  });

  /* ── reset ─────────────────────────────────────────────────────── */

  it("reset restores default state but keeps experiments list", async () => {
    // Set up some state
    const experiment = makeExperiment({ id: "exp-1" });
    getExperimentMock.mockResolvedValueOnce(experiment);
    await useExperimentViewStore.getState().loadExperiment("exp-1");
    useExperimentViewStore.setState({ error: "oops" });

    useExperimentViewStore.getState().reset();

    const state = useExperimentViewStore.getState();
    expect(state.view).toBe("list");
    expect(state.currentExperiment).toBeNull();
    expect(state.compareExperiment).toBeNull();
    expect(state.benchmarkExperiments).toEqual([]);
    expect(state.cloneConfig).toBeNull();
    expect(state.cloneWithOptimize).toBe(false);
    expect(state.error).toBeNull();
  });

  /* ── View state transitions ────────────────────────────────────── */

  it("transitions: list -> results (via loadExperiment) -> compare (via loadCompareExperiment) -> results (via clearCompare)", async () => {
    const exp1 = makeExperiment({ id: "exp-1" });
    const exp2 = makeExperiment({ id: "exp-2" });

    getExperimentMock.mockResolvedValueOnce(exp1);
    await useExperimentViewStore.getState().loadExperiment("exp-1");
    expect(useExperimentViewStore.getState().view).toBe("results");

    getExperimentMock.mockResolvedValueOnce(exp2);
    await useExperimentViewStore.getState().loadCompareExperiment("exp-2");
    expect(useExperimentViewStore.getState().view).toBe("compare");

    useExperimentViewStore.getState().clearCompare();
    expect(useExperimentViewStore.getState().view).toBe("results");
  });

  it("transitions: list -> setup (via setClone) -> list (via reset)", () => {
    useExperimentViewStore.getState().setClone(makeConfig());
    expect(useExperimentViewStore.getState().view).toBe("setup");

    useExperimentViewStore.getState().reset();
    expect(useExperimentViewStore.getState().view).toBe("list");
  });
});
