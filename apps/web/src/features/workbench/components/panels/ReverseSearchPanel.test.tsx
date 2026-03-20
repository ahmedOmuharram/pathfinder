// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mock stores and API — vi.mock factories must not reference outer variables
// ---------------------------------------------------------------------------

const storeState: Record<string, unknown> = {
  geneSets: [],
  activeSetId: null,
  expandedPanels: new Set(["reverse-search"]),
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

const sessionState: Record<string, unknown> = {
  selectedSite: "PlasmoDB",
};

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector(sessionState),
}));

const mockRequestJson = vi.fn();
vi.mock("@/lib/api/http", () => ({
  requestJson: (...args: unknown[]) => mockRequestJson(...args),
}));

// Mock GeneChipInput — render a minimal stub that exposes label and lets
// tests drive onChange via a data-testid button.
let capturedOnChange: Record<string, (ids: string[]) => void> = {};

vi.mock("../GeneChipInput", () => ({
  GeneChipInput: ({
    label,
    onChange,
    value,
    tint,
    required,
  }: {
    label: string;
    onChange: (ids: string[]) => void;
    value: string[];
    tint?: string;
    required?: boolean;
  }) => {
    // Store onChange so tests can call it
    capturedOnChange[label] = onChange;
    return (
      <div data-testid={`gene-chip-input-${tint ?? "neutral"}`}>
        <span>{label}</span>
        {required && <span>*</span>}
        <span data-testid={`chip-count-${tint ?? "neutral"}`}>{value.length}</span>
      </div>
    );
  },
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { ReverseSearchPanel } from "./ReverseSearchPanel";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ReverseSearchPanel", () => {
  afterEach(() => {
    cleanup();
    mockRequestJson.mockReset();
    capturedOnChange = {};
  });

  beforeEach(() => {
    storeState["geneSets"] = [
      { id: "gs-1", name: "Test Set", geneIds: ["G1", "G2"], siteId: "PlasmoDB" },
    ];
    storeState["activeSetId"] = "gs-1";
    storeState["expandedPanels"] = new Set(["reverse-search"]);
    sessionState["selectedSite"] = "PlasmoDB";
  });

  it("renders GeneChipInput with correct labels", () => {
    render(<ReverseSearchPanel />);
    expect(screen.getByText("Positive Gene IDs")).toBeTruthy();
    expect(screen.getByText("Negative Gene IDs")).toBeTruthy();
    expect(screen.getByTestId("gene-chip-input-positive")).toBeTruthy();
    expect(screen.getByTestId("gene-chip-input-negative")).toBeTruthy();
  });

  it("shows error when searching with no positive genes", async () => {
    render(<ReverseSearchPanel />);

    const buttons = screen.getAllByRole("button", { name: /search/i });
    const runButton = buttons[buttons.length - 1]!;
    fireEvent.click(runButton);

    await waitFor(() => {
      expect(screen.getByText("Enter at least one positive gene ID.")).toBeTruthy();
    });
  });

  it("shows ranked results table after search", async () => {
    mockRequestJson.mockResolvedValueOnce([
      {
        geneSetId: "gs-1",
        name: "Test Set",
        searchName: "GenesByTaxon",
        recall: 0.8,
        precision: 0.6,
        f1: 0.686,
        resultCount: 100,
        overlapCount: 4,
      },
    ]);

    render(<ReverseSearchPanel />);

    // Drive positive genes via the captured onChange callback
    const positiveOnChange = capturedOnChange["Positive Gene IDs"];
    expect(positiveOnChange).toBeDefined();

    // Flush the state update so the panel sees the new gene IDs
    act(() => {
      positiveOnChange!(["G1", "G2", "G3", "G4", "G5"]);
    });

    // Click Search after state has settled
    const buttons2 = screen.getAllByRole("button", { name: /search/i });
    const runButton2 = buttons2[buttons2.length - 1]!;
    fireEvent.click(runButton2);

    await waitFor(() => {
      expect(screen.getByText("Test Set")).toBeTruthy();
    });
    expect(screen.getByText("80.0%")).toBeTruthy();
  });

  it("disabled when no site selected", () => {
    sessionState["selectedSite"] = "";

    render(<ReverseSearchPanel />);
    expect(screen.getByText("Reverse Search")).toBeTruthy();
    // When disabled, the panel body (containing GeneChipInput) is not rendered
    expect(screen.queryByTestId("gene-chip-input-positive")).toBeNull();
  });
});
