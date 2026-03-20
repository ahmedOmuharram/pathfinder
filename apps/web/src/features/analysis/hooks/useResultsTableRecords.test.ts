/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

const mockGetRecords = vi.fn();

vi.mock("@/features/analysis/api/stepResults", () => ({
  getRecords: (...args: unknown[]) => mockGetRecords(...args),
}));

import { useResultsTableRecords } from "./useResultsTableRecords";
import type { EntityRef } from "@/features/analysis/api/stepResults";

function makeRecordsResponse(count: number) {
  return {
    records: Array.from({ length: count }, (_, i) => ({
      id: [{ name: "source_id", value: `GENE_${i}` }],
      attributes: { gene_id: `GENE_${i}` },
    })),
    meta: {
      totalCount: count,
      displayTotalCount: count,
      responseCount: count,
      pagination: { offset: 0, numRecords: 25 },
      attributes: ["gene_id"],
      tables: [],
    },
  };
}

describe("useResultsTableRecords", () => {
  const entityRef: EntityRef = { type: "experiment", id: "exp-1" };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches records when visibleColumns are non-empty", async () => {
    mockGetRecords.mockResolvedValueOnce(makeRecordsResponse(3));

    const visibleColumns = new Set(["gene_id", "organism"]);
    const { result } = renderHook(() =>
      useResultsTableRecords(entityRef, visibleColumns),
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.records).toHaveLength(3);
    expect(result.current.meta?.totalCount).toBe(3);
  });

  it("does not fetch when visibleColumns is empty", () => {
    const visibleColumns = new Set<string>();
    renderHook(() => useResultsTableRecords(entityRef, visibleColumns));

    expect(mockGetRecords).not.toHaveBeenCalled();
  });

  it("handleSort toggles direction on same column", async () => {
    mockGetRecords.mockResolvedValue(makeRecordsResponse(1));

    const visibleColumns = new Set(["gene_id"]);
    const { result } = renderHook(() =>
      useResultsTableRecords(entityRef, visibleColumns),
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    act(() => {
      result.current.handleSort("gene_id");
    });

    expect(result.current.sortColumn).toBe("gene_id");
    expect(result.current.sortDir).toBe("ASC");

    act(() => {
      result.current.handleSort("gene_id");
    });

    expect(result.current.sortDir).toBe("DESC");
  });

  it("handleSort resets to ASC on new column", async () => {
    mockGetRecords.mockResolvedValue(makeRecordsResponse(1));

    const visibleColumns = new Set(["gene_id", "organism"]);
    const { result } = renderHook(() =>
      useResultsTableRecords(entityRef, visibleColumns),
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    act(() => {
      result.current.handleSort("gene_id");
    });
    act(() => {
      result.current.handleSort("gene_id");
    });
    // Now sortDir is DESC for gene_id
    expect(result.current.sortDir).toBe("DESC");

    act(() => {
      result.current.handleSort("organism");
    });

    expect(result.current.sortColumn).toBe("organism");
    expect(result.current.sortDir).toBe("ASC");
  });

  it("resets offset on sort change", async () => {
    mockGetRecords.mockResolvedValue(makeRecordsResponse(1));

    const visibleColumns = new Set(["gene_id"]);
    const { result } = renderHook(() =>
      useResultsTableRecords(entityRef, visibleColumns),
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    act(() => {
      result.current.setOffset(50);
    });
    act(() => {
      result.current.handleSort("gene_id");
    });

    expect(result.current.offset).toBe(0);
  });

  it("reports error on fetch failure", async () => {
    mockGetRecords.mockRejectedValueOnce(new Error("Network error"));

    const visibleColumns = new Set(["gene_id"]);
    const { result } = renderHook(() =>
      useResultsTableRecords(entityRef, visibleColumns),
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe("Network error");
  });
});
