/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { VariantComparison } from "@pathfinder/shared";

import { DataVariantComparison } from "./DataVariantComparison";

const COMPARISON: VariantComparison = {
  variants: [
    {
      label: "kinases",
      searchName: "GenesByText",
      geneCount: 1105,
      uniqueCount: 84,
      sampleUniqueGenes: ["PF3D7_0100100"],
    },
    {
      label: "phosphatases",
      searchName: "GenesByText",
      geneCount: 342,
      uniqueCount: 12,
      sampleUniqueGenes: [],
    },
  ],
  overlaps: [{ a: "kinases", b: "phosphatases", shared: 30, jaccard: 0.02 }],
  truncated: false,
};

describe("DataVariantComparison", () => {
  it("captions the figure with the variant count and the largest set", () => {
    render(<DataVariantComparison data={COMPARISON} />);
    expect(screen.getByTestId("figure-caption").textContent).toBe(
      "2 variants, 1,105 genes in the largest",
    );
  });

  it("titles the figure Variants and keeps every label in the body", () => {
    render(<DataVariantComparison data={COMPARISON} />);
    const title = screen.getByText("Variants");
    expect(title.tagName).toBe("FIGCAPTION");
    const card = screen.getByTestId("data-variant-comparison");
    expect(card).toHaveTextContent("kinases");
    expect(card).toHaveTextContent("phosphatases");
  });

  it("reads zero in the largest when every variant failed", () => {
    render(
      <DataVariantComparison
        data={{
          variants: [
            {
              label: "kinases",
              searchName: "GenesByText",
              geneCount: 0,
              uniqueCount: 0,
              sampleUniqueGenes: [],
              error: "search timed out",
            },
          ],
          overlaps: [],
        }}
      />,
    );
    expect(screen.getByTestId("figure-caption").textContent).toBe(
      "1 variants, 0 genes in the largest",
    );
    expect(screen.getByTestId("data-variant-comparison")).toHaveTextContent(
      "failed: search timed out",
    );
  });

  it("separates itself with a hairline, never with a card", () => {
    render(<DataVariantComparison data={COMPARISON} />);
    expect(screen.getByTestId("figure").className.split(/\s+/)).toEqual([
      "my-6",
      "border-t",
      "border-border/60",
      "pt-4",
    ]);
    expect(screen.getByTestId("data-variant-comparison").className).not.toMatch(
      /\bborder\b|\brounded-md\b|\bbg-card\b/,
    );
  });
});
