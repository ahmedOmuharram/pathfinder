// @vitest-environment jsdom
import { queryOptions } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ControlSet } from "@pathfinder/shared";

const mockListControlSets = vi.fn<(siteId: string) => Promise<ControlSet[]>>();
vi.mock("../api/controlSets", () => ({
  listControlSets: (siteId: string) => mockListControlSets(siteId),
  controlSetsOptions: (siteId: string) =>
    queryOptions({
      queryKey: ["control-sets", "list", siteId] as const,
      queryFn: () => mockListControlSets(siteId),
      enabled: siteId !== "",
    }),
}));

import { ControlSetQuickPick } from "./ControlSetQuickPick";

afterEach(() => {
  cleanup();
  mockListControlSets.mockReset();
});

function makeControlSet(overrides: Partial<ControlSet> = {}): ControlSet {
  return {
    id: "cs-1",
    name: "Apicoplast kinases",
    siteId: "PlasmoDB",
    recordType: "gene",
    positiveIds: ["PF3D7_0100100", "PF3D7_0200200"],
    negativeIds: ["PF3D7_0900900"],
    source: "curation",
    tags: [],
    provenanceNotes: "",
    version: 1,
    isPublic: true,
    userId: null,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("ControlSetQuickPick", () => {
  it("loads and displays saved control sets", async () => {
    mockListControlSets.mockResolvedValue([
      makeControlSet({ id: "cs-1", name: "Apicoplast kinases" }),
      makeControlSet({ id: "cs-2", name: "Erythrocyte invasion" }),
    ]);
    render(<ControlSetQuickPick siteId="PlasmoDB" onSelect={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/apicoplast kinases/i)).toBeTruthy();
    });
  });

  it("calls onSelect with positive and negative IDs when a set is chosen", async () => {
    const cs = makeControlSet();
    mockListControlSets.mockResolvedValue([cs]);
    const onSelect = vi.fn();
    render(<ControlSetQuickPick siteId="PlasmoDB" onSelect={onSelect} />);
    await waitFor(() => expect(screen.getByText(/apicoplast kinases/i)).toBeTruthy());
    fireEvent.click(screen.getByText(/apicoplast kinases/i));
    expect(onSelect).toHaveBeenCalledWith(cs.positiveIds, cs.negativeIds);
  });

  it("shows empty state when no control sets exist", async () => {
    mockListControlSets.mockResolvedValue([]);
    render(<ControlSetQuickPick siteId="PlasmoDB" onSelect={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/no saved control sets/i)).toBeTruthy();
    });
  });

  it("shows control set details (count of positive/negative)", async () => {
    mockListControlSets.mockResolvedValue([makeControlSet()]);
    render(<ControlSetQuickPick siteId="PlasmoDB" onSelect={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/2\+/)).toBeTruthy(); // 2 positives
      expect(screen.getByText(/1\u2212/)).toBeTruthy(); // 1 negative (unicode minus)
    });
  });
});
