import { describe, expect, it } from "vitest";
import {
  VEuPathDBSiteSchema,
  VEuPathDBSiteListSchema,
  RecordTypeSchema,
  RecordTypeListSchema,
  SearchSchema,
  SearchListSchema,
  ParamSpecSchema,
  ParamSpecListSchema,
  SearchValidationResponseSchema,
} from "./site";

// ---------------------------------------------------------------------------
// VEuPathDBSiteSchema
// ---------------------------------------------------------------------------

const validSite = {
  id: "plasmodb",
  name: "PlasmoDB",
  displayName: "PlasmoDB (Plasmodium)",
  baseUrl: "https://plasmodb.org",
  projectId: "PlasmoDB",
  isPortal: false,
};

describe("VEuPathDBSiteSchema", () => {
  it("parses a valid site", () => {
    const result = VEuPathDBSiteSchema.safeParse(validSite);
    expect(result.success).toBe(true);
    expect(result.data?.id).toBe("plasmodb");
  });

  it("passes through extra fields", () => {
    const result = VEuPathDBSiteSchema.safeParse({ ...validSite, region: "global" });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>)["region"]).toBe("global");
  });

  it("rejects missing isPortal", () => {
    const { isPortal: _, ...noPortal } = validSite;
    const result = VEuPathDBSiteSchema.safeParse(noPortal);
    expect(result.success).toBe(false);
  });
});

describe("VEuPathDBSiteListSchema", () => {
  it("parses an array of sites", () => {
    const result = VEuPathDBSiteListSchema.safeParse([validSite]);
    expect(result.success).toBe(true);
    expect(result.data).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// RecordTypeSchema
// ---------------------------------------------------------------------------

describe("RecordTypeSchema", () => {
  it("parses a valid record type", () => {
    const result = RecordTypeSchema.safeParse({
      name: "gene",
      displayName: "Gene",
    });
    expect(result.success).toBe(true);
  });

  it("accepts optional description", () => {
    const result = RecordTypeSchema.safeParse({
      name: "gene",
      displayName: "Gene",
      description: "A gene record",
    });
    expect(result.success).toBe(true);
    expect(result.data?.description).toBe("A gene record");
  });
});

describe("RecordTypeListSchema", () => {
  it("parses an array of record types", () => {
    const result = RecordTypeListSchema.safeParse([
      { name: "gene", displayName: "Gene" },
      { name: "compound", displayName: "Compound" },
    ]);
    expect(result.success).toBe(true);
    expect(result.data).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// SearchSchema
// ---------------------------------------------------------------------------

describe("SearchSchema", () => {
  it("parses a valid search", () => {
    const result = SearchSchema.safeParse({
      name: "GeneByTextSearch",
      displayName: "Text Search",
      recordType: "gene",
    });
    expect(result.success).toBe(true);
  });

  it("rejects missing recordType", () => {
    const result = SearchSchema.safeParse({
      name: "GeneByTextSearch",
      displayName: "Text Search",
    });
    expect(result.success).toBe(false);
  });
});

describe("SearchListSchema", () => {
  it("parses an array of searches", () => {
    const result = SearchListSchema.safeParse([
      { name: "GeneByTextSearch", displayName: "Text", recordType: "gene" },
    ]);
    expect(result.success).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// ParamSpecSchema
// ---------------------------------------------------------------------------

describe("ParamSpecSchema", () => {
  it("parses a minimal param spec", () => {
    const result = ParamSpecSchema.safeParse({
      name: "text_expression",
      type: "string",
      allowEmptyValue: false,
      countOnlyLeaves: false,
      isNumber: false,
    });
    expect(result.success).toBe(true);
  });

  it("parses a full param spec with all optional fields", () => {
    const result = ParamSpecSchema.safeParse({
      name: "fold_change",
      displayName: "Fold Change",
      type: "string",
      allowEmptyValue: false,
      allowMultipleValues: false,
      multiPick: false,
      minSelectedCount: 1,
      maxSelectedCount: 1,
      countOnlyLeaves: false,
      initialDisplayValue: "2",
      vocabulary: [
        ["2", "2x"],
        ["4", "4x"],
      ],
      min: 0,
      max: 100,
      increment: 0.5,
      isNumber: true,
    });
    expect(result.success).toBe(true);
    expect(result.data?.isNumber).toBe(true);
  });

  it("accepts nullable min/max/increment", () => {
    const result = ParamSpecSchema.safeParse({
      name: "text",
      type: "string",
      allowEmptyValue: false,
      countOnlyLeaves: false,
      isNumber: false,
      min: null,
      max: null,
      increment: null,
    });
    expect(result.success).toBe(true);
  });
});

describe("ParamSpecListSchema", () => {
  it("parses an array of param specs", () => {
    const result = ParamSpecListSchema.safeParse([
      {
        name: "a",
        type: "string",
        allowEmptyValue: false,
        countOnlyLeaves: false,
        isNumber: false,
      },
      {
        name: "b",
        type: "number",
        allowEmptyValue: false,
        countOnlyLeaves: false,
        isNumber: true,
      },
    ]);
    expect(result.success).toBe(true);
    expect(result.data).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// SearchValidationResponseSchema
// ---------------------------------------------------------------------------

describe("SearchValidationResponseSchema", () => {
  it("parses a valid validation response", () => {
    const result = SearchValidationResponseSchema.safeParse({
      validation: {
        isValid: true,
        normalizedContextValues: { text_expression: "kinase" },
        errors: { general: [], byKey: {} },
      },
    });
    expect(result.success).toBe(true);
    expect(result.data?.validation.isValid).toBe(true);
  });

  it("parses a response with errors", () => {
    const result = SearchValidationResponseSchema.safeParse({
      validation: {
        isValid: false,
        normalizedContextValues: {},
        errors: {
          general: ["Invalid query"],
          byKey: { text_expression: ["Required"] },
        },
      },
    });
    expect(result.success).toBe(true);
    expect(result.data?.validation.isValid).toBe(false);
    expect(result.data?.validation.errors?.general).toEqual(["Invalid query"]);
  });

  it("rejects missing validation field", () => {
    const result = SearchValidationResponseSchema.safeParse({});
    expect(result.success).toBe(false);
  });
});
