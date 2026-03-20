/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { RecordDetail, WdkRecord } from "@/lib/types/wdk";

const mockGetRecordDetail = vi.fn();

vi.mock("@/features/analysis/api/stepResults", () => ({
  getRecordDetail: (...args: unknown[]) => mockGetRecordDetail(...args),
}));

import { useResultsTableDetail } from "./useResultsTableDetail";
import type { EntityRef } from "@/features/analysis/api/stepResults";

describe("useResultsTableDetail", () => {
  const entityRef: EntityRef = { type: "experiment", id: "exp-1" };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts with no expanded row", () => {
    const { result } = renderHook(() => useResultsTableDetail(entityRef));
    expect(result.current.expandedKey).toBeNull();
    expect(result.current.detail).toBeNull();
    expect(result.current.detailError).toBeNull();
    expect(result.current.detailLoading).toBe(false);
  });

  it("expands a row and fetches detail", async () => {
    const detail: RecordDetail = {
      id: [{ name: "source_id", value: "G1" }],
      attributes: { gene_id: "G1" },
      tables: {},
      recordType: "gene",
    };
    mockGetRecordDetail.mockResolvedValueOnce(detail);

    const recordId: WdkRecord["id"] = [{ name: "source_id", value: "G1" }];
    const { result } = renderHook(() => useResultsTableDetail(entityRef));

    await act(async () => {
      result.current.handleExpandRow("row-1", recordId);
    });

    await waitFor(() => {
      expect(result.current.detailLoading).toBe(false);
    });

    expect(result.current.expandedKey).toBe("row-1");
    expect(result.current.detail).toEqual(detail);
    expect(result.current.detailError).toBeNull();
  });

  it("collapses when clicking the same row", async () => {
    const detail: RecordDetail = {
      id: [{ name: "source_id", value: "G1" }],
      attributes: { gene_id: "G1" },
      tables: {},
      recordType: "gene",
    };
    mockGetRecordDetail.mockResolvedValueOnce(detail);

    const recordId: WdkRecord["id"] = [{ name: "source_id", value: "G1" }];
    const { result } = renderHook(() => useResultsTableDetail(entityRef));

    await act(async () => {
      result.current.handleExpandRow("row-1", recordId);
    });

    await waitFor(() => {
      expect(result.current.expandedKey).toBe("row-1");
    });

    act(() => {
      result.current.handleExpandRow("row-1", recordId);
    });

    expect(result.current.expandedKey).toBeNull();
    expect(result.current.detail).toBeNull();
  });

  it("shows error when detail fetch fails", async () => {
    mockGetRecordDetail.mockRejectedValueOnce(new Error("server error"));

    const recordId: WdkRecord["id"] = [{ name: "source_id", value: "G1" }];
    const { result } = renderHook(() => useResultsTableDetail(entityRef));

    await act(async () => {
      result.current.handleExpandRow("row-1", recordId);
    });

    await waitFor(() => {
      expect(result.current.detailLoading).toBe(false);
    });

    expect(result.current.detailError).toBe("server error");
    expect(result.current.detail).toBeNull();
  });
});
