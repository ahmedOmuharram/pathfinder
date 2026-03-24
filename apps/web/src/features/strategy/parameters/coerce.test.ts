import { describe, it, expect } from "vitest";
import type { ParamSpec } from "@/features/strategy/parameters/spec";
import { coerceMultiValue, coerceParametersForSpecs } from "./coerce";

// ---------------------------------------------------------------------------
// coerceMultiValue
// ---------------------------------------------------------------------------
describe("coerceMultiValue", () => {
  describe("nullish and empty inputs", () => {
    it("returns [] for null", () => {
      expect(coerceMultiValue(null)).toEqual([]);
    });

    it("returns [] for undefined", () => {
      expect(coerceMultiValue(undefined)).toEqual([]);
    });

    it("returns [] for empty string", () => {
      expect(coerceMultiValue("")).toEqual([]);
    });

    it("returns [] for whitespace-only string", () => {
      expect(coerceMultiValue("   ")).toEqual([]);
    });
  });

  describe("array inputs", () => {
    it("stringifies array elements", () => {
      expect(coerceMultiValue([1, 2, 3])).toEqual(["1", "2", "3"]);
    });

    it("filters out falsy-after-stringify entries (empty strings)", () => {
      expect(coerceMultiValue(["a", "", "b"])).toEqual(["a", "b"]);
    });

    it("returns empty for empty array", () => {
      expect(coerceMultiValue([])).toEqual([]);
    });

    it("returns [@@fake@@] sentinel when array contains @@fake@@", () => {
      expect(coerceMultiValue(["a", "@@fake@@", "b"])).toEqual(["@@fake@@"]);
    });

    it("handles array with only @@fake@@", () => {
      expect(coerceMultiValue(["@@fake@@"])).toEqual(["@@fake@@"]);
    });
  });

  describe("string inputs — JSON array parsing", () => {
    it("parses JSON array string", () => {
      expect(coerceMultiValue('["x","y"]')).toEqual(["x", "y"]);
    });

    it("parses JSON array with whitespace", () => {
      expect(coerceMultiValue('  ["a", "b"]  ')).toEqual(["a", "b"]);
    });

    it("returns [@@fake@@] if parsed JSON array contains sentinel", () => {
      expect(coerceMultiValue('["ok","@@fake@@"]')).toEqual(["@@fake@@"]);
    });

    it("falls through to single-value wrap when JSON is invalid", () => {
      expect(coerceMultiValue("[not-json")).toEqual(["[not-json"]);
    });

    it("falls through when JSON parses to non-array", () => {
      // JSON.parse of a number string won't be an array
      expect(coerceMultiValue("42")).toEqual(["42"]);
    });
  });

  describe("string inputs — CSV parsing", () => {
    it("does NOT split CSV without allowStringParsing + allowCsv", () => {
      expect(coerceMultiValue("a,b,c")).toEqual(["a,b,c"]);
    });

    it("does NOT split CSV with only allowStringParsing", () => {
      expect(coerceMultiValue("a,b,c", { allowStringParsing: true })).toEqual([
        "a,b,c",
      ]);
    });

    it("does NOT split CSV with only allowCsv", () => {
      expect(coerceMultiValue("a,b,c", { allowCsv: true })).toEqual(["a,b,c"]);
    });

    it("splits CSV when both allowStringParsing and allowCsv are true", () => {
      expect(
        coerceMultiValue("a, b , c", {
          allowStringParsing: true,
          allowCsv: true,
        }),
      ).toEqual(["a", "b", "c"]);
    });

    it("filters blanks from CSV split", () => {
      expect(
        coerceMultiValue("a,,b, ,c", {
          allowStringParsing: true,
          allowCsv: true,
        }),
      ).toEqual(["a", "b", "c"]);
    });

    it("returns [@@fake@@] from CSV if sentinel present", () => {
      expect(
        coerceMultiValue("ok,@@fake@@,other", {
          allowStringParsing: true,
          allowCsv: true,
        }),
      ).toEqual(["@@fake@@"]);
    });
  });

  describe("string inputs — sentinel handling", () => {
    it("returns [@@fake@@] for bare sentinel string", () => {
      expect(coerceMultiValue("@@fake@@")).toEqual(["@@fake@@"]);
    });
  });

  describe("scalar non-string inputs", () => {
    it("wraps a number as a string", () => {
      expect(coerceMultiValue(42)).toEqual(["42"]);
    });

    it("wraps a boolean as a string", () => {
      expect(coerceMultiValue(true)).toEqual(["true"]);
    });
  });
});

// ---------------------------------------------------------------------------
// coerceParametersForSpecs
// ---------------------------------------------------------------------------
/** Build a ParamSpec with required fields filled in. */
function spec(overrides: Partial<ParamSpec> & { name: string; type: string }): ParamSpec {
  return {
    allowEmptyValue: false,
    countOnlyLeaves: false,
    isNumber: false,
    isVisible: true,
    ...overrides,
  };
}

describe("coerceParametersForSpecs", () => {
  const multiSpec = spec({
    name: "organisms",
    type: "multi-pick",
    allowMultipleValues: true,
  });
  const scalarSpec = spec({ name: "threshold", type: "number" });
  const namelessSpec = spec({ name: "", type: "hidden" });

  it("coerces multi-param values through coerceMultiValue", () => {
    const result = coerceParametersForSpecs(
      { organisms: '["a","b"]', threshold: "5" },
      [multiSpec, scalarSpec],
    );
    expect(result["organisms"]).toEqual(["a", "b"]);
  });

  it("extracts first element for scalar params when value is array", () => {
    const result = coerceParametersForSpecs({ threshold: ["10", "20"] }, [scalarSpec]);
    expect(result["threshold"]).toBe("10");
  });

  it("leaves scalar value untouched when already scalar", () => {
    const result = coerceParametersForSpecs({ threshold: 42 }, [scalarSpec]);
    expect(result["threshold"]).toBe(42);
  });

  it("returns undefined for scalar spec with empty array value", () => {
    const result = coerceParametersForSpecs({ threshold: [] }, [scalarSpec]);
    expect(result["threshold"]).toBeUndefined();
  });

  it("skips specs with no name", () => {
    const result = coerceParametersForSpecs({ organisms: ["x"], threshold: 5 }, [
      namelessSpec,
      multiSpec,
      scalarSpec,
    ]);
    expect(result["organisms"]).toEqual(["x"]);
    expect(result["threshold"]).toBe(5);
  });

  it("preserves extra keys not in specs", () => {
    const result = coerceParametersForSpecs({ organisms: ["a"], extra: "val" }, [
      multiSpec,
    ]);
    expect(result["extra"]).toBe("val");
    expect(result["organisms"]).toEqual(["a"]);
  });

  it("passes options through to coerceMultiValue", () => {
    const result = coerceParametersForSpecs({ organisms: "a,b,c" }, [multiSpec], {
      allowStringParsing: true,
      allowCsv: true,
    });
    expect(result["organisms"]).toEqual(["a", "b", "c"]);
  });
});
