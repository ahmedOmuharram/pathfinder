// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { Experiment, ExperimentMetrics, GeneSet } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Mock the workbench store
// ---------------------------------------------------------------------------

const storeState: Record<string, unknown> = {
  activeSetId: "set-1",
  geneSets: [] as GeneSet[],
  expandedPanels: new Set(["batch"]),
  togglePanel: vi.fn(),
};

vi.mock("@/state/useWorkbenchStore", () => ({
  useWorkbenchStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector(storeState),
}));

// ---------------------------------------------------------------------------
// Mock the streaming API
// ---------------------------------------------------------------------------

const mockCreateBatchStream =
  vi.fn<(...args: unknown[]) => Promise<{ close: () => void }>>();

vi.mock("@/features/workbench/api", () => ({
  createBatchExperimentStream: (...args: unknown[]) => mockCreateBatchStream(...args),
}));

// ---------------------------------------------------------------------------
// Mock listOrganisms
// ---------------------------------------------------------------------------

const mockListOrganisms = vi.fn<(...args: unknown[]) => Promise<string[]>>();

vi.mock("@/lib/api/genes", () => ({
  listOrganisms: (...args: unknown[]) => mockListOrganisms(...args),
  resolveGeneIds: vi.fn().mockResolvedValue({ resolved: [], unresolved: [] }),
  searchGenes: vi.fn().mockResolvedValue({ results: [], total: 0 }),
}));

// ---------------------------------------------------------------------------
// Mock useParamSpecs for ParamNameSelect
// ---------------------------------------------------------------------------

const mockParamSpecs: { name: string; displayName: string; type: string }[] = [];
let mockParamLoading = false;

vi.mock("@/lib/hooks/useParamSpecs", () => ({
  useParamSpecs: () => ({
    paramSpecs: mockParamSpecs,
    isLoading: mockParamLoading,
  }),
}));

// ---------------------------------------------------------------------------
// Mock sub-components used by GeneChipInput
// ---------------------------------------------------------------------------

