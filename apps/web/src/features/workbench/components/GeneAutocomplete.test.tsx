// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { GeneSearchResponse } from "@pathfinder/shared";

const mockSearchGenes = vi.fn<(...args: unknown[]) => Promise<GeneSearchResponse>>();
vi.mock("@/lib/api/genes", () => ({
  searchGenes: (...args: unknown[]) => mockSearchGenes(...args),
}));

import { GeneAutocomplete } from "./GeneAutocomplete";

describe("GeneAutocomplete", () => {
  afterEach(() => {
    cleanup();
    mockSearchGenes.mockReset();
  });

  it("renders placeholder input", () => {
    render(<GeneAutocomplete siteId="PlasmoDB" onSelect={() => {}} />);
    expect(screen.getByPlaceholderText("Search genes...")).toBeTruthy();
  });

  it("calls searchGenes on input and shows results", async () => {
    mockSearchGenes.mockResolvedValue({
      results: [
        {
          geneId: "PF3D7_0100100",
          displayName: "PF3D7_0100100",
          organism: "Plasmodium falciparum 3D7",
          product: "erythrocyte membrane protein 1, PfEMP1",
          geneName: "",
          geneType: "",
          location: "",
          matchedFields: ["geneId"],
        },
      ],
      totalCount: 1,
      suggestedOrganisms: [],
    });

    render(<GeneAutocomplete siteId="PlasmoDB" onSelect={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText("Search genes..."), {
      target: { value: "PF3D7" },
    });

    await waitFor(() => {
      expect(screen.getByText("PF3D7_0100100")).toBeTruthy();
      expect(screen.getByText(/erythrocyte membrane protein/)).toBeTruthy();
    });
  });

  it("calls onSelect when a result is clicked and clears input", async () => {
    mockSearchGenes.mockResolvedValue({
      results: [
        {
          geneId: "PF3D7_0100100",
          displayName: "PF3D7_0100100",
          organism: "Plasmodium falciparum 3D7",
          product: "erythrocyte membrane protein 1",
          geneName: "",
          geneType: "",
          location: "",
          matchedFields: ["geneId"],
        },
      ],
      totalCount: 1,
      suggestedOrganisms: [],
    });
    const onSelect = vi.fn();

    render(<GeneAutocomplete siteId="PlasmoDB" onSelect={onSelect} />);
    fireEvent.change(screen.getByPlaceholderText("Search genes..."), {
      target: { value: "PF3D7" },
    });
    await waitFor(() => {
      expect(screen.getByText("PF3D7_0100100")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("PF3D7_0100100"));

    expect(onSelect).toHaveBeenCalledWith("PF3D7_0100100");
  });

  it("closes dropdown on Escape", async () => {
    mockSearchGenes.mockResolvedValue({
      results: [
        {
          geneId: "PF3D7_0100100",
          displayName: "PF3D7_0100100",
          organism: "Plasmodium falciparum 3D7",
          product: "test",
          geneName: "",
          geneType: "",
          location: "",
          matchedFields: ["geneId"],
        },
      ],
      totalCount: 1,
      suggestedOrganisms: [],
    });

    render(<GeneAutocomplete siteId="PlasmoDB" onSelect={() => {}} />);
    const input = screen.getByPlaceholderText("Search genes...");
    fireEvent.change(input, { target: { value: "PF3D7" } });
    await waitFor(() => {
      expect(screen.getByText("PF3D7_0100100")).toBeTruthy();
    });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByText("PF3D7_0100100")).toBeNull();
  });
});
