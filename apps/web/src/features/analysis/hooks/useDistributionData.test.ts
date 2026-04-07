/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { createTestWrapper } from "@/lib/query/testing";
import { APIError } from "@/lib/api/http";
import type { DistributionResponse } from "@/lib/types/wdk";

const mockGetDistribution = vi.fn();

vi.mock("@/features/analysis/api/stepResults", () => {
  const { queryOptions } = require("@tanstack/react-query");
  return {
    getDistribution: (...args: unknown[]) => mockGetDistribution(...args),
    distributionOptions: (entityRef: { type: string; id: string }, attr: string) =>
      queryOptions({
        queryKey: ["experiments", "distribution", entityRef.type, entityRef.id, attr] as const,
        queryFn: () => mockGetDistribution(entityRef, attr),
        staleTime: 60_000,
        enabled: attr !== "",
      }),
  };
});

import { parseDistribution, useDistributionData } from "./useDistributionData";
import type { EntityRef } from "@/features/analysis/api/stepResults";

const emptyStats: DistributionResponse["statistics"] = {
  subsetSize: 0,
  subsetMin: null,
  subsetMax: null,
  subsetMean: null,
  numVarValues: 0,
  numDistinctValues: 0,
  numDistinctEntityRecords: 0,
  numMissingCases: 0,
};

describe("parseDistribution", () => {
  it("returns empty array for empty histogram", () => {
    const raw: DistributionResponse = { histogram: [], statistics: emptyStats };
    expect(parseDistribution(raw)).toEqual([]);
  });

  it("preserves WDK order for numeric bins (with binStart)", () => {
    const raw: DistributionResponse = {
      histogram: [
        { binStart: "0", binEnd: "10", binLabel: "0-10", value: 5 },
        { binStart: "10", binEnd: "20", binLabel: "10-20", value: 20 },
        { binStart: "20", binEnd: "30", binLabel: "20-30", value: 3 },
      ],
      statistics: emptyStats,
    };
    const result = parseDistribution(raw);
    // Numeric bins should NOT be re-sorted — preserve WDK order
    expect(result).toEqual([
      { value: "0-10", count: 5 },
      { value: "10-20", count: 20 },
      { value: "20-30", count: 3 },
    ]);
  });

  it("sorts categorical bins (empty binStart) by count descending", () => {
    const raw: DistributionResponse = {
      histogram: [
        { binStart: "", binEnd: "", binLabel: "Plasmodium falciparum", value: 5 },
        { binStart: "", binEnd: "", binLabel: "Plasmodium vivax", value: 20 },
        { binStart: "", binEnd: "", binLabel: "Plasmodium knowlesi", value: 10 },
      ],
      statistics: emptyStats,
    };
    const result = parseDistribution(raw);
    expect(result).toEqual([
      { value: "Plasmodium vivax", count: 20 },
      { value: "Plasmodium knowlesi", count: 10 },
      { value: "Plasmodium falciparum", count: 5 },
    ]);
  });

  it("filters out bins with value 0", () => {
    const raw: DistributionResponse = {
      histogram: [
        { binStart: "", binEnd: "", binLabel: "A", value: 10 },
        { binStart: "", binEnd: "", binLabel: "B", value: 0 },
        { binStart: "", binEnd: "", binLabel: "C", value: 5 },
      ],
      statistics: emptyStats,
    };
    const result = parseDistribution(raw);
    expect(result).toHaveLength(2);
    expect(result.every((e) => e.count > 0)).toBe(true);
  });

  it("uses binStart as label fallback when binLabel is empty", () => {
    const raw: DistributionResponse = {
      histogram: [{ binStart: "42", binEnd: "50", binLabel: "", value: 7 }],
      statistics: emptyStats,
    };
    const result = parseDistribution(raw);
    expect(result).toEqual([{ value: "42", count: 7 }]);
  });
});

