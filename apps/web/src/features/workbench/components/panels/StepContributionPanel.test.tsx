// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type {
  Experiment,
  StepAnalysisResult,
  StepContribution,
  StepEvaluation,
  OperatorComparison,
} from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Mock the workbench store so AnalysisPanelContainer renders children
// ---------------------------------------------------------------------------

const { storeState, mockStore } = vi.hoisted(() => {
  const storeState: Record<string, unknown> = {
    activeSetId: "set-1",
    lastExperiment: null,
    lastExperimentSetId: null,
    expandedPanels: new Set(["step-analysis"]),
    togglePanel: () => {},
  };
  const mockStore = (selector: (s: Record<string, unknown>) => unknown) =>
    selector(storeState);
  return { storeState, mockStore };
});

vi.mock("../../store", () => ({
  useWorkbenchStore: mockStore,
}));

// AnalysisPanelContainer imports from the concrete module path
vi.mock("../../store/useWorkbenchStore", () => ({
  useWorkbenchStore: mockStore,
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { StepContributionPanel } from "./StepContributionPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeContribution(overrides: Partial<StepContribution> = {}): StepContribution {
  return {
    stepId: "step-1",
    searchName: "GenesByTaxon",
    baselineRecall: 0.8,
    ablatedRecall: 0.5,
    recallDelta: -0.3,
    baselineFpr: 0.1,
    ablatedFpr: 0.15,
    fprDelta: 0.05,
    verdict: "essential",
    enrichmentDelta: -0.2,
    narrative: "Removing this step significantly reduces recall.",
    ...overrides,
  };
}

function makeEvaluation(overrides: Partial<StepEvaluation> = {}): StepEvaluation {
  return {
    stepId: "step-1",
    searchName: "GenesByTaxon",
    displayName: "Genes by Taxon",
    resultCount: 150,
    positiveHits: 40,
    positiveTotal: 50,
    negativeHits: 10,
    negativeTotal: 100,
    recall: 0.8,
    falsePositiveRate: 0.1,
    capturedPositiveIds: [],
    capturedNegativeIds: [],
    tpMovement: 0,
    fpMovement: 0,
    fnMovement: 0,
    ...overrides,
  };
}

function makeOperatorComparison(
  overrides: Partial<OperatorComparison> = {},
): OperatorComparison {
  return {
    combineNodeId: "combine-1",
    currentOperator: "intersect",
    variants: [
      {
        operator: "intersect",
        positiveHits: 40,
        negativeHits: 5,
        totalResults: 100,
        recall: 0.8,
        falsePositiveRate: 0.05,
        f1Score: 0.85,
      },
      {
        operator: "union",
        positiveHits: 48,
        negativeHits: 30,
        totalResults: 300,
        recall: 0.96,
        falsePositiveRate: 0.3,
        f1Score: 0.7,
      },
    ],
    recommendation: "Keep intersect for better precision.",
    recommendedOperator: "intersect",
    precisionAtKDelta: {},
    ...overrides,
  };
}

function makeStepAnalysis(
  overrides: Partial<StepAnalysisResult> = {},
): StepAnalysisResult {
  return {
    stepEvaluations: [makeEvaluation()],
    operatorComparisons: [],
    stepContributions: [makeContribution()],
    parameterSensitivities: [],
    ...overrides,
  };
}

function makeExperiment(stepAnalysis: StepAnalysisResult | null = null): Experiment {
  return {
    id: "exp-1",
    status: "completed",
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
      name: "Test Experiment",
      description: "",
      mode: "single",
      optimizationBudget: 30,
      optimizationObjective: "balanced_accuracy",
      enableStepAnalysis: false,
      treeOptimizationObjective: "precision_at_50",
      treeOptimizationBudget: 50,
      sortDirection: "ASC",
    },
    metrics: null,
    enrichmentResults: [],
    crossValidation: null,
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
    createdAt: "2026-03-09T00:00:00Z",
    completedAt: "2026-03-09T00:01:00Z",
    wdkStrategyId: null,
    wdkStepId: null,
    stepAnalysis,
    rankMetrics: null,
    robustness: null,
    treeOptimization: null,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StepContributionPanel", () => {
  afterEach(cleanup);

  beforeEach(() => {
    storeState.activeSetId = "set-1";
    storeState.lastExperiment = null;
    storeState.lastExperimentSetId = null;
    storeState.expandedPanels = new Set(["step-analysis"]);
  });

  it("shows disabled state when no experiment is available", () => {
    render(<StepContributionPanel />);
    // The panel header should still render, but children should not
    expect(screen.getByText("Step Contribution")).toBeTruthy();
    // No table content when disabled
    expect(screen.queryByText("GenesByTaxon")).toBeNull();
  });

  it("shows disabled state when experiment has no stepAnalysis", () => {
    storeState.lastExperiment = makeExperiment(null);
    storeState.lastExperimentSetId = "set-1";

    render(<StepContributionPanel />);
    expect(screen.queryByText("GenesByTaxon")).toBeNull();
  });

  it("shows disabled state when stepContributions is empty", () => {
    storeState.lastExperiment = makeExperiment(
      makeStepAnalysis({ stepContributions: [] }),
    );
    storeState.lastExperimentSetId = "set-1";

    render(<StepContributionPanel />);
    expect(screen.queryByText("GenesByTaxon")).toBeNull();
  });

  it("renders contribution table when stepAnalysis data is present", () => {
    storeState.lastExperiment = makeExperiment(makeStepAnalysis());
    storeState.lastExperimentSetId = "set-1";

    render(<StepContributionPanel />);
    expect(screen.getByText("Step Contributions")).toBeTruthy();
    expect(screen.getByText("GenesByTaxon")).toBeTruthy();
  });

  it("color-codes verdict badges correctly", () => {
    const contributions = [
      makeContribution({ stepId: "s1", searchName: "Essential", verdict: "essential" }),
      makeContribution({ stepId: "s2", searchName: "Helpful", verdict: "helpful" }),
      makeContribution({ stepId: "s3", searchName: "Neutral", verdict: "neutral" }),
      makeContribution({ stepId: "s4", searchName: "Harmful", verdict: "harmful" }),
    ];

    storeState.lastExperiment = makeExperiment(
      makeStepAnalysis({ stepContributions: contributions }),
    );
    storeState.lastExperimentSetId = "set-1";

    render(<StepContributionPanel />);

    const essentialBadge = screen.getByText("essential");
    const helpfulBadge = screen.getByText("helpful");
    const neutralBadge = screen.getByText("neutral");
    const harmfulBadge = screen.getByText("harmful");

    expect(essentialBadge.className).toContain("green");
    expect(helpfulBadge.className).toContain("blue");
    expect(neutralBadge.className).toContain("gray");
    expect(harmfulBadge.className).toContain("red");
  });

  it("renders operator comparison table when available", () => {
    storeState.lastExperiment = makeExperiment(
      makeStepAnalysis({
        operatorComparisons: [makeOperatorComparison()],
      }),
    );
    storeState.lastExperimentSetId = "set-1";

    render(<StepContributionPanel />);
    expect(screen.getByText("Operator Comparisons")).toBeTruthy();
    expect(screen.getByText("intersect")).toBeTruthy();
    expect(screen.getByText("union")).toBeTruthy();
  });

  it("does not render operator comparison section when empty", () => {
    storeState.lastExperiment = makeExperiment(
      makeStepAnalysis({ operatorComparisons: [] }),
    );
    storeState.lastExperimentSetId = "set-1";

    render(<StepContributionPanel />);
    expect(screen.queryByText("Operator Comparisons")).toBeNull();
  });

  it("renders per-step evaluation table", () => {
    storeState.lastExperiment = makeExperiment(makeStepAnalysis());
    storeState.lastExperimentSetId = "set-1";

    render(<StepContributionPanel />);
    expect(screen.getByText("Per-Step Evaluation")).toBeTruthy();
    expect(screen.getByText("Genes by Taxon")).toBeTruthy();
  });

  it("shows disabled when experiment belongs to a different set", () => {
    storeState.lastExperiment = makeExperiment(makeStepAnalysis());
    storeState.lastExperimentSetId = "set-other";

    render(<StepContributionPanel />);
    expect(screen.queryByText("GenesByTaxon")).toBeNull();
  });
});
