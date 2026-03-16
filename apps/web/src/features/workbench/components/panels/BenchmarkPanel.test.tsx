// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { Experiment, ControlSet } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Mock the workbench store
// ---------------------------------------------------------------------------

const storeState: Record<string, unknown> = {
  activeSetId: "set-1",
  geneSets: [
    {
      id: "set-1",
      name: "Test Set",
      siteId: "PlasmoDB",
      geneIds: ["PF3D7_0100100"],
      geneCount: 1,
      source: "strategy",
      searchName: "GenesByTaxon",
      recordType: "gene",
      parameters: { organism: "Plasmodium falciparum 3D7" },
    },
  ],
  expandedPanels: new Set(["benchmark"]),
  togglePanel: vi.fn(),
  setLastExperiment: vi.fn(),
};

vi.mock("../../store", () => ({
  useWorkbenchStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector(storeState),
}));
vi.mock("../../store/useWorkbenchStore", () => ({
  useWorkbenchStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector(storeState),
}));

// ---------------------------------------------------------------------------
// Mock gene API used by GeneChipInput
// ---------------------------------------------------------------------------

const mockResolveGeneIds = vi.fn();
const mockSearchGenes = vi.fn();
vi.mock("@/lib/api/genes", () => ({
  resolveGeneIds: (...args: unknown[]) => mockResolveGeneIds(...args),
  searchGenes: (...args: unknown[]) => mockSearchGenes(...args),
}));

// ---------------------------------------------------------------------------
// Mock the control sets + benchmark streaming APIs
// ---------------------------------------------------------------------------

const mockListControlSets = vi.fn<() => Promise<ControlSet[]>>();
const mockCreateBenchmarkStream = vi.fn();

