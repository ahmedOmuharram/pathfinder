import { describe, expect, it } from "vitest";
import { parseJsonRecord } from "@/features/chat/utils/parseJson";

describe("parseJsonRecord", () => {
  it("returns null for non-string", () => {
    expect(parseJsonRecord(null)).toBeNull();
    expect(parseJsonRecord({})).toBeNull();
  });

  it("returns record for object JSON, else null", () => {
    expect(parseJsonRecord(JSON.stringify({ a: 1 }))).toEqual({ a: 1 });
    expect(parseJsonRecord(JSON.stringify([1, 2]))).toBeNull();
    expect(parseJsonRecord("not json")).toBeNull();
  });
});
