import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock requestJson before importing the module under test
vi.mock("@/lib/api/http", () => ({
  requestJson: vi.fn(),
}));

import {
  runCrossValidation,
  runEnrichment,
  computeOverlap,
  compareEnrichment,
} from "./analysis";
import type { OverlapResult, EnrichmentCompareResult } from "./analysis";
import { requestJson } from "@/lib/api/http";
import type {
  CrossValidationResult,
  EnrichmentResult,
  EnrichmentAnalysisType,
  ExperimentMetrics,
} from "@pathfinder/shared";

const mockRequestJson = vi.mocked(requestJson);

beforeEach(() => {
  mockRequestJson.mockReset();
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const metricsFixture: ExperimentMetrics = {
  confusionMatrix: {
    truePositives: 40,
    falsePositives: 10,
    trueNegatives: 90,
    falseNegatives: 10,
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
};

const baseFold = {
  metrics: metricsFixture,
  positiveControlIds: ["PF3D7_0100100"],
  negativeControlIds: ["PF3D7_0200200"],
};

const crossValidationFixture: CrossValidationResult = {
  k: 5,
  folds: [
    { ...baseFold, foldIndex: 0 },
    { ...baseFold, foldIndex: 1 },
    { ...baseFold, foldIndex: 2 },
    { ...baseFold, foldIndex: 3 },
    { ...baseFold, foldIndex: 4 },
  ],
  meanMetrics: metricsFixture,
  stdMetrics: { f1Score: 0.02, sensitivity: 0.03, specificity: 0.01 },
  overfittingScore: 0.1,
  overfittingLevel: "low",
};

const enrichmentFixture: EnrichmentResult = {
  analysisType: "go_function",
  terms: [
    {
      termId: "GO:0003674",
      termName: "molecular_function",
      geneCount: 5,
      backgroundCount: 100,
      foldEnrichment: 2.5,
      oddsRatio: 3.0,
      pValue: 0.001,
      fdr: 0.01,
      bonferroni: 0.05,
      genes: ["G1", "G2", "G3", "G4", "G5"],
    },
  ],
  totalGenesAnalyzed: 50,
  backgroundSize: 5000,
};

const overlapFixture: OverlapResult = {
  experimentIds: ["exp-1", "exp-2"],
  experimentLabels: { "exp-1": "Experiment 1", "exp-2": "Experiment 2" },
  pairwise: [
    {
      experimentA: "exp-1",
      experimentB: "exp-2",
      labelA: "Experiment 1",
      labelB: "Experiment 2",
      sizeA: 100,
      sizeB: 80,
      intersection: 30,
      union: 150,
      jaccard: 0.2,
      sharedGenes: ["G1", "G2"],
      uniqueA: ["G3"],
      uniqueB: ["G4"],
    },
  ],
  perExperiment: [
    {
      experimentId: "exp-1",
      label: "Experiment 1",
      totalGenes: 100,
      uniqueGenes: 70,
      sharedGenes: 30,
    },
    {
      experimentId: "exp-2",
      label: "Experiment 2",
      totalGenes: 80,
      uniqueGenes: 50,
      sharedGenes: 30,
    },
  ],
  universalGenes: ["G1"],
  totalUniqueGenes: 150,
  geneMembership: [
    {
      geneId: "G1",
      foundIn: 2,
      totalExperiments: 2,
      experiments: ["exp-1", "exp-2"],
    },
  ],
};

const enrichmentCompareFixture: EnrichmentCompareResult = {
  experimentIds: ["exp-1", "exp-2"],
  experimentLabels: { "exp-1": "Experiment 1", "exp-2": "Experiment 2" },
  rows: [
    {
      termKey: "GO:0003674",
      termName: "molecular_function",
      analysisType: "go_function",
      scores: { "exp-1": 0.001, "exp-2": 0.05 },
      maxScore: 0.05,
      experimentCount: 2,
    },
  ],
  totalTerms: 1,
};

// ---------------------------------------------------------------------------
// runCrossValidation
// ---------------------------------------------------------------------------

describe("runCrossValidation", () => {
  it("sends POST to /api/v1/experiments/:id/cross-validate with kFolds", async () => {
    mockRequestJson.mockResolvedValue(crossValidationFixture);

    const result = await runCrossValidation("exp-1", 5);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1/cross-validate",
      {
        method: "POST",
        body: { kFolds: 5 },
      },
    );
    expect(result).toEqual(crossValidationFixture);
  });

  it("supports different fold counts", async () => {
    mockRequestJson.mockResolvedValue(crossValidationFixture);

    await runCrossValidation("exp-1", 10);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1/cross-validate",
      {
        method: "POST",
        body: { kFolds: 10 },
      },
    );
  });

  it("returns result with overfitting assessment", async () => {
    mockRequestJson.mockResolvedValue(crossValidationFixture);

    const result = await runCrossValidation("exp-1", 5);

    expect((result as unknown as typeof crossValidationFixture)["overfittingLevel"]).toBe("low");
    expect((result as unknown as typeof crossValidationFixture)["overfittingScore"]).toBe(0.1);
    expect(result.folds).toHaveLength(5);
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("Cross-validation failed"));

    await expect(runCrossValidation("exp-1", 5)).rejects.toThrow(
      "Cross-validation failed",
    );
  });
});

// ---------------------------------------------------------------------------
// runEnrichment
// ---------------------------------------------------------------------------

