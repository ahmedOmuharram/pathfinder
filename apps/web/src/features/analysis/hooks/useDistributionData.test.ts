/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { parseDistribution } from "./useDistributionData";
import type { DistributionResponse } from "@/lib/types/wdk";

describe("parseDistribution", () => {
  it("returns empty array for empty histogram", () => {
    const raw: DistributionResponse = { histogram: [] };
    expect(parseDistribution(raw)).toEqual([]);
  });

  it("preserves WDK order for numeric bins (with binStart)", () => {
    const raw: DistributionResponse = {
      histogram: [
        { binStart: "0", binLabel: "0-10", value: 5 },
        { binStart: "10", binLabel: "10-20", value: 20 },
        { binStart: "20", binLabel: "20-30", value: 3 },
      ],
    };
    const result = parseDistribution(raw);
    // Numeric bins should NOT be re-sorted — preserve WDK order
    expect(result).toEqual([
      { value: "0-10", count: 5 },
      { value: "10-20", count: 20 },
      { value: "20-30", count: 3 },
    ]);
  });

  it("sorts categorical bins (without binStart) by count descending", () => {
    const raw: DistributionResponse = {
      histogram: [
        { binLabel: "Plasmodium falciparum", value: 5 },
        { binLabel: "Plasmodium vivax", value: 20 },
        { binLabel: "Plasmodium knowlesi", value: 10 },
      ],
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
        { binLabel: "A", value: 10 },
        { binLabel: "B", value: 0 },
        { binLabel: "C", value: 5 },
      ],
    };
    const result = parseDistribution(raw);
    expect(result).toHaveLength(2);
    expect(result.every((e) => e.count > 0)).toBe(true);
  });

  it("handles flat distribution object", () => {
    const raw: DistributionResponse = {
      total: 100,
      attributeName: "organism",
      "Plasmodium falciparum": 60,
      "Plasmodium vivax": 40,
    } as DistributionResponse;
    const result = parseDistribution(raw);
    // Should exclude `total` and `attributeName` keys
    expect(result).toEqual([
      { value: "Plasmodium falciparum", count: 60 },
      { value: "Plasmodium vivax", count: 40 },
    ]);
  });

  it("handles wrapped distribution field", () => {
    const raw: DistributionResponse = {
      distribution: {
        "Plasmodium falciparum": 30,
        "Plasmodium vivax": 70,
      },
    };
    const result = parseDistribution(raw);
    expect(result).toEqual([
      { value: "Plasmodium vivax", count: 70 },
      { value: "Plasmodium falciparum", count: 30 },
    ]);
  });

  it("uses binStart as label fallback when binLabel is missing", () => {
    const raw: DistributionResponse = {
      histogram: [{ binStart: "42", value: 7 }],
    };
    const result = parseDistribution(raw);
    expect(result).toEqual([{ value: "42", count: 7 }]);
  });
});
