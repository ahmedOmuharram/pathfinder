import { describe, expect, it } from "vitest";
import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";

describe("StrategyListItem", () => {
  it("saved strategy with wdkStrategyId", () => {
    const item: StrategyListItem = {
      id: "abc-123",
      name: "My Strategy",
      updatedAt: "2026-01-01T00:00:00.000Z",
      siteId: "plasmodb",
      wdkStrategyId: 42,
      isSaved: true,
    };

    expect(item.isSaved).toBe(true);
    expect(item.wdkStrategyId).toBe(42);
  });

  it("draft strategy with wdkStrategyId", () => {
    const item: StrategyListItem = {
      id: "ghi-789",
      name: "My Draft",
      updatedAt: "2026-01-03T00:00:00.000Z",
      siteId: "plasmodb",
      wdkStrategyId: 99,
      isSaved: false,
    };

    expect(item.isSaved).toBe(false);
    expect(item.wdkStrategyId).toBe(99);
  });

  it("not-yet-synced strategy (no wdkStrategyId)", () => {
    const item: StrategyListItem = {
      id: "def-456",
      name: "Draft",
      updatedAt: "2026-01-02T00:00:00.000Z",
      isSaved: false,
    };

    expect(item.isSaved).toBe(false);
    expect(item.wdkStrategyId).toBeUndefined();
  });
});