vi.mock("../GeneChip", () => ({
  GeneChip: () => null,
}));
vi.mock("../GeneAutocomplete", () => ({
  GeneAutocomplete: () => null,
}));
vi.mock("../GeneSetPicker", () => ({
  GeneSetPicker: () => null,
}));
vi.mock("../CsvImportButton", () => ({
  CsvImportButton: () => null,
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { BatchPanel } from "./BatchPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeGeneSet(overrides: Partial<GeneSet> = {}): GeneSet {
  return {
    id: "set-1",
    name: "Test Set",
    siteId: "PlasmoDB",
    geneIds: ["PF3D7_0100100"],
    geneCount: 1,
    source: "strategy",
    searchName: "GenesByTaxon",
    recordType: "gene",
    parameters: { organism: "Plasmodium falciparum 3D7" },
    stepCount: 1,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeMetrics(overrides: Partial<ExperimentMetrics> = {}): ExperimentMetrics {
  return {
    confusionMatrix: {
      truePositives: 40,
      falsePositives: 10,
      falseNegatives: 5,
      trueNegatives: 45,
    },
    sensitivity: 0.889,
    specificity: 0.818,
    precision: 0.8,
    negativePredictiveValue: 0.9,
    falsePositiveRate: 0.182,
    falseNegativeRate: 0.111,
    f1Score: 0.842,
    mcc: 0.71,
    balancedAccuracy: 0.854,
    youdensJ: 0.707,
    totalResults: 100,
    totalPositives: 45,
    totalNegatives: 55,
    ...overrides,
  };
}

function makeExperiment(organism: string): Experiment {
  return {
    id: `exp-${organism}`,
    config: {
      siteId: "PlasmoDB",
      recordType: "gene",
      searchName: "GenesByTaxon",
      parameters: { organism },
      positiveControls: ["PF3D7_0100100"],
      negativeControls: [],
      controlsSearchName: "GeneByLocusTag",
      controlsParamName: "ds_gene_ids",
      controlsValueFormat: "newline",
      enableCrossValidation: false,
      kFolds: 5,
      enrichmentTypes: [],
      name: `Batch: ${organism}`,
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
    metrics: makeMetrics(),
    crossValidation: null,
    enrichmentResults: [],
    truePositiveGenes: [],
    falseNegativeGenes: [],
    falsePositiveGenes: [],
    trueNegativeGenes: [],
    optimizationResult: null,
    notes: null,
    batchId: "batch-1",
    benchmarkId: null,
    controlSetLabel: null,
    isPrimaryBenchmark: false,
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
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BatchPanel", () => {
  afterEach(() => {
    cleanup();
    mockCreateBatchStream.mockReset();
    mockListOrganisms.mockReset();
    mockParamSpecs.length = 0;
    mockParamLoading = false;
  });

  beforeEach(() => {
    storeState["activeSetId"] = "set-1";
    storeState["geneSets"] = [];
    storeState["expandedPanels"] = new Set(["batch"]);
    // Default: listOrganisms resolves to empty array so useEffect never blows up
    mockListOrganisms.mockResolvedValue([]);
  });

  it("is disabled when no active gene set has search context", () => {
    storeState["geneSets"] = [makeGeneSet({ searchName: null, parameters: null })];

    render(<BatchPanel />);

    expect(screen.getByText("Batch Evaluation")).toBeTruthy();
    // Form should not render when disabled
    expect(screen.queryByText("Run Batch")).toBeNull();
  });

  it("renders organism multi-select and param name select when enabled", async () => {
    storeState["geneSets"] = [makeGeneSet()];
    mockListOrganisms.mockResolvedValue([
      "Plasmodium falciparum 3D7",
      "Plasmodium vivax",
      "Toxoplasma gondii",
    ]);
    mockParamSpecs.push({
      name: "organism",
      displayName: "Organism",
      type: "multi-pick-vocabulary",
    });

    render(<BatchPanel />);

    // SearchableMultiSelect should render with placeholder after loading
    await waitFor(() => {
      expect(screen.getByText("Select target organisms")).toBeTruthy();
    });

    // ParamNameSelect should render as a native select with the param option
    expect(screen.getByRole("combobox")).toBeTruthy();

    // GeneChipInput labels should appear
    expect(screen.getByText("Shared Positive Controls")).toBeTruthy();
    expect(screen.getByText("Shared Negative Controls")).toBeTruthy();

    expect(screen.getByText("Run Batch")).toBeTruthy();
  });

  it("shows results table after batch completes", async () => {
    storeState["geneSets"] = [makeGeneSet()];
    mockListOrganisms.mockResolvedValue([
      "Plasmodium falciparum 3D7",
      "Plasmodium vivax",
    ]);
    mockParamSpecs.push({
      name: "organism",
      displayName: "Organism",
      type: "multi-pick-vocabulary",
    });

    mockCreateBatchStream.mockImplementation(
      async (_base, _param, _targets, handlers) => {
        const h = handlers as {
          onComplete?: (experiments: Experiment[], batchId: string) => void;
        };
        h.onComplete?.(
          [
            makeExperiment("Plasmodium falciparum 3D7"),
            makeExperiment("Plasmodium vivax"),
          ],
          "batch-1",
        );
        return { close: vi.fn() };
      },
    );

    render(<BatchPanel />);

    // Wait for organisms to load
    await waitFor(() => {
      expect(screen.getByText("Select target organisms")).toBeTruthy();
    });

    // Open dropdown and select organisms
    fireEvent.click(screen.getByText("Select target organisms"));
    await waitFor(() => {
      expect(screen.getByText("Plasmodium falciparum 3D7")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Plasmodium falciparum 3D7"));
    fireEvent.click(screen.getByText("Plasmodium vivax"));

    // Select a param name
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "organism" },
    });

    // Click run
    fireEvent.click(screen.getByText("Run Batch"));

    // Results table should appear with metrics
    await waitFor(() => {
      expect(screen.getAllByText("0.889").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("0.818").length).toBeGreaterThan(0);
    expect(screen.getAllByText("0.842").length).toBeGreaterThan(0);
  });

  it("displays error state", async () => {
    storeState["geneSets"] = [makeGeneSet()];
    mockListOrganisms.mockResolvedValue(["Plasmodium falciparum 3D7"]);
    mockParamSpecs.push({
      name: "organism",
      displayName: "Organism",
      type: "multi-pick-vocabulary",
    });

    mockCreateBatchStream.mockImplementation(
      async (_base, _param, _targets, handlers) => {
        const h = handlers as { onError?: (error: string) => void };
        h.onError?.("Batch evaluation failed: server error");
        return { close: vi.fn() };
      },
    );

    render(<BatchPanel />);

    // Wait for organisms to load
    await waitFor(() => {
      expect(screen.getByText("Select target organisms")).toBeTruthy();
    });

    // Open dropdown and select an organism
    fireEvent.click(screen.getByText("Select target organisms"));
    await waitFor(() => {
      expect(screen.getByText("Plasmodium falciparum 3D7")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Plasmodium falciparum 3D7"));

    // Select a param name
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "organism" },
    });

    // Click run
    fireEvent.click(screen.getByText("Run Batch"));

    expect(
      await screen.findByText("Batch evaluation failed: server error"),
    ).toBeTruthy();
  });

  // -----------------------------------------------------------------------
  // Organism column uses organismParamNameRef instead of hardcoded key
  // -----------------------------------------------------------------------
  it("uses the selected organism param name for the organism column", async () => {
    storeState["geneSets"] = [makeGeneSet()];
    mockListOrganisms.mockResolvedValue([
      "Plasmodium falciparum 3D7",
      "Plasmodium vivax",
    ]);
    mockParamSpecs.push({
      name: "text_search_organism",
      displayName: "Organism",
      type: "multi-pick-vocabulary",
    });

    const pf3d7Experiment = makeExperiment("Plasmodium falciparum 3D7");
    // Use a non-standard param key to verify organismParamNameRef is used
    pf3d7Experiment.config.parameters = {
      text_search_organism: "Plasmodium falciparum 3D7",
    };

    mockCreateBatchStream.mockImplementation(
      async (_base, _param, _targets, handlers) => {
        const h = handlers as {
          onComplete?: (experiments: Experiment[], batchId: string) => void;
        };
        h.onComplete?.([pf3d7Experiment], "batch-1");
        return { close: vi.fn() };
      },
    );

    render(<BatchPanel />);

    await waitFor(() => {
      expect(screen.getByText("Select target organisms")).toBeTruthy();
    });

    // Select organism
    fireEvent.click(screen.getByText("Select target organisms"));
    await waitFor(() => {
      expect(screen.getByText("Plasmodium falciparum 3D7")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Plasmodium falciparum 3D7"));

    // Select the custom param name
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "text_search_organism" },
    });

    fireEvent.click(screen.getByText("Run Batch"));

    // The table should display the organism value extracted via the custom param key
    await waitFor(() => {
      // The organism column value comes from
      // exp.config.parameters[organismParamNameRef.current]
      expect(
        screen.getAllByText("Plasmodium falciparum 3D7").length,
      ).toBeGreaterThanOrEqual(1);
    });
  });

  // -----------------------------------------------------------------------
  // Missing results show "X of Y completed" warning
  // -----------------------------------------------------------------------
  it("shows partial completion warning when some organisms fail", async () => {
    storeState["geneSets"] = [makeGeneSet()];
    mockListOrganisms.mockResolvedValue([
      "Plasmodium falciparum 3D7",
      "Plasmodium vivax",
      "Toxoplasma gondii",
    ]);
    mockParamSpecs.push({
      name: "organism",
      displayName: "Organism",
      type: "multi-pick-vocabulary",
    });

    // Only return 2 of 3 results — simulating one failure
    mockCreateBatchStream.mockImplementation(
      async (_base, _param, _targets, handlers) => {
        const h = handlers as {
          onComplete?: (experiments: Experiment[], batchId: string) => void;
        };
        h.onComplete?.(
          [
            makeExperiment("Plasmodium falciparum 3D7"),
            makeExperiment("Plasmodium vivax"),
          ],
          "batch-1",
        );
        return { close: vi.fn() };
      },
    );

    render(<BatchPanel />);

    await waitFor(() => {
      expect(screen.getByText("Select target organisms")).toBeTruthy();
    });

    // Select all 3 organisms
    fireEvent.click(screen.getByText("Select target organisms"));
    await waitFor(() => {
      expect(screen.getByText("Plasmodium falciparum 3D7")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Plasmodium falciparum 3D7"));
    fireEvent.click(screen.getByText("Plasmodium vivax"));
    fireEvent.click(screen.getByText("Toxoplasma gondii"));

    // Select param name
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "organism" },
    });

    // Run batch
    fireEvent.click(screen.getByText("Run Batch"));

    // Should show "2 of 3" warning
    await waitFor(() => {
      expect(screen.getByText(/Completed 2 of 3 organisms/i)).toBeTruthy();
    });
  });

  // -----------------------------------------------------------------------
  // expectedCount tracks selected organism count
  // -----------------------------------------------------------------------
  it("does not show warning when all organisms complete", async () => {
    storeState["geneSets"] = [makeGeneSet()];
    mockListOrganisms.mockResolvedValue([
      "Plasmodium falciparum 3D7",
      "Plasmodium vivax",
    ]);
    mockParamSpecs.push({
      name: "organism",
      displayName: "Organism",
      type: "multi-pick-vocabulary",
    });

    // Return all 2 results
    mockCreateBatchStream.mockImplementation(
      async (_base, _param, _targets, handlers) => {
        const h = handlers as {
          onComplete?: (experiments: Experiment[], batchId: string) => void;
        };
        h.onComplete?.(
          [
            makeExperiment("Plasmodium falciparum 3D7"),
            makeExperiment("Plasmodium vivax"),
          ],
          "batch-1",
        );
        return { close: vi.fn() };
      },
    );

    render(<BatchPanel />);

    await waitFor(() => {
      expect(screen.getByText("Select target organisms")).toBeTruthy();
    });

    // Select both organisms
    fireEvent.click(screen.getByText("Select target organisms"));
    await waitFor(() => {
      expect(screen.getByText("Plasmodium falciparum 3D7")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Plasmodium falciparum 3D7"));
    fireEvent.click(screen.getByText("Plasmodium vivax"));

    // Select param
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "organism" },
    });

    fireEvent.click(screen.getByText("Run Batch"));

    // Results should appear
    await waitFor(() => {
      expect(screen.getAllByText("0.889").length).toBeGreaterThan(0);
    });

    // No warning text about partial completion
    expect(screen.queryByText(/Completed.*of.*organisms/i)).toBeNull();
  });
});
