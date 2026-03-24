import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// Mock http module before importing the module under test
vi.mock("@/lib/api/http", () => ({
  requestJson: vi.fn(),
  requestVoid: vi.fn(),
  requestBlob: vi.fn(),
}));

import {
  getExperiment,
  deleteExperiment,
  updateExperimentNotes,
  exportExperiment,
  refineExperiment,
  reEvaluateExperiment,
} from "./experiments";
import { requestJson, requestVoid, requestBlob } from "@/lib/api/http";
import type {
  Experiment,
  ExperimentConfig,
  ExperimentMetrics,
} from "@pathfinder/shared";

const mockRequestJson = vi.mocked(requestJson);
const mockRequestVoid = vi.mocked(requestVoid);
const mockRequestBlob = vi.mocked(requestBlob);

beforeEach(() => {
  mockRequestJson.mockReset();
  mockRequestVoid.mockReset();
  mockRequestBlob.mockReset();
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

const configFixture: ExperimentConfig = {
  siteId: "plasmodb",
  recordType: "gene",
  searchName: "GeneByTextSearch",
  parameters: { text_expression: "kinase" },
  name: "Test Experiment",
  description: "A test experiment",
  positiveControls: ["PF3D7_0100100"],
  negativeControls: ["PF3D7_0200200"],
  controlsSearchName: "GeneByLocusTag",
  controlsParamName: "ds_gene_ids",
  controlsValueFormat: "newline",
  enableCrossValidation: false,
  kFolds: 5,
  enrichmentTypes: [],
  mode: "single",
  optimizationBudget: 30,
  optimizationObjective: "balanced_accuracy",
  enableStepAnalysis: false,
  treeOptimizationObjective: "precision_at_50",
  treeOptimizationBudget: 50,
  sortDirection: "ASC",
};

const experimentFixture: Experiment = {
  id: "exp-1",
  config: configFixture,
  status: "completed",
  metrics: metricsFixture,
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
  totalTimeSeconds: 12.5,
  createdAt: "2026-01-01T00:00:00Z",
  completedAt: "2026-01-01T00:01:00Z",
  wdkStrategyId: null,
  wdkStepId: null,
  stepAnalysis: null,
  rankMetrics: null,
  robustness: null,
  treeOptimization: null,
};

// ---------------------------------------------------------------------------
// getExperiment
// ---------------------------------------------------------------------------

describe("getExperiment", () => {
  it("sends GET to /api/v1/experiments/:id", async () => {
    mockRequestJson.mockResolvedValue(experimentFixture);

    const result = await getExperiment("exp-1");

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1",
    );
    expect(result).toEqual(experimentFixture);
  });

  it("returns experiment with all fields populated", async () => {
    const fullExperiment: Experiment = {
      ...experimentFixture,
      notes: "Some notes",
      batchId: "batch-1",
      benchmarkId: "bench-1",
      controlSetLabel: "Primary",
      isPrimaryBenchmark: true,
    };
    mockRequestJson.mockResolvedValue(fullExperiment);

    const result = await getExperiment("exp-full");

    expect(result.notes).toBe("Some notes");
    expect(result.batchId).toBe("batch-1");
    expect(result.isPrimaryBenchmark).toBe(true);
  });

  it("propagates API errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("404 Not Found"));

    await expect(getExperiment("nonexistent")).rejects.toThrow("404 Not Found");
  });
});

// ---------------------------------------------------------------------------
// deleteExperiment
// ---------------------------------------------------------------------------

describe("deleteExperiment", () => {
  it("sends DELETE to /api/v1/experiments/:id", async () => {
    mockRequestVoid.mockResolvedValue(undefined);

    await deleteExperiment("exp-1");

    expect(mockRequestVoid).toHaveBeenCalledWith("/api/v1/experiments/exp-1", {
      method: "DELETE",
    });
  });

  it("propagates errors on deletion failure", async () => {
    mockRequestVoid.mockRejectedValue(new Error("403 Forbidden"));

    await expect(deleteExperiment("exp-1")).rejects.toThrow("403 Forbidden");
  });
});

// ---------------------------------------------------------------------------
// updateExperimentNotes
// ---------------------------------------------------------------------------

describe("updateExperimentNotes", () => {
  it("sends PATCH to /api/v1/experiments/:id with notes body", async () => {
    const updated = { ...experimentFixture, notes: "Updated notes" };
    mockRequestJson.mockResolvedValue(updated);

    const result = await updateExperimentNotes("exp-1", "Updated notes");

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1",
      {
        method: "PATCH",
        body: { notes: "Updated notes" },
      },
    );
    expect(result.notes).toBe("Updated notes");
  });

  it("handles empty notes string", async () => {
    const updated = { ...experimentFixture, notes: "" };
    mockRequestJson.mockResolvedValue(updated);

    await updateExperimentNotes("exp-1", "");

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1",
      {
        method: "PATCH",
        body: { notes: "" },
      },
    );
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("500 Internal Server Error"));

    await expect(updateExperimentNotes("exp-1", "notes")).rejects.toThrow(
      "500 Internal Server Error",
    );
  });
});

// ---------------------------------------------------------------------------
// exportExperiment
// ---------------------------------------------------------------------------

