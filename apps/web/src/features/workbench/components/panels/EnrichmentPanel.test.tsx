// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { GeneSet } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Mock the workbench store
// ---------------------------------------------------------------------------

function makeGeneSet(overrides: Partial<GeneSet> = {}): GeneSet {
  return {
    id: "set-1",
    name: "Test Set",
    siteId: "PlasmoDB",
    geneIds: ["PF3D7_0100100", "PF3D7_0100200"],
    geneCount: 2,
    source: "strategy",
    searchName: "GenesByTaxon",
    recordType: "gene",
    parameters: { organism: "Plasmodium falciparum 3D7" },
    stepCount: 1,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const storeState: Record<string, unknown> = {
  activeSetId: "set-1" as string | null,
  geneSets: [] as GeneSet[],
  expandedPanels: new Set(["enrichment"]),
  togglePanel: vi.fn(),
};

vi.mock("../../store", () => ({
  useWorkbenchStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector(storeState),
}));
vi.mock("../../store/useWorkbenchStore", () => ({
  useWorkbenchStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector(storeState),
}));

// ---------------------------------------------------------------------------
// Mock the enrichment API
// ---------------------------------------------------------------------------

const mockEnrichGeneSet = vi.fn();

vi.mock("../../api/geneSets", () => ({
  enrichGeneSet: (...args: unknown[]) => mockEnrichGeneSet(...args),
}));

// ---------------------------------------------------------------------------
// Mock EnrichmentSection to simplify rendering
// ---------------------------------------------------------------------------

vi.mock("@/features/analysis", () => ({
  EnrichmentSection: () => <div data-testid="enrichment-results">Results</div>,
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { EnrichmentPanel } from "./EnrichmentPanel";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EnrichmentPanel", () => {
  afterEach(() => {
    cleanup();
    mockEnrichGeneSet.mockReset();
  });

  beforeEach(() => {
    storeState.activeSetId = "set-1";
    storeState.geneSets = [makeGeneSet()];
    storeState.expandedPanels = new Set(["enrichment"]);
  });

  // -----------------------------------------------------------------------
  // Button disabled when no active gene set
  // -----------------------------------------------------------------------
  it("disables the run button when no active gene set", () => {
    storeState.activeSetId = null;
    storeState.geneSets = [];

    render(<EnrichmentPanel />);

    const button = screen.getByRole("button", { name: /run enrichment/i });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  // -----------------------------------------------------------------------
  // Button disabled when no enrichment types selected
  // -----------------------------------------------------------------------
  it("disables the run button when no enrichment types are selected", () => {
    storeState.geneSets = [makeGeneSet()];
    storeState.activeSetId = "set-1";

    render(<EnrichmentPanel />);

    // Deselect all enrichment types (they start selected by default)
    const chips = ["GO:BP", "GO:MF", "GO:CC", "Pathway", "Word"];
    for (const label of chips) {
      fireEvent.click(screen.getByText(label));
    }

    const button = screen.getByRole("button", { name: /run enrichment/i });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  // -----------------------------------------------------------------------
  // Button enabled when both conditions met
  // -----------------------------------------------------------------------
  it("enables the run button when active gene set and enrichment types are selected", () => {
    storeState.geneSets = [makeGeneSet()];
    storeState.activeSetId = "set-1";

    render(<EnrichmentPanel />);

    // All types are selected by default
    const button = screen.getByRole("button", { name: /run enrichment/i });
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });

  it("re-enables the run button when an enrichment type is re-selected", () => {
    storeState.geneSets = [makeGeneSet()];
    storeState.activeSetId = "set-1";

    render(<EnrichmentPanel />);

    // Deselect all
    const chips = ["GO:BP", "GO:MF", "GO:CC", "Pathway", "Word"];
    for (const label of chips) {
      fireEvent.click(screen.getByText(label));
    }

    const button = screen.getByRole("button", { name: /run enrichment/i });
    expect((button as HTMLButtonElement).disabled).toBe(true);

    // Re-select one type
    fireEvent.click(screen.getByText("GO:BP"));
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });

  it("calls enrichGeneSet with correct arguments when run is clicked", async () => {
    storeState.geneSets = [makeGeneSet()];
    storeState.activeSetId = "set-1";

    mockEnrichGeneSet.mockResolvedValue([]);

    render(<EnrichmentPanel />);

    // Deselect all, then select only GO:BP and Pathway
    const allChips = ["GO:BP", "GO:MF", "GO:CC", "Pathway", "Word"];
    for (const label of allChips) {
      fireEvent.click(screen.getByText(label));
    }
    fireEvent.click(screen.getByText("GO:BP"));
    fireEvent.click(screen.getByText("Pathway"));

    fireEvent.click(screen.getByRole("button", { name: /run enrichment/i }));

    await waitFor(() => {
      expect(mockEnrichGeneSet).toHaveBeenCalledWith(
        "set-1",
        expect.arrayContaining(["go_process", "pathway"]),
      );
    });
  });
});
