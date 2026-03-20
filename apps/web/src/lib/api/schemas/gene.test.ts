import { describe, expect, it } from "vitest";
import {
  OrganismListResponseSchema,
  GeneSearchResultSchema,
  GeneSearchResponseSchema,
  ResolvedGeneSchema,
  GeneResolveResponseSchema,
} from "./gene";

describe("OrganismListResponseSchema", () => {
  it("parses a valid organism list response", () => {
    const result = OrganismListResponseSchema.safeParse({
      organisms: ["P. falciparum", "P. vivax"],
    });
    expect(result.success).toBe(true);
    expect(result.data?.organisms).toEqual(["P. falciparum", "P. vivax"]);
  });

  it("passes through extra fields", () => {
    const result = OrganismListResponseSchema.safeParse({
      organisms: [],
      totalCount: 0,
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>)["totalCount"]).toBe(0);
  });

  it("rejects missing organisms field", () => {
    const result = OrganismListResponseSchema.safeParse({});
    expect(result.success).toBe(false);
  });
});

const validGeneResult = {
  geneId: "PF3D7_1133400",
  displayName: "PF3D7_1133400",
  organism: "Plasmodium falciparum 3D7",
  product: "apical membrane antigen 1",
  matchedFields: ["product"],
  geneName: "",
  geneType: "",
  location: "",
};

describe("GeneSearchResultSchema", () => {
  it("parses a valid gene search result", () => {
    const result = GeneSearchResultSchema.safeParse(validGeneResult);
    expect(result.success).toBe(true);
  });

  it("accepts optional fields", () => {
    const result = GeneSearchResultSchema.safeParse({
      ...validGeneResult,
      geneName: "ama1",
      geneType: "protein_coding",
      location: "chr11:1234-5678",
    });
    expect(result.success).toBe(true);
    expect(result.data?.geneName).toBe("ama1");
  });

  it("rejects missing required fields", () => {
    const result = GeneSearchResultSchema.safeParse({
      geneId: "PF3D7_1133400",
    });
    expect(result.success).toBe(false);
  });
});

describe("GeneSearchResponseSchema", () => {
  it("parses a valid search response", () => {
    const result = GeneSearchResponseSchema.safeParse({
      results: [validGeneResult],
      totalCount: 1,
      suggestedOrganisms: [],
    });
    expect(result.success).toBe(true);
    expect(result.data?.results).toHaveLength(1);
    expect(result.data?.totalCount).toBe(1);
  });

  it("accepts suggestedOrganisms with values", () => {
    const result = GeneSearchResponseSchema.safeParse({
      results: [],
      totalCount: 0,
      suggestedOrganisms: ["P. falciparum"],
    });
    expect(result.success).toBe(true);
    expect(result.data?.suggestedOrganisms).toEqual(["P. falciparum"]);
  });

  it("rejects missing totalCount", () => {
    const result = GeneSearchResponseSchema.safeParse({
      results: [],
      suggestedOrganisms: [],
    });
    expect(result.success).toBe(false);
  });
});

const validResolvedGene = {
  geneId: "PF3D7_1133400",
  displayName: "PF3D7_1133400",
  organism: "Plasmodium falciparum 3D7",
  product: "apical membrane antigen 1",
  geneName: "ama1",
  geneType: "protein_coding",
  location: "chr11:1234-5678",
};

describe("ResolvedGeneSchema", () => {
  it("parses a valid resolved gene", () => {
    const result = ResolvedGeneSchema.safeParse(validResolvedGene);
    expect(result.success).toBe(true);
  });

  it("rejects missing geneName (required for resolved)", () => {
    const { geneName: _, ...noGeneName } = validResolvedGene;
    const result = ResolvedGeneSchema.safeParse(noGeneName);
    expect(result.success).toBe(false);
  });
});

describe("GeneResolveResponseSchema", () => {
  it("parses a valid resolve response", () => {
    const result = GeneResolveResponseSchema.safeParse({
      resolved: [validResolvedGene],
      unresolved: ["INVALID_ID"],
    });
    expect(result.success).toBe(true);
    expect(result.data?.resolved).toHaveLength(1);
    expect(result.data?.unresolved).toEqual(["INVALID_ID"]);
  });

  it("accepts empty arrays", () => {
    const result = GeneResolveResponseSchema.safeParse({
      resolved: [],
      unresolved: [],
    });
    expect(result.success).toBe(true);
  });

  it("rejects missing resolved field", () => {
    const result = GeneResolveResponseSchema.safeParse({
      unresolved: [],
    });
    expect(result.success).toBe(false);
  });
});
