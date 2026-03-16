import { describe, it, expect } from "vitest";
import {
  formatCompact,
  formatCompactClean,
  formatCompactShort,
  formatCost,
  formatPrice,
} from "./format";

describe("formatCompact", () => {
  it("formats millions with 1 decimal", () => {
    expect(formatCompact(1_500_000)).toBe("1.5M");
    expect(formatCompact(1_000_000)).toBe("1.0M");
  });

  it("formats thousands with 1 decimal", () => {
    expect(formatCompact(1_500)).toBe("1.5k");
    expect(formatCompact(1_000)).toBe("1.0k");
  });

  it("returns plain string for small numbers", () => {
    expect(formatCompact(42)).toBe("42");
    expect(formatCompact(0)).toBe("0");
  });
});

describe("formatCompactClean", () => {
  it("trims .0 for round millions", () => {
    expect(formatCompactClean(1_000_000)).toBe("1M");
    expect(formatCompactClean(2_000_000)).toBe("2M");
  });

  it("keeps decimal for non-round millions", () => {
    expect(formatCompactClean(1_500_000)).toBe("1.5M");
  });

  it("trims .0 for round thousands", () => {
    expect(formatCompactClean(128_000)).toBe("128K");
    expect(formatCompactClean(1_000)).toBe("1K");
  });

  it("keeps decimal for non-round thousands", () => {
    expect(formatCompactClean(1_500)).toBe("1.5K");
  });

  it("returns plain string for small numbers", () => {
    expect(formatCompactClean(42)).toBe("42");
  });
});

describe("formatCompactShort", () => {
  it("formats thousands with 0 decimals", () => {
    expect(formatCompactShort(128_000)).toBe("128k");
    expect(formatCompactShort(1_500)).toBe("2k"); // rounded
    expect(formatCompactShort(8_192)).toBe("8k");
  });

  it("formats millions with 1 decimal", () => {
    expect(formatCompactShort(1_500_000)).toBe("1.5M");
  });

  it("returns plain string for small numbers", () => {
    expect(formatCompactShort(42)).toBe("42");
  });
});

describe("formatCost", () => {
  it("shows <$0.01 for tiny costs", () => {
    expect(formatCost(0.001)).toBe("<$0.01");
    expect(formatCost(0.009)).toBe("<$0.01");
  });

  it("shows 2 decimal places for normal costs", () => {
    expect(formatCost(0.01)).toBe("$0.01");
    expect(formatCost(1.5)).toBe("$1.50");
    expect(formatCost(0.15)).toBe("$0.15");
  });

  it("shows <$0.01 for zero", () => {
    expect(formatCost(0)).toBe("<$0.01");
  });
});

describe("formatPrice", () => {
  it('returns "Free" for zero', () => {
    expect(formatPrice(0)).toBe("Free");
  });

  it("shows <$0.01 for tiny prices", () => {
    expect(formatPrice(0.005)).toBe("<$0.01");
  });

  it("shows 2 decimal places for normal prices", () => {
    expect(formatPrice(3.0)).toBe("$3.00");
    expect(formatPrice(0.15)).toBe("$0.15");
  });
});
