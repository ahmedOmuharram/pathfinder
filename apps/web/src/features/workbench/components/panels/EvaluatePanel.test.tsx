// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ControlSet, GeneSet } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Mock workbench store
// ---------------------------------------------------------------------------

const storeState: Record<string, unknown> = {
  activeSetId: "set-1",
  geneSets: [] as GeneSet[],
  expandedPanels: new Set(["evaluate"]),
  togglePanel: vi.fn(),
  setLastExperiment: vi.fn(),
  pendingPositiveControls: [] as string[],
  pendingNegativeControls: [] as string[],
  clearPendingControls: vi.fn(),
};

vi.mock("@/state/useWorkbenchStore", () => ({
  useWorkbenchStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector(storeState),
}));

// ---------------------------------------------------------------------------
// Mock streaming API
// ---------------------------------------------------------------------------

const mockCreateExperimentStream = vi.fn();
vi.mock("@/features/workbench/api", () => ({
  createExperimentStream: (...args: unknown[]) => mockCreateExperimentStream(...args),
}));

// ---------------------------------------------------------------------------
// Mock analysis components used in results display
// ---------------------------------------------------------------------------

vi.mock("@/features/analysis", () => ({
  MetricsOverview: () => <div data-testid="metrics-overview" />,
  ConfusionMatrixSection: () => <div data-testid="confusion-matrix" />,
  CrossValidationSection: () => <div data-testid="cross-validation" />,
  GeneListsSection: () => <div data-testid="gene-lists" />,
  EnrichmentSection: () => <div data-testid="enrichment" />,
  RobustnessSection: () => <div data-testid="robustness" />,
  RankMetricsSection: () => <div data-testid="rank-metrics" />,
}));

// ---------------------------------------------------------------------------
// Mock resolveGeneIds / searchGenes for GeneChipInput
// ---------------------------------------------------------------------------

const mockResolveGeneIds = vi.fn();
const mockSearchGenes = vi.fn();
vi.mock("@/lib/api/genes", () => ({
  resolveGeneIds: (...args: unknown[]) => mockResolveGeneIds(...args),
  searchGenes: (...args: unknown[]) => mockSearchGenes(...args),
}));

// ---------------------------------------------------------------------------
// Mock GeneChipInput sub-components
// ---------------------------------------------------------------------------

vi.mock("../GeneChip", () => ({
  GeneChip: ({ geneId }: { geneId: string }) => (
    <span data-testid={`gene-chip-${geneId}`}>{geneId}</span>
  ),
}));
vi.mock("../GeneAutocomplete", () => ({
  GeneAutocomplete: () => <div data-testid="gene-autocomplete" />,
}));
vi.mock("../GeneSetPicker", () => ({
  GeneSetPicker: () => <div data-testid="gene-set-picker" />,
}));
vi.mock("../CsvImportButton", () => ({
  CsvImportButton: () => <div data-testid="csv-import" />,
}));

// ---------------------------------------------------------------------------
// Mock controlSets API (listControlSets + createControlSet)
// ---------------------------------------------------------------------------

const mockListControlSets = vi.fn<() => Promise<ControlSet[]>>();
const mockCreateControlSet = vi.fn();
vi.mock("../../api/controlSets", () => ({
  listControlSets: (...args: unknown[]) => mockListControlSets(...(args as [])),
  createControlSet: (...args: unknown[]) => mockCreateControlSet(...args),
}));

// ---------------------------------------------------------------------------
// Import SUT after mocks
// ---------------------------------------------------------------------------

import { EvaluatePanel } from "./EvaluatePanel";

// ---------------------------------------------------------------------------
// Factories
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

