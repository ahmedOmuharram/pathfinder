// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CsvImportButton } from "./CsvImportButton";

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
