/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataGeneSet } from "./DataGeneSet";

describe("DataGeneSet", () => {
  it("renders gene set info", () => {
    render(
      <DataGeneSet
        data={{
          geneSetId: "gs1",
          name: "Erythrocytic Transcripts",
          geneCount: 342,
          siteId: "plasmodb",
        }}
      />,
    );
    expect(screen.getByTestId("data-gene-set")).toBeInTheDocument();
    expect(screen.getByText("Erythrocytic Transcripts")).toBeInTheDocument();
    expect(screen.getByText("342 genes")).toBeInTheDocument();
    expect(screen.getByText("plasmodb")).toBeInTheDocument();
  });
});
