import { describe, expect, it } from "vitest";
import {
  StrategySchema,
  StrategyListItemSchema,
  StrategyListItemListSchema,
  OpenStrategyResponseSchema,
  StepCountsResponseSchema,
  NormalizePlanResponseSchema,
} from "./strategy";

const validStep = {
  id: "step-1",
  displayName: "Gene search",
  searchName: "GeneByTextSearch",
  recordType: "gene",
  parameters: { text_expression: "kinase" },
};

const validStrategy = {
  id: "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  name: "Test Strategy",
  siteId: "plasmodb",
  recordType: "gene",
  steps: [validStep],
  rootStepId: "step-1",
  isSaved: false,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("StrategyListItemSchema", () => {
  it("parses a minimal list item (no steps/rootStepId)", () => {
    const result = StrategyListItemSchema.safeParse({
      id: "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
      name: "My Strategy",
      siteId: "plasmodb",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
    });
    expect(result.success).toBe(true);
    expect(result.data?.steps).toBeUndefined();
  });

  it("parses a full list item with optional fields", () => {
    const result = StrategyListItemSchema.safeParse(validStrategy);
    expect(result.success).toBe(true);
    expect(result.data?.recordType).toBe("gene");
  });

  it("strips unknown fields", () => {
    const result = StrategyListItemSchema.safeParse({
      ...validStrategy,
      futureField: 42,
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>)["futureField"]).toBeUndefined();
  });

  it("rejects missing name", () => {
    const { name: _, ...noName } = validStrategy;
    const result = StrategyListItemSchema.safeParse(noName);
    expect(result.success).toBe(false);
  });

  it("rejects invalid UUID", () => {
    const result = StrategyListItemSchema.safeParse({
      ...validStrategy,
      id: "not-a-uuid",
    });
    expect(result.success).toBe(false);
  });
});

describe("StrategyListItemListSchema", () => {
  it("parses an empty array", () => {
    const result = StrategyListItemListSchema.safeParse([]);
    expect(result.success).toBe(true);
  });

  it("parses a list of items", () => {
    const result = StrategyListItemListSchema.safeParse([
      validStrategy,
      { ...validStrategy, id: "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e" },
    ]);
    expect(result.success).toBe(true);
    expect(result.data).toHaveLength(2);
  });
});

describe("OpenStrategyResponseSchema", () => {
  it("parses a valid response", () => {
    const result = OpenStrategyResponseSchema.safeParse({
      strategyId: "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
    });
    expect(result.success).toBe(true);
  });

  it("strips unknown fields", () => {
    const result = OpenStrategyResponseSchema.safeParse({
      strategyId: "abc",
      isNew: true,
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>)["isNew"]).toBeUndefined();
  });

  it("rejects missing strategyId", () => {
    const result = OpenStrategyResponseSchema.safeParse({});
    expect(result.success).toBe(false);
  });
});

describe("StepCountsResponseSchema", () => {
  it("parses valid step counts", () => {
    const result = StepCountsResponseSchema.safeParse({
      counts: { "step-1": 42, "step-2": null },
    });
    expect(result.success).toBe(true);
    expect(result.data?.counts["step-1"]).toBe(42);
    expect(result.data?.counts["step-2"]).toBeNull();
  });

  it("parses empty counts", () => {
    const result = StepCountsResponseSchema.safeParse({ counts: {} });
    expect(result.success).toBe(true);
  });

  it("rejects missing counts field", () => {
    const result = StepCountsResponseSchema.safeParse({});
    expect(result.success).toBe(false);
  });
});

describe("NormalizePlanResponseSchema", () => {
  it("parses a valid normalization response", () => {
    const result = NormalizePlanResponseSchema.safeParse({
      plan: {
        recordType: "gene",
        root: { searchName: "GeneByTextSearch", parameters: {} },
      },
      warnings: [],
    });
    expect(result.success).toBe(true);
  });

  it("accepts null warnings", () => {
    const result = NormalizePlanResponseSchema.safeParse({
      plan: { recordType: "gene", root: { searchName: "GenesByText" } },
      warnings: null,
    });
    expect(result.success).toBe(true);
    expect(result.data?.warnings).toBeNull();
  });

  it("accepts missing warnings", () => {
    const result = NormalizePlanResponseSchema.safeParse({
      plan: { recordType: "gene", root: { searchName: "GenesByText" } },
    });
    expect(result.success).toBe(true);
    expect(result.data?.warnings).toBeUndefined();
  });

  it("strips unknown fields", () => {
    const result = NormalizePlanResponseSchema.safeParse({
      plan: { recordType: "gene", root: { searchName: "GenesByText" } },
      metadata: { version: 2 },
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>)["metadata"]).toBeUndefined();
  });

  it("rejects missing plan field", () => {
    const result = NormalizePlanResponseSchema.safeParse({
      warnings: [],
    });
    expect(result.success).toBe(false);
  });
});

describe("StrategySchema (full detail)", () => {
  it("parses a valid full strategy", () => {
    const result = StrategySchema.safeParse(validStrategy);
    expect(result.success).toBe(true);
  });

  it("accepts missing steps array (optional per OpenAPI spec)", () => {
    const { steps: _, ...noSteps } = validStrategy;
    const result = StrategySchema.safeParse(noSteps);
    expect(result.success).toBe(true);
  });

  it("accepts optional message and thinking blobs", () => {
    const result = StrategySchema.safeParse({
      ...validStrategy,
      messages: [{ role: "user", content: "hello", timestamp: "2026-01-01" }],
      thinking: { reasoning: "Let me think..." },
    });
    expect(result.success).toBe(true);
  });
});
