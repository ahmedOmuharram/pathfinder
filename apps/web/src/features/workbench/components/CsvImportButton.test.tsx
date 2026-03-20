// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CsvImportButton, parseGeneIds } from "./CsvImportButton";

describe("CsvImportButton", () => {
  it("renders import button", () => {
    render(<CsvImportButton onImport={() => {}} />);
    expect(screen.getByText(/Import/)).toBeTruthy();
  });

  it("renders hidden file input accepting csv/tsv/txt", () => {
    render(<CsvImportButton onImport={() => {}} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toBeTruthy();
    expect(input.accept).toBe(".csv,.tsv,.txt");
    expect(input.className).toContain("hidden");
  });
});

describe("parseGeneIds", () => {
  it("parses CSV content, skipping header row", () => {
    const csv = "geneId,product\nPF3D7_0100100,PfEMP1\nPF3D7_0200200,HSP90\n";
    expect(parseGeneIds(csv)).toEqual(["PF3D7_0100100", "PF3D7_0200200"]);
  });

  it("parses plain text (one ID per line)", () => {
    const txt = "PF3D7_0100100\nPF3D7_0200200\nPF3D7_0300300\n";
    expect(parseGeneIds(txt)).toEqual([
      "PF3D7_0100100",
      "PF3D7_0200200",
      "PF3D7_0300300",
    ]);
  });

  it("handles Windows line endings", () => {
    const txt = "PF3D7_0100100\r\nPF3D7_0200200\r\n";
    expect(parseGeneIds(txt)).toEqual(["PF3D7_0100100", "PF3D7_0200200"]);
  });

  it("trims whitespace from gene IDs", () => {
    const txt = "  PF3D7_0100100  \n  PF3D7_0200200  \n";
    expect(parseGeneIds(txt)).toEqual(["PF3D7_0100100", "PF3D7_0200200"]);
  });

  it("skips empty lines", () => {
    const txt = "PF3D7_0100100\n\n\nPF3D7_0200200\n";
    expect(parseGeneIds(txt)).toEqual(["PF3D7_0100100", "PF3D7_0200200"]);
  });

  it("skips header variants", () => {
    expect(parseGeneIds("GeneId\nPF3D7_0100100\n")).toEqual(["PF3D7_0100100"]);
    expect(parseGeneIds("geneid\nPF3D7_0100100\n")).toEqual(["PF3D7_0100100"]);
    expect(parseGeneIds("gene_id\nPF3D7_0100100\n")).toEqual(["PF3D7_0100100"]);
  });

  it("handles TSV by taking first column", () => {
    const tsv = "geneId\tproduct\nPF3D7_0100100\tPfEMP1\n";
    expect(parseGeneIds(tsv)).toEqual(["PF3D7_0100100"]);
  });
});
