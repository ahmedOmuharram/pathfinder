/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { DataMemoryRetrieved } from "./DataMemoryRetrieved";

describe("DataMemoryRetrieved", () => {
  it("renders one row per memory with its kind badge + name and a count header", () => {
    render(
      <DataMemoryRetrieved
        data={{
          memories: [
            {
              key: "m1",
              kind: "gene_set",
              name: "Erythrocytic genes",
              summary: "150 genes from PlasmoDB",
              score: 0.92,
            },
            {
              key: "m2",
              kind: "strategy",
              name: "Kinome sweep",
              summary: "prior strategy",
              score: 0.7,
            },
          ],
        }}
      />,
    );
    const card = screen.getByTestId("data-memory-retrieved");
    expect(card).toHaveTextContent("Recalled memories (2)");

    const rows = within(card).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("gene_set");
    expect(rows[0]).toHaveTextContent("Erythrocytic genes");
    expect(rows[1]).toHaveTextContent("strategy");
    expect(rows[1]).toHaveTextContent("Kinome sweep");
  });

  it("renders nothing (returns null) when there are no memories", () => {
    const { container } = render(<DataMemoryRetrieved data={{ memories: [] }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