describe("runEnrichment", () => {
  it("sends POST to /api/v1/experiments/:id/enrich with enrichment types", async () => {
    mockRequestJson.mockResolvedValue([enrichmentFixture]);

    const types: EnrichmentAnalysisType[] = ["go_function", "pathway"];
    const result = await runEnrichment("exp-1", types);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1/enrich",
      {
        method: "POST",
        body: { enrichmentTypes: ["go_function", "pathway"] },
      },
    );
    expect(result).toEqual([enrichmentFixture]);
  });

  it("handles single enrichment type", async () => {
    mockRequestJson.mockResolvedValue([enrichmentFixture]);

    await runEnrichment("exp-1", ["go_function"]);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1/enrich",
      {
        method: "POST",
        body: { enrichmentTypes: ["go_function"] },
      },
    );
  });

  it("handles empty enrichment types array", async () => {
    mockRequestJson.mockResolvedValue([]);

    const result = await runEnrichment("exp-1", []);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1/enrich",
      {
        method: "POST",
        body: { enrichmentTypes: [] },
      },
    );
    expect(result).toEqual([]);
  });

  it("returns multiple enrichment results", async () => {
    const goProcess: EnrichmentResult = {
      ...enrichmentFixture,
      analysisType: "go_process",
    };
    mockRequestJson.mockResolvedValue([enrichmentFixture, goProcess]);

    const result = await runEnrichment("exp-1", ["go_function", "go_process"]);

    expect(result).toHaveLength(2);
    expect((result[0] as unknown as typeof enrichmentFixture)["analysisType"]).toBe("go_function");
    expect((result[1] as unknown as typeof enrichmentFixture)["analysisType"]).toBe("go_process");
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("Enrichment failed"));

    await expect(runEnrichment("exp-1", ["go_function"])).rejects.toThrow(
      "Enrichment failed",
    );
  });
});

// ---------------------------------------------------------------------------
// computeOverlap
// ---------------------------------------------------------------------------

describe("computeOverlap", () => {
  it("sends POST to /api/v1/experiments/overlap with experiment IDs", async () => {
    mockRequestJson.mockResolvedValue(overlapFixture);

    const result = await computeOverlap(["exp-1", "exp-2"]);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/overlap",
      {
        method: "POST",
        body: { experimentIds: ["exp-1", "exp-2"] },
      },
    );
    expect(result).toEqual(overlapFixture);
  });

  it("includes orthologAware query parameter when true", async () => {
    mockRequestJson.mockResolvedValue(overlapFixture);

    await computeOverlap(["exp-1", "exp-2"], { orthologAware: true });

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/overlap",
      {
        method: "POST",
        body: { experimentIds: ["exp-1", "exp-2"] },
        query: { orthologAware: "true" },
      },
    );
  });

  it("omits orthologAware query parameter when false", async () => {
    mockRequestJson.mockResolvedValue(overlapFixture);

    await computeOverlap(["exp-1", "exp-2"], { orthologAware: false });

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/overlap",
      {
        method: "POST",
        body: { experimentIds: ["exp-1", "exp-2"] },
      },
    );
  });

  it("omits query when no options are provided", async () => {
    mockRequestJson.mockResolvedValue(overlapFixture);

    await computeOverlap(["exp-1"]);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/overlap",
      {
        method: "POST",
        body: { experimentIds: ["exp-1"] },
      },
    );
  });

  it("handles multiple experiments", async () => {
    mockRequestJson.mockResolvedValue(overlapFixture);

    await computeOverlap(["exp-1", "exp-2", "exp-3"]);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/overlap",
      {
        method: "POST",
        body: { experimentIds: ["exp-1", "exp-2", "exp-3"] },
      },
    );
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("Overlap computation failed"));

    await expect(computeOverlap(["exp-1", "exp-2"])).rejects.toThrow(
      "Overlap computation failed",
    );
  });
});

// ---------------------------------------------------------------------------
// compareEnrichment
// ---------------------------------------------------------------------------

describe("compareEnrichment", () => {
  it("sends POST to /api/v1/experiments/enrichment-compare with experiment IDs", async () => {
    mockRequestJson.mockResolvedValue(enrichmentCompareFixture);

    const result = await compareEnrichment(["exp-1", "exp-2"]);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/enrichment-compare",
      {
        method: "POST",
        body: { experimentIds: ["exp-1", "exp-2"] },
      },
    );
    expect(result).toEqual(enrichmentCompareFixture);
  });

  it("includes analysisType when provided", async () => {
    mockRequestJson.mockResolvedValue(enrichmentCompareFixture);

    await compareEnrichment(["exp-1", "exp-2"], "go_function");

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/enrichment-compare",
      {
        method: "POST",
        body: { experimentIds: ["exp-1", "exp-2"], analysisType: "go_function" },
      },
    );
  });

  it("omits analysisType when not provided", async () => {
    mockRequestJson.mockResolvedValue(enrichmentCompareFixture);

    await compareEnrichment(["exp-1", "exp-2"]);

    const callBody = mockRequestJson.mock.calls[0]![2] as {
      body: { experimentIds: string[]; analysisType?: string };
    };
    expect(callBody.body).not.toHaveProperty("analysisType");
  });

  it("returns comparison rows with scores per experiment", async () => {
    mockRequestJson.mockResolvedValue(enrichmentCompareFixture);

    const result = await compareEnrichment(["exp-1", "exp-2"]);

    expect(result.rows).toHaveLength(1);
    expect(result.rows[0]!.scores["exp-1"]).toBe(0.001);
    expect(result.rows[0]!.scores["exp-2"]).toBe(0.05);
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("Comparison failed"));

    await expect(compareEnrichment(["exp-1", "exp-2"])).rejects.toThrow(
      "Comparison failed",
    );
  });
});