function makeControlSet(overrides: Partial<ControlSet> = {}): ControlSet {
  return {
    id: "cs-1",
    name: "Apicoplast kinases",
    siteId: "PlasmoDB",
    recordType: "gene",
    positiveIds: ["PF3D7_0100100", "PF3D7_0200200"],
    negativeIds: ["PF3D7_0900900"],
    source: "curation",
    tags: [],
    provenanceNotes: "",
    version: 1,
    isPublic: true,
    userId: null,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EvaluatePanel", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  beforeEach(() => {
    storeState["activeSetId"] = "set-1";
    storeState["geneSets"] = [makeGeneSet()];
    storeState["expandedPanels"] = new Set(["evaluate"]);
    storeState["pendingPositiveControls"] = [];
    storeState["pendingNegativeControls"] = [];
    mockListControlSets.mockResolvedValue([]);
  });

  it("is disabled when no active gene set has search context", () => {
    storeState["geneSets"] = [
      makeGeneSet({
        searchName: null,
        parameters: null,
        geneIds: [],
      }),
    ];
    render(<EvaluatePanel />);
    expect(screen.getByText("Evaluate Strategy")).toBeTruthy();
    // Panel is disabled, so Run button should not be visible
    expect(screen.queryByText("Run Evaluation")).toBeNull();
  });

  it("renders GeneChipInput for positive and negative controls", () => {
    render(<EvaluatePanel />);
    expect(screen.getByText("Positive Controls")).toBeTruthy();
    expect(screen.getByText("Negative Controls")).toBeTruthy();
    // required marker on positive
    expect(screen.getByText("*")).toBeTruthy();
  });

  it("renders ControlSetQuickPick when siteId is available", async () => {
    mockListControlSets.mockResolvedValue([makeControlSet()]);
    render(<EvaluatePanel />);
    await waitFor(() => {
      expect(screen.getByText("Apicoplast kinases")).toBeTruthy();
    });
  });

  it("pre-fills controls when a saved control set is selected", async () => {
    const cs = makeControlSet();
    mockListControlSets.mockResolvedValue([cs]);
    render(<EvaluatePanel />);

    await waitFor(() => {
      expect(screen.getByText("Apicoplast kinases")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Apicoplast kinases"));

    // After clicking, GeneChipInput renders chips for the pre-filled gene IDs
    await waitFor(() => {
      expect(screen.getByText("PF3D7_0100100")).toBeTruthy();
      expect(screen.getByText("PF3D7_0200200")).toBeTruthy();
    });
  });

  it("shows error when running without positive controls", async () => {
    render(<EvaluatePanel />);
    fireEvent.click(screen.getByText("Run Evaluation"));
    expect(screen.getByText(/at least one positive control/i)).toBeTruthy();
  });

  it("renders analysis options (cross-validation, enrichment types)", () => {
    render(<EvaluatePanel />);
    expect(screen.getByText(/cross-validation/i)).toBeTruthy();
    expect(screen.getByText("GO:BP")).toBeTruthy();
    expect(screen.getByText("GO:MF")).toBeTruthy();
  });

  it("renders step contribution analysis checkbox", () => {
    render(<EvaluatePanel />);
    expect(screen.getByText("Step contribution analysis")).toBeTruthy();
    // The checkbox itself is an input[type=checkbox]
    const checkboxes = screen.getAllByRole("checkbox");
    // At least 2 checkboxes: cross-validation and step analysis
    expect(checkboxes.length).toBeGreaterThanOrEqual(2);
  });

  it("cleans up SSE subscription on unmount", async () => {
    const mockUnsubscribe = vi.fn();
    mockCreateExperimentStream.mockResolvedValue({
      unsubscribe: mockUnsubscribe,
    });

    // Set up positive controls via store pending controls
    storeState["pendingPositiveControls"] = ["PF3D7_0100100"];

    const { unmount } = render(<EvaluatePanel />);

    // Wait for pending controls to be consumed
    await waitFor(() => {
      expect(screen.getByText("PF3D7_0100100")).toBeTruthy();
    });

    // Trigger a run to create the subscription
    fireEvent.click(screen.getByText("Run Evaluation"));

    await waitFor(() => {
      expect(mockCreateExperimentStream).toHaveBeenCalled();
    });

    // Unmount should clean up
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalled();
  });
});
