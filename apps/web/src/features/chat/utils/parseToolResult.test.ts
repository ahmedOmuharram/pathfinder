import { describe, expect, it } from "vitest";
import { parseToolResult } from "@/features/chat/utils/parseToolResult";

describe("parseToolResult", () => {
  it("returns null for empty input", () => {
    expect(parseToolResult()).toBeNull();
    expect(parseToolResult("")).toBeNull();
  });

  it("returns null for non-object JSON", () => {
    expect(parseToolResult(JSON.stringify("x"))).toBeNull();
    expect(parseToolResult(JSON.stringify([]))).toBeNull();
  });

  it("extracts graphSnapshot if it is a record", () => {
    const out = parseToolResult(JSON.stringify({ graphSnapshot: { a: 1 } }));
    expect(out).toEqual({ graphSnapshot: { a: 1 } });
  });

  it("returns {graphSnapshot: undefined} when JSON object but missing/invalid snapshot", () => {
    expect(parseToolResult(JSON.stringify({}))).toEqual({ graphSnapshot: undefined });
    expect(parseToolResult(JSON.stringify({ graphSnapshot: [] }))).toEqual({
      graphSnapshot: undefined,
    });
  });
});
