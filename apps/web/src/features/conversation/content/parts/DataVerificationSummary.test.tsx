/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataVerificationSummary } from "./DataVerificationSummary";

describe("DataVerificationSummary figure", () => {
  it("captions the figure with the checks that passed out of the total", () => {
    render(
      <DataVerificationSummary
        data={{
          passed: false,
          summary: "One check failed",
          checks: [
            { name: "Gene count", passed: true },
            { name: "No duplicates", passed: true },
            { name: "Controls recovered", passed: false },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("figure-caption").textContent).toBe(
      "2 of 3 checks passed",
    );
    expect(screen.getByText("Verification").tagName).toBe("FIGCAPTION");
  });

  it("separates itself with a hairline, never with a card", () => {
    render(
      <DataVerificationSummary
        data={{ passed: true, summary: "All checks passed", checks: [] }}
      />,
    );
    expect(screen.getByTestId("figure").className.split(/\s+/)).toEqual([
      "my-6",
      "border-t",
      "border-border/60",
      "pt-4",
    ]);
    expect(screen.getByTestId("data-verification-summary").className).not.toMatch(
      /\bborder\b|\brounded-md\b/,
    );
  });
});

describe("DataVerificationSummary", () => {
  it("renders passed summary with checks", () => {
    render(
      <DataVerificationSummary
        data={{
          passed: true,
          summary: "All checks passed",
          checks: [
            { name: "Gene count", passed: true, detail: "342 genes" },
            { name: "No duplicates", passed: true },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("data-verification-summary")).toBeInTheDocument();
    expect(screen.getByText("Verification passed")).toBeInTheDocument();
    expect(screen.getByText("Gene count")).toBeInTheDocument();
  });

  it("renders failed summary", () => {
    render(
      <DataVerificationSummary
        data={{
          passed: false,
          summary: "Gene count too low",
          checks: [{ name: "Min gene count", passed: false, detail: "Only 2 genes" }],
        }}
      />,
    );
    expect(screen.getByText("Verification failed")).toBeInTheDocument();
  });
});
