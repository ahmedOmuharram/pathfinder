/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataMemoryRetrieved } from "./DataMemoryRetrieved";

describe("DataMemoryRetrieved", () => {
  it("renders memory items", () => {
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
          ],
        }}
      />,
    );
    expect(screen.getByTestId("data-memory-retrieved")).toBeInTheDocument();
    expect(screen.getByText("Erythrocytic genes")).toBeInTheDocument();
    expect(screen.getByText("gene_set")).toBeInTheDocument();
  });

  it("renders nothing for empty memories", () => {
    const { container } = render(
      <DataMemoryRetrieved data={{ memories: [] }} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
