// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Experiment } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Mock the workbench store so AnalysisPanelContainer renders children
// ---------------------------------------------------------------------------

const storeState: Record<string, unknown> = {
  activeSetId: "set-1",
  lastExperiment: null as Experiment | null,
  lastExperimentSetId: null as string | null,
  expandedPanels: new Set(["confidence"]),
  togglePanel: vi.fn(),
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
// Import after mocks
// ---------------------------------------------------------------------------

import { ConfidencePanel } from "./ConfidencePanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
      name: "Test",
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
    metrics: null,
    enrichmentResults: [],
    crossValidation: null,
    truePositiveGenes: [],
    falsePositiveGenes: [],
    trueNegativeGenes: [],
    falseNegativeGenes: [],
    optimizationResult: null,
    notes: null,
    batchId: null,
    benchmarkId: null,
    controlSetLabel: null,
    isPrimaryBenchmark: false,
    error: null,
    totalTimeSeconds: null,
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

describe("ConfidencePanel", () => {
  afterEach(cleanup);

  beforeEach(() => {
    storeState.activeSetId = "set-1";
    storeState.lastExperiment = null;
    storeState.lastExperimentSetId = null;
    storeState.expandedPanels = new Set(["confidence"]);
  });

  it("shows disabled state when no experiment is available", () => {
    render(<ConfidencePanel />);
    expect(screen.getByText("Gene Confidence")).toBeTruthy();
    // No table content when disabled
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("shows disabled state when experiment has no classified genes", () => {
    storeState.lastExperiment = makeExperiment();
    storeState.lastExperimentSetId = "set-1";

    render(<ConfidencePanel />);
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("renders confidence table with gene IDs and scores", () => {
    storeState.lastExperiment = makeExperiment({
      truePositiveGenes: [{ id: "G1", name: "Gene1" }],
      falsePositiveGenes: [{ id: "G2", name: "Gene2" }],
      falseNegativeGenes: [{ id: "G3", name: "Gene3" }],
      trueNegativeGenes: [{ id: "G4", name: "Gene4" }],
    });
    storeState.lastExperimentSetId = "set-1";

    render(<ConfidencePanel />);
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByText("G1")).toBeTruthy();
    expect(screen.getByText("G2")).toBeTruthy();
    expect(screen.getByText("G3")).toBeTruthy();
    expect(screen.getByText("G4")).toBeTruthy();
  });

  it("shows dimension breakdown columns", () => {
    storeState.lastExperiment = makeExperiment({
      truePositiveGenes: [{ id: "G1" }],
    });
    storeState.lastExperimentSetId = "set-1";

    render(<ConfidencePanel />);
    expect(screen.getByText("Composite")).toBeTruthy();
    expect(screen.getByText("Classification")).toBeTruthy();
    expect(screen.queryByText("Ensemble")).toBeNull();
    expect(screen.getByText("Enrichment")).toBeTruthy();
  });

  it("shows disabled when experiment belongs to a different set", () => {
    storeState.lastExperiment = makeExperiment({
      truePositiveGenes: [{ id: "G1" }],
    });
    storeState.lastExperimentSetId = "set-other";

    render(<ConfidencePanel />);
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("does NOT render an Ensemble column", () => {
    storeState.lastExperiment = makeExperiment({
      truePositiveGenes: [{ id: "G1" }],
    });
    storeState.lastExperimentSetId = "set-1";

    render(<ConfidencePanel />);
    // The table header should NOT contain "Ensemble"
    expect(screen.queryByText("Ensemble")).toBeNull();
    // But should contain the 2-component columns
    expect(screen.getByText("Classification")).toBeTruthy();
    expect(screen.getByText("Enrichment")).toBeTruthy();
    expect(screen.getByText("Composite")).toBeTruthy();
  });

  it("computes 2-component composite: TP with enrichment 0.5 scores 0.75", () => {
    // TP classification = 1.0, enrichment fraction = 0.5
    // Composite = (1.0 + 0.5) / 2.0 = 0.75
    // Set up: 2 significant terms, G1 appears in only 1 of them
    storeState.lastExperiment = makeExperiment({
      truePositiveGenes: [{ id: "G1" }],
      enrichmentResults: [
        {
          analysisType: "go_process",
          totalGenesAnalyzed: 10,
          backgroundSize: 100,
          terms: [
            {
              termId: "GO:0001",
              termName: "process1",
              geneCount: 1,
              backgroundCount: 10,
              foldEnrichment: 10,
              oddsRatio: 5,
              pValue: 0.001,
              fdr: 0.01,
              bonferroni: 0.05,
              genes: ["G1"],
            },
            {
              termId: "GO:0002",
              termName: "process2",
              geneCount: 1,
              backgroundCount: 10,
              foldEnrichment: 10,
              oddsRatio: 5,
              pValue: 0.001,
              fdr: 0.01,
              bonferroni: 0.05,
              genes: ["OTHER"],
            },
          ],
        },
      ],
    });
    storeState.lastExperimentSetId = "set-1";

    render(<ConfidencePanel />);

    // G1 in 1-of-2 significant terms => enrichment = 0.5
    // Composite = (1.0 + 0.5) / 2.0 = 0.75
    expect(screen.getByText("0.750")).toBeTruthy();
    // Classification = 1.0 rendered as "1.0"
    expect(screen.getByText("1.0")).toBeTruthy();
    // Enrichment = 0.5 rendered as "0.50"
    expect(screen.getByText("0.50")).toBeTruthy();
  });

  it("computes composite correctly: TP in all enrichment terms scores 1.0", () => {
    // G1 in both significant terms => enrichment = 1.0
    // Composite = (1.0 + 1.0) / 2.0 = 1.0
    storeState.lastExperiment = makeExperiment({
      truePositiveGenes: [{ id: "G1" }],
      enrichmentResults: [
        {
          analysisType: "go_process",
          totalGenesAnalyzed: 10,
          backgroundSize: 100,
          terms: [
            {
              termId: "GO:0001",
              termName: "process1",
              geneCount: 1,
              backgroundCount: 10,
              foldEnrichment: 10,
              oddsRatio: 5,
              pValue: 0.001,
              fdr: 0.01,
              bonferroni: 0.05,
              genes: ["G1"],
            },
            {
              termId: "GO:0002",
              termName: "process2",
              geneCount: 1,
              backgroundCount: 10,
              foldEnrichment: 10,
              oddsRatio: 5,
              pValue: 0.001,
              fdr: 0.01,
              bonferroni: 0.05,
              genes: ["G1"],
            },
          ],
        },
      ],
    });
    storeState.lastExperimentSetId = "set-1";

    render(<ConfidencePanel />);

    // Composite = 1.0 rendered as "1.000"
    expect(screen.getByText("1.000")).toBeTruthy();
  });

  it("FP gene with no enrichment scores -0.500 composite", () => {
    // Classification for FP = -1.0
    // Enrichment = 0 (no significant terms)
    // Composite = (-1.0 + 0.0) / 2.0 = -0.5
    storeState.lastExperiment = makeExperiment({
      falsePositiveGenes: [{ id: "G2" }],
    });
    storeState.lastExperimentSetId = "set-1";

    render(<ConfidencePanel />);

    expect(screen.getByText("-0.500")).toBeTruthy();
    expect(screen.getByText("-1.0")).toBeTruthy();
    expect(screen.getByText("0.00")).toBeTruthy();
  });
});
