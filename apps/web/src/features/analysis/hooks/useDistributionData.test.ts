/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { parseDistribution } from "./useDistributionData";
import type { DistributionResponse } from "@/lib/types/wdk";

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
