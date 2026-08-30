/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataGeneSet } from "./DataGeneSet";

const GENE_SET = {
  geneSetId: "gs1",
  name: "Erythrocytic Transcripts",
  geneCount: 3420,
  siteId: "plasmodb",
};

describe("DataGeneSet", () => {
  it("titles the figure with the gene set name", () => {
    render(<DataGeneSet data={GENE_SET} />);
    expect(screen.getByText("Erythrocytic Transcripts").tagName).toBe("FIGCAPTION");
    expect(screen.getByTestId("data-gene-set")).toHaveTextContent("Gene set created");
  });

  it("captions the figure with the gene count and the site", () => {
    render(<DataGeneSet data={GENE_SET} />);
    expect(screen.getByTestId("figure-caption").textContent).toBe(
      "3,420 genes on plasmodb",
    );
  });

  it("separates itself with a hairline, never with a card", () => {
    render(<DataGeneSet data={GENE_SET} />);
    expect(screen.getByTestId("figure").className.split(/\s+/)).toEqual([
      "my-6",
      "border-t",
      "border-border/60",
      "pt-4",
    ]);
    expect(screen.getByTestId("data-gene-set").className).not.toMatch(
      /\bborder\b|\brounded-md\b|\bbg-card\b/,
    );
  });
});
