import { describe, expect, it } from "vitest";

import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import type { ConversationSummary } from "@/lib/api/conversations";

import { groupConversationsByTime } from "./groupByTime";

function makeItem(
  partial: Pick<ConversationItem, "id" | "updatedAt"> &
    Partial<Pick<ConversationItem, "isSaved" | "title">>,
): ConversationItem {
  const chat: ConversationSummary = {
    id: partial.id,
    name: partial.title ?? "conv",
    siteId: "plasmodb",
    experimentId: null,
    wdkStrategyId: null,
    isSaved: partial.isSaved ?? false,
    stepCount: 0,
    estimatedSize: null,
    dismissedAt: null,
    createdAt: partial.updatedAt,
    updatedAt: partial.updatedAt,
    recordType: null,
  };
  return {
    id: partial.id,
    title: partial.title ?? "conv",
    updatedAt: partial.updatedAt,
    siteId: "plasmodb",
    isDismissed: false,
    isSaved: partial.isSaved ?? false,
    stepCount: 0,
    experimentId: null,
    parentConversationId: null,
    parentMessageId: null,
    chat,
  };
}

describe("groupConversationsByTime", () => {
  it("returns empty list for empty input", () => {
    expect(groupConversationsByTime([])).toEqual([]);
  });

  it("places today's items under 'Today'", () => {
    const now = new Date().toISOString();
    const groups = groupConversationsByTime([makeItem({ id: "a", updatedAt: now })]);
    expect(groups).toHaveLength(1);
    const [first] = groups;
    if (first === undefined) throw new Error("group missing");
    expect(first.label).toBe("Today");
    expect(first.items.map((i) => i.id)).toEqual(["a"]);
  });

  it("splits items into Today, Yesterday, Last 7 days, Last 30 days, Older", () => {
    const now = new Date();
    const mk = (offsetMs: number) => new Date(now.getTime() - offsetMs).toISOString();

    const today = mk(2 * 60 * 60 * 1000);
    const yesterday = mk(26 * 60 * 60 * 1000);
    const threeDaysAgo = mk(3 * 24 * 60 * 60 * 1000);
    const twoWeeksAgo = mk(14 * 24 * 60 * 60 * 1000);
    const threeMonthsAgo = mk(90 * 24 * 60 * 60 * 1000);

    const groups = groupConversationsByTime([
      makeItem({ id: "today", updatedAt: today }),
      makeItem({ id: "yesterday", updatedAt: yesterday }),
      makeItem({ id: "week", updatedAt: threeDaysAgo }),
      makeItem({ id: "month", updatedAt: twoWeeksAgo }),
      makeItem({ id: "older", updatedAt: threeMonthsAgo }),
    ]);

    const map = new Map(groups.map((g) => [g.label, g.items.map((i) => i.id)]));
    expect(map.get("Today")).toEqual(["today"]);
    expect(map.get("Yesterday")).toEqual(["yesterday"]);
    expect(map.get("Last 7 days")).toEqual(["week"]);
    expect(map.get("Last 30 days")).toEqual(["month"]);
    expect(map.get("Older")).toEqual(["older"]);
  });

  it("hoists saved items into 'Saved' regardless of age", () => {
    const now = new Date().toISOString();
    const old = new Date(Date.now() - 200 * 24 * 60 * 60 * 1000).toISOString();
    const groups = groupConversationsByTime([
      makeItem({ id: "saved-old", updatedAt: old, isSaved: true }),
      makeItem({ id: "today", updatedAt: now }),
    ]);
    const [saved, today2] = groups;
    if (saved === undefined || today2 === undefined) throw new Error("groups missing");
    expect(saved.label).toBe("Saved");
    expect(saved.items.map((i) => i.id)).toEqual(["saved-old"]);
    expect(today2.label).toBe("Today");
  });

  it("omits empty groups", () => {
    const twoWeeksAgo = new Date(
      Date.now() - 14 * 24 * 60 * 60 * 1000,
    ).toISOString();
    const groups = groupConversationsByTime([
      makeItem({ id: "a", updatedAt: twoWeeksAgo }),
    ]);
    expect(groups.map((g) => g.label)).toEqual(["Last 30 days"]);
  });
});
