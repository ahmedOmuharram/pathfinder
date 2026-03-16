/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useGeneSetExport } from "./useGeneSetExport";
import type { Strategy } from "@pathfinder/shared";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/features/workbench/api/geneSets", () => ({
  createGeneSetFromStrategy: vi.fn(),
}));

const mockPush = vi.fn();

const { createGeneSetFromStrategy } = await import("@/features/workbench/api/geneSets");
const mockCreate = vi.mocked(createGeneSetFromStrategy);

const baseStrategy: Strategy = {
  id: "s1",
  name: "Test Strategy",
  siteId: "plasmodb",
  recordType: "gene",
  rootStepId: "step-1",
  isSaved: false,
  steps: [
    {
      id: "step-1",
      kind: "search",
      displayName: "Step 1",
      searchName: "GeneByTextSearch",
      recordType: "gene",
      wdkStepId: 42,
      parameters: { text: "kinase" },
    },
  ],
  wdkStrategyId: 99,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("useGeneSetExport", () => {
  const mockAddGeneSet = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts with exporting=false", () => {
    const { result } = renderHook(() =>
      useGeneSetExport({ selectedSite: "plasmodb", addGeneSet: mockAddGeneSet }),
    );
    expect(result.current.exportingGeneSet).toBe(false);
  });

  it("exports a gene set from a strategy", async () => {
    const fakeGeneSet = { id: "gs1", name: "Test Strategy" };
    mockCreate.mockResolvedValue(fakeGeneSet as never);

    const { result } = renderHook(() =>
      useGeneSetExport({ selectedSite: "plasmodb", addGeneSet: mockAddGeneSet }),
    );

    await act(async () => {
      await result.current.handleExportAsGeneSet(baseStrategy);
    });

    expect(mockCreate).toHaveBeenCalledWith({
      name: "Test Strategy",
      siteId: "plasmodb",
      wdkStrategyId: 99,
      wdkStepId: 42,
      searchName: "GeneByTextSearch",
      recordType: "gene",
      parameters: { text: "kinase" },
    });
    expect(mockAddGeneSet).toHaveBeenCalledWith(fakeGeneSet);
    expect(mockPush).toHaveBeenCalledWith("/workbench/gs1");
    expect(result.current.exportingGeneSet).toBe(false);
  });

  it("does nothing when strategy has no wdkStrategyId", async () => {
    const noWdkStrategy = { ...baseStrategy, wdkStrategyId: undefined };
    const { result } = renderHook(() =>
      useGeneSetExport({ selectedSite: "plasmodb", addGeneSet: mockAddGeneSet }),
    );

    await act(async () => {
      await result.current.handleExportAsGeneSet(noWdkStrategy);
    });

    expect(mockCreate).not.toHaveBeenCalled();
    expect(result.current.exportingGeneSet).toBe(false);
  });

  it("handles errors gracefully and resets exporting state", async () => {
    mockCreate.mockRejectedValue(new Error("Network error"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { result } = renderHook(() =>
      useGeneSetExport({ selectedSite: "plasmodb", addGeneSet: mockAddGeneSet }),
    );

    await act(async () => {
      await result.current.handleExportAsGeneSet(baseStrategy);
    });

    expect(result.current.exportingGeneSet).toBe(false);
    expect(mockPush).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