describe("exportExperiment", () => {
  let clickSpy: ReturnType<typeof vi.fn>;
  let createdUrls: string[];
  let revokedUrls: string[];

  beforeEach(() => {
    clickSpy = vi.fn();
    createdUrls = [];
    revokedUrls = [];

    vi.stubGlobal("URL", {
      createObjectURL: vi.fn((_blob: Blob) => {
        const url = `blob:mock-${createdUrls.length}`;
        createdUrls.push(url);
        return url;
      }),
      revokeObjectURL: vi.fn((url: string) => {
        revokedUrls.push(url);
      }),
    });

    vi.stubGlobal("document", {
      createElement: vi.fn(() => ({
        href: "",
        download: "",
        click: clickSpy,
      })),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches a blob and triggers a download", async () => {
    const mockBlob = new Blob(["content"], { type: "application/zip" });
    mockRequestBlob.mockResolvedValue(mockBlob);

    await exportExperiment("exp-1", "My Experiment");

    expect(mockRequestBlob).toHaveBeenCalledWith("/api/v1/experiments/exp-1/export");
    expect(clickSpy).toHaveBeenCalledOnce();
    expect(createdUrls).toHaveLength(1);
    expect(revokedUrls).toHaveLength(1);
  });

  it("sanitizes whitespace in the filename", async () => {
    const mockBlob = new Blob(["content"], { type: "application/zip" });
    mockRequestBlob.mockResolvedValue(mockBlob);

    const el = { href: "", download: "", click: clickSpy };
    vi.mocked(document.createElement).mockReturnValue(el as unknown as HTMLElement);

    await exportExperiment("exp-1", "My  Experiment  Name");

    // \s+ replaces runs of whitespace with a single underscore
    expect(el.download).toBe("My_Experiment_Name.zip");
  });

  it("truncates long names to 50 characters", async () => {
    const mockBlob = new Blob(["content"], { type: "application/zip" });
    mockRequestBlob.mockResolvedValue(mockBlob);

    const longName = "A".repeat(100);
    const el = { href: "", download: "", click: clickSpy };
    vi.mocked(document.createElement).mockReturnValue(el as unknown as HTMLElement);

    await exportExperiment("exp-1", longName);

    // After replace and slice(0, 50), should be 50 chars + ".zip"
    expect(el.download).toBe("A".repeat(50) + ".zip");
  });

  it("propagates blob fetch errors", async () => {
    mockRequestBlob.mockRejectedValue(new Error("Network error"));

    await expect(exportExperiment("exp-1", "Test")).rejects.toThrow("Network error");
  });
});

// ---------------------------------------------------------------------------
// refineExperiment
// ---------------------------------------------------------------------------

describe("refineExperiment", () => {
  it("sends POST to /api/v1/experiments/:id/refine with combine action", async () => {
    const result = { success: true, newStepId: 42 };
    mockRequestJson.mockResolvedValue(result);

    const config = {
      searchName: "GeneByOrthologs",
      parameters: { organism: "P. vivax" },
      operator: "intersect",
    };

    const response = await refineExperiment("exp-1", "combine", config);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1/refine",
      {
        method: "POST",
        body: {
          action: "combine",
          searchName: "GeneByOrthologs",
          parameters: { organism: "P. vivax" },
          operator: "intersect",
        },
      },
    );
    expect(response).toEqual(result);
  });

  it("sends POST with transform action", async () => {
    const result = { success: true };
    mockRequestJson.mockResolvedValue(result);

    const config = {
      stepId: 7,
    };

    await refineExperiment("exp-1", "transform", config);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1/refine",
      {
        method: "POST",
        body: {
          action: "transform",
          stepId: 7,
        },
      },
    );
  });

  it("spreads additional config properties into the body", async () => {
    mockRequestJson.mockResolvedValue({ success: true });

    const config = {
      searchName: "GeneByLocation",
      customField: "custom-value",
    };

    await refineExperiment("exp-1", "combine", config);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1/refine",
      {
        method: "POST",
        body: expect.objectContaining({
          action: "combine",
          customField: "custom-value",
        }),
      },
    );
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("Refine failed"));

    await expect(refineExperiment("exp-1", "combine", {})).rejects.toThrow(
      "Refine failed",
    );
  });
});

// ---------------------------------------------------------------------------
// reEvaluateExperiment
// ---------------------------------------------------------------------------

describe("reEvaluateExperiment", () => {
  it("sends POST to /api/v1/experiments/:id/re-evaluate", async () => {
    mockRequestJson.mockResolvedValue(experimentFixture);

    const result = await reEvaluateExperiment("exp-1");

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments/exp-1/re-evaluate",
      { method: "POST" },
    );
    expect(result).toEqual(experimentFixture);
  });

  it("returns updated experiment after re-evaluation", async () => {
    const updated = {
      ...experimentFixture,
      metrics: { ...metricsFixture, f1Score: 0.92 },
    };
    mockRequestJson.mockResolvedValue(updated);

    const result = await reEvaluateExperiment("exp-1");

    expect((result as unknown as typeof updated).metrics?.f1Score).toBe(0.92);
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("Re-evaluation failed"));

    await expect(reEvaluateExperiment("exp-1")).rejects.toThrow("Re-evaluation failed");
  });
});
