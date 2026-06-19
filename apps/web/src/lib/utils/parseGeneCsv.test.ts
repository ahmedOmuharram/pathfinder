import { describe, it, expect } from "vitest";
import { parseGeneCsv } from "./parseGeneCsv";

describe("parseGeneCsv", () => {
  it("parses CSV content, skipping header row and extra columns", () => {
    const csv = "geneId,product\nPF3D7_0100100,PfEMP1\nPF3D7_0200200,HSP90\n";
    expect(parseGeneCsv(csv)).toEqual(["PF3D7_0100100", "PF3D7_0200200"]);
  });

  it("parses plain text (one ID per line)", () => {
    const txt = "PF3D7_0100100\nPF3D7_0200200\nPF3D7_0300300\n";
    expect(parseGeneCsv(txt)).toEqual([
      "PF3D7_0100100",
      "PF3D7_0200200",
      "PF3D7_0300300",
    ]);
  });

  it("handles Windows line endings", () => {
    expect(parseGeneCsv("PF3D7_0100100\r\nPF3D7_0200200\r\n")).toEqual([
      "PF3D7_0100100",
      "PF3D7_0200200",
    ]);
  });

  it("trims whitespace from gene IDs", () => {
    expect(parseGeneCsv("  PF3D7_0100100  \n  PF3D7_0200200  \n")).toEqual([
      "PF3D7_0100100",
      "PF3D7_0200200",
    ]);
  });

  it("skips empty lines", () => {
    expect(parseGeneCsv("PF3D7_0100100\n\n\nPF3D7_0200200\n")).toEqual([
      "PF3D7_0100100",
      "PF3D7_0200200",
    ]);
  });

  it("skips header variants", () => {
    expect(parseGeneCsv("GeneId\nPF3D7_0100100\n")).toEqual(["PF3D7_0100100"]);
    expect(parseGeneCsv("geneid\nPF3D7_0100100\n")).toEqual(["PF3D7_0100100"]);
    expect(parseGeneCsv("gene_id\nPF3D7_0100100\n")).toEqual(["PF3D7_0100100"]);
  });

  it("handles TSV by taking first column", () => {
    expect(parseGeneCsv("geneId\tproduct\nPF3D7_0100100\tPfEMP1\n")).toEqual([
      "PF3D7_0100100",
    ]);
  });

  it("deduplicates preserving first-occurrence order", () => {
    const txt = "PF3D7_0100100\nPF3D7_0200200\nPF3D7_0100100\n";
    expect(parseGeneCsv(txt)).toEqual(["PF3D7_0100100", "PF3D7_0200200"]);
  });

  it("returns empty array for empty input", () => {
    expect(parseGeneCsv("")).toEqual([]);
    expect(parseGeneCsv("   ")).toEqual([]);
  });
});
