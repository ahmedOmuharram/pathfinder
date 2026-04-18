/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { RecordDetail, WdkRecord } from "@/lib/types/wdk";
import { createTestWrapper } from "@/lib/query/testing";

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

  it("does not fetch when expandedKey is null", () => {
    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(
      () =>
        useResultsTableDetail({
          entityRef,
          expandedKey: null,
          recordId: null,
        }),
      { wrapper: Wrapper },
    );

    expect(result.current.detail).toBeNull();
    expect(result.current.detailError).toBeNull();
    expect(result.current.detailLoading).toBe(false);
    expect(mockGetRecordDetail).not.toHaveBeenCalled();
  });

  it("fetches detail when expandedKey and recordId are set", async () => {
    const detail: RecordDetail = {
      displayName: "G1",
      id: [{ name: "source_id", value: "G1" }],
      recordClassName: "TranscriptRecordClasses.TranscriptRecordClass",
      attributes: { gene_id: "G1" },
      attributeNames: { gene_id: "Gene ID" },
      tables: {},
      tableErrors: [],
    };
    mockGetRecordDetail.mockResolvedValueOnce(detail);

    const recordId: WdkRecord["id"] = [{ name: "source_id", value: "G1" }];
    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(
      () =>
        useResultsTableDetail({
          entityRef,
          expandedKey: "row-1",
          recordId,
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.detailLoading).toBe(false);
    });

    expect(result.current.detail).toEqual(detail);
    expect(result.current.detailError).toBeNull();
  });

  it("reports error when detail fetch fails", async () => {
    mockGetRecordDetail.mockRejectedValueOnce(new Error("server error"));

    const recordId: WdkRecord["id"] = [{ name: "source_id", value: "G1" }];
    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(
      () =>
        useResultsTableDetail({
          entityRef,
          expandedKey: "row-1",
          recordId,
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.detailLoading).toBe(false);
    });

    expect(result.current.detailError).toBe("server error");
    expect(result.current.detail).toBeNull();
  });
});
