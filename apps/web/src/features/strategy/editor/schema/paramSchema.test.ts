// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { buildParamSchema } from "./paramSchema";
import type { ParamSpec } from "@pathfinder/shared";

function makeSpec(overrides: Partial<ParamSpec> = {}): ParamSpec {
  return {
    name: "test_param",
    type: "string",
    displayName: "Test",
    displayType: "",
    allowEmptyValue: true,
    isVisible: true,
    isNumber: false,
    countOnlyLeaves: false,
    ...overrides,
  } as ParamSpec;
}

describe("buildParamSchema", () => {
  it("builds a schema that accepts valid string values", () => {
    const specs = [makeSpec({ name: "organism", type: "string" })];
    const schema = buildParamSchema(specs);
    const result = schema.safeParse({ organism: "P. falciparum" });
    expect(result.success).toBe(true);
  });

  it("rejects empty string when allowEmptyValue is false", () => {
    const specs = [makeSpec({ name: "gene_id", allowEmptyValue: false })];
    const schema = buildParamSchema(specs);
    const result = schema.safeParse({ gene_id: "" });
    expect(result.success).toBe(false);
  });

  it("accepts empty string when allowEmptyValue is true", () => {
    const specs = [makeSpec({ name: "gene_id", allowEmptyValue: true })];
    const schema = buildParamSchema(specs);
    const result = schema.safeParse({ gene_id: "" });
    expect(result.success).toBe(true);
  });

  it("handles multi-pick params as string arrays", () => {
    const specs = [makeSpec({ name: "organisms", allowMultipleValues: true })];
    const schema = buildParamSchema(specs);
    const result = schema.safeParse({ organisms: ["P. falciparum", "P. vivax"] });
    expect(result.success).toBe(true);
  });

  it("rejects single string for multi-pick params", () => {
    const specs = [makeSpec({ name: "organisms", allowMultipleValues: true })];
    const schema = buildParamSchema(specs);
    const result = schema.safeParse({ organisms: "P. falciparum" });
    expect(result.success).toBe(false);
  });

  it("validates numeric params reject non-numeric strings", () => {
    const specs = [makeSpec({ name: "min_weight", type: "number", isNumber: true })];
    const schema = buildParamSchema(specs);
    expect(schema.safeParse({ min_weight: "50000" }).success).toBe(true);
    expect(schema.safeParse({ min_weight: "not-a-number" }).success).toBe(false);
  });

  it("accepts empty string for optional numeric params", () => {
    const specs = [makeSpec({ name: "min_weight", type: "number", isNumber: true, allowEmptyValue: true })];
    const schema = buildParamSchema(specs);
    expect(schema.safeParse({ min_weight: "" }).success).toBe(true);
  });

  it("builds schema for multiple params", () => {
    const specs = [
      makeSpec({ name: "organism", type: "string" }),
      makeSpec({ name: "min_weight", type: "number", isNumber: true }),
      makeSpec({ name: "go_terms", allowMultipleValues: true }),
    ];
    const schema = buildParamSchema(specs);
    const result = schema.safeParse({
      organism: "P. falciparum",
      min_weight: "50000",
      go_terms: ["GO:0006915"],
    });
    expect(result.success).toBe(true);
  });

  it("skips hidden params", () => {
    const specs = [
      makeSpec({ name: "visible_param" }),
      makeSpec({ name: "hidden_param", isVisible: false }),
    ];
    const schema = buildParamSchema(specs);
    const result = schema.safeParse({ visible_param: "val" });
    expect(result.success).toBe(true);
  });

  it("skips params with no name", () => {
    // Runtime API data can have missing fields despite the generated type
    const specs = [makeSpec({ name: undefined as unknown as string })];
    const schema = buildParamSchema(specs);
    expect(schema.safeParse({}).success).toBe(true);
  });

  it("returns empty schema for empty specs", () => {
    const schema = buildParamSchema([]);
    expect(schema.safeParse({}).success).toBe(true);
  });

  it("required multi-pick rejects empty array", () => {
    const specs = [makeSpec({ name: "orgs", allowMultipleValues: true, allowEmptyValue: false })];
    const schema = buildParamSchema(specs);
    expect(schema.safeParse({ orgs: [] }).success).toBe(false);
    expect(schema.safeParse({ orgs: ["val"] }).success).toBe(true);
  });

  it("multiPick flag also triggers array schema", () => {
    const specs = [makeSpec({ name: "items", multiPick: true })];
    const schema = buildParamSchema(specs);
    expect(schema.safeParse({ items: ["a", "b"] }).success).toBe(true);
    expect(schema.safeParse({ items: "a" }).success).toBe(false);
  });
});
