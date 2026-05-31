/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataVerificationSummary } from "./DataVerificationSummary";

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
