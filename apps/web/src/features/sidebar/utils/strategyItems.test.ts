import { describe, expect, it } from "vitest";
import { buildStrategySidebarItems } from "@/features/sidebar/utils/strategyItems";

describe("buildStrategySidebarItems", () => {
  it("merges local items and remote WDK items, hiding internal and already-local ones", () => {
    const nowIso = () => "2026-01-01T00:00:00.000Z";
    const local: any[] = [
      {
        id: "local-1",
        name: "Draft A",
        updatedAt: "2026-01-02T00:00:00.000Z",
        siteId: "plasmodb",
        wdkStrategyId: null,
      },
      {
        id: "local-2",
        name: "Synced B",
        updatedAt: "2026-01-03T00:00:00.000Z",
        siteId: "plasmodb",
        wdkStrategyId: 10,
      },
    ];
    const remote: any[] = [
      {
        wdkStrategyId: 10,
        name: "Already Local",
        siteId: "plasmodb",
        isInternal: false,
      },
      {
        wdkStrategyId: 11,
        name: "Remote Visible",
        siteId: "plasmodb",
        isInternal: false,
      },
      {
        wdkStrategyId: 12,
        name: "Remote Internal",
        siteId: "plasmodb",
        isInternal: true,
      },
    ];

    const items = buildStrategySidebarItems({
      local: local as any,
      remote: remote as any,
      nowIso,
    });
    const ids = items.map((i) => i.id);
    expect(ids).toEqual(["local-1", "local-2", "wdk:11"]);

    const wdk = items.find((i) => i.id === "wdk:11");
    expect(wdk).toMatchObject({
      name: "Remote Visible",
      updatedAt: "2026-01-01T00:00:00.000Z",
      source: "synced",
      isRemote: true,
      wdkStrategyId: 11,
    });
  });
});
