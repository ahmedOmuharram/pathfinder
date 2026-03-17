/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mock the stepResults API module
// ---------------------------------------------------------------------------

vi.mock("@/features/analysis/api/stepResults", () => ({
  getAttributes: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Mock the attribute filter to pass everything through by default
// ---------------------------------------------------------------------------

vi.mock("@/features/analysis/components/DistributionExplorer/attributeFilters", () => ({
  isDistributableAttr: vi.fn(() => true),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { useAttributeFiltering } from "./useAttributeFiltering";
import { getAttributes } from "@/features/analysis/api/stepResults";
import { isDistributableAttr } from "@/features/analysis/components/DistributionExplorer/attributeFilters";
import type { EntityRef } from "@/features/analysis/api/stepResults";
import type { RecordAttribute } from "@/lib/types/wdk";

const mockGetAttributes = vi.mocked(getAttributes);
const mockIsDistributable = vi.mocked(isDistributableAttr);

function makeAttrs(...names: string[]): RecordAttribute[] {
  return names.map((name) => ({
    name,
    displayName: name.replace(/_/g, " "),
    isDisplayable: true,
  }));
}

describe("useAttributeFiltering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsDistributable.mockImplementation(() => true);
  });

  it("resets selectedAttr to empty string when entityRef changes", async () => {
    const attrs1 = makeAttrs("organism", "gene_product");
    const attrs2 = makeAttrs("molecular_weight", "go_terms");

    mockGetAttributes
      .mockResolvedValueOnce({ attributes: attrs1, recordType: "gene" })
      .mockResolvedValueOnce({ attributes: attrs2, recordType: "gene" });

    const entity1: EntityRef = { type: "experiment", id: "exp-1" };
    const entity2: EntityRef = { type: "experiment", id: "exp-2" };

    const { result, rerender } = renderHook(
      ({ entityRef }) => useAttributeFiltering(entityRef),
      { initialProps: { entityRef: entity1 } },
    );

    // Wait for first fetch to complete
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.selectedAttr).toBe("organism");

    // Switch entity — selectedAttr should reset before new attrs load
    rerender({ entityRef: entity2 });

    // During loading, selectedAttr should be reset to ""
    expect(result.current.selectedAttr).toBe("");

    // After second fetch completes, auto-selects first distributable attr
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.selectedAttr).toBe("molecular_weight");
  });

  it("auto-selects first distributable attribute when attributes load", async () => {
    const attrs = makeAttrs("url_field", "organism", "gene_product");
    // Only organism and gene_product pass the filter
    mockIsDistributable.mockImplementation((a) => a.name !== "url_field");
    mockGetAttributes.mockResolvedValueOnce({
      attributes: attrs,
      recordType: "gene",
    });

    const entity: EntityRef = { type: "experiment", id: "exp-1" };
    const { result } = renderHook(() => useAttributeFiltering(entity));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.selectedAttr).toBe("organism");
    expect(result.current.attributes).toHaveLength(2);
  });

  it("keeps selectedAttr empty when no distributable attributes exist", async () => {
    mockIsDistributable.mockImplementation(() => false);
    mockGetAttributes.mockResolvedValueOnce({
      attributes: makeAttrs("url_field"),
      recordType: "gene",
    });

    const entity: EntityRef = { type: "experiment", id: "exp-1" };
    const { result } = renderHook(() => useAttributeFiltering(entity));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.selectedAttr).toBe("");
    expect(result.current.attributes).toHaveLength(0);
  });

  it("sets error when getAttributes fails", async () => {
    mockGetAttributes.mockRejectedValueOnce(new Error("Network error"));

    const entity: EntityRef = { type: "experiment", id: "exp-1" };
    const { result } = renderHook(() => useAttributeFiltering(entity));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toContain("Network error");
  });

  it("allows manual selection via setSelectedAttr", async () => {
    mockGetAttributes.mockResolvedValueOnce({
      attributes: makeAttrs("organism", "gene_product"),
      recordType: "gene",
    });

    const entity: EntityRef = { type: "experiment", id: "exp-1" };
    const { result } = renderHook(() => useAttributeFiltering(entity));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    act(() => {
      result.current.setSelectedAttr("gene_product");
    });

    expect(result.current.selectedAttr).toBe("gene_product");
  });
});
