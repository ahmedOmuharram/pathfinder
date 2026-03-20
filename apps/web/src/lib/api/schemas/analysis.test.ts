import { describe, expect, it } from "vitest";
import { CustomEnrichmentResultSchema } from "./analysis";

const validResult = {
  geneSetName: "kinases",
  geneSetSize: 120,
  overlapCount: 15,
  overlapGenes: ["PF3D7_0106300", "PF3D7_1211900"],
  backgroundSize: 5000,
  tpCount: 15,
  foldEnrichment: 2.5,
  pValue: 0.001,
  oddsRatio: 3.2,
};

describe("CustomEnrichmentResultSchema", () => {
  it("parses a valid enrichment result", () => {
    const result = CustomEnrichmentResultSchema.safeParse(validResult);
    expect(result.success).toBe(true);
    expect(result.data?.geneSetName).toBe("kinases");
    expect(result.data?.overlapGenes).toHaveLength(2);
  });

  it("passes through extra fields from backend", () => {
    const result = CustomEnrichmentResultSchema.safeParse({
      ...validResult,
      adjustedPValue: 0.005,
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>)["adjustedPValue"]).toBe(0.005);
  });

  it("rejects missing required fields", () => {
    const { pValue: _, ...noPValue } = validResult;
    const result = CustomEnrichmentResultSchema.safeParse(noPValue);
    expect(result.success).toBe(false);
  });

  it("rejects non-array overlapGenes", () => {
    const result = CustomEnrichmentResultSchema.safeParse({
      ...validResult,
      overlapGenes: "not-an-array",
    });
    expect(result.success).toBe(false);
  });

  it("accepts empty overlapGenes array", () => {
    const result = CustomEnrichmentResultSchema.safeParse({
      ...validResult,
      overlapCount: 0,
      overlapGenes: [],
    });
    expect(result.success).toBe(true);
    expect(result.data?.overlapGenes).toEqual([]);
  });
});
