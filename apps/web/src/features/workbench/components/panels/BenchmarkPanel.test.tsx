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
      geneIds: ["PF3D7_0100100", "PF3D7_0100200", "PF3D7_0100300"],
      geneCount: 3,
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

/** Helper: select a saved control set checkbox and click Run Benchmark. */
async function selectControlSetAndRun(label: string) {
  await waitFor(() => {
    expect(screen.getByText(label)).toBeTruthy();
  });
  const checkbox = screen.getByRole("checkbox", { name: new RegExp(label, "i") });
  fireEvent.click(checkbox);
  fireEvent.click(screen.getByText("Run Benchmark"));
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
    storeState["activeSetId"] = "set-1";
    storeState["geneSets"] = [
      {
        id: "set-1",
        name: "Test Set",
        siteId: "PlasmoDB",
        geneIds: ["PF3D7_0100100", "PF3D7_0100200", "PF3D7_0100300"],
        geneCount: 3,
        source: "strategy",
        searchName: "GenesByTaxon",
        recordType: "gene",
        parameters: { organism: "Plasmodium falciparum 3D7" },
      },
    ];
    storeState["expandedPanels"] = new Set(["benchmark"]);
    mockListControlSets.mockResolvedValue([]);
    mockResolveGeneIds.mockResolvedValue({ resolved: [], unresolved: [] });
    mockSearchGenes.mockResolvedValue({ results: [], total: 0 });
  });

  // =========================================================================
  // Panel enablement — the panel must be enabled whenever the gene set has
  // data to evaluate (gene IDs OR search context).
  // =========================================================================

  describe("panel enablement", () => {
    it("is disabled when active gene set has neither geneIds nor search context", () => {
      storeState["geneSets"] = [
        {
          id: "set-1",
          name: "Empty Set",
          siteId: "PlasmoDB",
          geneIds: [],
          geneCount: 0,
          source: "paste",
          // no searchName or parameters
        },
      ];
      render(<BenchmarkPanel />);
      expect(screen.getByText("Benchmark")).toBeTruthy();
      expect(screen.queryByText("Run Benchmark")).toBeNull();
    });

    it("is enabled when gene set has geneIds but no search context", () => {
      storeState["geneSets"] = [
        {
          id: "set-1",
          name: "Pasted Set",
          siteId: "PlasmoDB",
          geneIds: ["PF3D7_0100100", "PF3D7_0100200"],
          geneCount: 2,
          source: "paste",
          // no searchName or parameters — must still be evaluable via geneIds
        },
      ];
      render(<BenchmarkPanel />);
      expect(screen.getByText("Run Benchmark")).toBeTruthy();
    });

    it("is enabled when gene set has search context but empty geneIds", () => {
      storeState["geneSets"] = [
        {
          id: "set-1",
          name: "Search-Only Set",
          siteId: "PlasmoDB",
          geneIds: [],
          geneCount: 0,
          source: "strategy",
          searchName: "GenesByTaxon",
          recordType: "gene",
          parameters: { organism: "Plasmodium falciparum 3D7" },
        },
      ];
      render(<BenchmarkPanel />);
      expect(screen.getByText("Run Benchmark")).toBeTruthy();
    });

    it("is enabled when gene set has both geneIds and search context", () => {
      // Default store state has both — just verify
      render(<BenchmarkPanel />);
      expect(screen.getByText("Run Benchmark")).toBeTruthy();
    });
  });

  // =========================================================================
  // Request payload — THE critical contract. The benchmark MUST send
  // targetGeneIds so the backend evaluates the actual gene set, not a
  // re-execution of stale search parameters.
  // =========================================================================

  describe("request payload — targetGeneIds", () => {
    it("sends targetGeneIds from the active gene set when running benchmark", async () => {
      const geneIds = ["PF3D7_0100100", "PF3D7_0100200", "PF3D7_0100300"];
      storeState["geneSets"] = [
        {
          id: "set-1",
          name: "Strategy Set",
          siteId: "PlasmoDB",
          geneIds,
          geneCount: 3,
          source: "strategy",
          searchName: "GenesByTaxon",
          recordType: "gene",
          parameters: { organism: "Plasmodium falciparum 3D7" },
        },
      ];

      mockListControlSets.mockResolvedValue([makeControlSet()]);
      mockCreateBenchmarkStream.mockImplementation(
        (
          _base: unknown,
          _cs: unknown,
          handlers: { onComplete?: (exps: Experiment[], id: string) => void },
        ) => {
          handlers.onComplete?.([], "bench-1");
          return Promise.resolve({ close: vi.fn() });
        },
      );

      render(<BenchmarkPanel />);
      await selectControlSetAndRun("Curated Controls");

      expect(mockCreateBenchmarkStream).toHaveBeenCalledTimes(1);
      const [baseConfig] = mockCreateBenchmarkStream.mock.calls[0] as [
        Record<string, unknown>,
      ];
      expect(baseConfig["targetGeneIds"]).toEqual(geneIds);
    });

    it("sends targetGeneIds even when searchName/parameters are empty", async () => {
      const geneIds = ["AGAP000001", "AGAP000002"];
      storeState["geneSets"] = [
        {
          id: "set-1",
          name: "Pasted Set",
          siteId: "VectorBase",
          geneIds,
          geneCount: 2,
          source: "paste",
          // no searchName, no parameters
        },
      ];

      mockListControlSets.mockResolvedValue([
        makeControlSet({ id: "cs-1", name: "VB Controls", siteId: "VectorBase" }),
      ]);
      mockCreateBenchmarkStream.mockImplementation(
        (
          _base: unknown,
          _cs: unknown,
          handlers: { onComplete?: (exps: Experiment[], id: string) => void },
        ) => {
          handlers.onComplete?.([], "bench-1");
          return Promise.resolve({ close: vi.fn() });
        },
      );

      render(<BenchmarkPanel />);
      await selectControlSetAndRun("VB Controls");

      expect(mockCreateBenchmarkStream).toHaveBeenCalledTimes(1);
      const [baseConfig] = mockCreateBenchmarkStream.mock.calls[0] as [
        Record<string, unknown>,
      ];
      expect(baseConfig["targetGeneIds"]).toEqual(geneIds);
    });

    it("does not send targetGeneIds when gene set has empty geneIds array", async () => {
      storeState["geneSets"] = [
        {
          id: "set-1",
          name: "Search-Only Set",
          siteId: "PlasmoDB",
          geneIds: [],
          geneCount: 0,
          source: "strategy",
          searchName: "GenesByTaxon",
          recordType: "gene",
          parameters: { organism: "Plasmodium falciparum 3D7" },
        },
      ];

      mockListControlSets.mockResolvedValue([makeControlSet()]);
      mockCreateBenchmarkStream.mockImplementation(
        (
          _base: unknown,
          _cs: unknown,
          handlers: { onComplete?: (exps: Experiment[], id: string) => void },
        ) => {
          handlers.onComplete?.([], "bench-1");
          return Promise.resolve({ close: vi.fn() });
        },
      );

      render(<BenchmarkPanel />);
      await selectControlSetAndRun("Curated Controls");

      expect(mockCreateBenchmarkStream).toHaveBeenCalledTimes(1);
      const [baseConfig] = mockCreateBenchmarkStream.mock.calls[0] as [
        Record<string, unknown>,
      ];
      // targetGeneIds should be undefined (falsy guard in the component)
      expect(baseConfig["targetGeneIds"]).toBeUndefined();
    });
  });

  // =========================================================================
  // Control set payload — verify the control sets are correctly built from
  // saved selections and inline entries, and passed to the API.
  // =========================================================================

  describe("request payload — control sets", () => {
    it("passes saved control set positive/negative IDs to the API", async () => {
      const controlSet = makeControlSet({
        id: "cs-42",
        name: "Insecticide Resistance",
        positiveIds: ["AGAP000001", "AGAP000002", "AGAP000003"],
        negativeIds: ["AGAP009001", "AGAP009002"],
      });
      mockListControlSets.mockResolvedValue([controlSet]);
      mockCreateBenchmarkStream.mockImplementation(
        (
          _base: unknown,
          _cs: unknown,
          handlers: { onComplete?: (exps: Experiment[], id: string) => void },
        ) => {
          handlers.onComplete?.([], "bench-1");
          return Promise.resolve({ close: vi.fn() });
        },
      );

      render(<BenchmarkPanel />);
      await selectControlSetAndRun("Insecticide Resistance");

      const [, controlSets] = mockCreateBenchmarkStream.mock.calls[0] as [
        unknown,
        Array<Record<string, unknown>>,
      ];
      expect(controlSets).toHaveLength(1);
      const cs0 = controlSets[0]!;
      expect(cs0["label"]).toBe("Insecticide Resistance");
      expect(cs0["positiveControls"]).toEqual([
        "AGAP000001",
        "AGAP000002",
        "AGAP000003",
      ]);
      expect(cs0["negativeControls"]).toEqual(["AGAP009001", "AGAP009002"]);
      expect(cs0["controlSetId"]).toBe("cs-42");
      expect(cs0["isPrimary"]).toBe(true);
    });

    it("marks first control set as primary when none explicitly set", async () => {
      mockListControlSets.mockResolvedValue([
        makeControlSet({ id: "cs-1", name: "Set A" }),
        makeControlSet({ id: "cs-2", name: "Set B" }),
      ]);
      mockCreateBenchmarkStream.mockImplementation(
        (
          _base: unknown,
          _cs: unknown,
          handlers: { onComplete?: (exps: Experiment[], id: string) => void },
        ) => {
          handlers.onComplete?.([], "bench-1");
          return Promise.resolve({ close: vi.fn() });
        },
      );

      render(<BenchmarkPanel />);
      await waitFor(() => {
        expect(screen.getByText("Set A")).toBeTruthy();
      });
      // Select both
      fireEvent.click(screen.getByRole("checkbox", { name: /Set A/i }));
      fireEvent.click(screen.getByRole("checkbox", { name: /Set B/i }));
      fireEvent.click(screen.getByText("Run Benchmark"));

      const [, controlSets] = mockCreateBenchmarkStream.mock.calls[0] as [
        unknown,
        Array<Record<string, unknown>>,
      ];
      expect(controlSets).toHaveLength(2);
      expect(controlSets[0]!["isPrimary"]).toBe(true);
      expect(controlSets[1]!["isPrimary"]).toBe(false);
    });
  });

  // =========================================================================
  // Results rendering — verify the table shows metrics from the response.
  // =========================================================================

  describe("results rendering", () => {
    it("shows comparison table with metrics after benchmark completes", async () => {
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
          handlers.onComplete?.([primaryExperiment, secondaryExperiment], "bench-1");
          return Promise.resolve({ close: vi.fn() });
        },
      );

      mockListControlSets.mockResolvedValue([
        makeControlSet({ id: "cs-1", name: "Primary Set" }),
      ]);

      render(<BenchmarkPanel />);
      await selectControlSetAndRun("Primary Set");

      await waitFor(() => {
        expect(screen.getAllByText("Primary Set").length).toBeGreaterThanOrEqual(2);
        expect(screen.getByText("Secondary Set")).toBeTruthy();
      });

      expect(screen.getAllByText("0.800").length).toBeGreaterThan(0);
      expect(screen.getAllByText("0.900").length).toBeGreaterThan(0);
      expect(screen.getByText("0.700")).toBeTruthy();
    });
  });

  // =========================================================================
  // Error handling
  // =========================================================================

  describe("error handling", () => {
    it("shows error from benchmark stream handler", async () => {
      mockCreateBenchmarkStream.mockImplementation(
        (
          _base: unknown,
          _cs: unknown,
          handlers: { onError?: (err: string) => void },
        ) => {
          handlers.onError?.("Benchmark failed: server error");
          return Promise.resolve({ close: vi.fn() });
        },
      );

      mockListControlSets.mockResolvedValue([
        makeControlSet({ id: "cs-1", name: "Test Controls" }),
      ]);

      render(<BenchmarkPanel />);
      await selectControlSetAndRun("Test Controls");

      await waitFor(() => {
        expect(screen.getByText("Benchmark failed: server error")).toBeTruthy();
      });
    });

    it("shows error when no control sets are selected", async () => {
      mockListControlSets.mockResolvedValue([]);
      render(<BenchmarkPanel />);
      fireEvent.click(screen.getByText("Run Benchmark"));

      await waitFor(() => {
        expect(
          screen.getByText(
            "Select or add at least one control set with positive controls.",
          ),
        ).toBeTruthy();
      });
    });

    it("shows error when listControlSets fails", async () => {
      mockListControlSets.mockRejectedValue(new Error("Network error"));
      render(<BenchmarkPanel />);

      await waitFor(() => {
        expect(screen.getByText("Failed to load saved control sets")).toBeTruthy();
      });
    });

    it("shows error when benchmark throws an exception", async () => {
      mockCreateBenchmarkStream.mockRejectedValue(new Error("Unexpected crash"));
      mockListControlSets.mockResolvedValue([makeControlSet()]);

      render(<BenchmarkPanel />);
      await selectControlSetAndRun("Curated Controls");

      await waitFor(() => {
        expect(screen.getByText("Unexpected crash")).toBeTruthy();
      });
    });
  });

  // =========================================================================
  // UI interactions
  // =========================================================================

  describe("UI interactions", () => {
    it("renders GeneChipInput in inline control sets", async () => {
      mockListControlSets.mockResolvedValue([]);
      render(<BenchmarkPanel />);

      fireEvent.click(screen.getByText(/add inline control set/i));

      expect(screen.getByText("Positive Controls")).toBeTruthy();
      expect(screen.getByText("Negative Controls")).toBeTruthy();
      const searchInputs = screen.getAllByPlaceholderText("Search genes...");
      expect(searchInputs).toHaveLength(2);
    });

    it("allows only one primary — toggling one untoggles others", async () => {
      mockListControlSets.mockResolvedValue([]);
      render(<BenchmarkPanel />);

      fireEvent.click(screen.getByText(/add inline control set/i));
      fireEvent.click(screen.getByText(/add inline control set/i));

      const primaryCheckboxes = screen.getAllByRole("checkbox", { name: /primary/i });
      expect(primaryCheckboxes).toHaveLength(2);

      const first = primaryCheckboxes[0]!;
      const second = primaryCheckboxes[1]!;
      fireEvent.click(first);
      expect((first as HTMLInputElement).checked).toBe(true);
      expect((second as HTMLInputElement).checked).toBe(false);

      fireEvent.click(second);
      expect((first as HTMLInputElement).checked).toBe(false);
      expect((second as HTMLInputElement).checked).toBe(true);
    });
  });
});