vi.mock("../../api", () => ({
  listControlSets: (...args: unknown[]) => mockListControlSets(...(args as [])),
  createBenchmarkStream: (...args: unknown[]) =>
    mockCreateBenchmarkStream(...(args as [])),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { BenchmarkPanel } from "./BenchmarkPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeControlSet(overrides: Partial<ControlSet> = {}): ControlSet {
  return {
    id: "cs-1",
    name: "Curated Controls",
    siteId: "PlasmoDB",
    recordType: "gene",
    positiveIds: ["PF3D7_0100100", "PF3D7_0100200"],
    negativeIds: ["PF3D7_0900100"],
    source: "curation",
    tags: [],
    provenanceNotes: "",
    version: 1,
    isPublic: false,
    createdAt: "2026-03-09T00:00:00Z",
    ...overrides,
  };
}

function makeExperiment(overrides: Partial<Experiment> = {}): Experiment {
  return {
    id: "exp-1",
    config: {
      siteId: "PlasmoDB",
      recordType: "gene",
      searchName: "GenesByTaxon",
      parameters: {},
      positiveControls: ["PF3D7_0100100"],
      negativeControls: [],
      controlsSearchName: "GeneByLocusTag",
      controlsParamName: "ds_gene_ids",
      controlsValueFormat: "newline",
      enableCrossValidation: false,
      kFolds: 5,
      enrichmentTypes: [],
      name: "Benchmark: Curated Controls",
      description: "",
      mode: "single",
      optimizationBudget: 30,
      optimizationObjective: "balanced_accuracy",
      enableStepAnalysis: false,
      treeOptimizationObjective: "precision_at_50",
      treeOptimizationBudget: 50,
      sortDirection: "ASC",
    },
    status: "completed",
    metrics: {
      confusionMatrix: {
        truePositives: 40,
        falsePositives: 10,
        falseNegatives: 10,
        trueNegatives: 90,
      },
      sensitivity: 0.8,
      specificity: 0.9,
      precision: 0.8,
      negativePredictiveValue: 0.9,
      falsePositiveRate: 0.1,
      falseNegativeRate: 0.2,
      f1Score: 0.8,
      mcc: 0.7,
      balancedAccuracy: 0.85,
      youdensJ: 0.7,
      totalResults: 150,
      totalPositives: 50,
      totalNegatives: 100,
    },
    crossValidation: null,
    enrichmentResults: [],
    truePositiveGenes: [],
    falseNegativeGenes: [],
    falsePositiveGenes: [],
    trueNegativeGenes: [],
    optimizationResult: null,
    notes: null,
    batchId: null,
    benchmarkId: "bench-1",
    controlSetLabel: "Curated Controls",
    isPrimaryBenchmark: true,
    error: null,
    totalTimeSeconds: 5,
    createdAt: "2026-03-09T00:00:00Z",
    completedAt: "2026-03-09T00:01:00Z",
    wdkStrategyId: null,
    wdkStepId: null,
    stepAnalysis: null,
    rankMetrics: null,
    robustness: null,
    treeOptimization: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BenchmarkPanel", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  beforeEach(() => {
    storeState.activeSetId = "set-1";
    storeState.geneSets = [
      {
        id: "set-1",
        name: "Test Set",
        siteId: "PlasmoDB",
        geneIds: ["PF3D7_0100100"],
        geneCount: 1,
        source: "strategy",
        searchName: "GenesByTaxon",
        recordType: "gene",
        parameters: { organism: "Plasmodium falciparum 3D7" },
      },
    ];
    storeState.expandedPanels = new Set(["benchmark"]);
    mockListControlSets.mockResolvedValue([]);
    mockResolveGeneIds.mockResolvedValue({ resolved: [], unresolved: [] });
    mockSearchGenes.mockResolvedValue({ results: [], total: 0 });
  });

  it("is disabled when no active gene set has search context", () => {
    storeState.geneSets = [
      {
        id: "set-1",
        name: "Plain Set",
        siteId: "PlasmoDB",
        geneIds: ["PF3D7_0100100"],
        geneCount: 1,
        source: "paste",
        // no searchName or parameters
      },
    ];

    render(<BenchmarkPanel />);

    // Panel header renders but content does not (disabled)
    expect(screen.getByText("Benchmark")).toBeTruthy();
    expect(screen.queryByText("Run Benchmark")).toBeNull();
  });

  it("renders control set selection form when enabled", async () => {
    mockListControlSets.mockResolvedValue([makeControlSet()]);

    render(<BenchmarkPanel />);

    // Wait for control sets to load
    await waitFor(() => {
      expect(screen.getByText("Curated Controls")).toBeTruthy();
    });

    expect(screen.getByText("Run Benchmark")).toBeTruthy();
  });

  it("shows comparison table after benchmark completes", async () => {
    const primaryExperiment = makeExperiment({
      controlSetLabel: "Primary Set",
      isPrimaryBenchmark: true,
      metrics: {
        confusionMatrix: {
          truePositives: 40,
          falsePositives: 10,
          falseNegatives: 10,
          trueNegatives: 90,
        },
        sensitivity: 0.8,
        specificity: 0.9,
        precision: 0.8,
        negativePredictiveValue: 0.9,
        falsePositiveRate: 0.1,
        falseNegativeRate: 0.2,
        f1Score: 0.8,
        mcc: 0.7,
        balancedAccuracy: 0.85,
        youdensJ: 0.7,
        totalResults: 150,
        totalPositives: 50,
        totalNegatives: 100,
      },
    });

    const secondaryExperiment = makeExperiment({
      id: "exp-2",
      controlSetLabel: "Secondary Set",
      isPrimaryBenchmark: false,
      metrics: {
        confusionMatrix: {
          truePositives: 30,
          falsePositives: 20,
          falseNegatives: 20,
          trueNegatives: 80,
        },
        sensitivity: 0.6,
        specificity: 0.8,
        precision: 0.6,
        negativePredictiveValue: 0.8,
        falsePositiveRate: 0.2,
        falseNegativeRate: 0.4,
        f1Score: 0.6,
        mcc: 0.4,
        balancedAccuracy: 0.7,
        youdensJ: 0.4,
        totalResults: 150,
        totalPositives: 50,
        totalNegatives: 100,
      },
    });

    mockCreateBenchmarkStream.mockImplementation(
      (
        _base: unknown,
        _cs: unknown,
        handlers: { onComplete?: (exps: Experiment[], id: string) => void },
      ) => {
        // Simulate immediate completion
        handlers.onComplete?.([primaryExperiment, secondaryExperiment], "bench-1");
        return Promise.resolve({ close: vi.fn() });
      },
    );

    mockListControlSets.mockResolvedValue([
      makeControlSet({ id: "cs-1", name: "Primary Set" }),
    ]);

    render(<BenchmarkPanel />);

    // Wait for control sets to load then add an inline control set
    await waitFor(() => {
      expect(screen.getByText("Primary Set")).toBeTruthy();
    });

    // Toggle on the saved control set
    const checkbox = screen.getByRole("checkbox", { name: /Primary Set/i });
    fireEvent.click(checkbox);

    // Click run
    const runButton = screen.getByText("Run Benchmark");
    fireEvent.click(runButton);

    // Results table should appear with metrics columns
    await waitFor(() => {
      // "Primary Set" appears in both checkbox label and results table
      expect(screen.getAllByText("Primary Set").length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("Secondary Set")).toBeTruthy();
    });

    // Check metric values are rendered in the table
    // sensitivity=0.8 appears multiple times (sensitivity, f1, precision for primary)
    expect(screen.getAllByText("0.800").length).toBeGreaterThan(0);
    // specificity=0.9 for primary
    expect(screen.getAllByText("0.900").length).toBeGreaterThan(0);
    // MCC=0.700 for primary
    expect(screen.getByText("0.700")).toBeTruthy();
  });

  it("handles error state", async () => {
    mockCreateBenchmarkStream.mockImplementation(
      (_base: unknown, _cs: unknown, handlers: { onError?: (err: string) => void }) => {
        handlers.onError?.("Benchmark failed: server error");
        return Promise.resolve({ close: vi.fn() });
      },
    );

    mockListControlSets.mockResolvedValue([
      makeControlSet({ id: "cs-1", name: "Test Controls" }),
    ]);

    render(<BenchmarkPanel />);

    await waitFor(() => {
      expect(screen.getByText("Test Controls")).toBeTruthy();
    });

    // Toggle on a control set
    const checkbox = screen.getByRole("checkbox", { name: /Test Controls/i });
    fireEvent.click(checkbox);

    // Click run
    fireEvent.click(screen.getByText("Run Benchmark"));

    await waitFor(() => {
      expect(screen.getByText("Benchmark failed: server error")).toBeTruthy();
    });
  });

  it("renders GeneChipInput in inline control sets", async () => {
    mockListControlSets.mockResolvedValue([]);
    render(<BenchmarkPanel />);

    // Click "Add inline control set"
    fireEvent.click(screen.getByText(/add inline control set/i));

    // Should see GeneChipInput labels
    expect(screen.getByText("Positive Controls")).toBeTruthy();
    expect(screen.getByText("Negative Controls")).toBeTruthy();

    // GeneChipInput renders autocomplete search inputs (no textareas)
    const searchInputs = screen.getAllByPlaceholderText("Search genes...");
    expect(searchInputs).toHaveLength(2);
  });
});
