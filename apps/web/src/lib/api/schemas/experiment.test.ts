import { describe, expect, it } from "vitest";
import { ExperimentSummarySchema, ExperimentSummaryListSchema } from "./experiment";

const validSummary = {
  id: "exp-1",
  name: "Test Experiment",
  siteId: "plasmodb",
  searchName: "GeneByTextSearch",
  recordType: "gene",
  status: "completed",
  f1Score: 0.85,
  sensitivity: 0.9,
  specificity: 0.8,
  totalPositives: 50,
  totalNegatives: 100,
  createdAt: "2026-01-01T00:00:00Z",
  batchId: null,
  benchmarkId: null,
  controlSetLabel: null,
  isPrimaryBenchmark: false,
};

describe("ExperimentSummarySchema", () => {
  it("parses a valid experiment summary", () => {
    const result = ExperimentSummarySchema.safeParse(validSummary);
    expect(result.success).toBe(true);
    expect(result.data).toEqual(validSummary);
  });

  it("accepts optional mode field", () => {
    const result = ExperimentSummarySchema.safeParse({
      ...validSummary,
      mode: "multi-step",
    });
    expect(result.success).toBe(true);
    expect(result.data?.mode).toBe("multi-step");
  });

  it("strips unknown fields", () => {
    const result = ExperimentSummarySchema.safeParse({
      ...validSummary,
      futureField: "hello",
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>)["futureField"]).toBeUndefined();
  });

  it("rejects missing required fields", () => {
    const { id: _, ...noId } = validSummary;
    const result = ExperimentSummarySchema.safeParse(noId);
    expect(result.success).toBe(false);
  });

  it("rejects invalid status enum", () => {
    const result = ExperimentSummarySchema.safeParse({
      ...validSummary,
      status: "invalid_status",
    });
    expect(result.success).toBe(false);
  });

  it("accepts nullable metric fields", () => {
    const result = ExperimentSummarySchema.safeParse({
      ...validSummary,
      f1Score: null,
      sensitivity: null,
      specificity: null,
    });
    expect(result.success).toBe(true);
  });
});

describe("ExperimentSummaryListSchema", () => {
  it("parses an empty list", () => {
    const result = ExperimentSummaryListSchema.safeParse([]);
    expect(result.success).toBe(true);
    expect(result.data).toEqual([]);
  });

  it("parses a list of summaries", () => {
    const result = ExperimentSummaryListSchema.safeParse([
      validSummary,
      { ...validSummary, id: "exp-2" },
    ]);
    expect(result.success).toBe(true);
    expect(result.data).toHaveLength(2);
  });

  it("rejects non-array input", () => {
    const result = ExperimentSummaryListSchema.safeParse("not an array");
    expect(result.success).toBe(false);
  });
});
