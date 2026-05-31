/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataPlanArtifact } from "./DataPlanArtifact";

describe("DataPlanArtifact", () => {
  it("renders plan steps and rationale", () => {
    render(
      <DataPlanArtifact
        data={{
          planId: "p1",
          rationale: "Two-step approach for erythrocytic stage genes",
          steps: [
            { order: 0, searchName: "GenesByTextSearch", rationale: "keyword filter" },
            {
              order: 1,
              searchName: "GenesByRNASeqEvidence",
              rationale: "expression data",
            },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("data-plan-artifact")).toBeInTheDocument();
    expect(screen.getByText("GenesByTextSearch")).toBeInTheDocument();
    expect(screen.getByText("GenesByRNASeqEvidence")).toBeInTheDocument();
    expect(
      screen.getByText("Two-step approach for erythrocytic stage genes"),
    ).toBeInTheDocument();
  });
});
