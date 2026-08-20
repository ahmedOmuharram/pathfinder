/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { EnrichmentTerm } from "@pathfinder/shared";
import { EnrichmentTable } from "./EnrichmentTable";

function term(overrides: Partial<EnrichmentTerm> = {}): EnrichmentTerm {
  return {
    termId: "GO:0004672",
    termName: "protein kinase activity",
    geneCount: 3,
    backgroundCount: 120,
    foldEnrichment: 3.48,
    oddsRatio: 4.12,
    pValue: 0.0001,
    fdr: 0.002,
    bonferroni: 0.005,
    genes: [],
    ...overrides,
  };
}

describe("EnrichmentTable", () => {
  afterEach(cleanup);

  it("shows the numbers of a finite term", () => {
    render(<EnrichmentTable terms={[term()]} />);
    expect(screen.getByText("3.48")).toBeTruthy();
    expect(screen.getByText("1.00e-4")).toBeTruthy();
    expect(screen.getByText("2.00e-3")).toBeTruthy();
  });

  it("shows an unbounded fold enrichment as Inf and an unknown p as n/a", () => {
    render(<EnrichmentTable terms={[term({ foldEnrichment: null, pValue: null })]} />);
    expect(screen.getByText("Inf")).toBeTruthy();
    expect(screen.getByText("n/a")).toBeTruthy();
  });

  it("shows an unbounded odds ratio and an unknown bonferroni in the detail row", async () => {
    render(<EnrichmentTable terms={[term({ oddsRatio: null, bonferroni: null })]} />);

    await userEvent.click(screen.getByText("protein kinase activity"));

    expect(screen.getByText("Inf")).toBeTruthy();
    expect(screen.getByText("n/a")).toBeTruthy();
  });
});
