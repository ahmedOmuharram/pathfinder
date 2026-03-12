import { describe, it, expect } from "vitest";
import { extractSpecVocabulary } from "./stepEditorUtils";
import { buildContextValues } from "@/lib/utils/buildContextValues";

// ---------------------------------------------------------------------------
// extractSpecVocabulary
// ---------------------------------------------------------------------------
describe("extractSpecVocabulary", () => {
  it("returns vocabulary when present", () => {
    expect(extractSpecVocabulary({ vocabulary: ["a", "b"] })).toEqual(["a", "b"]);
  });

  it("falls back to values when vocabulary is absent", () => {
    expect(extractSpecVocabulary({ values: [1, 2, 3] })).toEqual([1, 2, 3]);
  });

  it("falls back to items when vocabulary and values are absent", () => {
    expect(extractSpecVocabulary({ items: ["x"] })).toEqual(["x"]);
  });

  it("falls back to terms", () => {
    expect(extractSpecVocabulary({ terms: ["t1", "t2"] })).toEqual(["t1", "t2"]);
  });

  it("falls back to options", () => {
    expect(extractSpecVocabulary({ options: [{ label: "A", value: "a" }] })).toEqual([
      { label: "A", value: "a" },
    ]);
  });

  it("falls back to allowedValues as last resort", () => {
    expect(extractSpecVocabulary({ allowedValues: ["yes", "no"] })).toEqual([
      "yes",
      "no",
    ]);
  });

  it("returns undefined when no vocabulary-like field is set", () => {
    expect(extractSpecVocabulary({ name: "param", type: "string" })).toBeUndefined();
  });

  it("prefers vocabulary over values (precedence chain)", () => {
    expect(extractSpecVocabulary({ vocabulary: ["v"], values: ["x"] })).toEqual(["v"]);
  });

  it("prefers values over items", () => {
    expect(extractSpecVocabulary({ values: ["v"], items: ["i"] })).toEqual(["v"]);
  });

  it("handles null vocabulary gracefully (null is nullish, falls through)", () => {
    // null is nullish so ?? will skip it... wait, null IS nullish for ??
    // Actually spec.vocabulary ?? spec.values — if vocabulary is null, ?? falls through
    expect(extractSpecVocabulary({ vocabulary: null, values: ["fallback"] })).toEqual([
      "fallback",
    ]);
  });

  it("does NOT fall through when vocabulary is 0 or empty string (non-nullish falsy)", () => {
    // 0 and "" are not nullish (not null/undefined), so ?? returns them
    expect(extractSpecVocabulary({ vocabulary: 0, values: ["x"] })).toBe(0);
    expect(extractSpecVocabulary({ vocabulary: "", values: ["x"] })).toBe("");
  });

  it("returns empty array vocabulary as-is (not falling through)", () => {
    expect(extractSpecVocabulary({ vocabulary: [], values: ["x"] })).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// buildContextValues
// ---------------------------------------------------------------------------
describe("buildContextValues", () => {
  describe("filtering out sentinel and empty values", () => {
    it("excludes @@fake@@ string values", () => {
      const result = buildContextValues({ a: "@@fake@@", b: "real" });
      expect(result).toEqual({ b: "real" });
    });

    it("excludes arrays containing @@fake@@", () => {
      const result = buildContextValues({
        a: ["@@fake@@"],
        b: ["x", "y"],
      });
      expect(result).toEqual({ b: ["x", "y"] });
    });

    it("excludes array with @@fake@@ among other values", () => {
      const result = buildContextValues({
        a: ["ok", "@@fake@@"],
      });
      expect(result).toEqual({});
    });

    it("excludes null values", () => {
      const result = buildContextValues({ a: null, b: "ok" });
      expect(result).toEqual({ b: "ok" });
    });

    it("excludes undefined values", () => {
      const result = buildContextValues({ a: undefined, b: 42 });
      expect(result).toEqual({ b: 42 });
    });

    it("excludes empty string values", () => {
      const result = buildContextValues({ a: "", b: "ok" });
      expect(result).toEqual({ b: "ok" });
    });

    it("excludes empty array values", () => {
      const result = buildContextValues({ a: [], b: [1] });
      expect(result).toEqual({ b: [1] });
    });
  });

  describe("retaining valid values", () => {
    it("keeps non-empty strings", () => {
      const result = buildContextValues({ name: "hello" });
      expect(result).toEqual({ name: "hello" });
    });

    it("keeps numbers (including 0)", () => {
      const result = buildContextValues({ count: 0, size: 10 });
      expect(result).toEqual({ count: 0, size: 10 });
    });

    it("keeps booleans", () => {
      const result = buildContextValues({ flag: false, other: true });
      expect(result).toEqual({ flag: false, other: true });
    });

    it("keeps non-empty arrays", () => {
      const result = buildContextValues({ items: ["a", "b"] });
      expect(result).toEqual({ items: ["a", "b"] });
    });

    it("keeps objects", () => {
      const result = buildContextValues({ config: { x: 1 } });
      expect(result).toEqual({ config: { x: 1 } });
    });
  });

  describe("allowedKeys filtering", () => {
    it("only includes keys in the allowedKeys list", () => {
      const result = buildContextValues({ a: "yes", b: "no", c: "maybe" }, ["a", "c"]);
      expect(result).toEqual({ a: "yes", c: "maybe" });
    });

    it("still filters out sentinel values even when key is allowed", () => {
      const result = buildContextValues({ a: "@@fake@@", b: "real" }, ["a", "b"]);
      expect(result).toEqual({ b: "real" });
    });

    it("returns empty when no keys match", () => {
      const result = buildContextValues({ a: "val" }, ["b", "c"]);
      expect(result).toEqual({});
    });

    it("includes all valid values when allowedKeys is undefined", () => {
      const result = buildContextValues({ a: "x", b: "y" });
      expect(result).toEqual({ a: "x", b: "y" });
    });

    it("handles empty allowedKeys array (nothing passes)", () => {
      const result = buildContextValues({ a: "x" }, []);
      expect(result).toEqual({});
    });
  });

  describe("combined edge cases", () => {
    it("handles all-filtered-out input", () => {
      const result = buildContextValues({
        a: null,
        b: undefined,
        c: "",
        d: [],
        e: "@@fake@@",
        f: ["@@fake@@"],
      });
      expect(result).toEqual({});
    });

    it("handles empty input", () => {
      expect(buildContextValues({})).toEqual({});
    });
  });
});