describe("useDistributionData", () => {
  const entityRef: EntityRef = { type: "experiment", id: "exp-123" };

  function makeDistributionResponse(
    bins: { binLabel: string; binStart: string; value: number }[],
  ): DistributionResponse {
    return {
      histogram: bins.map((b) => ({
        binLabel: b.binLabel,
        binStart: b.binStart,
        binEnd: "",
        value: b.value,
      })),
      statistics: emptyStats,
    };
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads distribution for selected attribute", async () => {
    const response = makeDistributionResponse([
      { binLabel: "GO:0005634", binStart: "", value: 42 },
      { binLabel: "GO:0005737", binStart: "", value: 28 },
    ]);
    mockGetDistribution.mockResolvedValueOnce(response);

    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(
      () => useDistributionData(entityRef, "go_term"),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.distribution).toEqual([
      { value: "GO:0005634", count: 42 },
      { value: "GO:0005737", count: 28 },
    ]);
    expect(result.current.error).toBeNull();
  });

  it("returns loading=true during fetch", () => {
    mockGetDistribution.mockReturnValueOnce(new Promise(() => {}));

    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(
      () => useDistributionData(entityRef, "go_term"),
      { wrapper: Wrapper },
    );

    expect(result.current.loading).toBe(true);
    expect(result.current.distribution).toEqual([]);
  });

  it("returns parsed distribution data sorted by count descending", async () => {
    const response = makeDistributionResponse([
      { binLabel: "kinase activity", binStart: "", value: 10 },
      { binLabel: "nucleus", binStart: "", value: 50 },
      { binLabel: "membrane", binStart: "", value: 25 },
      { binLabel: "cytoplasm", binStart: "", value: 3 },
    ]);
    mockGetDistribution.mockResolvedValueOnce(response);

    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(
      () => useDistributionData(entityRef, "gene_product"),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.distribution).toEqual([
      { value: "nucleus", count: 50 },
      { value: "membrane", count: 25 },
      { value: "kinase activity", count: 10 },
      { value: "cytoplasm", count: 3 },
    ]);
  });

  it("handles 404 gracefully with user-friendly message", async () => {
    mockGetDistribution.mockRejectedValueOnce(
      new APIError("Not Found", {
        status: 404,
        statusText: "Not Found",
        url: "/test",
        data: null,
      }),
    );

    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(
      () => useDistributionData(entityRef, "go_term"),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });

    expect(result.current.error).toBe(
      "No distribution data available for this attribute. Try a different one.",
    );
    expect(result.current.loading).toBe(false);
    expect(result.current.distribution).toEqual([]);
  });

  it("handles 422 gracefully with user-friendly message", async () => {
    mockGetDistribution.mockRejectedValueOnce(
      new APIError("Unprocessable Entity", {
        status: 422,
        statusText: "Unprocessable Entity",
        url: "/test",
        data: null,
      }),
    );

    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(
      () => useDistributionData(entityRef, "gene_product"),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });

    expect(result.current.error).toBe(
      "No distribution data available for this attribute. Try a different one.",
    );
    expect(result.current.loading).toBe(false);
  });

  it("refetches when selectedAttr changes", async () => {
    const goResponse = makeDistributionResponse([
      { binLabel: "GO:0005634", binStart: "", value: 42 },
    ]);
    const productResponse = makeDistributionResponse([
      { binLabel: "hypothetical protein", binStart: "", value: 100 },
    ]);
    mockGetDistribution
      .mockResolvedValueOnce(goResponse)
      .mockResolvedValueOnce(productResponse);

    const { Wrapper } = createTestWrapper();
    const { result, rerender } = renderHook(
      ({ attr }: { attr: string }) => useDistributionData(entityRef, attr),
      { wrapper: Wrapper, initialProps: { attr: "go_term" } },
    );

    await waitFor(() => {
      expect(result.current.distribution).toEqual([
        { value: "GO:0005634", count: 42 },
      ]);
    });

    rerender({ attr: "gene_product" });

    await waitFor(() => {
      expect(result.current.distribution).toEqual([
        { value: "hypothetical protein", count: 100 },
      ]);
    });

    expect(mockGetDistribution).toHaveBeenCalledTimes(2);
    expect(mockGetDistribution).toHaveBeenNthCalledWith(1, entityRef, "go_term");
    expect(mockGetDistribution).toHaveBeenNthCalledWith(2, entityRef, "gene_product");
  });

  it("does not fetch when selectedAttr is empty", () => {
    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(
      () => useDistributionData(entityRef, ""),
      { wrapper: Wrapper },
    );

    expect(mockGetDistribution).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    expect(result.current.distribution).toEqual([]);
  });
});
